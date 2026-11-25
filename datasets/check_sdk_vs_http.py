"""Compare equivalent retrieval-free Responses calls through SDK and raw HTTP."""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from moss import MossInference

from mossbench.config import load_config


ENDPOINT = "https://inference.moss.dev/v1/responses"
PROMPT = "Reply with exactly NET_OK."
INSTRUCTIONS = "Reply with exactly NET_OK and no other text."


def response_text(payload):
    direct = payload.get("output_text")
    if isinstance(direct, str):
        return direct
    parts = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                parts.append(part["text"])
    return "".join(parts)


async def main():
    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be configured")
    body = {
        "model": config.moss_model, "input": PROMPT, "instructions": INSTRUCTIONS,
        "max_output_tokens": 16,
    }
    report = {"model": config.moss_model, "endpoint": ENDPOINT, "cache": False, "retrieve": False}
    sdk = MossInference(config.moss_project_id, config.moss_project_key, max_retries=0, timeout=30)
    try:
        started = time.monotonic()
        sdk_response = await sdk.responses.create(
            **body, retrieve=False, cache=False, max_retries=0, timeout=30)
        report["sdk"] = {
            "status": sdk_response.status,
            "text": sdk_response.output_text,
            "latency_ms": round((time.monotonic() - started) * 1000, 3),
            "input_tokens": sdk_response.usage.input_tokens if sdk_response.usage else None,
            "output_tokens": sdk_response.usage.output_tokens if sdk_response.usage else None,
        }
    except Exception as exc:
        report["sdk"] = {"error_type": type(exc).__name__, "error_code": getattr(exc, "code", None), "http_status": getattr(exc, "status", None)}
    finally:
        await sdk.close()

    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            async with client.stream(
                "POST", ENDPOINT,
                headers={
                    "Authorization": f"Bearer {config.moss_project_id}:{config.moss_project_key}",
                    "Content-Type": "application/json", "Accept": "text/event-stream",
                    "X-Moss-Retrieve": "off", "X-Moss-Cache": "off",
                },
                json={**body, "stream": True},
            ) as response:
                elapsed = None
                final_payload = None
                if response.is_success:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            event = json.loads(line[6:])
                            if event.get("type") == "response.completed":
                                final_payload = event.get("response") or {}
                elapsed = round((time.monotonic() - started) * 1000, 3)
                if response.is_success and final_payload is not None:
                    usage = final_payload.get("usage") or {}
                    report["raw_http"] = {
                        "http_status": response.status_code,
                        "response_status": final_payload.get("status"), "text": response_text(final_payload),
                        "latency_ms": elapsed,
                        "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
                    }
                else:
                    report["raw_http"] = {"http_status": response.status_code, "latency_ms": elapsed, "completed_event_seen": final_payload is not None}
    except Exception as exc:
        report["raw_http"] = {"error_type": type(exc).__name__, "latency_ms": round((time.monotonic() - started) * 1000, 3)}
    report["text_matches"] = bool(report.get("sdk", {}).get("text")) and report.get("sdk", {}).get("text") == report.get("raw_http", {}).get("text")
    report["usage_matches"] = all(report.get("sdk", {}).get(key) == report.get("raw_http", {}).get(key) for key in ("input_tokens", "output_tokens"))
    report["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
    out = Path("results/phase2-sdk-vs-http")
    out.mkdir(parents=True, exist_ok=True)
    (out / "comparison.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in {"sdk", "raw_http"}}, indent=2))
    print(json.dumps({mode: {key: value for key, value in report[mode].items() if key != "text"} for mode in ("sdk", "raw_http")}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
