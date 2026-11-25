"""Temporarily index contradictory test passages and assess conflict handling."""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from moss import MossClient, MossInference, MutationOptions, QueryOptions

from mossbench.config import load_config


INDEX = "mossbench-synth-100"
DOCS = [
    {"id": "mossbench-contradiction-a", "text": "Benchmark fixture A: In this fictional test setup, Celery task retry_limit is exactly 5 attempts.", "metadata": {"topic": "mossbench-contradiction", "fixture": "A"}},
    {"id": "mossbench-contradiction-b", "text": "Benchmark fixture B: In this fictional test setup, Celery task retry_limit is exactly 9 attempts.", "metadata": {"topic": "mossbench-contradiction", "fixture": "B"}},
]
QUERY = "In the supplied benchmark documents, what is the Celery retry_limit?"


async def main():
    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be configured")
    retrieval = MossClient(config.moss_project_id, config.moss_project_key)
    inference = MossInference(config.moss_project_id, config.moss_project_key)
    report = {"index": INDEX, "query": QUERY, "started_at_utc": datetime.now(timezone.utc).isoformat()}
    try:
        existing = {doc.id for doc in await retrieval.get_docs(INDEX)}
        if existing & {doc["id"] for doc in DOCS}:
            raise RuntimeError("guard refused: contradiction fixture ID already exists")
        await retrieval.add_docs(INDEX, DOCS, MutationOptions(upsert=False))
        await retrieval.load_index(INDEX)
        hits = await retrieval.query(INDEX, QUERY, QueryOptions(top_k=5))
        report["retrieved"] = [{"id": doc.id, "text": doc.text, "score": doc.score} for doc in hits.docs]
        context = "\n\n".join(f"[{doc.id}] {doc.text}" for doc in hits.docs)
        started = time.monotonic()
        response = await inference.responses.create(
            model=config.moss_model,
            input=f"Context:\n{context}\n\nQuestion: {QUERY}",
            instructions=("Use only the supplied context. If the context contains conflicting claims, explicitly identify "
                          "the conflict and do not choose one as correct without evidence. Answer briefly."),
            retrieve=False, cache=False, max_output_tokens=128,
        )
        report["answer"] = response.output_text
        report["latency_ms"] = round((time.monotonic() - started) * 1000, 3)
        report["input_tokens"] = response.usage.input_tokens if response.usage else None
        report["output_tokens"] = response.usage.output_tokens if response.usage else None
        report["status"] = "success"
    except Exception as exc:
        report["status"] = "error"
        report["error_type"] = type(exc).__name__
        report["error_message"] = str(exc)[:300]
        raise
    finally:
        try:
            current = {doc.id for doc in await retrieval.get_docs(INDEX)}
            to_delete = sorted(current & {doc["id"] for doc in DOCS})
            if to_delete:
                await retrieval.delete_docs(INDEX, to_delete)
            after = {doc.id for doc in await retrieval.get_docs(INDEX)}
            report["cleanup_verified"] = not (after & {doc["id"] for doc in DOCS})
        finally:
            await inference.close()
            await retrieval.close()
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        out = Path("results/phase2-contradictions")
        out.mkdir(parents=True, exist_ok=True)
        (out / "contradictions.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    if not report.get("cleanup_verified"):
        raise RuntimeError("contradiction fixture cleanup could not be verified")
    print(json.dumps({k: v for k, v in report.items() if k not in {"retrieved"}}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
