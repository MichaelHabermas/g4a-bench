# Yardstick — Decisions (ADR-lite)

Append-only. Newest at bottom.

---

## 2026-05-29 — Product name: Yardstick

**Decision:** TypeScript platform named Yardstick at repo root monorepo.

**Why:** Captures cohort yardstick memory — the core differentiator.

**Doubts:** Name may confuse with "yardstick" as a single metric definition vs the whole app.

---

## 2026-05-29 — Baseline = upstream first commit

**Decision:** For change/% metrics, baseline is the upstream repo's first commit, not team self-report or counterfactual rebuilds.

**Why:** All teams start from the same place; comparable debate line.

**Doubts:** Upstream URL may be missing for some weeks — show "baseline not configured", never fake.

---

## 2026-05-29 — Files + SQLite

**Decision:** Run artifacts stay as JSON files; SQLite indexes runs, chat, jobs, baselines.

**Why:** Git-auditable bundles + fast UI queries.

---

## 2026-05-29 — Provider-agnostic LLM and observability

**Decision:** `LlmProvider` and `TraceProvider` interfaces; Anthropic + Langfuse first adapters.

**Why:** User will likely move to OpenAI; observability should not be Langfuse-only long term.

---

## 2026-05-29 — Hybrid agent (Python bridge first)

**Decision:** TS orchestrator spawns `g4a-harness/agent_runner.py` before full TS agent port.

**Why:** Proven loop; de-risk UI and sync first.

**Revisit when:** TS tool loop reaches parity on Week 4 cat-1 and cat-2.

---

## 2026-05-29 — Yardstick auto-promote with history

**Decision:** On challenge success + high confidence, auto-promote; superseded methods remain in `yardstick_attempts` and `alternatives_considered`.

**Why:** User wants visible evolution, not silent replacement.

**Doubts:** May need human gate for judgment yardsticks later.

---

## 2026-05-29 — Dev-mode chat includes clone source

**Decision:** Production chat uses artifacts + DB only. When `YARDSTICK_DEV_MODE=true`, chat context adds `coverage_gaps`, ripgrep hits, and file snippets from team clone paths so operators can ask *why* a rubric sub-metric is blank and propose harness improvements.

**Why:** Week 4 showed **untyped params** on the scorecard with no harness measurement for two teams and an unverified 0% artifact for a third — dev chat should surface that honestly and search repos for counting scripts.

**Revisit when:** TS agent can run targeted measurements on demand; dev-only code access may fold into a scoped "investigate metric" job.
