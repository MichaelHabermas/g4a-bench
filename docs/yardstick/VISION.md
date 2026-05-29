# Yardstick — Vision

**Status:** living doc (v0.1) — update as we learn, do not treat as frozen spec.

Yardstick is the measurement platform for G4A weekly challenger benchmarks. It reads week specs, clones repos, runs an adversarial measurement agent, verifies claims, ranks within a cohort, and surfaces evidence — not just a winner.

## What Yardstick is

- A **measurement compiler** per week: specs + repos → plan → evaluate → auditable bundle.
- **Trust-gated ranking:** verified harness numbers outrank self-report.
- **Cohort yardstick memory:** the first good method for a criterion is cached; later repos replay it; better methods can supersede with full history visible.
- **Baseline policy:** for change metrics, the debate line is the **upstream repo's first commit** (same starting point for every team). Team markdown baselines are cross-check evidence only.

## What Yardstick is not

- A universal rubric across all weeks.
- A trust in team self-reported numbers without verification.
- A chatbot that reads cloned repo source in production (chat uses run artifacts and DB index only). In **dev mode** (`YARDSTICK_DEV_MODE=true`), chat may include clone snippets and ripgrep hits to explain coverage gaps.
- A hosted multi-tenant product (v1 is local-only).

## One UI entry point

- **Yardstick** at `/` lists runs; opening a run lands on **Overview** with a persistent sidebar (Scorecard, Compare, **Decision Trail**, Workbench, Run plan).
- Deep links are normal routes under the same shell — not separate apps or orphan HTML files.

## Decision Trail

- Append-only `decision-log.jsonl` per run records clone, verify, sync, agent, yardstick, and orchestrator choices (why, evidence, confidence).
- **Decision Trail** in the run sidebar is the human-readable view; dev chat can focus on a specific `decision_id`.

## Adversarial stance

- Verification beats self-report.
- The agent may say **"I don't know"** — never invent numbers.
- Every measured value traces to a command or is labeled **judgment**.
- When data is missing, UI shows the gap; we do not borrow the team's baseline.

## Doubts / revisit if

- Week specs may not always define a clean upstream repo URL — baseline resolver may need per-cohort overrides.
- Auto-promote yardsticks may adopt a worse method if confidence heuristics are too loose — tighten promotion gates if we see regressions.
- Hybrid Python agent bridge may linger longer than planned — revisit TS port priority after Week 4 is stable.
