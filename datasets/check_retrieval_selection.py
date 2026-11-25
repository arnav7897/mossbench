"""Check retrieval off, explicit existing-index selection, and missing-index errors."""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from moss import MossInference

from mossbench.config import load_config


QUESTION = "How does FastAPI validate a JSON request body?"
EXISTING_INDEX = "mossbench-synth-100"
MISSING_INDEX = "mossbench-does-not-exist-probe"


async def main():
    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be configured")
    client = MossInference(config.moss_project_id, config.moss_project_key, max_retries=0, timeout=30)
    cases = [
        ("retrieval_off", False, []),
        ("explicit_existing_index", True, [EXISTING_INDEX]),
        ("explicit_missing_index", True, [MISSING_INDEX]),
    ]
    rows = []
    try:
        for label, retrieve, indexes in cases:
            started = time.monotonic()
            try:
                response = await client.responses.create(
                    model=config.moss_model, input=QUESTION,
                    instructions="Answer in one short sentence. If you do not know, say so.",
                    indexes=indexes, retrieve=retrieve, cache=False,
                    max_output_tokens=64, max_retries=0, timeout=30,
                )
                rows.append({
                    "case": label, "status": response.status,
                    "latency_ms": round((time.monotonic() - started) * 1000, 3),
                    "nonempty_output": bool(response.output_text.strip()),
                    "input_tokens": response.usage.input_tokens if response.usage else None,
                    "output_tokens": response.usage.output_tokens if response.usage else None,
                })
            except Exception as exc:
                rows.append({
                    "case": label, "status": "error",
                    "latency_ms": round((time.monotonic() - started) * 1000, 3),
                    "error_type": type(exc).__name__,
                    "error_code": getattr(exc, "code", None),
                    "http_status": getattr(exc, "status", None),
                })
    finally:
        await client.close()
    report = {
        "model": config.moss_model, "existing_index": EXISTING_INDEX,
        "missing_index_name": MISSING_INDEX, "question": QUESTION,
        "cases": rows, "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "note": "No index was created or changed; a third-party index was not selected.",
    }
    out = Path("results/phase2-retrieval-selection")
    out.mkdir(parents=True, exist_ok=True)
    (out / "selection.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
