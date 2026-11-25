"""Check Moss streaming event order, completion, and assembled response text."""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from moss import MossInference

from mossbench.config import load_config


async def main():
    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be configured")
    client = MossInference(config.moss_project_id, config.moss_project_key)
    events, deltas = [], []
    started = time.monotonic()
    first_text_ms = None
    try:
        stream = await client.responses.create(
            model=config.moss_model,
            input="Reply with exactly the token STREAM_OK.",
            instructions="Reply with exactly STREAM_OK and no other text.",
            retrieve=False, cache=False, stream=True, max_output_tokens=16,
        )
        async for event in stream:
            events.append(event.type)
            if event.type == "response.output_text.delta" and event.delta:
                deltas.append(event.delta)
                if first_text_ms is None:
                    first_text_ms = round((time.monotonic() - started) * 1000, 3)
        final = await stream.get_final_response()
        report = {
            "model": config.moss_model,
            "prompt": "Reply with exactly the token STREAM_OK.",
            "event_types": events,
            "first_text_delta_ms": first_text_ms,
            "end_to_end_ms": round((time.monotonic() - started) * 1000, 3),
            "stream_text": "".join(deltas),
            "final_text": final.output_text,
            "stream_matches_final": "".join(deltas) == final.output_text,
            "completed_event_seen": "response.completed" in events,
            "usage": {
                "input_tokens": final.usage.input_tokens if final.usage else None,
                "output_tokens": final.usage.output_tokens if final.usage else None,
            },
            "status": final.status,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        await client.close()
    out = Path("results/phase2-streaming")
    out.mkdir(parents=True, exist_ok=True)
    (out / "streaming.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in {"stream_text", "final_text"}}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
