from __future__ import annotations

import asyncio
import json
import os
import shutil
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.exceptions import BrightDataParseError, BrightDataTimeout, BrightDataUnavailable
from app.logging import log

JSON_START = ("[", "{")


def extract_json_payload(text: str) -> Any:
    """Bright Data CLI may print logs before JSON. Recover the last valid payload."""
    stripped = (text or "").strip()
    if not stripped:
        raise BrightDataParseError("Empty Bright Data collector output")

    try:
        parsed = json.loads(stripped)
        return parsed
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    last_value: Any = None
    index = 0
    while index < len(stripped):
        while index < len(stripped) and stripped[index] not in JSON_START:
            index += 1
        if index >= len(stripped):
            break
        try:
            value, end = decoder.raw_decode(stripped, index)
        except json.JSONDecodeError:
            index += 1
            continue
        last_value = value
        index = end
    if last_value is None:
        raise BrightDataParseError("Unable to parse JSON from Bright Data collector output")
    return last_value


def as_record_list(payload: Any) -> list[dict]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "results", "items", "articles", "records"):
            nested = payload.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
        if "status" in payload and "message" in payload and len(payload) <= 4:
            return []
        return [payload]
    raise BrightDataParseError("Collector payload was not a JSON object or array")


class BrightDataClient:
    """Abstraction over Bright Data Scraper Studio collectors (CLI and HTTP)."""

    TRIGGER_PATH = "/dca/trigger"
    DATASET_PATH = "/dca/dataset"

    def __init__(self) -> None:
        self.settings = get_settings()

    async def run_collector(self, collector_id: str, url: str) -> list[dict]:
        transport = self.settings.effective_brightdata_transport
        started = asyncio.get_event_loop().time()
        try:
            if transport == "http":
                records = await self._run_http(collector_id, url)
            else:
                records = await self._run_cli(collector_id, url)
            duration_ms = int((asyncio.get_event_loop().time() - started) * 1000)
            log.info(
                "brightdata_collector_ok",
                extra={
                    "source": "brightdata",
                    "collector": collector_id,
                    "url": url,
                    "transport": transport,
                    "duration_ms": duration_ms,
                    "success": True,
                    "article_count": len(records),
                },
            )
            return records
        except Exception as exc:
            duration_ms = int((asyncio.get_event_loop().time() - started) * 1000)
            log.info(
                "brightdata_collector_failed",
                extra={
                    "source": "brightdata",
                    "collector": collector_id,
                    "url": url,
                    "transport": transport,
                    "duration_ms": duration_ms,
                    "success": False,
                    "error": type(exc).__name__,
                },
            )
            raise

    async def _run_cli(self, collector_id: str, url: str) -> list[dict]:
        npx = shutil.which("npx") or "npx"
        command = [
            npx,
            "-y",
            "-p",
            "@brightdata/cli",
            "bdata",
            "scraper",
            "run",
            collector_id,
            url,
            "--pretty",
        ]
        env = os.environ.copy()
        if self.settings.brightdata_api_token:
            env.setdefault("BRIGHTDATA_API_TOKEN", self.settings.brightdata_api_token)
            env.setdefault("BRIGHT_DATA_API_TOKEN", self.settings.brightdata_api_token)
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except FileNotFoundError as exc:
            raise BrightDataUnavailable("npx is not available for Bright Data CLI transport") from exc

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                process.communicate(),
                timeout=self.settings.brightdata_cli_timeout_s,
            )
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise BrightDataTimeout(f"Bright Data CLI timed out for collector {collector_id}") from exc

        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        combined = stdout if stdout.strip() else stderr
        if process.returncode not in (0, None) and not stdout.strip():
            raise BrightDataUnavailable(
                f"Bright Data CLI failed for collector {collector_id}",
                details={"returncode": process.returncode, "stderr_preview": stderr[-500:]},
            )
        try:
            payload = extract_json_payload(combined)
        except BrightDataParseError:
            if stderr.strip() and stderr != combined:
                payload = extract_json_payload(stdout + "\n" + stderr)
            else:
                raise
        return as_record_list(payload)

    async def _run_http(self, collector_id: str, url: str) -> list[dict]:
        token = self.settings.brightdata_api_token
        if not token:
            raise BrightDataUnavailable("BRIGHTDATA_API_TOKEN is required for HTTP transport")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(30.0, read=60.0)
        async with httpx.AsyncClient(base_url=self.settings.brightdata_http_base, timeout=timeout) as client:
            collection_id = await self._trigger(client, headers, collector_id, url)
            return await self._poll_dataset(client, headers, collection_id, collector_id)

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _trigger(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        collector_id: str,
        url: str,
    ) -> str:
        response = await client.post(
            self.TRIGGER_PATH,
            params={"collector": collector_id, "queue_next": 1},
            headers=headers,
            json=[{"url": url}],
        )
        if response.status_code >= 500:
            raise BrightDataUnavailable(
                f"Bright Data trigger failed ({response.status_code})",
                details={"collector": collector_id},
            )
        if response.status_code >= 400:
            raise BrightDataUnavailable(
                f"Bright Data rejected collector trigger ({response.status_code})",
                details={"collector": collector_id},
            )
        data = response.json()
        collection_id = data.get("collection_id") or data.get("snapshot_id") or data.get("id")
        if not collection_id:
            raise BrightDataParseError("Bright Data trigger response missing collection_id")
        return str(collection_id)

    async def _poll_dataset(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        collection_id: str,
        collector_id: str,
    ) -> list[dict]:
        deadline = asyncio.get_event_loop().time() + self.settings.brightdata_http_timeout_s
        last_error: str | None = None
        while asyncio.get_event_loop().time() < deadline:
            try:
                response = await self._get_dataset(client, headers, collection_id)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_error = type(exc).__name__
                await asyncio.sleep(self.settings.brightdata_poll_interval_s)
                continue
            if response.status_code == 202:
                await asyncio.sleep(self.settings.brightdata_poll_interval_s)
                continue
            if response.status_code >= 500:
                last_error = f"http_{response.status_code}"
                await asyncio.sleep(self.settings.brightdata_poll_interval_s)
                continue
            if response.status_code >= 400:
                raise BrightDataUnavailable(
                    f"Bright Data dataset poll failed ({response.status_code})",
                    details={"collector": collector_id, "collection_id": collection_id},
                )
            payload = response.json()
            if isinstance(payload, dict) and payload.get("status") in {"building", "running", "pending"}:
                await asyncio.sleep(self.settings.brightdata_poll_interval_s)
                continue
            return as_record_list(payload)
        raise BrightDataTimeout(
            f"Timed out waiting for Bright Data collector {collector_id}",
            details={"last_error": last_error, "collection_id": collection_id},
        )

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _get_dataset(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        collection_id: str,
    ) -> httpx.Response:
        return await client.get(self.DATASET_PATH, params={"id": collection_id}, headers=headers)
