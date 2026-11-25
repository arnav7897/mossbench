"""Probe retrieval ranking on supported and unsupported questions."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from moss import MossClient, QueryOptions

from mossbench.config import load_config


INDEX = "mossbench-synth-100"
CASES = [
    {"id": "hn-001", "query": "How does FastAPI validate a JSON request body with a Pydantic model?", "supported_parent": "fastapi-body"},
    {"id": "hn-002", "query": "What is the default administrator password for FastAPI?", "supported_parent": None},
    {"id": "hn-003", "query": "Which MossBench employee owns the PostgreSQL production database?", "supported_parent": None},
    {"id": "hn-004", "query": "What exact numeric connection timeout does this MossBench project configure for Redis?", "supported_parent": None},
]


async def main():
    config = load_config()
    if not config.moss_project_id or not config.moss_project_key:
        raise SystemExit("MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be configured")
    client = MossClient(config.moss_project_id, config.moss_project_key)
    rows = []
    try:
        await client.load_index(INDEX)
        for case in CASES:
            result = await client.query(INDEX, case["query"], QueryOptions(top_k=5))
            rows.append({
                **case,
                "results": [{
                    "id": doc.id,
                    "parent_id": (doc.metadata or {}).get("parentId") or (doc.metadata or {}).get("parent_id") or doc.id,
                    "score": doc.score,
                } for doc in result.docs],
            })
    finally:
        await client.close()
    out = Path("results/phase2-hard-negatives")
    out.mkdir(parents=True, exist_ok=True)
    path = out / "hard-negatives.json"
    path.write_text(json.dumps({"index": INDEX, "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "cases": rows}, indent=2) + "\n")
    print(f"saved {path}; cases={len(rows)}")


if __name__ == "__main__":
    asyncio.run(main())
