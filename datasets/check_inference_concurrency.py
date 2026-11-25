"""Run a small, non-retrying Moss Responses concurrency sweep."""

import asyncio
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from moss import MossInference

from mossbench.config import load_config


CALLS_PER_LEVEL = 10
LEVELS = (1, 2, 5)


def percentile(values, p):
    ordered = sorted(values)
    return ordered[max(0, (len(ordered) * p + 99) // 100 - 1)] if ordered else None


async def main():
    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be configured")
    client = MossInference(config.moss_project_id, config.moss_project_key, timeout=30, idle_timeout=20, max_retries=0)
    results = []
    summaries = []
    try:
        for concurrency in LEVELS:
            semaphore = asyncio.Semaphore(concurrency)

            async def call(number):
                async with semaphore:
                    started = time.monotonic()
                    try:
                        response = await client.responses.create(
                            model=config.moss_model,
                            input=f"Reply with exactly OK. Concurrency probe {concurrency}-{number:02d}.",
                            instructions="Reply with exactly OK.",
                            retrieve=False, cache=False, max_output_tokens=8, timeout=30, idle_timeout=20,
                            max_retries=0,
                        )
                        return {
                            "concurrency": concurrency, "call": number, "status": "success",
                            "latency_ms": round((time.monotonic() - started) * 1000, 3),
                            "input_tokens": response.usage.input_tokens if response.usage else None,
                            "output_tokens": response.usage.output_tokens if response.usage else None,
                        }
                    except Exception as exc:
                        return {
                            "concurrency": concurrency, "call": number, "status": "error",
                            "latency_ms": round((time.monotonic() - started) * 1000, 3),
                            "error_type": type(exc).__name__, "error_code": getattr(exc, "code", None),
                            "http_status": getattr(exc, "status", None),
                        }

            batch_started = time.monotonic()
            batch = await asyncio.gather(*(call(number) for number in range(1, CALLS_PER_LEVEL + 1)))
            wall_seconds = time.monotonic() - batch_started
            successful = [row for row in batch if row["status"] == "success"]
            latencies = [row["latency_ms"] for row in successful]
            results.extend(batch)
            summary = {
                "summary": True, "concurrency": concurrency, "attempted": len(batch),
                "successes": len(successful), "failures": len(batch) - len(successful),
                "wall_seconds": round(wall_seconds, 6),
                "successful_requests_per_second": round(len(successful) / wall_seconds, 3) if wall_seconds else None,
                "latency_ms_p50": statistics.median(latencies) if latencies else None,
                "latency_ms_p95": percentile(latencies, 95),
                "input_tokens": sum(row.get("input_tokens") or 0 for row in successful),
                "output_tokens": sum(row.get("output_tokens") or 0 for row in successful),
            }
            summaries.append(summary)
            print(json.dumps(summary))
    finally:
        await client.close()
    out = Path("results/phase2-inference-concurrency")
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "model": config.moss_model, "calls_per_level": CALLS_PER_LEVEL, "levels": list(LEVELS),
        "cache": False, "sdk_retries": 0, "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "summaries": summaries, "results": results,
    }
    (out / "concurrency.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
