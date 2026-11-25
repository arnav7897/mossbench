"""Check supported retrieval filters, mutations, empty queries, and reload behavior."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from moss import MossClient, MutationOptions, QueryOptions

from mossbench.config import load_config


INDEX = "mossbench-synth-100"
PROBE_ID = "mossbench-phase2-contract-probe"
OUT = Path("results/phase2-real-retrieval-contracts.json")


def mutation_summary(result):
    return {"job_id": result.job_id, "index_name": result.index_name, "doc_count": result.doc_count}


async def new_client(config, *, load=False):
    client = MossClient(config.moss_project_id, config.moss_project_key)
    if load:
        await client.load_index(INDEX)
    return client


async def main():
    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be configured")
    report = {"index": INDEX, "started_at_utc": datetime.now(timezone.utc).isoformat(), "checks": {}}

    client = await new_client(config, load=True)
    try:
        filtered = await client.query(
            INDEX,
            "How does a Redis consumer group acknowledge a processed message?",
            QueryOptions(top_k=10, filter={"field": "topic", "condition": {"$eq": "redis"}}),
        )
        topics = [doc.metadata.get("topic") for doc in filtered.docs]
        report["checks"]["metadata_filter"] = {
            "passed": bool(topics) and all(topic == "redis" for topic in topics),
            "result_count": len(topics), "topics": topics,
        }

        try:
            empty = await client.query(INDEX, "", QueryOptions(top_k=3))
            report["checks"]["empty_query"] = {"outcome": "returned", "result_count": len(empty.docs)}
        except Exception as exc:
            report["checks"]["empty_query"] = {
                "outcome": "rejected", "error_type": type(exc).__name__,
                "code": getattr(exc, "code", None), "message": str(exc)[:240],
            }

        no_match = await client.query(
            INDEX, "mossbench_unmatchable_probe_zebra_927351",
            QueryOptions(top_k=3, min_score=0.999999),
        )
        report["checks"]["empty_results"] = {"passed": len(no_match.docs) == 0, "result_count": len(no_match.docs)}

        stable_query = "How does XADD append a new entry to a Redis Stream?"
        before = await client.query(INDEX, stable_query, QueryOptions(top_k=5))
        before_ids = [doc.id for doc in before.docs]
        if any(doc.id == PROBE_ID for doc in await client.get_docs(INDEX)):
            raise RuntimeError(f"guard refused: {PROBE_ID} already exists")
    finally:
        await client.close()

    client = await new_client(config, load=True)
    try:
        after = await client.query(INDEX, stable_query, QueryOptions(top_k=5))
        after_ids = [doc.id for doc in after.docs]
        report["checks"]["fresh_client_reload"] = {"passed": before_ids == after_ids, "before_ids": before_ids, "after_ids": after_ids}
    finally:
        await client.close()

    try:
        client = await new_client(config)
        first = await client.add_docs(INDEX, [{
            "id": PROBE_ID,
            "text": "MossBench probe original_marker saffron_624193 for update visibility.",
            "metadata": {"topic": "mossbench-probe"},
        }], MutationOptions(upsert=True))
        await client.close()
        client = None

        client = await new_client(config)
        second = await client.add_docs(INDEX, [{
            "id": PROBE_ID,
            "text": "MossBench probe revised_marker indigo_883017 for upsert visibility.",
            "metadata": {"topic": "mossbench-probe"},
        }], MutationOptions(upsert=True))
        await client.close()
        client = None

        client = await new_client(config, load=True)
        stored = await client.get_docs(INDEX, options=None)
        matches = [doc for doc in stored if doc.id == PROBE_ID]
        query_result = await client.query(INDEX, "revised_marker indigo_883017", QueryOptions(top_k=3, alpha=0))
        report["checks"]["duplicate_id_upsert"] = {
            "passed": len(matches) == 1 and "revised_marker" in matches[0].text and "original_marker" not in matches[0].text,
            "matching_documents": len(matches), "updated_text_visible": bool(matches and "revised_marker" in matches[0].text),
            "search_ranks_probe": [doc.id for doc in query_result.docs],
            "first_mutation": mutation_summary(first), "second_mutation": mutation_summary(second),
        }
        await client.close()
        client = None

        client = await new_client(config)
        deleted = await client.delete_docs(INDEX, [PROBE_ID])
        await client.close()
        client = None

        client = await new_client(config, load=True)
        remaining = [doc for doc in await client.get_docs(INDEX) if doc.id == PROBE_ID]
        delete_query = await client.query(INDEX, "revised_marker indigo_883017", QueryOptions(top_k=10, alpha=0))
        report["checks"]["delete_visibility"] = {
            "passed": not remaining and all(doc.id != PROBE_ID for doc in delete_query.docs),
            "remaining_documents": len(remaining), "probe_in_search": any(doc.id == PROBE_ID for doc in delete_query.docs),
            "delete_mutation": mutation_summary(deleted),
        }
        await client.close()
        client = None
    finally:
        if client is not None:
            await client.close()
        cleanup = await new_client(config)
        try:
            if any(doc.id == PROBE_ID for doc in await cleanup.get_docs(INDEX)):
                await cleanup.delete_docs(INDEX, [PROBE_ID])
        finally:
            await cleanup.close()

    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for name, result in report["checks"].items():
        print(name, result)
    print("saved", OUT)


if __name__ == "__main__":
    asyncio.run(main())
