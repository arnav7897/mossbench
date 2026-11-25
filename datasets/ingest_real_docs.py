"""Replace only MossBench's known synthetic smoke docs with the real-doc corpus."""

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from moss import MossClient, MutationOptions

from mossbench.config import load_config


INDEX = "mossbench-synth-100"
EXPECTED_SYNTHETIC_IDS = {f"synthetic-{number:05d}" for number in range(100)}
CORPUS_PATH = Path(__file__).resolve().parent / "real_docs" / "corpus.jsonl"
MANIFEST_PATH = Path(__file__).resolve().parent / "real_docs" / "sources.json"
RECEIPT_PATH = Path(__file__).resolve().parent / "real_docs" / "ingest-receipt.json"


async def main():
    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be configured")
    docs = [json.loads(line) for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    real_ids = {doc["id"] for doc in docs}
    source_ids = {doc["metadata"]["parentId"] for doc in docs}
    if len(real_ids) != len(docs) or not real_ids:
        raise SystemExit("real-doc corpus must have unique, nonempty document IDs")
    if any(not doc["id"].startswith(doc["metadata"]["parentId"] + "#chunk-") for doc in docs):
        raise SystemExit("real-doc corpus contains an unexpected document ID format")

    client = MossClient(config.moss_project_id, config.moss_project_key)
    try:
        indexes = await client.list_indexes()
        if INDEX not in {index.name for index in indexes}:
            raise SystemExit(f"guard refused: {INDEX} is not present in this project")
        current = await client.get_docs(INDEX)
        current_ids = {doc.id for doc in current}
        allowed_ids = EXPECTED_SYNTHETIC_IDS | source_ids | real_ids
        if not current_ids or not current_ids <= allowed_ids:
            raise SystemExit(
                "guard refused: the index contains IDs outside the known MossBench synthetic/page/chunk corpus"
            )

        added = await client.add_docs(INDEX, docs, MutationOptions(upsert=True))
        after_add = await client.get_docs(INDEX)
        after_add_ids = {doc.id for doc in after_add}
        if not real_ids <= after_add_ids:
            raise RuntimeError(f"upsert incomplete: only {len(real_ids & after_add_ids)}/{len(real_ids)} real docs visible")

        obsolete_ids = current_ids & (EXPECTED_SYNTHETIC_IDS | source_ids)
        deleted = await client.delete_docs(INDEX, sorted(obsolete_ids)) if obsolete_ids else None
        final_docs = await client.get_docs(INDEX)
        final_ids = {doc.id for doc in final_docs}
        if final_ids != real_ids:
            raise RuntimeError(
                f"final index verification mismatch: {len(final_ids)} docs, "
                f"expected {len(real_ids)}; unexpected={sorted(final_ids-real_ids)[:5]}"
            )

        receipt = {
            "index": INDEX,
            "document_count": len(final_docs),
            "source_page_count": len(source_ids),
            "document_ids_sha256": hashlib.sha256("\n".join(sorted(real_ids)).encode()).hexdigest(),
            "chunk_size_chars": json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["chunk_size_chars"],
            "chunk_overlap_chars": json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["chunk_overlap_chars"],
            "obsolete_documents_replaced": len(obsolete_ids),
            "upsert_result": {"job_id": added.job_id, "index_name": added.index_name, "doc_count": added.doc_count},
            "delete_result": ({"job_id": deleted.job_id, "index_name": deleted.index_name, "doc_count": deleted.doc_count}
                              if deleted is not None else None),
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        RECEIPT_PATH.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(f"Index ready: {INDEX}; verified real-doc documents={len(final_docs)}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
