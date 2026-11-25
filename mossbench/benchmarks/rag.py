"""Compare no-retrieval, explicit-context, and Moss-hosted retrieval answers."""

import asyncio
import hashlib
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from moss import MossClient, MossInference, QueryOptions

MODES = ("llm_only", "manual_rag", "hosted_rag")
INSTRUCTIONS = (
    "Answer accurately in at most three short sentences. Use only information "
    "available to you. If the answer is unavailable, say you do not know."
)
MAX_OUTPUT_TOKENS = 128


def parent_id(doc):
    metadata = doc.metadata or {}
    return metadata.get("parentId") or metadata.get("parent_id") or doc.id


async def run(project_id, project_key, model, index_name, queries_path, output_dir, limit=None):
    queries = [json.loads(line) for line in Path(queries_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if limit:
        queries = queries[:limit]
    digest = hashlib.sha256(Path(queries_path).read_bytes()).hexdigest()
    retrieval = MossClient(project_id, project_key)
    inference = MossInference(project_id, project_key)
    rows = []
    try:
        await retrieval.load_index(index_name)
        for query in queries:
            hits = await retrieval.query(index_name, query["query"], QueryOptions(top_k=3))
            context = "\n\n".join(f"[{doc.id}] {doc.text}" for doc in hits.docs)
            for mode in MODES:
                started = time.monotonic()
                if mode == "llm_only":
                    response = await inference.responses.create(
                        model=model, input=query["query"], instructions=INSTRUCTIONS,
                        retrieve=False, cache=False, max_output_tokens=MAX_OUTPUT_TOKENS)
                elif mode == "manual_rag":
                    response = await inference.responses.create(
                        model=model, input=f"Context:\n{context}\n\nQuestion: {query['query']}",
                        instructions=INSTRUCTIONS, retrieve=False, cache=False,
                        max_output_tokens=MAX_OUTPUT_TOKENS)
                else:
                    response = await inference.responses.create(
                        model=model, input=query["query"], instructions=INSTRUCTIONS,
                        indexes=[index_name], retrieve=True, cache=False,
                        max_output_tokens=MAX_OUTPUT_TOKENS)
                latency_ms = round((time.monotonic() - started) * 1000, 3)
                usage = response.usage
                rows.append({
                    "test_id": query["id"], "suite": "rag", "mode": mode,
                    "source": "live", "split": query["split"], "category": query["category"],
                    "query": query["query"], "reference_ids": query["relevant_ids"],
                    "retrieved_ids": [doc.id for doc in hits.docs],
                    "retrieved_parent_ids": [parent_id(doc) for doc in hits.docs],
                    "answer": response.output_text, "latency_ms": latency_ms,
                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                    "input_tokens": usage.input_tokens if usage else None,
                    "output_tokens": usage.output_tokens if usage else None,
                    "cached_input_tokens": getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", None) if usage else None,
                    "accuracy": None, "source_support": None, "status": "success",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                })
    finally:
        await inference.close()
        await retrieval.close()
    summaries = []
    for mode in MODES:
        group = [r for r in rows if r["mode"] == mode]
        latencies = sorted(r["latency_ms"] for r in group)
        summaries.append({
            "mode": mode, "n": len(group),
            "latency_ms_p50": latencies[len(latencies)//2] if latencies else None,
            "latency_ms_p95": latencies[max(0, (len(latencies)*95+99)//100-1)] if latencies else None,
            "input_tokens": sum(r["input_tokens"] or 0 for r in group),
            "output_tokens": sum(r["output_tokens"] or 0 for r in group),
            "accuracy_review_pending": len(group),
        })
    summary = {"model": model, "index": index_name, "query_count": len(queries),
               "dataset_sha256": digest, "max_output_tokens": MAX_OUTPUT_TOKENS, "modes": summaries,
               "generated_at_utc": datetime.now(timezone.utc).isoformat(),
               "note": "Accuracy and support are unscored pending manual review; cost not exposed in response usage."}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rag.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False)+"\n" for r in rows), encoding="utf-8")
    (out / "rag-summary.json").write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    return summary


async def run_abstention(project_id, project_key, model, index_name, output_dir):
    """Probe unsupported questions with no context and retrieved context (2 questions × 2 modes)."""
    questions = [
        {"id": "ua-001", "query": "What is the exact current production password for the Redis server described in these documents?"},
        {"id": "ua-002", "query": "Which MossBench team member owns the PostgreSQL production database, and what is their phone number?"},
    ]
    retrieval = MossClient(project_id, project_key)
    inference = MossInference(project_id, project_key)
    rows = []
    try:
        await retrieval.load_index(index_name)
        for question in questions:
            hits = await retrieval.query(index_name, question["query"], QueryOptions(top_k=3))
            context = "\n\n".join(f"[{doc.id}] {doc.text}" for doc in hits.docs)
            for mode in ("llm_only", "manual_rag"):
                prompt = question["query"] if mode == "llm_only" else f"Context:\n{context}\n\nQuestion: {question['query']}"
                started = time.monotonic()
                response = await inference.responses.create(
                    model=model, input=prompt,
                    instructions=("Answer accurately in at most two short sentences. Use only the supplied information. "
                                  "Never guess credentials or personal contact details. If the information is unavailable, "
                                  "say you do not know."),
                    retrieve=False, cache=False, max_output_tokens=96)
                usage = response.usage
                rows.append({
                    "test_id": question["id"], "mode": mode, "query": question["query"],
                    "answer": response.output_text, "latency_ms": round((time.monotonic() - started) * 1000, 3),
                    "retrieved_ids": [doc.id for doc in hits.docs],
                    "input_tokens": usage.input_tokens if usage else None,
                    "output_tokens": usage.output_tokens if usage else None,
                    "max_output_tokens": 96, "status": "success",
                })
    finally:
        await inference.close()
        await retrieval.close()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "abstention.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return rows
