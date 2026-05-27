# G4A Benchmark Harness Spec

## Purpose

G4A Bench exists to measure challenger work across weekly build challenges whose goals, artifacts, and success criteria differ from week to week.

The benchmark harness must not impose one global rubric. Week 1 asks for a trustworthy clinical co-pilot. Week 3 asks for an adversarial AI security platform. Week 4 asks for measurable improvement to a production TypeScript codebase. Week 5 asks for a proactive graph agent inside Ship. A single fixed scorecard would erase what each week is actually testing.

The harness should instead behave like a measurement compiler:

1. Read the week specs and repo list.
2. Derive a week-specific measurement plan.
3. Generate an evaluator for that week.
4. Run the evaluator against each submitted repo.
5. Collect evidence, logs, scores, and rankings.
6. Produce a cohort learning report that surfaces standouts, patterns, and useful follow-up questions.

The primary output is not just "who won." The primary output is a reproducible measurement bundle. Rankings are one view over that bundle. Cohort learning is another.

## Non-Goals

- Do not create a universal rubric across all weeks.
- Do not score teams without preserving the evidence behind the score.
- Do not make hidden one-shot LLM judgments that cannot be inspected.
- Do not treat subjective product/design impressions as equal to measured criteria.
- Do not mix cohorts or weeks in primary rankings.
- Do not commit full cloned challenger repos or secrets into this repository.

## Core Model

The stable system is the harness. The generated system is the week evaluator.

```text
g4a-specs/{cohort}/week-{n}/
g4a-challenger-repos/{cohort}/week-{n}/REPOS.md
        |
        v
spec reader
        |
        v
measurement planner
        |
        v
evaluator generator
        |
        v
isolated repo runner
        |
        v
evidence collector
        |
        v
scorer and ranker
        |
        v
cohort learning insight engine
        |
        v
g4a-benchmarks/{cohort}/week-{n}/runs/{run-id}/
```

## Stable Source Layout

These directories should be source-controlled as maintained system code:

```text
g4a-harness/
  core runner
  spec ingestion
  repo ingestion
  sandbox/runtime orchestration
  evaluator generation
  artifact writing
  scoring schemas
  report writers

g4a-evaluators/
  optional promoted evaluators that proved reusable or worth hand-maintaining
```

Generated evaluators should start as run artifacts, not as permanent source code. If a generated evaluator proves useful, stable, and worth reusing, promote it into `g4a-evaluators/` later.

## Run Artifact Layout

Each benchmark run writes an auditable bundle:

```text
g4a-benchmarks/
  {cohort}/
    week-{n}/
      runs/
        {run-id}/
          run.json
          measurement-plan.md
          rubric.json
          evaluator/
          teams/
            {team}/
              summary.json
              logs/
              evidence/
          rankings.json
          rankings.md
          insights.md
```

`run-id` should encode enough information to distinguish reruns, such as timestamp, harness version, git SHA, or a short generated ID.

Team names must be stable identifiers. `REPOS.md` should include a canonical team name and repo URL for every submission. If a week only lists repo URLs, the harness should fail with a clear validation error or require an explicit generated team-name mapping before scoring.

## Pipeline

### 1. Spec Reader

The spec reader loads all materials for a given `{cohort}/week-{n}`:

- Markdown, text, and extracted PDF text.
- Supplemental briefs, audit docs, surprise challenges, advisor notes, and templates.
- The matching `REPOS.md`.

It should produce a normalized input bundle that records:

- source file paths
- content hashes
- detected deliverables
- hard gates
- deadlines and submission stages
- required artifacts
- explicit grading weights, if present
- ambiguous or conflicting instructions

The reader must preserve references back to source files so the measurement planner can justify why a criterion exists.

### 2. Measurement Planner

The measurement planner is the most important agent step. It reads the normalized input bundle and writes `measurement-plan.md`.

The plan must include:

- What the week is testing.
- What a strong submission looks like.
- Required deliverables.
- Hard gates that cause failure regardless of score.
- Measurable criteria.
- Which criteria can be checked deterministically.
- Which criteria require LLM-assisted review.
- Which criteria require browser or deployed-app inspection.
- Which criteria cannot be measured reliably by automation.
- The proposed weighting model.
- Evidence required for each score.
- Known risks in the measurement approach.

The measurement plan is generated automatically. It does not require human approval before the run, but it must be stored as a first-class artifact so humans can inspect, edit, rerun, or reject the evaluator later.

### 3. Rubric Builder

The rubric builder converts the measurement plan into `rubric.json`.

The rubric should be machine-readable and contain:

- criteria IDs
- criterion names
- descriptions
- weights
- score ranges or pass/fail rules
- required evidence types
- source references back to spec files
- scoring method: deterministic, LLM-assisted, browser-assisted, or manual-only
- hard-gate status

Rubrics are week-local. A score of 85 in Week 4 does not mean the same thing as a score of 85 in Week 5.

### 4. Evaluator Generator

The evaluator generator creates week-specific code under the run artifact directory:

```text
g4a-benchmarks/{cohort}/week-{n}/runs/{run-id}/evaluator/
```

Generated evaluators may include:

- repo setup scripts
- README and deliverable checks
- static analysis checks
- test runners
- browser inspection scripts
- deployed URL checks
- artifact parsers
- LLM review prompts
- scoring adapters
- report fragments

The evaluator must be disposable. It should be easy to delete the run and regenerate from the specs.

The evaluator must also be inspectable. Generated prompts, commands, check definitions, and scoring logic should be saved in files, not hidden in agent memory.

### 5. Isolated Repo Runner

The runner clones each challenger repo and runs the generated evaluator in isolation.

Minimum responsibilities:

- clone the submitted repo at a recorded commit SHA
- detect project type and setup instructions
- run only within an isolated workspace
- capture stdout, stderr, exit codes, timings, and tool versions
- avoid committing cloned repos into this repository
- redact secrets from logs
- continue evaluating other teams when one repo fails setup

The runner should support local execution first. It should be designed so the same artifact contract can later run in CI or a remote worker.

### 6. Evidence Collector

Every score should point to evidence.

Evidence can include:

- command output
- test results
- static analysis summaries
- generated reports from the team repo
- screenshots
- browser traces
- deployed URLs
- parsed markdown deliverables
- source file references
- LLM review transcripts
- human-readable notes

Evidence should be stored under:

```text
teams/{team}/evidence/
```

Per-team `summary.json` should link scores to evidence paths.

### 7. Scorer and Ranker

The scorer applies `rubric.json` to each team's evidence bundle.

It must produce:

- per-criterion scores
- hard-gate pass/fail status
- total score
- confidence level
- evidence links
- evaluator warnings
- reasons a score could not be computed

The ranker produces `rankings.json` and `rankings.md`.

Rankings are useful, but they are not the whole product. The ranking should answer "how did teams compare on this week's measured criteria?" It should not imply cross-week superiority.

### 8. Cohort Learning Insight Engine

After scoring, the harness writes `insights.md`.

This is a cohort learning report, not a second ranking table.

It should surface:

- standout implementations
- unusually strong scores on specific criteria
- reusable engineering patterns
- clever product or UX decisions
- smart uses of the underlying platform
- common failure modes across the cohort
- surprising tradeoffs
- teams worth interviewing about specific strengths
- questions graders or instructors should ask
- signals about what to teach or emphasize next

The insight engine has two layers:

1. Evidence-backed insights. These are claims directly tied to scores, logs, source references, screenshots, or evaluator outputs.
2. Impression notes. These are subjective but useful observations from running the app or reading the work: "this interaction felt polished," "this architecture choice was smart," "this team used the built-in notification system well," or "this visual treatment made the product easier to understand."

Impression notes are allowed, but they must be labeled as impressions. They are additive. They should never silently determine the benchmark score.

## Output Files

### `run.json`

Machine-readable run metadata:

- cohort
- week
- run ID
- started and completed timestamps
- harness version
- source git SHA
- model/provider configuration, if applicable
- spec file hashes
- repo list hash
- evaluator path
- runner environment

### `measurement-plan.md`

Human-readable plan explaining how this week will be measured.

This is the best artifact for debugging whether the harness understood the assignment.

### `rubric.json`

Machine-readable scoring contract.

This is the best artifact for comparing intended scoring to actual scoring.

### `evaluator/`

Generated scripts, prompts, check definitions, and adapters used for the run.

This is the best artifact for reproducing or modifying the evaluator.

### `teams/{team}/summary.json`

Machine-readable per-team result:

- repo URL
- commit SHA
- setup status
- hard-gate status
- per-criterion scores
- evidence links
- warnings
- notable strengths
- notable risks

### `rankings.json`

Machine-readable ranking output for downstream tools.

### `rankings.md`

Human-readable ranking report.

### `insights.md`

Cohort learning report.

This should be readable by instructors, graders, and participants who want to know what the cohort did well and what is worth learning from.

## Scoring Principles

1. Measure the week that exists, not the week the harness wishes existed.
2. Hard gates must remain hard gates.
3. Prefer deterministic checks where they fit.
4. Use LLM-assisted review where qualitative judgment is necessary.
5. Store the prompts and outputs behind LLM-assisted judgments.
6. Separate evidence-backed conclusions from subjective impressions.
7. Treat setup failures as meaningful data, but do not let one failed repo block the run.
8. Rank within a week, not across unlike weeks.
9. Make reruns explainable, even when results change.

## LLM-Assisted Review

LLM review is expected because many weekly assignments evaluate architecture quality, product judgment, documentation clarity, and defensibility.

LLM-assisted scoring must:

- use the generated rubric
- cite evidence paths
- preserve prompts and responses
- record model name and settings
- produce structured outputs
- include confidence or uncertainty
- avoid inventing criteria not present in the plan

The harness should prefer narrow LLM tasks over broad "grade this repo" prompts.

Good:

```text
Given FLEETGRAPH.md, trace links, and the rubric criterion for trigger model defense,
score only criterion FG-TRIGGER-01 and cite evidence.
```

Bad:

```text
Which team did best?
```

## Browser and Deployed-App Inspection

Many submissions require a deployed app or UI behavior. The harness should support browser-assisted checks when the week calls for it.

Browser-assisted checks can inspect:

- whether the deployed URL works
- whether core flows are reachable
- whether a chat or agent UI is embedded in context
- whether screenshots or visual evidence can be captured
- whether obvious runtime errors occur
- whether UI polish or product impressions are worth noting

Browser observations can feed both scores and impression notes, depending on the rubric.

## Failure Handling

The harness should make failures visible and useful.

Examples:

- Missing `REPOS.md`: fail the run before evaluator generation.
- Missing team names: fail validation or generate a required mapping step.
- Repo clone failure: mark that team as setup failed and continue.
- Dependency install failure: store logs and continue.
- Missing required deliverable: score the relevant hard gate as failed.
- Generated evaluator crash: mark evaluator failure, preserve logs, and avoid producing misleading rankings.
- Ambiguous spec requirement: record the ambiguity in `measurement-plan.md` and choose a defensible interpretation.

## First Implementation Target

The first useful version should support one cohort and one week at a time:

```text
g4a-harness run --cohort g4a-c5-2 --week 5
```

Minimum viable output:

- `run.json`
- `measurement-plan.md`
- `rubric.json`
- generated `evaluator/`
- per-team `summary.json`
- `rankings.md`
- `rankings.json`
- `insights.md`

The first implementation should optimize for inspectability and rerunnability, not perfect grading.

## Open Design Choices For Implementation

These decisions should be made during implementation planning:

- sandbox mechanism for untrusted repos
- model provider and model routing
- whether remote/private repos require auth support in v1
- how much of each run artifact bundle should be committed
- whether large evidence files should live in git, object storage, or both
- whether promoted evaluators are hand-edited or regenerated from locked measurement plans
- how to diff two runs of the same week
- how to handle human edits to generated measurement plans

## Definition of Done

The harness is working when a user can point it at a cohort and week, then receive an auditable benchmark bundle that explains:

- what the week asked teams to build
- how the harness decided to measure it
- what evaluator was generated
- what happened when each repo was run
- how each score was assigned
- who ranked where
- what the cohort should learn from the submissions
- which standout teams or patterns deserve human follow-up
