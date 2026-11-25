"""Compare streamed and non-streamed Moss Responses text for one prompt."""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from moss import MossInference

from mossbench.config import load_config


PROMPT = "Reply with exactly STREAM_COMPARE_OK."


async def main():
    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be configured")
    client = MossInference(config.moss_project_id, config.moss_project_key, max_retries=0, timeout=30)
    report = {"model": config.moss_model, "prompt": PROMPT, "cache": False, "retrieve": False}
    try:
        started = time.monotonic()
        whole = await client.responses.create(
            model=config.moss_model, input=PROMPT,
            instructions="Reply with exactly STREAM_COMPARE_OK and no other text.",
            retrieve=False, cache=False, max_output_tokens=16, max_retries=0,
        )
        report["nonstream"] = {
            "status": whole.status, "text": whole.output_text,
            "latency_ms": round((time.monotonic() - started) * 1000, 3),
            "input_tokens": whole.usage.input_tokens if whole.usage else None,
            "output_tokens": whole.usage.output_tokens if whole.usage else None,
        }

        started = time.monotonic()
        stream = await client.responses.create(
            model=config.moss_model, input=PROMPT,
            instructions="Reply with exactly STREAM_COMPARE_OK and no other text.",
            retrieve=False, cache=False, max_output_tokens=16, max_retries=0,
            stream=True,
        )
        deltas, events = [], []
        async for event in stream:
            events.append(event.type)
            if event.type == "response.output_text.delta" and event.delta:
                deltas.append(event.delta)
        final = await stream.get_final_response()
        streamed_text = "".join(deltas)
        report["stream"] = {
            "status": final.status, "text": streamed_text,
            "matches_stream_final": streamed_text == final.output_text,
            "latency_ms": round((time.monotonic() - started) * 1000, 3),
            "events": events,
            "input_tokens": final.usage.input_tokens if final.usage else None,
            "output_tokens": final.usage.output_tokens if final.usage else None,
        }
        report["texts_match"] = report["nonstream"]["text"] == streamed_text
    finally:
        await client.close()
    report["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
    out = Path("results/phase2-stream-equivalence")
    out.mkdir(parents=True, exist_ok=True)
    (out / "equivalence.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in {"nonstream", "stream"}}, indent=2))
    print(json.dumps({mode: {key: val for key, val in report[mode].items() if key != "text"} for mode in ("nonstream", "stream")}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
