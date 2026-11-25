"""Run two bounded Python documentation tasks and publish ID-free measurements."""

import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from moss import MossInference

from mossbench.config import load_config
from mossbench.state import Ledger


URL = "https://docs.python.org/3/library/index.html"
GOAL = (
    "Prepare an annotated guide from the official Python library reference. "
    "Visit each individual module page for pathlib, os, shutil, tempfile, glob, fnmatch, "
    "zipfile, tarfile, gzip, bz2, lzma, csv, configparser, argparse, logging, json, "
    "tomllib, calendar, datetime, zoneinfo, time, string, textwrap, enum and graphlib. "
    "For every page, identify one public function or class, one exact sentence from "
    "its documentation, and the section anchor URL. Do not use index snippets. "
    "Save the verified rows in guide.md. If interrupted, return verified rows only."
)
PILOT_GOAL = (
    "Using the official Python library reference, open each chapter for pathlib, "
    "os, shutil, tempfile, glob, fnmatch, zipfile, tarfile, gzip and bz2. "
    "For each, record its page title, one public function or class, and its URL. "
    "Visit each chapter before reporting it. If interrupted, return verified rows only."
)
MONITOR_GOAL = (
    "Monitor the title on this public Python documentation page for 90 seconds. "
    "Record the title on opening and at 30, 60 and 90 seconds of actual elapsed "
    "time. Wait between samples. If the service stops early, report only the "
    "samples actually observed. Do not extrapolate or browse other pages."
)


async def measure(client, ledger, name, cap, runtime, goal):
    start = time.monotonic()
    row = {"scenario": name, "requested_model_limit_usd": cap, "runtime_limit_s": runtime}
    try:
        task = await client.tasks.create(
            goal=goal, environment={"type": "browser", "start_url": URL},
            model="moss-fast", effort="low",
            limits={"max_runtime_seconds": runtime, "max_cost_usd": cap},
        )
        ledger.save_task(task.id, task.status)
        final = await client.tasks.wait(task.id, timeout=runtime + 90, poll_interval=2)
        ledger.save_task(final.id, final.status)
        row.update(
            terminal_status=final.status, error_code=final.error.code if final.error else None,
            returned_model_limit_usd=final.limits.get("max_cost_usd"),
            returned_runtime_limit_s=final.limits.get("max_runtime_seconds"),
            started_at=final.started_at, finished_at=final.finished_at,
        )
        if final.started_at and final.finished_at:
            duration = datetime.fromisoformat(final.finished_at) - datetime.fromisoformat(final.started_at)
            row["service_duration_s"] = round(duration.total_seconds(), 3)
        if final.usage and "cost_usd" in final.usage.raw:
            cost = final.usage.cost_usd
            row.update(model_cost_usd=cost, model_overshoot_usd=round(max(cost - cap, 0), 6))
    except Exception as exc:
        row.update(exception_type=type(exc).__name__, error_code=getattr(exc, "code", None))
    row["client_duration_s"] = round(time.monotonic() - start, 3)
    return row


async def main(pilot, monitor):
    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("Configure Moss project credentials before running")
    client = MossInference(config.moss_project_id, config.moss_project_key, max_retries=0)
    ledger = Ledger()
    goal, spend_cap, spend_runtime = (PILOT_GOAL, 0.001, 60) if pilot else (GOAL, 0.01, 180)
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
              "workload": "timed title monitor" if monitor else ("ten-module pilot" if pilot else "annotated module guide"),
              "source": URL, "model": "moss-fast", "poll_interval_s": 2,
              "limit_docs": "https://docs.moss.dev/docs/inference/tasks.md",
              "expected": {"runtime": "An unfinished task at the runtime limit fails with time_limit",
                           "spend": "At the threshold an unfinished task fails with budget_exceeded. In-flight model calls can finish and bill.",
                           "concurrency": "Each independent submission reaches its own terminal state"}}
    try:
        if monitor:
            ledger.reserve(report["started_at_utc"], 0.10, "Single public-doc monitoring task, model cap only")
            rows = [await measure(client, ledger, "runtime", 0.10, 60, MONITOR_GOAL)]
        else:
            ledger.reserve(report["started_at_utc"], 0.15 + spend_cap, "Two public-doc tasks, model caps only")
            rows = await asyncio.gather(measure(client, ledger, "runtime", 0.15, 60, goal),
                                        measure(client, ledger, "spend", spend_cap, spend_runtime, goal))
        report["observations"] = rows
        if len(rows) == 2 and all(r.get("started_at") and r.get("finished_at") for r in rows):
            overlap = min(datetime.fromisoformat(r["finished_at"]) for r in rows) - max(
                datetime.fromisoformat(r["started_at"]) for r in rows)
            report["service_run_overlap_s"] = max(round(overlap.total_seconds(), 3), 0)
    finally:
        await client.close()
        ledger.db.close()
    path = Path("reports/evidence/task-limit-checks.json")
    previous = json.loads(path.read_text()) if path.exists() else []
    history = previous if isinstance(previous, list) else [previous]
    path.write_text(json.dumps([*history, report], indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--pilot", action="store_true", help="repeat the shorter ten-module run")
    mode.add_argument("--monitor", action="store_true", help="run one timed title-monitoring task")
    args = parser.parse_args()
    asyncio.run(main(args.pilot, args.monitor))
