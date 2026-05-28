# Week 4 Cohort Learning Insights

This is a prototype cohort-learning report. It separates measured static signals from impression notes.

## Evidence-Backed Signals

### labs-gauntletai-com-daltondinderman-shipshape

- Strength: Broad audit language covers most Week 4 categories.
- Strength: Strong before/after and measurement vocabulary appears across submission evidence.
- Strength: Category-specific evidence files appear for every required Week 4 category.
- Strength: Security probe language appears to cover several required attack surfaces.
- Strength: Repo includes a visible test surface for regression protection.
- Risk: No major static risk found.
- Static score: 99.3 / 100 (94.3 before impression notes).
- Submission/evidence files scanned: 437.
- Category coverage found: type safety, bundle size, api response time, database query, test coverage, runtime error, accessibility, security.
- Strongest category evidence paths: security (117), accessibility (60), bundle size (53).

### github-com-michaelhabermas-ship-shape

- Strength: Broad audit language covers most Week 4 categories.
- Strength: Strong before/after and measurement vocabulary appears across submission evidence.
- Strength: Security probe language appears to cover several required attack surfaces.
- Strength: Repo includes a visible test surface for regression protection.
- Risk: Category-specific evidence files were not found for: type safety, api response time, database query, test coverage, runtime error, accessibility.
- Static score: 89.55 / 100 (84.55 before impression notes).
- Submission/evidence files scanned: 158.
- Category coverage found: type safety, bundle size, api response time, database query, test coverage, runtime error, accessibility, security.
- Strongest category evidence paths: security (119), bundle size (4), type safety (0).
- Missing category-specific evidence paths: type safety, api response time, database query, test coverage, runtime error, accessibility.

## Impression Notes

- labs-gauntletai-com-daltondinderman-shipshape: Impression: notification-related work may be a reusable pattern worth inspecting.
- labs-gauntletai-com-daltondinderman-shipshape: Impression: accessibility work appears to use recognizable tools.
- labs-gauntletai-com-daltondinderman-shipshape: Impression: Playwright appears in the submission and may indicate runnable regression work.
- github-com-michaelhabermas-ship-shape: Impression: notification-related work may be a reusable pattern worth inspecting.
- github-com-michaelhabermas-ship-shape: Impression: accessibility work appears to use recognizable tools.
- github-com-michaelhabermas-ship-shape: Impression: Playwright appears in the submission and may indicate runnable regression work.

## Follow-Up Questions

- Ask `labs-gauntletai-com-daltondinderman-shipshape` to show the concrete before/after evidence behind its highest-scoring categories.
- Ask `github-com-michaelhabermas-ship-shape` to show the concrete before/after evidence behind its highest-scoring categories.
