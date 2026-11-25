"""Generate deterministic synthetic benchmark corpora and labeled queries."""

import argparse
import json
import random
from pathlib import Path

FACTS = [
    ("fastapi", "FastAPI validates request bodies with Pydantic models.", "validation"),
    ("celery", "Celery retry behavior is configured with task.retry and retry limits.", "retries"),
    ("redis", "Redis persistence can use RDB snapshots or the AOF log.", "persistence"),
    ("postgresql", "PostgreSQL transactions provide atomicity and isolation.", "transactions"),
    ("celery-redis", "Celery can use Redis as a broker and result backend.", "integration"),
    ("fastapi-auth", "FastAPI dependencies can enforce authentication on routes.", "security"),
    ("redis-ttl", "Redis keys can expire after a configured time-to-live.", "expiration"),
    ("postgres-index", "PostgreSQL indexes can speed reads but add write overhead.", "indexing"),
    ("celery-acks", "Acknowledgements affect when Celery considers a message handled.", "delivery"),
    ("fastapi-async", "FastAPI supports async path operations for awaitable I/O.", "async"),
]

QUERIES = [
    ("What validates FastAPI request bodies?", "fastapi", "exact"),
    ("How do I validate a body sent to FastAPI?", "fastapi", "paraphrase"),
    ("How are Celery task retries configured?", "celery", "exact"),
    ("How can a worker retry a failed job?", "celery", "paraphrase"),
    ("What are Redis persistence options?", "redis", "exact"),
    ("How can Redis data survive restart?", "redis", "paraphrase"),
    ("What do PostgreSQL transactions provide?", "postgresql", "exact"),
    ("Which guarantees come from a database transaction?", "postgresql", "paraphrase"),
    ("Can Celery use Redis as both broker and result backend?", "celery-redis", "exact"),
    ("What connects Celery workers to Redis?", "celery-redis", "paraphrase"),
    ("How can FastAPI routes require authentication?", "fastapi-auth", "exact"),
    ("How do I protect an API endpoint with dependencies?", "fastapi-auth", "paraphrase"),
    ("How does Redis key expiration work?", "redis-ttl", "exact"),
    ("Can a cache entry expire automatically?", "redis-ttl", "paraphrase"),
    ("What is the tradeoff of PostgreSQL indexes?", "postgres-index", "exact"),
    ("Why might indexes slow database writes?", "postgres-index", "paraphrase"),
    ("When does Celery acknowledge a message?", "celery-acks", "exact"),
    ("What controls message acknowledgement in Celery?", "celery-acks", "paraphrase"),
    ("Does FastAPI support async endpoints?", "fastapi-async", "exact"),
    ("Can an API handler await network I/O?", "fastapi-async", "paraphrase"),
    ("What validates JSON input in FastAPI?", "fastapi", "paraphrase"),
    ("Where are retry limits set for Celery?", "celery", "paraphrase"),
    ("Name the Redis append-only persistence option.", "redis", "exact"),
    ("Which database feature makes a group of writes atomic?", "postgresql", "paraphrase"),
    ("Which datastore can back Celery task results?", "celery-redis", "paraphrase"),
    ("How can authentication be shared across FastAPI routes?", "fastapi-auth", "paraphrase"),
    ("What setting removes stale Redis keys?", "redis-ttl", "paraphrase"),
    ("How do indexes affect PostgreSQL read performance?", "postgres-index", "paraphrase"),
    ("What confirms a Celery message was processed?", "celery-acks", "paraphrase"),
    ("What Python syntax is used for async FastAPI handlers?", "fastapi-async", "paraphrase"),
    ("What validates FastAPI query parameters?", "fastapi", "paraphrase"),
    ("What happens when a Celery task calls retry?", "celery", "paraphrase"),
    ("What is AOF in Redis?", "redis", "exact"),
    ("What property prevents partial transactions?", "postgresql", "paraphrase"),
    ("How can Redis support a Celery deployment?", "celery-redis", "paraphrase"),
    ("How does FastAPI apply route dependencies?", "fastapi-auth", "paraphrase"),
    ("How long can Redis retain a key?", "redis-ttl", "paraphrase"),
    ("Do indexes have a cost during updates?", "postgres-index", "paraphrase"),
    ("What delivery setting affects redelivery after failure?", "celery-acks", "paraphrase"),
    ("Why use async in a FastAPI I/O handler?", "fastapi-async", "paraphrase"),
    ("How do I configure Celery max retries?", "celery", "exact"),
    ("Which Redis persistence mechanism records write operations?", "redis", "exact"),
    ("How do transactions isolate concurrent changes?", "postgresql", "paraphrase"),
    ("Can Redis store results for Celery tasks?", "celery-redis", "exact"),
    ("What mechanism checks a caller before a route runs?", "fastapi-auth", "paraphrase"),
    ("Can Redis automatically delete a key later?", "redis-ttl", "paraphrase"),
    ("Why not index every PostgreSQL column?", "postgres-index", "paraphrase"),
    ("What does late acknowledgement change?", "celery-acks", "paraphrase"),
    ("Can an async endpoint yield while waiting?", "fastapi-async", "paraphrase"),
    ("Which library validates FastAPI models?", "fastapi", "exact"),
]

NOISE_WORDS = ("amber", "birch", "cobalt", "delta", "elm", "fossil", "granite", "harbor",
               "isotope", "juniper", "kiln", "lagoon", "marble", "nectar", "onyx", "prairie",
               "quartz", "raven", "spruce", "topaz", "umber", "velvet", "willow", "xenon",
               "yucca", "zephyr")


def generate(size, seed, output):
    rng = random.Random(seed)
    docs = []
    for i in range(size):
        if i < len(FACTS):
            fact_id, text, category = FACTS[i]
        else:
            fact_id, category = "decoy", "negative"
            words = rng.sample(NOISE_WORDS, 5)
            text = f"Synthetic unrelated note {i}: " + " ".join(words)
        docs.append({"id": f"synthetic-{i:05d}", "text": text, "metadata": {"topic": fact_id, "category": category, "ordinal": i}})
    queries = [{"id": f"q-{i+1:03d}", "query": q, "relevant_ids": [f"synthetic-{next(j for j, fact in enumerate(FACTS) if fact[0] == fid):05d}"], "category": cat, "split": "held_out" if i % 5 == 0 else "evaluation"} for i, (q, fid, cat) in enumerate(QUERIES)]
    rng.shuffle(docs)
    path = Path(output)
    path.mkdir(parents=True, exist_ok=True)
    for name, rows in ((f"corpus-{size}.jsonl", docs), ("queries.jsonl", queries)):
        with (path / name).open("w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, choices=(100, 1000, 10000), required=True)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--output", default="datasets/generated")
    args = parser.parse_args()
    generate(args.size, args.seed, args.output)
