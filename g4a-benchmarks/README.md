# G4A Benchmarks

This folder is the **home for benchmark results** in the G4A bench repo. It does not hold the specs or challenger repos; it holds what we learn after running teams against those inputs.

Benchmark tooling (to be built) will clone repos from `[g4a-challenger-repos/](../g4a-challenger-repos/)`, score them against the week’s materials in `[g4a-specs/](../g4a-specs/)`, and **write outputs here**—organized by cohort, then by week, then by team.

## Why this exists

Each G4A week is a different product challenge with different success criteria. Week 1 might emphasize architecture and agent reliability; a later week might emphasize security audit findings or PRD fidelity. There is no single global scorecard across the program.

This directory makes that explicit:

- **Per week:** measurement and ranking follow whatever that week’s specs and rubric define.
- **Per cohort:** the same week number can run again for a new cohort; results must not be mixed across cohorts.
- **Over time:** as weeks complete, this folder becomes the cumulative record of how each team performed on each challenge.

Agents and humans should treat this README as the contract for what belongs here and how future automation should lay out artifacts.

## Relationship to other folders


| Folder                                              | Role                                                                                                                                                                          |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `[g4a-specs/](../g4a-specs/)`                       | **What “good” means** for a week—PRDs, case studies, audit briefs, acceptance themes. The benchmark reads these (not copies of them) to derive checks and scoring dimensions. |
| `[g4a-challenger-repos/](../g4a-challenger-repos/)` | **What to run**—per-week `REPOS.md` lists team names and Git URLs. Team names in that file are the canonical labels for results.                                              |
| `**g4a-benchmarks/`** (here)                        | **What happened**—scores, rankings, logs, repro notes, and any exported evidence from a benchmark run.                                                                        |


Specs are the source of truth for intent; challenger repos are the source of truth for *who* was measured; this folder is the source of truth for *outcomes*.

## Measurement model (important)

**Do not assume one rubric fits all weeks.**

For each `{cohort}/week-{n}/`:

1. **Ingest** the week’s spec files under `g4a-specs/{cohort}/week-{n}/`.
2. **Derive** week-specific criteria—functional requirements, quality bars, security expectations, doc completeness, etc. What matters in week 2 may be irrelevant in week 4.
3. **Execute** against each repo listed in `g4a-challenger-repos/{cohort}/week-{n}/REPOS.md` (clone, build, test, static analysis, scripted checks, or LLM-assisted evaluation—whatever the week’s harness requires).
4. **Score and rank** only on dimensions justified by that week’s specs. Document those dimensions in the week’s results so rankings are auditable.
5. **Publish** artifacts under this tree (see layout below).

Cross-week comparison (e.g. “best team overall for the cohort”) is optional and **secondary**. Primary reporting is **within a week**: who met the bar, who exceeded it, and how teams order against that week’s criteria.

## Intended layout

Structure is not fully implemented yet; new cohorts and weeks should follow this pattern so agents and scripts stay consistent:

```text
g4a-benchmarks/
  README.md
  {cohort}/                    # e.g. g4a-c5-2
    week-{n}/
      README.md                # optional: rubric summary, run date, tooling version
      rankings.{json|md}       # ordered teams + scores per dimension for this week only
      {team-name}/             # matches Team column in REPOS.md
        summary.json           # machine-readable scores + pass/fail per check
        logs/                  # build/test/benchmark output
        evidence/              # screenshots, reports, exports (if applicable)
```

Conventions:

- `**{cohort}**` mirrors directory names in `g4a-specs/` and `g4a-challenger-repos/` (e.g. `g4a-c5-2`).
- `**{team-name}**` must match `REPOS.md` exactly so results join cleanly across reruns.
- `**rankings.***` is the human-facing rollup for the week; per-team folders hold detail and reproducibility.
- Do not commit secrets, tokens, or full cloned repos—only scores, logs, and redacted artifacts.

## Lifecycle

1. **Before a run:** specs and `REPOS.md` for the week are finalized in their respective folders.
2. **During a run:** harness writes per-team outputs under `{cohort}/week-{n}/{team-name}/`.
3. **After a run:** generate `rankings.`* from aggregated scores; optional week `README.md` records rubric version, spec file hashes or paths, and run metadata.
4. **When all weeks for a cohort are measured:** each week has its own ranking; any cohort-wide synthesis (leaderboards, trends) should be derived from these week bundles and clearly labeled as composite—not as a replacement for week-specific results.

## Guidance for agents building the harness

When implementing or extending benchmark tooling:

1. **Read specs first.** Parse `g4a-specs/{cohort}/week-{n}/` and encode week-specific checks; do not hard-code week-1 rules globally.
2. **Read repos second.** Use `g4a-challenger-repos/{cohort}/week-{n}/REPOS.md` as the team list; fail loudly if a listed repo is missing or unreachable.
3. **Write results only under `g4a-benchmarks/`.** Keep specs and repo lists read-only inputs.
4. **Make rankings explainable.** Every score in `rankings.`* should trace to a named criterion documented in the week output (or in a generated rubric file).
5. **Prefer idempotent reruns.** Re-running a week should overwrite or version that week’s folder predictably (e.g. timestamp in metadata), not scatter files at the repo root.
6. **Stay cohort-local.** Never merge `g4a-c5-2` results with another cohort’s tree.

## Current status

This directory is intentionally sparse until benchmark runs exist. The first populated path should be something like:

`g4a-benchmarks/g4a-c5-2/week-1/` after week 1 is measured against `[g4a-specs/g4a-c5-2/week-1/SPECS.txt](../g4a-specs/g4a-c5-2/week-1/SPECS.txt)` and the teams in `[g4a-challenger-repos/g4a-c5-2/week-1/REPOS.md](../g4a-challenger-repos/g4a-c5-2/week-1/REPOS.md)`.

Until then, treat this README as the specification for what will land here and how it should be organized.