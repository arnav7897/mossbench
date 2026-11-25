"""Check whether raw hosted retrieval reports X-Moss-Retrieve-Ms."""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from mossbench.config import load_config


ENDPOINT = "https://inference.moss.dev/v1/responses"
INDEX = "mossbench-synth-100"


async def main():
    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be configured")
    body = {
        "model": config.moss_model,
        "input": "How does FastAPI validate a JSON request body?",
        "instructions": "Answer in one short sentence.",
        "max_output_tokens": 48,
        "stream": True,
    }
    started = time.monotonic()
    report = {"model": config.moss_model, "index": INDEX}
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        async with client.stream(
            "POST", ENDPOINT,
            headers={
                "Authorization": f"Bearer {config.moss_project_id}:{config.moss_project_key}",
                "Content-Type": "application/json", "Accept": "text/event-stream",
                "X-Moss-Indexes": INDEX, "X-Moss-Cache": "off",
            },
            json=body,
        ) as response:
            report["http_status"] = response.status_code
            header = response.headers.get("x-moss-retrieve-ms")
            report["retrieve_ms_header"] = header
            report["retrieve_ms_header_present"] = header is not None
            report["completed_event_seen"] = False
            if response.is_success:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        event = json.loads(line[6:])
                        if event.get("type") == "response.completed":
                            report["completed_event_seen"] = True
                            final = event.get("response") or {}
                            usage = final.get("usage") or {}
                            report["response_status"] = final.get("status")
                            report["input_tokens"] = usage.get("input_tokens")
                            report["output_tokens"] = usage.get("output_tokens")
    report["end_to_end_ms"] = round((time.monotonic() - started) * 1000, 3)
    report["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
    out = Path("results/phase2-retrieval-timing-header")
    out.mkdir(parents=True, exist_ok=True)
    (out / "header.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
