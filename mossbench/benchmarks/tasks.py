"""Bounded Tasks API reliability scenarios for Phase 3."""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from moss import MossInference

from ..state import Ledger

SCHEMA = {
    "type": "object",
    "required": ["page_title", "summary", "source_urls"],
    "properties": {
        "page_title": {"type": "string"},
        "summary": {"type": "string"},
        "source_urls": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}

EXTRACT_GOAL = (
    "Visit https://docs.python.org/3/ and return its page title, a one-sentence "
    "summary of what the site documents, and the source URL. Do not invent facts."
)


def schema_pass(output):
    return (isinstance(output, dict)
            and isinstance(output.get("page_title"), str) and bool(output["page_title"].strip())
            and isinstance(output.get("summary"), str) and bool(output["summary"].strip())
            and isinstance(output.get("source_urls"), list)
            and all(isinstance(url, str) and url.startswith("https://docs.python.org/") for url in output["source_urls"])
            and set(output).issubset(SCHEMA["properties"]))


async def run(project_id, project_key, output_dir, per_task_cost=0.25):
    client = MossInference(project_id, project_key)
    ledger = Ledger()
    scenarios = [
        {"id": "T01-T03", "goal": EXTRACT_GOAL, "url": "https://docs.python.org/3/", "schema": SCHEMA, "repeat": 1},
        {"id": "T06", "goal": "Visit https://example.invalid/mossbench and report whether it is reachable. Do not invent page content.", "url": "https://example.invalid/mossbench", "schema": None, "repeat": 1},
        {"id": "T16", "goal": EXTRACT_GOAL, "url": "https://docs.python.org/3/", "schema": SCHEMA, "repeat": 3},
    ]
    rows = []
    try:
        for scenario in scenarios:
            for repeat in range(scenario["repeat"]):
                start = time.monotonic()
                created = await client.tasks.create(
                    goal=scenario["goal"],
                    environment={"type": "browser", "start_url": scenario["url"]},
                    output_schema=scenario["schema"], model="moss-fast", effort="low",
                    limits={"max_runtime_seconds": 60, "max_cost_usd": per_task_cost},
                    metadata={"suite": "phase3", "scenario": scenario["id"], "repeat": repeat},
                )
                ledger.save_task(created.id, created.status)
                terminal = await client.tasks.wait(created.id, timeout=120, poll_interval=2)
                ledger.save_task(terminal.id, terminal.status)
                result = terminal.result
                output = getattr(result, "output", None) if result else None
                usage = terminal.usage
                rows.append({
                    "test_id": scenario["id"], "repeat": repeat, "task_id": created.id,
                    "status": terminal.status, "model": terminal.model,
                    "created_at": created.created_at, "started_at": terminal.started_at,
                    "finished_at": terminal.finished_at,
                    "observed_end_to_end_seconds": round(time.monotonic() - start, 3),
                    "output": output,
                    "output_text": getattr(result, "output_text", None) if result else None,
                    "schema_pass": schema_pass(output) if scenario["schema"] else None,
                    "verification": str(terminal.verification) if terminal.verification else None,
                    "usage": {"model_calls": getattr(usage, "model_calls", None),
                              "input_tokens": getattr(usage, "input_tokens", None),
                              "cached_input_tokens": getattr(usage, "cached_input_tokens", None),
                              "output_tokens": getattr(usage, "output_tokens", None),
                              "model_cost_usd": getattr(usage, "cost_usd", None)} if usage else None,
                    "error_type": type(terminal.error).__name__ if terminal.error else None,
                    "limits": terminal.limits,
                    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                })
    finally:
        await client.close()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "tasks.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False)+"\n" for row in rows), encoding="utf-8")
    summary = {
        "scenario_count": len(rows),
        "completed": sum(row["status"] == "completed" for row in rows),
        "schema_passes": sum(row["schema_pass"] is True for row in rows),
        "schema_applicable": sum(row["schema_pass"] is not None for row in rows),
        "model_cost_usd_reported": sum((row["usage"] or {}).get("model_cost_usd") or 0 for row in rows),
        "model_cost_reported_count": sum((row["usage"] or {}).get("model_cost_usd") is not None for row in rows),
        "note": "Model cost is the task usage field only; browser/total billing may differ. Polling times are observations, not exact transitions.",
    }
    (out / "tasks-summary.json").write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    return summary
