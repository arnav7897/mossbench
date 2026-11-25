"""Measure a loaded Moss index against labeled JSONL retrieval queries."""

import asyncio
import hashlib
import json
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from moss import MossClient, QueryOptions


def percentile(values, p):
    ordered = sorted(values)
    return ordered[max(0, (len(ordered) * p + 99) // 100 - 1)] if ordered else None


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def parent_id(doc):
    metadata = doc.metadata or {}
    return metadata.get("parentId") or metadata.get("parent_id") or doc.id


async def run(project_id, project_key, index_name, queries_path, repeats, warmups, output_dir, alphas=(1.0,)):
    queries = load_jsonl(queries_path)
    dataset_hash = hashlib.sha256(Path(queries_path).read_bytes()).hexdigest()
    client = MossClient(project_id, project_key)
    rows = []
    try:
        await client.load_index(index_name)
        for query in queries:
            for alpha in alphas:
                for _ in range(warmups):
                    await client.query(index_name, query["query"], QueryOptions(top_k=10, alpha=alpha))
        start_batch = time.monotonic()
        for query in queries:
            relevant = set(query["relevant_ids"])
            for alpha in alphas:
                mode = "moss-semantic" if alpha == 1 else "moss-keyword" if alpha == 0 else f"moss-hybrid-alpha-{alpha:g}"
                for repeat in range(repeats):
                    started = time.monotonic()
                    result = await client.query(index_name, query["query"], QueryOptions(top_k=10, alpha=alpha))
                    elapsed_ms = (time.monotonic() - started) * 1000
                    ranked = [doc.id for doc in result.docs]
                    ranked_parents = [parent_id(doc) for doc in result.docs]
                    first_rank = next((rank for rank, doc_id in enumerate(ranked_parents, 1) if doc_id in relevant), None)
                    rows.append({
                        "test_id": query["id"], "repeat": repeat, "suite": "retrieval",
                        "mode": mode, "alpha": alpha, "source": "live", "split": query["split"],
                        "category": query["category"], "query": query["query"],
                        "relevant_ids": sorted(relevant), "ranked_ids": ranked,
                        "ranked_parent_ids": ranked_parents,
                        "recall_at_1": len(set(ranked_parents[:1]) & relevant) / len(relevant) if relevant else 0,
                        "recall_at_5": len(set(ranked_parents[:5]) & relevant) / len(relevant) if relevant else 0,
                        "recall_at_10": len(set(ranked_parents[:10]) & relevant) / len(relevant) if relevant else 0,
                        "reciprocal_rank": 1 / first_rank if first_rank else 0,
                        "latency_ms": round(elapsed_ms, 3), "status": "success",
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    })
        wall_seconds = time.monotonic() - start_batch
    finally:
        await client.close()

    latencies = [row["latency_ms"] for row in rows]
    groups = defaultdict(list)
    for row in rows:
        groups[(row["mode"], row["split"], row["category"])].append(row)
    summaries = []
    for (mode, split, category), group in sorted(groups.items()):
        summaries.append({
            "mode": mode, "split": split, "category": category, "n": len(group),
            "recall@1": statistics.mean(r["recall_at_1"] for r in group),
            "recall@5": statistics.mean(r["recall_at_5"] for r in group),
            "recall@10": statistics.mean(r["recall_at_10"] for r in group),
            "mrr": statistics.mean(r["reciprocal_rank"] for r in group),
        })
    summary = {
        "index": index_name, "query_dataset": str(queries_path), "query_sha256": dataset_hash,
        "query_count": len(queries), "repeats": repeats, "warmups_per_query": warmups,
        "n": len(rows), "successful_qps": len(rows) / wall_seconds if wall_seconds else None,
        "latency_ms": {"p50": percentile(latencies, 50), "p95": percentile(latencies, 95), "p99": percentile(latencies, 99)},
        "groups": summaries, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "retrieval.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out / "retrieval-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
