from __future__ import annotations

import json
import logging
import sys
from typing import Any


class StructuredLogger(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        extra = kwargs.pop("extra", {}) or {}
        payload = {"msg": msg, **extra}
        # Never leak secrets if a caller accidentally passes them.
        for key in list(payload.keys()):
            lowered = key.lower()
            if any(token in lowered for token in ("token", "api_key", "secret", "password", "authorization")):
                payload[key] = "[redacted]"
        return json.dumps(payload, default=str), kwargs


def configure_logging(level: int = logging.INFO) -> StructuredLogger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger("causalens")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
    return StructuredLogger(root, {})


log = configure_logging()
