# Moss Inference internship work sample

## What I built

I built MossBench, a command-line assistant that searches technical documentation and answers questions with source links. I used 618 passages from 18 official FastAPI, Celery, Redis and PostgreSQL pages. For one end-to-end check, I asked for PostgreSQL’s default isolation level. Search found the supporting sentence first, Fastlane answered “Read Committed,” and a separate Moss browser task verified it in the manual. [Code, scripts and results on GitHub](https://github.com/arnav7897/mossbench)

## What I tested and liked

- **Portal.** I connected an index, used keyboard search, sent a Playground prompt and followed it into Logs & Traces. I liked being able to check which model answered, whether retrieval ran and how many tokens the request used, all in one row.
- **Inference API.** I ran 40 documentation questions three ways. Direct answers got 31 right, supplying three passages myself got 30, and hosted retrieval got 32. I liked how little integration the hosted path needed. I also tested invalid requests and streaming recovery. In a separate 150-call multiple-choice comparison with a 64-token cap, Fastlane completed 75/75 correctly. DeepSeek Flash completed 47/75 correctly and marked 28 incomplete.
- **Tasks API.** I tested structured extraction, an unreachable page, duplicate submissions, cancellation, polling after a restart, file downloads and runtime and spend limits. All four structured outputs passed validation. I especially liked that repeating a submission with the same idempotency key returned the original task ID.

## What I’d improve

- **Portal accessibility.** The index picker blocked clicks and stayed open after Escape until I reloaded. I’d make Escape close it and return focus to the button.
- **Answer quality.** Search found the right page in the top ten for all 40 questions, yet both retrieval paths said Celery rate limits apply globally. They apply per worker. I’d expose the exact passage behind each hosted answer.
- **Spend visibility.** A task set to $0.01 stopped with `budget_exceeded` after reporting $0.017258 in model usage. Moss allows in-flight calls to finish and bill. I’d explain that beside the limit and show actual usage alongside it.

## Where I could contribute

I’d start with passage-level debugging. My CLI already prints the retrieved passage IDs and source URLs. I’d bring those into request traces and turn the eight missed hosted answers into regression cases, so the team can see whether a change improved retrieval, the answer, or both.
