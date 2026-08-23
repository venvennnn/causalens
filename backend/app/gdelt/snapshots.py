from __future__ import annotations

import gzip
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.exceptions import GDELTUnavailable
from app.logging import log

NGRAM_SUFFIX = ".ngrams.txt.gz"
TOC_SUFFIX = ".toc.json.gz"


def snapshot_stamp(moment: datetime) -> str:
    utc = moment.astimezone(timezone.utc) if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    utc = utc.replace(second=0, microsecond=0)
    return utc.strftime("%Y%m%d%H%M00")


def parse_stamp(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def candidate_stamps(
    *,
    now: datetime | None = None,
    lag_minutes: int = 5,
    lookback_hours: int = 6,
    max_probes: int = 120,
    after_stamp: str | None = None,
    stride_minutes: int = 1,
) -> list[str]:
    """Newest-first stamps. Missing minutes are expected; callers skip 404s.

    stride_minutes>1 spaces probes across the lookback window so discovery is
    not limited to the most recent consecutive minutes of global ngrams.
    """
    now = now or datetime.now(timezone.utc)
    end = now - timedelta(minutes=lag_minutes)
    start = end - timedelta(hours=lookback_hours)
    step = max(int(stride_minutes or 1), 1)
    if after_stamp:
        try:
            after = parse_stamp(after_stamp)
            start = max(start, after + timedelta(minutes=1))
        except ValueError:
            pass
    cursor = end.replace(second=0, microsecond=0)
    stamps: list[str] = []
    probes = 0
    while cursor >= start and probes < max_probes:
        stamps.append(snapshot_stamp(cursor))
        cursor -= timedelta(minutes=step)
        probes += 1
    return stamps


class SnapshotFetcher:
    def __init__(self, cache_dir: str | Path | None = None) -> None:
        settings = get_settings()
        self.base = settings.gdelt_ngram_base_url.rstrip("/")
        self.cache_dir = Path(cache_dir or settings.gdelt_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = httpx.Timeout(settings.gdelt_timeout_s, connect=15.0)

    def ngram_url(self, stamp: str) -> str:
        return f"{self.base}/{stamp}{NGRAM_SUFFIX}"

    def toc_url(self, stamp: str) -> str:
        return f"{self.base}/{stamp}{TOC_SUFFIX}"

    def ngram_path(self, stamp: str) -> Path:
        return self.cache_dir / f"{stamp}{NGRAM_SUFFIX}"

    def toc_path(self, stamp: str) -> Path:
        return self.cache_dir / f"{stamp}{TOC_SUFFIX}"

    def ranked_cache_path(self, stamp: str, topic_name: str) -> Path:
        safe_topic = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in topic_name)[:48]
        return self.cache_dir / f"{stamp}.{safe_topic}.candidates.json"

    def files_cached(self, stamp: str) -> bool:
        ngram = self.ngram_path(stamp)
        toc = self.toc_path(stamp)
        return ngram.exists() and toc.exists() and ngram.stat().st_size > 0 and toc.stat().st_size > 0

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _download(self, client: httpx.AsyncClient, url: str, dest: Path) -> str:
        async with client.stream("GET", url) as response:
            if response.status_code == 404:
                return "missing"
            if response.status_code >= 400:
                raise GDELTUnavailable(
                    f"GDELT snapshot download failed ({response.status_code})",
                    details={"url": url},
                )
            tmp = dest.with_suffix(dest.suffix + ".partial")
            with tmp.open("wb") as handle:
                async for chunk in response.aiter_bytes():
                    handle.write(chunk)
            tmp.replace(dest)
            return "ok"

    def _status_from_head(self, response: httpx.Response) -> str:
        if response.status_code == 404:
            return "missing"
        if response.status_code in {200, 204, 301, 302, 303, 307, 308}:
            return "exists"
        return "unknown"

    async def snapshot_available(self, client: httpx.AsyncClient, stamp: str) -> str:
        """HEAD first so missing minutes do not look like errors. 404 is normal."""
        if self.files_cached(stamp):
            return "cached"
        try:
            response = await client.head(self.ngram_url(stamp))
            probed = self._status_from_head(response)
        except (httpx.TransportError, httpx.TimeoutException):
            probed = "unknown"
        if probed == "missing":
            return "missing"
        return await self.ensure_files(client, stamp)

    async def ensure_files(self, client: httpx.AsyncClient, stamp: str) -> str:
        if self.files_cached(stamp):
            return "cached"
        ngram = self.ngram_path(stamp)
        toc = self.toc_path(stamp)
        ngram_status = await self._download(client, self.ngram_url(stamp), ngram)
        if ngram_status == "missing":
            return "missing"
        toc_status = await self._download(client, self.toc_url(stamp), toc)
        if toc_status == "missing":
            if ngram.exists():
                ngram.unlink(missing_ok=True)
            log.info(
                "[GDELT] snapshot=%s toc_missing",
                extra={"source": "gdelt", "snapshot": stamp, "success": False},
            )
            return "missing_toc"
        return "ok"


def open_gzip(path: Path):
    return gzip.open(path, "rt", encoding="utf-8", errors="replace")
