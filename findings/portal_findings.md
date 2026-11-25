# Phase 1 · Portal and first request

## What I tested

I signed in, connected an existing index, tried the model filters, and sent a Playground prompt. I followed the response into Logs & Traces, checked index events and usage, and ran a browser task with limits. I also tried the command palette and index picker with a keyboard.

## What went well

I could reach Models by typing in the command palette and pressing Enter. Configure put the Python, TypeScript and cURL examples beside the project settings. I could match a Playground answer to its log entry by model, token counts and retrieval count.

## Recommendations

| What I expected | What I observed | Why I’d change it |
|---|---|---|
| Close the index picker and return to the prompt | Outside clicks were intercepted and Escape from the composer left it open. Reload restored access. | This interrupted both pointer and keyboard use. |
| Know why index creation failed | At three occupied slots, upload, sample and crawl took me to plan comparison. Existing search still worked. | Show the occupied slots and a link to manage them at the point of creation. |
| Understand the latency of one request | Playground showed 950 ms total and Logs showed 877 ms. Two empty requests also appeared on repeated Playground visits, with no matching log rows. | Label the timing boundaries and explain when an inference request starts. Billing for the empty requests was unobservable. |

## How I’d fix it

I’d display the selected indexes beside the prompt and return focus to the picker trigger on Escape. Keyboard search worked well enough to use as the pattern. Screen-reader behavior and contrast still need direct measurement. The account owner separately reported being able to reset their password twice with the same link. I’d prioritize internal verification and consume the reset token on the first successful change.

[Portal observations and timings](../reports/evidence/phase1-portal-smoke.json)
