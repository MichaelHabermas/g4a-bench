# g4a-bench

A home for **measuring G4A challenger work** week by week. Each week is a different build challenge with its own specs and its own bar for success—there isn’t one scorecard for the whole program.

## How it fits together

| Folder | What it holds |
|--------|----------------|
| [`g4a-specs/`](g4a-specs/) | Week briefs—PRDs, case studies, audits. Defines what “good” looks like. |
| [`g4a-challenger-repos/`](g4a-challenger-repos/) | Who to measure. Each week has a `REPOS.md` with team names and Git URLs. |
| [`g4a-benchmarks/`](g4a-benchmarks/) | Results land here after runs—scores and rankings per cohort, per week. |

Layout under each folder: `{cohort}/week-{n}/` (e.g. `g4a-c5-2/week-4/`).

## The idea

1. Read the week’s specs.
2. Clone and evaluate the repos listed for that week.
3. Score and rank against **that week’s** criteria only.
4. Publish outcomes under `g4a-benchmarks/`.

Benchmark harness and automation are still to come; the repo is set up so specs, repos, and results stay in separate, obvious places. More detail on results layout: [`g4a-benchmarks/README.md`](g4a-benchmarks/README.md).
