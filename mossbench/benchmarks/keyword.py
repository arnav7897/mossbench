"""Offline BM25 baseline for comparing labeled Moss retrieval queries."""

import hashlib
import json
import math
import re
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

TOKEN = re.compile(r"[a-z0-9_]+")


def tokens(text):
    return TOKEN.findall(text.lower())


def run(corpus_path, queries_path, output_dir):
    docs = [json.loads(line) for line in Path(corpus_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    queries = [json.loads(line) for line in Path(queries_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    token_docs = [tokens(doc["text"]) for doc in docs]
    lengths = [len(doc) for doc in token_docs]
    avgdl = sum(lengths) / len(lengths) if lengths else 0
    df = Counter(term for doc in token_docs for term in set(doc))
    idf = {term: math.log(1 + (len(docs) - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}
    rows = []
    for query in queries:
        started = time.monotonic()
        qterms = tokens(query["query"])
        ranked = []
        for doc, terms, length in zip(docs, token_docs, lengths):
            counts = Counter(terms)
            score = sum(idf.get(term, 0) * counts[term] * 2.2 / (counts[term] + 1.2 * (0.25 + 0.75 * length / (avgdl or 1))) for term in qterms)
            metadata = doc.get("metadata") or {}
            parent = metadata.get("parentId") or metadata.get("parent_id") or doc["id"]
            ranked.append((score, doc["id"], parent))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        top = [doc_id for _, doc_id, _ in ranked[:10]]
        top_parents = [parent for _, _, parent in ranked[:10]]
        relevant = set(query["relevant_ids"])
        rank = next((i for i, parent in enumerate(top_parents, 1) if parent in relevant), None)
        rows.append({
            "test_id": query["id"], "suite": "retrieval", "mode": "local-bm25",
            "source": "local", "split": query["split"], "category": query["category"],
            "ranked_ids": top, "ranked_parent_ids": top_parents,
            "recall_at_1": len(set(top_parents[:1]) & relevant) / len(relevant) if relevant else 0,
            "recall_at_5": len(set(top_parents[:5]) & relevant) / len(relevant) if relevant else 0,
            "recall_at_10": len(set(top_parents[:10]) & relevant) / len(relevant) if relevant else 0,
            "reciprocal_rank": 1 / rank if rank else 0,
            "latency_ms": round((time.monotonic() - started) * 1000, 3),
        })
    grouped = {}
    for split in ("evaluation", "held_out"):
        for category in ("exact", "paraphrase"):
            group = [r for r, q in zip(rows, queries) if q["split"] == split and q["category"] == category]
            if group:
                grouped[f"{split}_{category}"] = {"n": len(group), **{
                    metric: statistics.mean(row[metric] for row in group)
                    for metric in ("recall_at_1", "recall_at_5", "recall_at_10", "reciprocal_rank")}}
    summary = {"mode": "local-bm25", "corpus_sha256": hashlib.sha256(Path(corpus_path).read_bytes()).hexdigest(),
               "queries_sha256": hashlib.sha256(Path(queries_path).read_bytes()).hexdigest(),
               "n": len(rows), "groups": grouped,
               "latency_ms_p50": statistics.median(r["latency_ms"] for r in rows) if rows else None,
               "latency_ms_p95": sorted(r["latency_ms"] for r in rows)[max(0, (len(rows)*95+99)//100-1)] if rows else None,
               "generated_at_utc": datetime.now(timezone.utc).isoformat()}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "keyword.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows), encoding="utf-8")
    (out / "keyword-summary.json").write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    return summary
