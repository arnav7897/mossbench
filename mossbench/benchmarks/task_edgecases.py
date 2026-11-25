"""Bounded limit, idempotency, and cancellation-race checks for Tasks."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from moss import MossInference

from ..state import Ledger


async def run(project_id, project_key, output_dir):
    client = MossInference(project_id, project_key)
    ledger = Ledger()
    rows = []
    try:
        base = {"environment": {"type": "browser", "start_url": "https://docs.python.org/3/"},
                "model": "moss-fast", "effort": "low"}

        try:
            await client.tasks.create(
                goal="Report the title of the Python docs site.",
                limits={"max_runtime_seconds": 30, "max_cost_usd": 0.05}, **base)
            rows.append({"test_id": "T08", "outcome": "accepted_unexpectedly"})
        except Exception as exc:
            rows.append({"test_id": "T08", "outcome": "rejected_before_task",
                         "error_type": type(exc).__name__, "code": getattr(exc, "code", None),
                         "message": str(exc)[:300]})

        low = await client.tasks.create(
            goal="Visit https://docs.python.org/3/ and return only its page title.",
            limits={"max_runtime_seconds": 60, "max_cost_usd": 0.01}, **base)
        ledger.save_task(low.id, low.status)
        low_final = await client.tasks.wait(low.id, timeout=120, poll_interval=2)
        ledger.save_task(low.id, low_final.status)
        rows.append({"test_id": "T09", "task_id": low.id, "status": low_final.status,
                     "limit": low.limits,
                     "usage": str(low_final.usage) if low_final.usage else None,
                     "error_type": type(low_final.error).__name__ if low_final.error else None,
                     "result_text": getattr(low_final.result, "output_text", None) if low_final.result else None})

        idem_key = f"mossbench-phase3-duplicate-{uuid.uuid4()}"
        dup_args = {
            "goal": "Visit https://docs.python.org/3/ and return only its page title.",
            "environment": {"type": "browser", "start_url": "https://docs.python.org/3/"},
            "model": "moss-fast", "effort": "low",
            "limits": {"max_runtime_seconds": 60, "max_cost_usd": 0.05},
            "extra_headers": {"Idempotency-Key": idem_key},
        }
        first = await client.tasks.create(**dup_args)
        ledger.save_task(first.id, first.status)
        second = await client.tasks.create(**dup_args)
        dup_final = await client.tasks.wait(first.id, timeout=120, poll_interval=2)
        ledger.save_task(first.id, dup_final.status)
        rows.append({"test_id": "T13", "first_task_id": first.id, "second_task_id": second.id,
                     "same_task_id": first.id == second.id, "first_status": first.status,
                     "second_status": second.status, "terminal_status": dup_final.status,
                     "usage": str(dup_final.usage) if dup_final.usage else None})

        race = await client.tasks.create(
            goal="Read the Python docs introduction and summarize its purpose in one sentence.",
            limits={"max_runtime_seconds": 60, "max_cost_usd": 0.05}, **base)
        ledger.save_task(race.id, race.status)
        cancel_result, wait_result = await asyncio.gather(
            client.tasks.cancel(race.id),
            client.tasks.wait(race.id, timeout=120, poll_interval=2),
            return_exceptions=True,
        )
        if not isinstance(wait_result, Exception):
            ledger.save_task(race.id, wait_result.status)
        rows.append({"test_id": "T10-race", "task_id": race.id, "initial_status": race.status,
                     "cancel_status": getattr(cancel_result, "status", None) if not isinstance(cancel_result, Exception) else None,
                     "cancel_error": type(cancel_result).__name__ if isinstance(cancel_result, Exception) else None,
                     "terminal_status": getattr(wait_result, "status", None) if not isinstance(wait_result, Exception) else None,
                     "wait_error": type(wait_result).__name__ if isinstance(wait_result, Exception) else None,
                     "note": "Concurrent cancel and polling; observed terminal state is authoritative, poll timing is approximate."})
    finally:
        await client.close()

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "edgecases.jsonl").write_text("".join(json.dumps(row,ensure_ascii=False)+"\n" for row in rows),encoding="utf-8")
    (out / "edgecases-summary.json").write_text(json.dumps({"scenarios":len(rows),"created_task_scenarios":3,
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "note":"Task model-cost limits do not guarantee total task billing; usage field is model usage only."},indent=2)+"\n",encoding="utf-8")
    return rows
