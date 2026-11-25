"""Run a public documentation question from index lookup to independent browser verification."""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from moss import MossInference

from mossbench.clients.retrieval import RetrievalClient
from mossbench.config import load_config


INDEX = "mossbench-synth-100"
QUESTION = "What is PostgreSQL's default transaction isolation level?"
SOURCE = "https://www.postgresql.org/docs/current/transaction-iso.html"
FACT = "read committed is the default isolation level in postgresql"
SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}, "quote": {"type": "string"}},
    "required": ["answer", "quote"],
    "additionalProperties": False,
}


def normalized(text):
    return " ".join(text.lower().split()).strip(" .`*")


async def main():
    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("Configure the Moss project credentials before running this workflow.")
    retrieval = RetrievalClient(config.moss_project_id, config.moss_project_key)
    client = MossInference(config.moss_project_id, config.moss_project_key, max_retries=0)
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(), "question": QUESTION,
              "source": SOURCE, "expected_answer": "Read Committed", "top_k": 5,
              "task_limits": {"max_runtime_seconds": 60, "max_cost_usd": 0.05}}
    start = time.monotonic()
    stage = "retrieval"
    try:
        hits = await retrieval.search(INDEX, QUESTION, report["top_k"])
        matches = [rank for rank, doc in enumerate(hits.docs, 1)
                   if doc.metadata.get("source_url") == SOURCE and FACT in normalized(doc.text)]
        report["retrieval"] = {"passages": len(hits.docs), "supporting_ranks": matches,
                               "load_and_query_ms": round(1000 * (time.monotonic() - start))}
        stage = "inference"
        context = "\n\n".join(doc.text for doc in hits.docs)
        response = await client.responses.create(
            model=config.moss_model, instructions="Use only the passages. Reply with the isolation level name alone, or UNKNOWN.",
            input=f"{QUESTION}\n\n{context}", retrieve=False, cache=False, max_output_tokens=32)
        report["inference"] = {"model": config.moss_model, "status": response.status,
                               "answer_matches": normalized(response.output_text) == "read committed"}
        stage = "browser"
        task = await client.tasks.create(
            model="moss-fast", effort="low", limits=report["task_limits"], output_schema=SCHEMA,
            environment={"type": "browser", "start_url": SOURCE},
            goal=f"Read only the linked PostgreSQL page. {QUESTION} Return the level name alone in answer and the exact sentence establishing the default in quote.")
        terminal = await client.tasks.wait(task.id, timeout=120, poll_interval=2)
        output = getattr(terminal.result, "output", None)
        fields = output if isinstance(output, dict) else {}
        report["browser"] = {"status": terminal.status, "answer_matches": normalized(fields.get("answer") or "") == "read committed",
                             "quote_matches_source_sentence": normalized(fields.get("quote") or "").strip('"“”').rstrip(".") == FACT,
                             "model_cost_usd": getattr(terminal.usage, "cost_usd", None)}
        report["verified"] = bool(matches and report["inference"]["answer_matches"] and terminal.status == "completed" and
                                  report["browser"]["answer_matches"] and report["browser"]["quote_matches_source_sentence"])
    except Exception as exc:
        report.update(verified=False, failed_stage=stage, error=type(exc).__name__)
    finally:
        report["elapsed_seconds"] = round(time.monotonic() - start, 3)
        await client.close()
        await retrieval.close()
        Path("reports/evidence/system-workflow.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
