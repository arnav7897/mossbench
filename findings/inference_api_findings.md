# Phase 2 · Search, grounded answers and the Inference API

## What I tested

I compared direct answers, manually supplied passages, and Moss-hosted retrieval on Fastlane 1. The synthetic run used 50 questions in each mode (150 calls). The official-doc run used 40 questions in each mode (120 calls) across 618 passages from 18 FastAPI, Celery, Redis and PostgreSQL pages.

## What went well

| Check | Expected outcome | Observed outcome |
|---|---|---|
| Search official documentation | Find the labeled source page | Default hybrid search found it in the top ten for all 40 questions. Over 120 timed queries, median latency was 9.2 ms and p95 was 11.7 ms. |
| Answer from official documentation | Answer the labeled fact accurately | Direct answers scored 31/40, manual retrieval 30/40 and hosted retrieval 32/40. Median request times were 552, 591 and 622 ms respectively. |
| Authentication and input errors | Distinguish credentials from a bad request | Missing and dummy credentials returned 401. Malformed JSON, an unknown model and an unsupported field returned 400 with distinct codes. |
| Recover after a client disconnect | Complete a fresh request after closing the first stream | The client closed after one text delta. A separate request returned the expected answer in 690 ms. Server-side stop time and charges were unavailable. |
| Retry a temporary failure | Retry a 429 when enabled and surface it when retries are disabled | The SDK passed both cases with an injected 429. The separate live concurrency sweep saw 11 actual 429s across 30 attempts with retries disabled. |

Hosted retrieval got 49/49 supported synthetic facts right. The official-doc run exposed a harder problem. Both retrieval modes said Celery task rate limits were global by default. The documented scope is per worker instance. Finding the right page still left room for the wrong answer.

### Paired model comparison

I sampled 25 questions from the official-doc set with seed 42, supplied four same-topic answer choices, and repeated each question three times per model. Both models received identical prompts with retrieval, caching and retries disabled. Calls were sequential, model order alternated, and the output limit was 64 tokens. Scores count a completed response containing the correct letter.

| Model | Attempts | Completed and correct | Incomplete | Median / p95 latency of completed responses |
|---|---:|---:|---:|---:|
| Fastlane 1 | 75 | 75 | 0 | 161 / 537 ms |
| DeepSeek V4.1 Flash | 75 | 47 | 28 | 907 / 1,884 ms |

Four incomplete responses still contained the correct letter. A client checking only the text would have accepted them. Latency covers successful completions for each model, and the questions repeat across trials. This measures answer selection under a short output limit. The free-response results above measure a different skill.

[All 150 observations](../reports/evidence/model-comparison.json) · [Comparison script](../datasets/compare_models.py)

## Recommendations

Expose the passages that support a hosted answer, including their source links. Include a billing reference that a developer can reconcile with usage. The measured calls supplied token counts. Their individual dollar charges remain unknown.

## How I’d fix it

I’d attach passage IDs to each response and add the Celery question to a regression set scored on both the quoted passage and the answer. For streaming, I’d expose a final request state so a client can tell what happened after a disconnect.

[Real-document answer scores](../reports/evidence/phase2-real-rag.json) · [Live API contracts](../reports/evidence/inference-contracts.json) · [Concurrency results](../reports/evidence/phase2-inference-concurrency.json) · [Retry tests](../tests/test_retry_resume.py)
