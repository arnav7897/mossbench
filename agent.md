# Agent instructions

Use `plan.md` as the source of truth for MossBench scope, test safety, budgets, measurement definitions, and deliverables. If an implementation choice is not specified there, choose the smallest change that keeps measurements reproducible; document material assumptions.

## Required tools and workflows

- **Playwright:** use for portal/browser evaluation only. Keep authentication in an isolated local profile, never commit state or credentials, and sanitize screenshots and traces before saving evidence.
- **Ponytail:** follow the Ponytail skill for code changes: reuse the existing structure, keep changes minimal, and avoid dependencies or abstractions that are not needed.
- **CaveCrew:** use its investigator/builder/reviewer workflow when the task benefits from repository exploration, a focused implementation, or a diff review. Do not delegate routine edits that are clearer inline.
- **Context7:** consult current library documentation before relying on SDK/API signatures or behavior. `plan.md` explicitly requires verifying live API details; never infer undocumented parameters or pricing.

## Benchmark integrity

- Keep live, mocked, and local-only measurements distinguishable. Never invent results or fill missing measurements with estimates.
- Record run configuration, dataset identity, versions, sample counts, warmup policy, timestamps, outcomes, errors, and costs when available. Use monotonic clocks for durations.
- Keep failures and skips visible with separate denominators. Treat polling-derived task transition times as intervals, not exact timestamps.
- Use public or synthetic data, bounded workloads, and the budget gates in `plan.md`. Do not exceed the approval threshold or expose secrets in logs, evidence, or Git.
- Reports must be reproducible from saved measurements and must state unknowns and limitations.
