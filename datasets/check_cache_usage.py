"""Compare reported cache usage for repeated and unique inference prefixes."""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from moss import MossInference

from mossbench.config import load_config


COMMON = "MossBench cache probe. The fixed reference phrase is amber lighthouse 731. "
CASES = [
    ("repeated-1", COMMON + "Reply with exactly CACHE_OK."),
    ("repeated-2", COMMON + "Reply with exactly CACHE_OK."),
    ("unique-prefix", "MossBench unique cache probe. The unrelated prefix is cobalt orchard 284. Reply with exactly CACHE_OK."),
]


async def main():
    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be configured")
    client = MossInference(config.moss_project_id, config.moss_project_key, timeout=30, max_retries=0)
    rows = []
    try:
        for label, prompt in CASES:
            started = time.monotonic()
            response = await client.responses.create(
                model=config.moss_model, input=prompt,
                instructions="Reply with exactly CACHE_OK.",
                retrieve=False, cache=True, max_output_tokens=8,
                timeout=30, max_retries=0,
            )
            usage = response.usage
            input_details = getattr(usage, "input_tokens_details", None) if usage else None
            rows.append({
                "case": label, "status": response.status,
                "latency_ms": round((time.monotonic() - started) * 1000, 3),
                "input_tokens": usage.input_tokens if usage else None,
                "cached_input_tokens": getattr(input_details, "cached_tokens", None),
                "output_tokens": usage.output_tokens if usage else None,
                "output_matches_expected": response.output_text.strip() == "CACHE_OK",
            })
    finally:
        await client.close()
    report = {
        "model": config.moss_model, "cache_enabled": True, "retrieve": False,
        "calls": rows, "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "note": "Three sequential observations; cached-token counts are reported by the response and no cache hit is assumed.",
    }
    out = Path("results/phase2-cache")
    out.mkdir(parents=True, exist_ok=True)
    (out / "cache.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "calls"}, indent=2))
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
