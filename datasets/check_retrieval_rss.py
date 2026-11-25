"""Observe process RSS around Moss index load, query, and close."""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from moss import MossClient, QueryOptions

from mossbench.config import load_config


INDEX = "mossbench-synth-100"


def rss_kib():
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return None


async def main():
    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be configured")
    report = {"index": INDEX, "rss_before_client_kib": rss_kib()}
    client = MossClient(config.moss_project_id, config.moss_project_key)
    try:
        started = time.monotonic()
        await client.load_index(INDEX)
        report["load_ms"] = round((time.monotonic() - started) * 1000, 3)
        report["rss_after_load_kib"] = rss_kib()
        started = time.monotonic()
        result = await client.query(INDEX, "How does FastAPI validate a request body?", QueryOptions(top_k=5))
        report["query_ms"] = round((time.monotonic() - started) * 1000, 3)
        report["result_count"] = len(result.docs)
        report["rss_after_query_kib"] = rss_kib()
    finally:
        await client.close()
    report["rss_after_close_kib"] = rss_kib()
    report["rss_delta_after_load_kib"] = report["rss_after_load_kib"] - report["rss_before_client_kib"]
    report["rss_delta_after_close_kib"] = report["rss_after_close_kib"] - report["rss_before_client_kib"]
    report["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
    Path("results/phase2-retrieval-rss").mkdir(parents=True, exist_ok=True)
    Path("results/phase2-retrieval-rss/rss.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
