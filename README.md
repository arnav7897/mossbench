# MossBench

MossBench is a reproducible command-line evaluation of Moss retrieval, inference, and Tasks APIs. It compares semantic, keyword, and hybrid search; runs three RAG paths; saves request-level JSONL and summary JSON; and includes bounded Tasks API lifecycle checks.

## Setup

Requires Python 3.11 or newer and a Moss project ID and project key.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/pip install -e .
cp .env.example .env
```

Set `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY` in `.env`. The SDK uses the project key; do not commit `.env`, project credentials, browser state, or raw traces. `MOSS_MODEL` defaults to `moss/fastlane-1`; the Tasks API uses its own accepted model (`moss-fast`).

## Main commands

```bash
# One retrieval-free inference smoke call
.venv/bin/mossbench smoke-inference "Reply with READY."

# Search an existing index
.venv/bin/mossbench search --index mossbench-synth-100 --top-k 5 "How does Celery retry a task?"

# Run the three RAG modes on a labeled query set
.venv/bin/mossbench benchmark-rag \
  --index mossbench-synth-100 \
  --queries datasets/real_docs/queries.jsonl \
  --output-dir results/phase2-real-rag

# Four-call unsupported-answer smoke probe (two prompts × LLM-only/manual RAG)
.venv/bin/mossbench benchmark-abstention \
  --index mossbench-synth-100 \
  --output-dir results/phase2-abstention

# Supported control plus unsupported retrieval probes (read-only)
.venv/bin/python datasets/check_hard_negatives.py

# Temporary contradictory passages plus one manual-RAG inference call; verifies cleanup
.venv/bin/python datasets/check_contradictions.py

# One retrieval-free stream; verifies events, completion, and final text assembly
.venv/bin/python datasets/check_streaming.py

# Matched retrieval-free streamed and non-streamed response comparison
.venv/bin/python datasets/check_stream_equivalence.py

# 10 short inference calls at concurrency 1, 2, and 5; no cache or SDK retries
.venv/bin/python datasets/check_inference_concurrency.py

# One deterministic local function-tool call plus follow-up response
.venv/bin/python datasets/check_function_tool.py

# Equivalent uncached/retrieval-free Responses request through SDK and raw HTTP
.venv/bin/python datasets/check_sdk_vs_http.py

# One JSON Schema-constrained Responses call with local output validation
.venv/bin/python datasets/check_structured_output.py

# Three sequential repeated/unique-prefix requests; records reported cached-token usage
.venv/bin/python datasets/check_cache_usage.py

# Observe process RSS around Moss index load/query/close on Linux
.venv/bin/python datasets/check_retrieval_rss.py

# Retrieval off, explicit existing index, and missing index selection
.venv/bin/python datasets/check_retrieval_selection.py

# One raw request to check X-Moss-Retrieve-Ms
.venv/bin/python datasets/check_retrieval_timing_header.py

# Offline local BM25 scale sweep (no Moss API calls)
for size in 100 1000 10000; do
  .venv/bin/mossbench benchmark-keyword \
    --corpus datasets/generated/corpus-${size}.jsonl \
    --queries datasets/generated/queries.jsonl \
    --output-dir results/phase2-bm25-scale-${size}
done

# Summarize a request JSONL file
.venv/bin/mossbench report results/phase1-inference.jsonl --output results/phase1-inference-summary.json
```

`mossbench --help` lists the current command set. `ask` and `benchmark` are placeholders; use the specific `benchmark-*` commands.

## Reproduce the real-document benchmark

The snapshot contains public pages from FastAPI, Celery, Redis, and PostgreSQL. The fetch script stores source URLs, fetch time, raw-page hashes, extracted-text lengths, and chunk counts in `datasets/real_docs/sources.json`. Full downloaded pages and the indexed corpus are excluded from Git; rerun the script to refresh them. Questions and gold answers are versioned in `queries.jsonl`.

```bash
.venv/bin/python datasets/fetch_real_docs.py
.venv/bin/python datasets/ingest_real_docs.py

.venv/bin/mossbench benchmark-retrieval \
  --index mossbench-synth-100 \
  --queries datasets/real_docs/queries.jsonl \
  --repeats 3 --warmups 1 --alphas 1 0 0.5 0.8 \
  --output-dir results/phase2-real-modes

.venv/bin/mossbench benchmark-keyword \
  --corpus datasets/real_docs/corpus.jsonl \
  --queries datasets/real_docs/queries.jsonl \
  --output-dir results/phase2-real-bm25

.venv/bin/mossbench benchmark-rag \
  --index mossbench-synth-100 \
  --queries datasets/real_docs/queries.jsonl \
  --output-dir results/phase2-real-rag

.venv/bin/python datasets/check_retrieval_contracts.py
```

`ingest_real_docs.py` is deliberately guarded: it writes only to the existing `mossbench-synth-100` index, refuses unexpected document IDs, upserts the versioned real-doc chunks, removes only the known MossBench synthetic/page IDs, and verifies the final chunk set. It does not create or delete indexes.

Chunking is fixed at 1,200 characters with a 200-character overlap. Moss's native metadata filter query runs over the locally loaded index. The four `--alphas` values are `1.0` semantic-only, `0.0` keyword-only, `0.5` hybrid, and `0.8` the documented default hybrid mix.

## Results and evidence

- [`reports/benchmark-report.md`](reports/benchmark-report.md) — retrieval and RAG measurements, answer review, task evidence, findings, and limitations.
- [`reports/one-pager.md`](reports/one-pager.md) — concise hiring review draft.
- [`reports/evidence/`](reports/evidence/) — sanitized aggregate metrics generated from local results by `reports/export_evidence.py`.
- [`findings/phase1.md`](findings/phase1.md) and [`findings/phase4.md`](findings/phase4.md) — integration observations and ranked findings.
- Raw benchmark JSONL and complete task records live under `results/` locally; they are ignored by Git because raw answers and task records can contain account-specific IDs and text. After reproducing a run, regenerate the shareable summaries with `.venv/bin/python reports/export_evidence.py`.

The benchmark report is based on saved measurements. It does not estimate inference dollar cost from token counts. Review the report's sample sizes and unexecuted coverage before generalizing results.

## Current limits

- Authenticated Portal/Playwright smoke findings are in [`findings/phase1.md`](findings/phase1.md); this is not a full usability or accessibility audit.
- No web UI is implemented; the CLI is the minimum product surface.
- The local baseline is standard-library BM25; FAISS/Chroma was not installed or evaluated.
- The real-doc set has 40 answerable questions (32 evaluation, 8 held out), and the held-out sample is small. A separate two-question unsupported-answer smoke probe is documented in the benchmark report; it is too small to estimate general abstention behavior.
- One short 1/2/5 concurrency smoke sweep was run; sustained load and repeat-after-cooldown behavior remain untested. Streaming, function tools, structured output, cache usage, SDK/raw HTTP, and process RSS have separate smoke checks; isolated index memory and multi-index isolation remain untested.
- Retrieval-off and explicit benchmark-index selection completed; a nonexistent index returned 403 permission_error. The service returned `X-Moss-Retrieve-Ms` in one raw response. No empty index or multi-index fixture was created because all three project index slots are occupied.
- Dollar cost for individual inference responses and hosted retrieval provenance were not returned in the saved SDK responses.
- The Moss web-source crawler failed for a bounded FastAPI crawl; the corpus was fetched directly from the official public docs and uploaded as text chunks instead.
