# MossBench — RAG Knowledge & Research Assistant

> Moss hiring work sample: Portal, Inference API, Tasks API, plus retrieval SDK evaluation.

## Problem statement
Moss provides low-latency semantic retrieval, hosted LLM inference and asynchronous browser-agent execution. Evaluate whether these capabilities are fast, accurate, reliable, predictable in cost and easy to integrate into production applications. Build real applications, benchmark them against controlled baselines, reproduce meaningful issues and propose actionable improvements. Cover the Portal, Inference API and Tasks API required by the hiring assignment.

## Project we are building
MossBench is a RAG-powered technical knowledge and research assistant with an integrated performance evaluation framework. Users can index technical documents, search them, ask grounded questions, and delegate multi-step web research to agents that return structured results. The application compares Moss against conventional retrieval pipelines and exposes measured performance, accuracy, reliability and cost.

### Application features and user journey
- **Knowledge ingestion:** import Markdown/text documentation for FastAPI, Celery, Redis and PostgreSQL, plus a controlled synthetic corpus with known answers.
- **Semantic search:** enter natural-language queries; show ranked passages, document IDs, metadata, search mode and measured latency.
- **RAG chat:** ask technical questions, select the retrieval pipeline, stream answers, inspect retrieved passages and source citations where available.
- **Research agent:** submit a research question, observe task status, cancel if needed, inspect structured results, sources, artifacts and costs.
- **Evaluation console:** run reproducible suites, compare configurations and display latency distributions, accuracy, failures and cost from saved results.
- Example: ask how to implement reliable Celery retries with Redis and persistent state; retrieve documentation, generate a grounded answer, then optionally delegate further research.
- Keep research outputs separate from the trusted document index; only ingest them after source verification and explicit selection.

### Architecture and scope
```text
CLI / thin web demo (optional FastAPI + Streamlit)
  |-- Search service --> Moss retrieval SDK / local FAISS or Chroma baseline
  |-- RAG service ----> Moss Inference (direct / manual RAG / hosted retrieval)
  |-- Research agent -> Moss Tasks API --> polling / validated results / artifacts
  +-- Evaluation -----> common timing + metrics + JSONL/CSV + reports
                         SQLite task state and budget ledger
```
- A working CLI is the minimum product; add a simple UI only after core tests pass.
- The retrieval SDK, Inference API and Tasks API are separate integration surfaces; a task does not require a RAG index.
- Prefer one shared corpus, model configuration and benchmark harness over several disconnected demo projects.
- Deliver actual runnable software, not merely a collection of API examples or an elaborate dashboard.

## Stack and integration decisions
- Python 3.11+, Moss Python SDK (`moss`; verify installed version/package), OpenAI Python SDK, HTTPX, asyncio, pytest, jsonschema, psutil, NumPy, FAISS or ChromaDB; Playwright for portal.
- FastAPI/Streamlit only if a thin demo adds value; prioritize measurements and reproducibility.
- Obtain project credentials via the assigned portal; no manual web indexing is expected. Verify project/index permissions during smoke tests.
- Create persistent cloud indexes with the SDK for hosted RAG; use loaded indexes/local sessions for in-process retrieval. Push/sync local data before hosted retrieval where required.
- Basic inference and Tasks API do not require an index. Explicitly disable retrieval for the no-RAG baseline using the documented control.
- Prefer native SDK for supported methods, OpenAI SDK for interoperability, HTTPX for Tasks and raw protocol/header tests; verify Tasks SDK coverage before choosing its adapter.
- Discover actual endpoint paths, request fields, supported models, SDK versions and limits from current docs; do not invent parameters.
- Put all provider-specific methods behind small adapters; keep business logic and benchmark instrumentation independent of transport.
- Pin dependencies and store experiment configuration (model, index, top-k, seed, concurrency and budget) outside source code.

## Phase 1 — Foundation, portal and baseline API contracts
**Objective:** establish a working authenticated integration and trustworthy measurement infrastructure.
### Implement
- Sign up using the exact hiring link; manually authenticate in an isolated Playwright browser profile.
- Initialize Git, Python environment, dependency lock, `.env.example`, `.gitignore` and configuration loader.
- Implement reusable clients for retrieval SDK, inference SDK/OpenAI-compatible client and Tasks REST API.
- Implement a shared timed request logger: run ID, test ID, UTC timestamp, model, configuration, status, request ID if exposed, latency, usage, error and cost.
- Implement CLI commands for ingest, search, ask, research, benchmark and report; command names are project conventions, not Moss API methods.
- Add a local SQLite budget/task ledger and record spend or pending charges before executing paid suites.
- Build a small synthetic support knowledge base with unique IDs, source text, metadata and known answers; include confusing near-matches and absent answers.
- Generate reproducible corpora at 100/1,000/10,000 chunks as supported and affordable; seed all generators. Prepare 40–60 labeled queries including paraphrases, exact terms and filtered questions.
- Document setup commands and execute one low-cost inference call without an index, one SDK indexing/search smoke test and one bounded browser task.
### Test
- Portal: onboarding, key creation, project selection, navigation, quickstart copy/paste, index build progress, playground, task history, billing, empty/error/loading states and keyboard navigation.
- Capture sanitized screenshots, console errors, failed network requests and exact repro steps; avoid capturing secrets or auth state.
- API: valid/missing/invalid auth, invalid model, malformed body, unsupported parameters, missing index/task ID and response/error consistency; use own account only.
- Verify SDK install/import, index creation readiness and discovery, model discovery where supported, and one complete task lifecycle.
- Test key handling without displaying secrets; use fake invalid credentials and non-destructive validation requests.
- Verify documented request/response examples against actual responses; record documentation mismatches.
### Metrics / exit criteria
- Time to first successful call, onboarding steps, SDK setup friction, HTTP status/error-code consistency and portal network/console failures.
- Record baseline balance, environment and versions. Exit with three working smoke tests or explicitly documented blockers, baseline logs and initial portal findings.

## Phase 2 — Semantic search, RAG and Inference API evaluation
**Objective:** measure local retrieval and hosted inference separately, then evaluate end-to-end application behavior.
### Implement: retrieval engine
- Use Moss SDK for cloud index creation, local load, search, metadata filters, upsert/delete on dedicated test indexes and local sessions where supported.
- Compare vector, keyword and hybrid retrieval at top-k 1/5/10; test exact-term vs paraphrase and hard-negative queries.
- Implement a FAISS or Chroma baseline with identical chunks and embeddings when supported; otherwise label the comparison as end-to-end systems with different embedding models.
- Separately measure indexing/upload, index load, query embedding, search and full retrieval wherever observable; do not label total query time as vector-only time.
### Test: retrieval
- Scale corpus sizes; run seeded warm query sets (target >=100 measurements/config for key comparisons) and separate cold-load runs.
- Use two dataset families: synthetic labeled facts for repeatable scoring and versioned public technical docs for realistic usage.
- Keep a held-out query set; manually label all relevant passages for Recall@K and the first relevant rank for MRR.
- Test filter correctness, multi-index isolation, updated/deleted document visibility, duplicate IDs, empty queries/results and index persistence/reload.
- Test loaded-index offline search and local session updates; verify the actual network behavior rather than assume offline support for every operation.
- Test exact technical identifiers, error codes, acronyms, synonyms and contradictory documents; report breakdown by query category.
- Measure RSS memory before/after loading and release; test concurrency only where SDK guarantees safe usage.
- Metrics: p50/p95/p99 query latency (p99 exploratory at small n), QPS, Recall@1/5/10, MRR, filter correctness, build/load duration, update-to-visible latency and RSS delta.
### Implement: RAG application
- Expose CLI or minimal API for three modes with a shared question set: (A) LLM-only, (B) local baseline retrieval + Moss inference with explicit context, (C) native hosted Moss retrieval + same model.
- Optional fourth mode: local Moss retrieval + Moss inference, to isolate native retrieval integration from engine choice.
- Provide one command to run the same evaluation queries through all supported RAG modes; record retrieval settings and context lengths.
- Support streaming; expose sources/document IDs where returned and include source text in manual RAG prompts. Require abstention for unanswerable questions.
- Implement a deterministic read-only function tool (e.g., order lookup); execute returned tool calls locally and return results per protocol.
- Use OpenAI SDK for compatible Responses/Chat endpoints and HTTPX for raw response headers/stream checks; exercise Moss SDK directly.
### Test: inference
- Compare answer accuracy, source support, abstention and latency across modes; use exact-match/rule scoring plus manual verification, not only an LLM judge.
- Test automatic retrieval on/off, index selection, missing/empty index, and explicit moss_search tool if supported; distinguish retrieval misses from generation errors.
- Test streaming event order, completion, text assembly, early disconnect, error handling and stream vs non-stream output shape.
- Test structured output against a local JSON Schema validator if the selected inference model/API supports it; record malformed or truncated output.
- Test valid/malformed tool arguments, tool errors, max output limit, unsupported model options, long input near a safe documented limit and multi-turn context.
- Compare repeated prefixes vs unique prefixes; record reported cache usage rather than assume a cache hit.
- Run concurrency 1/2/5 only within documented limits; start small (e.g., 10 requests per level), expand key experiments if credits permit; avoid deliberate rate-limit saturation.
- Compare native SDK vs OpenAI SDK vs raw HTTP on equivalent requests; distinguish client overhead and network/server time.
### Metrics / exit criteria
- TTFT (request start to first nonempty text delta), end-to-end duration, output tokens/sec (if actual token count available), p50/p95, success/error rate, throughput and timeout rate.
- Hosted retrieval timing from documented response metadata/header if available; verify `X-Moss-Retrieve-Ms` support. Do not subtract unrelated timing measurements as if they were exact components.
- Compute throughput as completed successful requests / batch wall-clock duration; report failures separately.
- Input/output/cached tokens, observed cost per answer, supported-answer accuracy, unsupported-claim rate, correct abstention rate and tool-call success.
- Log model/settings, prompt/context length, n, cache state, hardware, region/network, SDK versions and warmup policy. Use identical questions and consistent settings; document differences.
- Exit with runnable search/RAG demos, baseline comparison tables, representative response evidence and reproducible findings.

## Phase 3 — Tasks API research agent and reliability evaluation
**Objective:** evaluate whether asynchronous agents produce correct, verifiable results under normal and failure conditions.
### Implement
- Create a Tasks client using documented API operations for submission, status retrieval, cancellation and artifact download; support SDK equivalents if available.
- Build a research agent that visits a small public documentation site or controlled fixture, follows links, extracts known facts and returns JSON with source URLs; include a file-output task if supported.
- Expose research submit/status/cancel/resume commands; retain the task ID across client restarts and show pending versus final outcomes.
- Create controlled HTML fixtures with known answers, multiple pages, missing fields, broken links and harmless misleading page instructions; use a reachable hosted fixture if cloud browser cannot access localhost.
- Add task ID persistence (SQLite/JSON), polling deadlines/backoff, resume after restart, schema validation, independent fact verification and explicit runtime/model-cost limits.
- Track task creation time, observed state transitions, terminal outcome, raw result, schema outcome, artifact metadata, error details and available billing components.
### Test: functional and failure cases
| ID | Scenario | Expected verification |
|---|---|---|
| T01 | Simple extraction | Correct facts and source URLs |
| T02 | Multi-page navigation | Complete independently verified result |
| T03 | Structured output | Valid JSON and required schema fields |
| T04 | Artifact generation | Downloadable, nonempty, correct file; checksum |
| T05 | Invalid task configuration/ID | Documented error status and actionable message |
| T06 | Missing or unreachable page | Honest failure/partial output, not fabricated facts |
| T07 | Impossible goal/conflicting constraints | Explicit inability; no false success |
| T08 | Short runtime limit | Terminal state and observed enforcement |
| T09 | Small model-cost limit | Model cost vs actual total cost and overshoot |
| T10 | Cancel active task | Terminal state, cancellation delay, charges |
| T11 | Cancel terminal task | Consistent state and documented error/no-op |
| T12 | Restart polling client | Resume using same ID; no duplicate creation |
| T13 | Duplicate submission | Verify documented idempotency behavior with bounded cheap tasks; skip if unsafe/costly |
| T14 | Premature artifact request | Predictable response before task completion |
| T15 | Harmless page instruction conflict | Agent follows user goal; never requests real secrets |
| T16 | Repeat same goal | Compare output consistency, duration and cost |
- Add a cancellation-versus-completion race test if affordable; report observed terminal state and avoid assuming a strict event order from polling.
- Check whether terminal `completed` guarantees schema validity and correct goal completion; independently validate both.
- Record which lifecycle events, progress data, traces, screenshots, webhooks and billing details are available; distinguish absent docs from proven absent functionality.
- Repeat a few representative cheap tasks (target 3 runs per selected scenario if budget allows); do not claim statistical significance from tiny samples.
### Metrics / exit criteria
- Submission latency, observed queue delay/run duration where timestamps exist, end-to-end task duration, polls/task and cancellation latency.
- Record API-reported timestamps separately from client-observed transition times; polling gives intervals, not exact transition times.
- API success rate, terminal completion rate, independently verified goal success, schema pass rate, artifact integrity and recovery success; use separate denominators and show counts.
- Model/browser/network cost where exposed, finalized vs pending cost, cost per verified successful task and limit overshoot; compare model limit against model charges, not total bill.
- Exit with a working agent, task lifecycle logs, measured failure cases and at least one prioritized improvement or documented absence of reproducible bugs.

## Phase 4 — Reproduction, engineering improvements and submission
**Objective:** turn test evidence into actionable product feedback and a reproducible engineering deliverable.
### Implement
- Rank findings by impact, confidence, reproducibility and engineering effort; classify confirmed bug, documented limitation, UX friction, hypothesis or test blocker.
- Reproduce high-impact findings on a minimal script, capture sanitized evidence and distinguish provider issues from client/environment errors.
- Improve the client where warranted: safe read retries, bounded polling, resume by task ID, strict result validation and transparent cost reporting. Do not blindly retry billable POSTs; use idempotency only if supported.
- For each strong finding, write expected vs actual behavior, minimal reproduction, observed frequency, impact, evidence, proposed fix and whether it is client-side or server-side.
- Add a compact Markdown/HTML report with latency distributions, accuracy/cost comparisons, task outcomes and a small reproducible demo.
- Write a README with architecture, installation, commands, expected inputs, configuration, limitations and paths to results. Publish code and sanitized evidence to GitHub.
- Write the required one-page review in the candidate's own words: Portal, Inference API, Tasks API; what worked, what did not, what was tested/broken, observed results and what to improve; link the repository.
### Test
- Unit-test metrics, validators, retry/backoff and task resumption using mocks; keep mock results separate from live results.
- Re-run a clean smoke suite and selected bug reproductions; compare pre/post adapter behavior without claiming provider-side fixes.
- Compare adapter behavior before/after with deterministic fault injection; re-run low-cost live tests where meaningful.
- Validate report calculations, link integrity, dataset reproducibility, README commands and Git history for secrets; verify the public repo contains no credentials or account data.
### Metrics / exit criteria
- Reproduction rate, documented coverage (pass/fail/skip counts), adapter validation/recovery results and evidence completeness.
- Final deliverables: working demos, tests, benchmark CSV/JSON, findings with repro commands, sanitized evidence, README, GitHub link and one-page review. Clearly mark unexecuted tests and unknowns.

## Budget, safety and measurement rules (all phases)
- $10 signup credit; suggested envelopes: $0.50 portal/smoke, $2.50 retrieval/inference, $4 Tasks, $3 reserve. These are caps to aim for, not guaranteed costs.
- Check balance frequently, track pending charges and seek approval before spending beyond $5; never auto-purchase. Runtime/model-cost limits may not cap all task costs.
- Start with cheap, small batches; skip expensive/unsupported cases with reason. No aggressive load, destructive requests, third-party account testing or credential exposure.
- Keep `.env`, browser profiles, auth state and raw traces out of Git. Sanitize headers, IDs where sensitive, screenshots and result text; use public/synthetic data only.
- Use monotonic clocks, consistent percentile method, independent verification, explicit sample counts and versioned configs; report actual results, never invented numbers.

## Repository structure
```text
moss-bench/
├── plan.md                         # This implementation specification
├── README.md                       # Setup, demo, architecture, results
├── pyproject.toml                  # Dependencies and CLI entrypoint
├── .env.example                    # Credential names only
├── .gitignore
├── configs/
│   └── benchmark.yaml              # Seed, models, top-k, limits, budget
├── clients/
│   ├── retrieval.py                # Native Moss retrieval SDK adapter
│   ├── inference.py                # Moss/OpenAI-compatible inference
│   └── tasks.py                    # Tasks transport and lifecycle
├── apps/
│   ├── cli.py                      # Ingest/search/ask/research commands
│   ├── search.py                   # Semantic/hybrid search service
│   ├── rag.py                      # Three comparable RAG pipelines
│   ├── research.py                 # Autonomous research workflow
│   └── dashboard.py                # Optional thin demo
├── core/
│   ├── telemetry.py                # Monotonic clocks and safe logs
│   ├── metrics.py                  # Latency, ranking, accuracy, cost
│   ├── validation.py               # Schema and factual verification
│   └── state.py                    # SQLite task IDs and budget ledger
├── datasets/
│   ├── generate.py                 # Reproducible corpus generation
│   ├── queries.jsonl               # Ground truth and query categories
│   └── fixtures/                   # Controlled HTML and expected results
├── benchmarks/
│   ├── retrieval.py                # Scale, quality, index and memory
│   ├── inference.py                # TTFT, throughput, cache, SDK comparison
│   ├── rag.py                      # Accuracy and pipeline latency
│   └── tasks.py                    # Goal success, lifecycle and costs
├── tests/
│   ├── unit/                       # Offline metrics and client tests
│   ├── retrieval/                  # SDK integration tests
│   ├── inference/                  # Live API and streaming tests
│   ├── tasks/                      # T01–T16 and selected repetitions
│   └── portal/                     # Playwright scripts and setup
├── results/                        # Sanitized JSONL, CSV, run manifests
├── findings/                       # Bug repros, screenshots and fixes
└── reports/
    ├── benchmark-report.md         # Actual experiment comparisons
    └── one-pager.md                # Required hiring submission
```

## Run workflow and evidence format
- `mossbench ingest` → build/sync test indexes and record configuration and readiness.
- `mossbench search` / `mossbench ask` → use the application manually and inspect output.
- `mossbench research` → submit, monitor, validate and retrieve results for a bounded task.
- `mossbench benchmark` → run selected suites with explicit live-test opt-in and budget checks.
- `mossbench report` → generate summaries from saved measurements; never create synthetic results.
- These are proposed CLI commands to implement; add exact working examples to README after testing.
- Every run has a manifest (Git commit, versions, environment, dataset hash, configuration, timestamp and test counts).
- Every finding links to a test ID, sanitized evidence and reproduction command; skipped tests include a reason.

## Official documentation (verify before coding)
- https://portal.usemoss.dev/inference
- https://docs.moss.dev/llms.txt — current documentation map; resolve detailed pages from here.
- https://docs.moss.dev/docs/start/quickstart.md — SDK indexing and search.
- https://docs.moss.dev/docs/reference/python/api.md — retrieval SDK reference.
- https://docs.moss.dev/docs/inference/quickstart.md — inference setup.
- https://docs.moss.dev/docs/inference/sdks/python.md — inference SDK.
- https://docs.moss.dev/docs/inference/retrieval.md — hosted RAG controls.
- https://docs.moss.dev/docs/inference/openai-compatibility.md — interoperability.
- https://docs.moss.dev/docs/inference/tasks.md — task operations.
- https://docs.moss.dev/docs/inference/errors-and-limits.md — error contracts and limits.
- https://docs.moss.dev/docs/inference/pricing.md — usage and billing.
- During execution, exact Moss signatures and limits were checked against the installed SDK and current official documentation. The run records and remaining unknowns are summarized below.

## Recorded execution status (2026-11-25)

- **Phase 1:** inference, retrieval, and Tasks smoke workflows completed. An async retrieval adapter bug and incorrect Tasks output-field handling were fixed; Portal UI checks remain intentionally skipped.
- **Phase 2:** synthetic and official-doc datasets were evaluated. The real-doc snapshot has 18 pages, 618 1,200-character chunks, and 40 questions. Moss semantic, keyword, hybrid, local BM25, and all three RAG modes were measured. Filter, empty query/result, duplicate-ID upsert/delete visibility, and fresh-client reload checks completed. A two-question unsupported-answer smoke probe produced abstentions in LLM-only and manual RAG (four calls total); this is not a general abstention estimate. Offline local BM25 scale sweep completed at 100, 1,000, and 10,000 documents over the same 50 synthetic queries. One supported control and three unsupported read-only retrieval probes were also run; unsupported queries returned plausible candidates and require an answer-support check. One temporary contradictory-passage fixture was surfaced by retrieval and acknowledged by manual RAG; cleanup was verified. One stream reached completion and assembled text matched the final response; a matched stream/non-stream pair returned identical text. One deterministic function-tool round trip succeeded. One matching raw HTTP/SDK pair produced the same text and usage. One JSON Schema-constrained response passed local validation. A three-call cache probe recorded the service-reported usage fields without assuming cache hits. One process RSS sample was collected around loading and closing the 618-chunk index; it does not isolate index memory. Retrieval-off and explicit existing-index calls completed; a nonexistent-index selection returned 403 permission_error. One raw response included X-Moss-Retrieve-Ms. A 1/2/5 inference concurrency sweep (10 calls per level) recorded 11 rate-limit responses above concurrency 1 in this single back-to-back run. Stream disconnect/errors, tool error cases, broader schema conformance, repeated RSS/contradiction measurements, and multi-index isolation remain untested; all three project index slots are occupied, so no empty or second benchmark index was created.
- **Phase 3:** bounded task extraction, cancellation, resume, artifact integrity, runtime/model-cost limit, idempotency, and race observations are recorded. These are small samples, not reliability estimates.
- **Phase 4:** reproducible setup, README, benchmark report, one-page review draft, sanitized public evidence, and ranked findings are in `README.md`, `reports/`, and `findings/phase4.md`. The locked install and editable package install succeeded in a fresh temporary venv; 12 offline metric/retry/resume/validator tests pass; evidence JSON and local Markdown links validate; query/corpus hashes match the manifest. Raw results, full downloaded docs, local credentials, and task identifiers are excluded from Git. Changes are organized into focused local commits.
- **External limitations:** the Portal UI was skipped by instruction; one bounded Moss web-source crawl failed with `CRAWL_FAILED`, so real docs were fetched from official sources and upserted as text; per-call inference dollar cost and hosted retrieval provenance are unavailable in saved responses.
