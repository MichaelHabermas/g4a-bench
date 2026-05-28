# Week 4 Cohort Learning Insights

This is a prototype cohort-learning report. It separates measured static signals from impression notes.

## Evidence-Backed Signals

### github-com-michaelhabermas-ship-shape

- Strength: Broad audit language covers most Week 4 categories.
- Strength: Structured submission ledger found with 8 proven categories.
- Strength: Strong before/after and measurement vocabulary appears across submission evidence.
- Strength: Category-specific evidence files appear for every required Week 4 category.
- Strength: Security probe language appears to cover several required attack surfaces.
- Strength: Repo includes a visible test surface for regression protection.
- Risk: No major static risk found.
- Extraction confidence: 100.0 / 100 (95.0 before impression notes).
- Final grade: not assigned by this prototype.
- Extraction basis: structured_submission_ledger_self_reported.
- Submission/evidence files scanned: 158.
- Independently checked: repo cloned, commit SHA recorded, files enumerated, package scripts read, submission/evidence text scanned.
- Not independently verified: reported measurements are truthful, before/after artifacts are comparable, chosen target path satisfies the spec when multiple target paths exist, tests are meaningful.
- Category coverage found: type safety, bundle size, api response time, database query, test coverage, runtime error, accessibility, security.
- Strongest category evidence paths: database query (14), runtime error (14), security (12).

### labs-gauntletai-com-daltondinderman-shipshape

- Strength: Broad audit language covers most Week 4 categories.
- Strength: Strong before/after and measurement vocabulary appears across submission evidence.
- Strength: Category-specific evidence files appear for every required Week 4 category.
- Strength: Security probe language appears to cover several required attack surfaces.
- Strength: Repo includes a visible test surface for regression protection.
- Risk: No structured submission ledger found; this run falls back to heuristic evidence parsing.
- Extraction confidence: 99.3 / 100 (94.3 before impression notes).
- Final grade: not assigned by this prototype.
- Extraction basis: heuristic_static_path_and_text_scan.
- Submission/evidence files scanned: 437.
- Independently checked: repo cloned, commit SHA recorded, files enumerated, package scripts read, submission/evidence text scanned.
- Not independently verified: reported measurements are truthful, before/after artifacts are comparable, chosen target path satisfies the spec when multiple target paths exist, tests are meaningful.
- Category coverage found: type safety, bundle size, api response time, database query, test coverage, runtime error, accessibility, security.
- Strongest category evidence paths: security (117), accessibility (60), bundle size (53).

## Agent Review Required

The next evaluator needs category-specific judgment. These questions are generated from the Week 4 rubric and should be answered before any final score exists.

### type safety
- Rerun or independently reproduce the submitted type-safety counts.
- Inspect whether reductions came from meaningful narrowing and boundary typing, not superficial syntax churn.

### bundle size
- Determine which allowed target the team is claiming: total bundle reduction or initial-load/code-splitting reduction.
- Verify before/after bundle artifacts were produced under comparable build conditions.

### api response time
- Verify P95 improvements on at least two endpoints under identical data volume, concurrency, hardware, and bypass/rate-limit conditions.
- Check whether excluded or failed benchmark artifacts change the conclusion.

### database query
- Verify the measured flow satisfies the Week 4 database-query target.
- Check whether EXPLAIN/query-count evidence compares like with like.

### test coverage
- Inspect whether the new tests are meaningful regression tests, not page-load or superficial assertions.
- Check flake/RCA claims when the team uses flake-fix path instead of new-test path.

### runtime error
- Inspect the three claimed error-handling fixes and confirm at least one addresses real user-facing data loss or confusion.
- Check before/after reproduction steps or screenshots.

### accessibility
- Determine whether the team chose Lighthouse improvement or Critical/Serious axe closeout.
- Verify scope covers the top pages claimed and does not overstate manual screen-reader/keyboard coverage.

### security
- Run or inspect the security probe tool and confirm it covers all four required attack surfaces.
- Verify at least two vulnerability fixes with before/after proof and no broken tests.

## Impression Notes

- github-com-michaelhabermas-ship-shape: Impression: notification-related work may be a reusable pattern worth inspecting.
- github-com-michaelhabermas-ship-shape: Impression: accessibility work appears to use recognizable tools.
- github-com-michaelhabermas-ship-shape: Impression: Playwright appears in the submission and may indicate runnable regression work.
- labs-gauntletai-com-daltondinderman-shipshape: Impression: notification-related work may be a reusable pattern worth inspecting.
- labs-gauntletai-com-daltondinderman-shipshape: Impression: accessibility work appears to use recognizable tools.
- labs-gauntletai-com-daltondinderman-shipshape: Impression: Playwright appears in the submission and may indicate runnable regression work.

## Follow-Up Questions

- Ask `github-com-michaelhabermas-ship-shape` to show the concrete before/after evidence behind its highest-scoring categories.
- Ask `labs-gauntletai-com-daltondinderman-shipshape` to show the concrete before/after evidence behind its highest-scoring categories.
