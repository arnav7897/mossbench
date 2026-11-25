# Trying Moss Inference

I tested Moss as a developer would: set up a project, explored the Portal, searched an indexed support corpus, sent an inference request, and ran a bounded browser task. The code, sanitized evidence, and fuller findings are in the [MossBench repository](https://github.com/arnav7897/mossbench).

## Portal

The Portal is easy to orient in. Build, observe, and account-management areas are separated clearly. I liked having Python, TypeScript, and cURL setup examples beside model discovery, Playground, indexes, tasks, logs, and usage. The task form exposes runtime and spend limits, and task details show output and execution steps. Billing makes plan limits and current balance visible.

I would make the active model and index scope more obvious: Models marked `moss/fastlane-1` as the default while Playground used `deepseek/deepseek-v4.1-flash`, and retrieval selected all project indexes. I also saw aborted empty response requests while revisiting the Playground/index picker; users should know that changing controls will not start inference or incur charges. The index picker did not close with Escape in my test. The visual design is consistent, but keyboard accessibility needs more work and a full screen-reader/contrast audit is still needed. I could not create another index because the project was at its three-index limit; create/upload/crawl paths led to plan comparison.

## Inference API

My exact-response request returned the expected text and appeared in Logs & Traces. Playground showed 941 ms first token and 950 ms total; the log showed 864 ms and 877 ms for the same request, with one retrieval. The trace exposes model, tokens, timing, status, and retrieval count, which is valuable when debugging. The 30-day dashboard showed 683 requests and 100% success, but those are account-wide totals, not my benchmark. I would align or explain Playground and log timing, clarify default-model selection, and show retrieval scope per request. One smoke request cannot establish latency or reliability; a repeated model comparison is still needed.

## Tasks API

I submitted a task to open the Python documentation home page and return its title, with a one-minute runtime and $0.05 spend limit. It completed in 22 seconds, used 3 steps, returned the correct title, and showed spend exactly at the $0.05 cap. I liked that the form accepts limits and the detail view shows steps, result, duration, and spend. In prior task history, an unreachable `example.invalid` page was labeled “Succeeded” even though details said it could not be reached. Separate task execution completion from whether the requested goal was achieved. I have not tested races, duplicate submissions, cancellation enforcement, or spend overshoot, so I cannot make claims about those behaviors.

The account owner also reported that a password-reset link can be reused after a successful password change within its one-hour lifetime. I have not independently reproduced it; Moss should verify this with a controlled account and invalidate each reset token after first use.

*Supporting details and sanitized results: [`findings/`](../findings/) and [`reports/evidence/`](evidence/).*
