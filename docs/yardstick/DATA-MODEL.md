# Yardstick — Data Model

**Schema version:** 1

## Run artifacts (files, source of truth)

Under `g4a-benchmarks/{cohort}/week-{n}/runs/{run-id}/`:

| File | Purpose |
|------|---------|
| `run.json` | Run metadata |
| `*-trace.json` | Category process traces (UI input) |
| `yardsticks.json` | Cohort yardstick memory |
| `run-state.json` | Aggregated measurement index |
| `verification.json` | Harness verification reasoning |
| `agent-measurements/*.json` | Raw agent outputs |
| `ledger.jsonl` | Append-only event log |

## Week baseline config

`g4a-specs/{cohort}/week-{n}/baseline.json`:

```json
{
  "upstream_repo_url": "https://github.com/.../ship-shape",
  "ref_policy": "first-commit"
}
```

`ref_policy: first-commit` resolves to the root commit SHA of the upstream repo. Cached in SQLite `baselines` + `baseline_measurements`.

## SQLite tables

| Table | Purpose |
|-------|---------|
| `runs` | Indexed runs (cohort, week, run_id, path) |
| `measurements` | Denormalized measurement index |
| `yardstick_versions` | Active + historical yardstick snapshots |
| `yardstick_attempts` | Failed/superseded methods |
| `baselines` | Upstream first-commit SHA per week |
| `baseline_measurements` | Verified baseline metric values |
| `jobs` | Agent measurement jobs |
| `chat_sessions` / `chat_messages` | Local chat history |
| `observability_refs` | trace_id ↔ job/session |

## Trust tiers (ranking)

`claimed` < `reported-math` < `artifact-backed` < `verified`

Verified = harness measured (AST counter, production build, etc.).

## Doubts / revisit if

- Zod schemas may lag prototype JSON evolution — version field on each artifact type.
- `measurements.trust_tier` denormalization may drift from traces — re-sync on every `POST /sync`.
