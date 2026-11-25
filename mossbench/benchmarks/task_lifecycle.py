"""Task lifecycle, cancellation, restart, and artifact checks."""

import asyncio
import hashlib
import json
import time
from pathlib import Path

from moss import MossInference

from ..state import Ledger


async def run(project_id, project_key, completed_task_id, output_dir):
    rows = []
    out = Path(output_dir)
    ledger = Ledger()
    client = MossInference(project_id, project_key)
    try:
        try:
            await client.tasks.retrieve("task_invalid_mossbench_id")
            rows.append({"test_id": "T05", "outcome": "unexpectedly_retrieved"})
        except Exception as exc:
            rows.append({"test_id": "T05", "outcome": "rejected", "error_type": type(exc).__name__,
                         "code": getattr(exc, "code", None), "message": str(exc)[:300]})

        try:
            task = await client.tasks.cancel(completed_task_id)
            rows.append({"test_id": "T11", "task_id": task.id, "outcome": "returned",
                         "status": task.status, "cancel_requested": task.cancel_requested})
        except Exception as exc:
            rows.append({"test_id": "T11", "task_id": completed_task_id, "outcome": "error",
                         "error_type": type(exc).__name__, "code": getattr(exc, "code", None),
                         "message": str(exc)[:300]})

        created = await client.tasks.create(
            goal="Browse the Python documentation contents page and list three major sections.",
            environment={"type": "browser", "start_url": "https://docs.python.org/3/contents.html"},
            model="moss-fast", effort="low",
            limits={"max_runtime_seconds": 60, "max_cost_usd": 0.25},
        )
        ledger.save_task(created.id, created.status)
        cancel_started = time.monotonic()
        try:
            cancelled = await client.tasks.cancel(created.id)
            final = await client.tasks.wait(created.id, timeout=120, poll_interval=2)
            ledger.save_task(final.id, final.status)
            rows.append({"test_id": "T10", "task_id": created.id, "initial_status": created.status,
                         "cancel_response_status": cancelled.status, "terminal_status": final.status,
                         "cancel_to_terminal_seconds": round(time.monotonic()-cancel_started,3),
                         "usage": str(final.usage) if final.usage else None})
        except Exception as exc:
            rows.append({"test_id": "T10", "task_id": created.id, "outcome": "error",
                         "error_type": type(exc).__name__, "message": str(exc)[:300]})
    finally:
        await client.close()

    # Resume a queued task after constructing a fresh client with the same project credentials.
    client = MossInference(project_id, project_key)
    try:
        created = await client.tasks.create(
            goal="Visit https://docs.python.org/3/ and return its page title.",
            environment={"type": "browser", "start_url": "https://docs.python.org/3/"},
            model="moss-fast", effort="low",
            limits={"max_runtime_seconds": 60, "max_cost_usd": 0.25},
        )
        ledger.save_task(created.id, created.status)
    finally:
        await client.close()
    client = MossInference(project_id, project_key)
    try:
        resumed = await client.tasks.wait(created.id, timeout=120, poll_interval=2)
        ledger.save_task(resumed.id, resumed.status)
        rows.append({"test_id": "T12", "task_id": resumed.id, "initial_status": created.status,
                     "terminal_status": resumed.status, "same_task_id": created.id == resumed.id,
                     "result_text": getattr(resumed.result, "output_text", None) if resumed.result else None,
                     "usage": str(resumed.usage) if resumed.usage else None})

        artifact_task = await client.tasks.create(
            goal=("Visit https://docs.python.org/3/ and create a small text file named summary.txt "
                  "containing the page title and source URL. Return the same information."),
            environment={"type": "browser", "start_url": "https://docs.python.org/3/"},
            model="moss-fast", effort="low",
            limits={"max_runtime_seconds": 60, "max_cost_usd": 0.25},
        )
        ledger.save_task(artifact_task.id, artifact_task.status)
        try:
            await client.tasks.files.list(artifact_task.id)
            premature = "available"
        except Exception as exc:
            premature = {"error_type": type(exc).__name__, "code": getattr(exc, "code", None), "message": str(exc)[:200]}
        finished = await client.tasks.wait(artifact_task.id, timeout=120, poll_interval=2)
        ledger.save_task(finished.id, finished.status)
        files = await client.tasks.files.list(finished.id)
        artifacts = []
        for file in files.data:
            content = await client.tasks.files.content(finished.id, file.path)
            artifact_path = out / "artifacts" / Path(file.path).name
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_bytes(content.data)
            artifacts.append({"path": file.path, "declared_bytes": file.bytes,
                              "actual_bytes": len(content.data), "sha256": hashlib.sha256(content.data).hexdigest(),
                              "content_type": content.content_type,
                              "saved_to": str(artifact_path)})
        rows.append({"test_id": "T04-T14", "task_id": finished.id, "status": finished.status,
                     "premature_request": premature, "artifacts": artifacts,
                     "result_text": getattr(finished.result, "output_text", None) if finished.result else None,
                     "usage": str(finished.usage) if finished.usage else None})
    finally:
        await client.close()

    out.mkdir(parents=True, exist_ok=True)
    (out / "lifecycle.jsonl").write_text("".join(json.dumps(row,ensure_ascii=False)+"\n" for row in rows),encoding="utf-8")
    return rows
