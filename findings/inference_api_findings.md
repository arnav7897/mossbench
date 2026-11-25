# Moss Inference API review

## What was exercised

- Sent an exact-response Playground request with project retrieval enabled and all indexes selected.
- Confirmed a successful streamed response (HTTP 200, `text/event-stream`) and matching result in Logs & Traces.
- Inspected model, retrieval count, token counts, first-token and total latency in Playground and the request log.
- Ran a Moss SDK search over the synthetic Celery corpus to inspect passages and ranking.

## Results and product feedback

- The exact-response prompt returned `PORTAL_SMOKE_OK`. Playground showed retrieval at 8 ms, first token at 941 ms, total at 950 ms, 720 input tokens and 32 output tokens. The corresponding log showed 864 ms first token, 877 ms total, 720 input and 32 output, with one retrieval. This one-run UI/log timing gap is a consistency check, not a statistically meaningful latency benchmark.
- Request logs expose useful trace details: model, status, timing, token counts, and retrieval count.
- Models listed `moss/fastlane-1` as Default while Playground used `deepseek/deepseek-v4.1-flash`. Make selection/default behavior explicit.
- Repeated Playground/index-picker visits emitted empty response POSTs that were aborted and did not appear as completed requests in Logs & Traces. Investigate whether the UI starts inference before explicit submit and make billing/logging outcomes unambiguous.
- Synthetic search returned near-duplicate Celery passages with identical 1.0000 scores. This is a limitation of the current test fixture; it does not establish a production retrieval defect. A useful comparison needs diverse real documentation, labeled relevant passages, paraphrases, hard negatives, and Recall@K/MRR.

## Account-level context

At the time reviewed, Analytics showed 683 inference requests, 100% success, $0.34 inference spend, 46 ms first-token metric, and 489 ms p50 / 1,376 ms p95 end-to-end latency for the displayed 30-day range. These aggregates include prior project activity. Usage separately showed 2,106 text queries and 198 retrievals; these are distinct metrics, not results of the single controlled request.

## Still needed

This is a smoke review, not the planned 150-call model comparison. Missing/invalid auth, malformed payloads, unsupported parameters, model errors, streaming disconnect behavior, retries, and repeated latency samples remain untested. Do not claim cost per individual inference call from dashboard aggregates.
