"""Append-only JSONL request logging with secret-key redaction."""

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

SECRET_PARTS = ("api_key", "authorization", "password", "secret", "token")


def sanitize(value):
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if any(part in key.lower() for part in SECRET_PARTS) else sanitize(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


class RequestLogger:
    def __init__(self, path, run_id=None):
        self.path = Path(path)
        self.run_id = run_id or str(uuid.uuid4())

    def record(self, *, test_id, suite, status, started, model=None, config=None,
               request_id=None, usage=None, error=None, cost=None, source="live", **fields):
        row = {
            "run_id": self.run_id, "test_id": test_id, "suite": suite, "status": status,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "latency_ms": round((time.monotonic() - started) * 1000, 3),
            "model": model, "config": config or {}, "request_id": request_id,
            "usage": usage, "error": error, "cost": cost, "source": source, **fields,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(sanitize(row), ensure_ascii=False) + "\n")


def start_timer():
    return time.monotonic()
