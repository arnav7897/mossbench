"""Fetch and normalize a small, versioned corpus from official documentation sites."""

import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent / "real_docs"
RAW = ROOT / "raw"
CORPUS = ROOT / "corpus.jsonl"
MANIFEST = ROOT / "sources.json"
USER_AGENT = "MossBench public documentation benchmark (local research project)"
MAX_BYTES = 4_000_000
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200

SOURCES = [
    ("fastapi-body", "fastapi", "https://fastapi.tiangolo.com/tutorial/body/"),
    ("fastapi-query-params", "fastapi", "https://fastapi.tiangolo.com/tutorial/query-params/"),
    ("fastapi-path-params", "fastapi", "https://fastapi.tiangolo.com/tutorial/path-params/"),
    ("fastapi-response-model", "fastapi", "https://fastapi.tiangolo.com/tutorial/response-model/"),
    ("fastapi-dependencies", "fastapi", "https://fastapi.tiangolo.com/tutorial/dependencies/"),
    ("fastapi-sub-dependencies", "fastapi", "https://fastapi.tiangolo.com/tutorial/dependencies/sub-dependencies/"),
    ("celery-tasks", "celery", "https://docs.celeryq.dev/en/stable/userguide/tasks.html"),
    ("celery-calling", "celery", "https://docs.celeryq.dev/en/stable/userguide/calling.html"),
    ("celery-workers", "celery", "https://docs.celeryq.dev/en/stable/userguide/workers.html"),
    ("redis-strings", "redis", "https://redis.io/docs/latest/develop/data-types/strings/"),
    ("redis-xadd", "redis", "https://redis.io/docs/latest/commands/xadd/"),
    ("redis-xreadgroup", "redis", "https://redis.io/docs/latest/commands/xreadgroup/"),
    ("postgres-transactions", "postgresql", "https://www.postgresql.org/docs/current/tutorial-transactions.html"),
    ("postgres-constraints", "postgresql", "https://www.postgresql.org/docs/current/ddl-constraints.html"),
    ("postgres-insert", "postgresql", "https://www.postgresql.org/docs/current/sql-insert.html"),
    ("postgres-isolation", "postgresql", "https://www.postgresql.org/docs/current/transaction-iso.html"),
    ("postgres-mvcc", "postgresql", "https://www.postgresql.org/docs/current/mvcc-intro.html"),
    ("postgres-vacuuming", "postgresql", "https://www.postgresql.org/docs/current/routine-vacuuming.html"),
]

SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "header", "aside"}


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts = []
        self.parts = []
        self.in_title = False
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.in_title = True
        if tag in SKIP_TAGS:
            self.skip_depth += 1
        if tag in {"p", "div", "section", "article", "main", "li", "pre", "tr", "h1", "h2", "h3", "h4", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
        if tag in {"p", "div", "section", "article", "main", "li", "pre", "tr", "h1", "h2", "h3", "h4", "br"}:
            self.parts.append("\n")

    def handle_data(self, data):
        value = " ".join(data.split())
        if not value:
            return
        if self.in_title:
            self.title_parts.append(value)
        if not self.skip_depth:
            self.parts.append(value)


def normalize_html(html):
    parser = TextExtractor()
    parser.feed(html)
    text = "\n".join(part.strip() for part in parser.parts if part.strip())
    text = re.sub(r"\n{3,}", "\n\n", text)
    return " ".join(parser.title_parts).strip(), text.strip()


def fetch(source_id, topic, url):
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urlopen(request, timeout=30) as response:
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError(f"source exceeds {MAX_BYTES} byte safety limit: {url}")
        final_url = response.url
        content_type = response.headers.get_content_type()
    if content_type not in {"text/html", "application/xhtml+xml"}:
        raise ValueError(f"unexpected content type {content_type}: {url}")
    html = raw.decode("utf-8", errors="replace")
    title, text = normalize_html(html)
    if len(text) < 500:
        raise ValueError(f"extracted text too short ({len(text)} chars): {url}")
    return {
        "id": source_id,
        "topic": topic,
        "url": final_url,
        "requested_url": url,
        "title": title,
        "text": text,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "raw_bytes": len(raw),
        "text_chars": len(text),
    }, raw


def chunk_text(text):
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            boundary = text.rfind("\n", start + CHUNK_SIZE // 2, end)
            if boundary > start:
                end = boundary
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)
    return [chunk for chunk in chunks if chunk]


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).isoformat()
    documents, manifest = [], []
    for source_id, topic, url in SOURCES:
        record, raw = fetch(source_id, topic, url)
        (RAW / f"{source_id}.html").write_bytes(raw)
        page_text = f"{record['title']}\n\nSource: {record['url']}\n\n{record['text']}"
        chunks = chunk_text(page_text)
        for number, chunk in enumerate(chunks):
            documents.append({
                "id": f"{source_id}#chunk-{number:03d}",
                "text": chunk,
                "metadata": {
                    "parentId": source_id,
                    "topic": topic,
                    "source_url": record["url"],
                    "source_title": record["title"],
                    "source_sha256": record["raw_sha256"],
                    "fetched_at_utc": fetched_at,
                },
            })
        record["chunk_count"] = len(chunks)
        manifest.append({key: value for key, value in record.items() if key != "text"} | {"fetched_at_utc": fetched_at})
        print(f"{source_id}: {record['title']} ({record['text_chars']} chars; {record['chunk_count']} chunks)")
    corpus_payload = "".join(json.dumps(doc, ensure_ascii=False) + "\n" for doc in documents)
    CORPUS.write_text(corpus_payload, encoding="utf-8")
    query_bytes = (ROOT / "queries.jsonl").read_bytes()
    MANIFEST.write_text(json.dumps({
        "dataset": "MossBench official technical documentation snapshot",
        "fetched_at_utc": fetched_at,
        "source_count": len(manifest),
        "parent_page_count": len(manifest),
        "chunk_size_chars": CHUNK_SIZE,
        "chunk_overlap_chars": CHUNK_OVERLAP,
        "document_count": len(documents),
        "corpus_sha256": hashlib.sha256(corpus_payload.encode()).hexdigest(),
        "query_dataset": "queries.jsonl",
        "query_count": sum(1 for line in query_bytes.splitlines() if line.strip()),
        "query_sha256": hashlib.sha256(query_bytes).hexdigest(),
        "sources": manifest,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {CORPUS} with {len(documents)} documents")


if __name__ == "__main__":
    main()
