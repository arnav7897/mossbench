"""Moss retrieval SDK adapter."""

import json
from pathlib import Path

from moss import MossClient, MutationOptions, QueryOptions


class RetrievalClient:
    def __init__(self, project_id, project_key):
        self.client = MossClient(project_id, project_key)

    async def ingest(self, index_name, corpus_path):
        docs = [json.loads(line) for line in Path(corpus_path).read_text(encoding="utf-8").splitlines() if line.strip()]
        if not docs:
            raise ValueError("corpus is empty")
        return await self.client.create_index(index_name, docs, wait=True)

    async def update(self, index_name, corpus_path):
        docs = [json.loads(line) for line in Path(corpus_path).read_text(encoding="utf-8").splitlines() if line.strip()]
        if not docs:
            raise ValueError("corpus is empty")
        return await self.client.add_docs(index_name, docs, MutationOptions(upsert=True))

    async def search(self, index_name, query, top_k=5):
        await self.client.load_index(index_name)
        return await self.client.query(index_name, query, QueryOptions(top_k=top_k))

    async def close(self):
        await self.client.close()
