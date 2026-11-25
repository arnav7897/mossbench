"""Exercise one deterministic local function tool through Moss Responses."""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from moss import MossInference

from mossbench.config import load_config


ORDERS = {"MOSS-001": {"status": "shipped", "eta": "2026-11-27"}}
TOOL = {
    "type": "function", "name": "order_lookup",
    "description": "Look up an order in the local benchmark fixture.",
    "parameters": {
        "type": "object", "properties": {"order_id": {"type": "string"}},
        "required": ["order_id"], "additionalProperties": False,
    },
}


async def main():
    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be configured")
    client = MossInference(config.moss_project_id, config.moss_project_key, max_retries=0)
    started = time.monotonic()
    report = {"model": config.moss_model, "tool_name": TOOL["name"], "status": "error"}
    try:
        first = await client.responses.create(
            model=config.moss_model,
            input="Use order_lookup to check order MOSS-001, then summarize its status and ETA.",
            instructions="Use the provided order_lookup function for the requested order. Do not invent data.",
            tools=[TOOL], tool_choice={"type": "function", "name": "order_lookup"},
            retrieve=False, cache=False, max_output_tokens=96,
        )
        calls = [item for item in first.output if getattr(item, "type", None) == "function_call"]
        report["function_call_count"] = len(calls)
        report["first_usage"] = {
            "input_tokens": first.usage.input_tokens if first.usage else None,
            "output_tokens": first.usage.output_tokens if first.usage else None,
        }
        if len(calls) != 1 or calls[0].name != TOOL["name"]:
            report["error"] = "expected exactly one order_lookup function call"
        else:
            call = calls[0]
            args = json.loads(call.arguments)
            result = ORDERS.get(args.get("order_id"), {"error": "order_not_found"})
            final = await client.responses.create(
                model=config.moss_model,
                input=[*first.output, {
                    "type": "function_call_output", "call_id": call.call_id,
                    "output": json.dumps(result),
                }],
                instructions="Summarize only the tool result in one short sentence.",
                retrieve=False, cache=False, max_output_tokens=48,
            )
            report.update({
                "status": "success", "local_tool_executed": True,
                "tool_returned_fixture_record": result == ORDERS["MOSS-001"],
                "final_answer": final.output_text,
                "final_mentions_shipped": "shipped" in final.output_text.lower(),
                "second_usage": {
                    "input_tokens": final.usage.input_tokens if final.usage else None,
                    "output_tokens": final.usage.output_tokens if final.usage else None,
                },
            })
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        report["error_code"] = getattr(exc, "code", None)
        report["http_status"] = getattr(exc, "status", None)
        report["error_message"] = str(exc)[:300]
    finally:
        await client.close()
        report["end_to_end_ms"] = round((time.monotonic() - started) * 1000, 3)
        report["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
        out = Path("results/phase2-function-tool")
        out.mkdir(parents=True, exist_ok=True)
        (out / "function-tool.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "final_answer"}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
