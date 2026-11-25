# Phase 4 findings and disposition

These findings separate confirmed local integration bugs from measured answer-quality issues, observed service failures, and unavailable telemetry. Severity describes likely user impact if the behavior occurs in a production application; confidence describes the evidence in this benchmark only.

## F1: RAG context misses relevant answer passages and hosted provenance is absent

- **Priority:** High
- **Classification:** Confirmed benchmark quality issue; hosted provenance is an observability limitation
- **Confidence:** High for the recorded questions; low for generalization
- **Expected:** A question retrieves a passage that contains its labeled answer; hosted RAG records enough source metadata to inspect the evidence used.
- **Observed:** All questions found their labeled parent page by top 10 in the default hybrid search, but top-three context missed several answer sections. Manual RAG scored 30/40, hosted RAG 32/40, and LLM-only 31/40. Hosted response records did not expose passages/citations or retrieval provenance.
- **Impact:** A page-level retrieval hit can still leave the model without the answer passage; without provenance, a hosted answer cannot be checked against its source.
- **Reproduction:** Run the three-mode real-doc command in [`README.md`](../README.md), then inspect the incorrect question IDs and mode scores in [`reports/evidence/phase2-real-rag.json`](../reports/evidence/phase2-real-rag.json). Complete raw outputs remain in the local ignored `results/phase2-real-rag/rag.jsonl`.
- **Proposed action:** Return/log retrieved passage IDs and snippets for hosted RAG; evaluate answer passage Recall@K separately from parent-page Recall@K; consider a configurable context depth. No provider-side fix is claimed.

## F2: Celery rate-limit scope was answered incorrectly by both RAG modes

- **Priority:** High
- **Classification:** Confirmed answer-quality failure in this run
- **Confidence:** High for the question and source snapshot
- **Expected:** Explain that Celery's task rate limit applies per worker instance, not globally across a cluster by default.
- **Observed:** Manual RAG and hosted RAG both stated that limits are global by default for `rd-017`. The LLM-only answer was correct.
- **Impact:** A user could under- or over-throttle production work after receiving a confidently wrong configuration explanation.
- **Reproduction:** `rd-017` is listed as incorrect in both RAG modes in [`reports/evidence/phase2-real-rag.json`](../reports/evidence/phase2-real-rag.json); the source page URL is in [`datasets/real_docs/sources.json`](../datasets/real_docs/sources.json).
- **Proposed action:** Test configuration scope with minimal examples and expose the exact source passage used. This is not evidence of an API defect.

## F3: One bounded Moss web-source crawl failed

- **Priority:** Medium
- **Classification:** Observed service failure / cause unconfirmed
- **Confidence:** Medium that the failure occurred; low on cause
- **Expected:** A one-page crawl of an official public documentation URL completes or returns an actionable cause.
- **Observed:** `create_web_source` accepted a single-page FastAPI source, then ended with `CRAWL_FAILED`. A direct HTTPS fetch of the same page returned 200 and the official documentation text could be uploaded through the SDK. The source was `77213891-a42d-48be-a7e3-fa762f979bb3` on `mossbench-synth-100`.
- **Impact:** Web-source ingestion could not be used for this corpus run; the benchmark used a locally fetched, hashed snapshot instead.
- **Reproduction:** The failed source remains visible through `MossClient.list_web_sources("mossbench-synth-100")`; one attempt only. The creation arguments were a single URL, `max_pages=1`, `max_documents=1`, `max_depth=0`, `respect_robots=True`, and `parse_documents=True`.
- **Proposed action:** Return crawl-stage diagnostics (robots, fetch, parse, index) and retry the same bounded request to establish reproducibility before calling this a product bug.

## F4: The retrieval adapter previously reported success without awaiting index creation

- **Priority:** High (fixed)
- **Classification:** Confirmed client integration bug, fixed locally
- **Confidence:** High
- **Expected:** The CLI reports index readiness only after the async SDK mutation has completed.
- **Observed:** The original adapter invoked async `create_index` and `close` without awaiting them, so it printed a success message while Python emitted “coroutine was never awaited” warnings. The adapter now awaits these methods; the corrected index mutations completed and the real-doc index was verified at 618 chunks.
- **Impact:** The old command gave false-positive setup status and left no usable index.
- **Evidence:** Historical details and the correction are in [`findings/phase1.md`](phase1.md), under the fixed adapter finding. Current ingestion implementation: [`retrieval.py`](../mossbench/clients/retrieval.py) and [`ingest_real_docs.py`](../datasets/ingest_real_docs.py).
- **Disposition:** Fixed in the client; no provider-side change is needed.

## F6: Reject unsupported Tasks runtime limits before sending a request

- **Priority:** Medium
- **Classification:** Client-side validation improvement, implemented
- **Confidence:** High; the API error reported the accepted range
- **Expected:** Invalid runtime limits fail locally with an actionable range before a request is sent.
- **Observed:** The API rejected 30 seconds and reported a supported range of 60–7,200 seconds. The CLI previously checked only the lower bound.
- **Change:** Both the CLI and `TasksClient.submit` now require an integer in the 60–7,200 range. Both also reject nonnumeric, boolean, zero, negative, and over-$0.25 `max_cost_usd` caps before submission.
- **Reproduction:** `mossbench research submit --goal x --url https://docs.python.org/3/ --max-runtime 30` and the same command with `--max-runtime 7201` both exit before network submission with `runtime must be 60-7200 seconds`.
- **Disposition:** Fixed locally; server behavior is unchanged.

## F5: Inference response usage does not provide per-call dollar cost

- **Priority:** Medium
- **Classification:** Product telemetry limitation / unknown
- **Confidence:** High that the saved SDK usage object exposed tokens but no dollar charge in these responses
- **Expected:** A benchmark can report the actual price for each response, or a documented authoritative billing lookup.
- **Observed:** Input/output token usage was available; the response object did not include dollar cost. No dollar value is extrapolated from token counts. Tasks expose model usage cost, but that is not necessarily total browser/task billing.
- **Impact:** Cost per answer and total request cost cannot be derived from these logs.
- **Evidence:** [`reports/evidence/phase2-real-rag.json`](../reports/evidence/phase2-real-rag.json) records dollar cost as unknown; [`reports/evidence/phase3-task-evidence.json`](../reports/evidence/phase3-task-evidence.json) distinguishes model usage from total browser/task billing.
- **Proposed action:** Return an authoritative per-response charge or a stable billing usage identifier with documented reconciliation semantics.

## Other evidence and untested coverage

- Tasks smoke/recovery cases completed with honest unreachable-URL failure, schema checks, cancellation, same-ID resume, artifact checksum, model-cost limit, duplicate idempotency key, and a cancel/poll race. The runs are small single observations; see the linked Phase 3 review files in [`reports/benchmark-report.md`](../reports/benchmark-report.md).
- Authenticated Portal UI smoke observations and ranked findings are recorded in [`findings/phase1.md`](../findings/phase1.md), with sanitized metrics in [`reports/evidence/phase1-portal-smoke.json`](../reports/evidence/phase1-portal-smoke.json). This is not a complete usability or accessibility audit.
- A two-question unsupported-answer probe produced four abstaining answers across LLM-only and manual RAG; this is a smoke observation, not a general abstention rate.
- Local BM25 ran against 100, 1,000, and 10,000 synthetic documents using the same 50 queries; recall stayed constant and p50 rose from 0.330 ms to 38.810 ms. All added documents were unrelated decoys, so this does not measure contradictory-document behavior or Moss cloud scaling.
- A supported retrieval control ranked its page first; three unsupported technical questions nevertheless returned plausible topic pages, including an unrelated Celery page for an exact Redis-timeout question. This is a retrieval false-positive smoke observation; scores are not calibrated and no answer-generation failure is inferred.
- One temporary contradiction fixture retrieved both conflicting passages, and manual RAG explicitly reported both claims rather than choosing one. Cleanup was verified. This is one controlled observation, not a contradiction-handling rate.
- One retrieval-free stream reached `response.completed`, and concatenated text deltas matched the final response text. A separate matched stream/non-stream pair returned identical text (129 input, 4 output tokens each); observed latencies were 445.684 ms non-stream and 141.007 ms stream, only one pair. Early disconnect and stream error behavior remain untested. Reproduce with `.venv/bin/python datasets/check_stream_equivalence.py`; sanitized evidence is in [`reports/evidence/phase2-stream-equivalence.json`](../reports/evidence/phase2-stream-equivalence.json).
- A single 1/2/5 concurrency sweep (10 calls per level, no retries) produced 10/10, 8/10, and 1/10 successes. All 11 failures were HTTP 429 `rate_limit_exceeded`; because levels ran back-to-back, this is not a stable quota estimate.
- One forced local `order_lookup` function call completed the tool round trip and the answer reflected the fixture result. Invalid tool arguments and tool failure paths remain untested.
- One equivalent raw HTTP/SDK pair matched response text and token usage (127 input, 3 output); raw HTTP was faster in this one sequential pair. This is not a stable client-overhead estimate.
- One Responses JSON Schema smoke call returned valid JSON with the required fields and types. Nested/complex schema behavior remains untested.
- In a three-call cache probe, the identical second request reported 0 input and 0 cached tokens with lower latency; the unique-prefix call reported 144 input and 0 cached tokens. The usage fields do not establish whether a response-cache or prompt-cache hit occurred.
- One Linux process RSS reading rose by 157,580 KiB after loading the 618-chunk index and remained 34,012 KiB above baseline after client close. RSS includes process/runtime state and is not isolated index memory.
- Retrieval-off and explicit benchmark-index inference both completed; a nonexistent index selection returned 403 `permission_error`, which does not distinguish absence from access control. No index was changed.
- One raw hosted-retrieval response included `X-Moss-Retrieve-Ms: 14.4`; this confirms presence in one response, not header stability or timing accuracy.
- The expanded offline suite has 12 passing tests, including mocked 429 retry/no-retry, truncated-stream errors, same-ID task resume/polling, ledger upsert, metrics, and Tasks limit validators.
- Multi-index isolation and isolated index memory remain untested. The listed streaming, tool, structured-output, cache, SDK/raw HTTP, concurrency, unsupported-answer, contradiction, and RSS checks are smoke observations; their broader failure, repeatability, and scale coverage remains incomplete.
- Context7 was unavailable in this session; API behavior was checked against the installed SDK and official Moss documentation. A CaveCrew reviewer reviewed the Phase 4 findings and flagged the need to label throughput as aggregate; the report now does so.
