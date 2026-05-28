# Week 4 Prototype Measurement Plan

This run is a quick prototype of the generated-evaluator flow. It measures the two Week 4 repos with static checks only. It does not install dependencies, start the apps, run Playwright, measure bundle size, or benchmark live API/database behavior yet.

## Inputs

Specs:

- `g4a-specs/g4a-c5-2/week-4/GFA-Week-4-ShipShape.txt`
- `g4a-specs/g4a-c5-2/week-4/ShipShape-Kickoff.txt`
- `g4a-specs/g4a-c5-2/week-4/Shipshape-Security-Audit.txt`

Repos:

- `github-com-michaelhabermas-ship-shape`: https://github.com/MichaelHabermas/ship-shape
- `labs-gauntletai-com-daltondinderman-shipshape`: https://labs.gauntletai.com/daltondinderman/shipshape
- `labs-gauntletai-com-shivkanthalu-ship`: https://labs.gauntletai.com/shivkanthalu/ship

## What Week 4 Tests

Week 4 asks challengers to inherit the Treasury Ship codebase, orient deeply, audit all required quality categories, improve the system with measurable before/after proof, and document the work. The security addendum adds an eighth category requiring a runnable security probe and fixes for at least two verified vulnerabilities.

## Prototype Criteria

- `W4-DOCS-01` (15 pts): Required deliverables and orientation - README/setup, audit/improvement/discovery/cost docs, and evidence that the team oriented around Ship.
- `W4-AUDIT-01` (20 pts): Audit coverage across categories - Coverage of the seven required ShipShape categories plus the security audit extension.
- `W4-PROOF-01` (25 pts): Before/after improvement evidence - Concrete baseline/after language, benchmarks, measurements, and reproducibility signals.
- `W4-SECURITY-01` (15 pts): Security probe deliverable - Runnable security probe or audit tooling covering auth/session, WebSocket validation, input sanitization, dependency audit, and manual review concerns.
- `W4-TESTS-01` (10 pts): Testing and regression protection - Presence of meaningful tests and scripts connected to the improvement work.
- `W4-REPO-01` (10 pts): Repo health and runnable shape - Basic project health: package metadata, workspace/config files, source tree, and recent commit availability.
- `W4-INSIGHT-01` (5 pts): Cohort learning signal - Interesting choices, standout polish, or transferable ideas visible from static review.

## Evidence This Prototype Collects

- repository clone status and commit SHA
- visible markdown deliverables
- mentions of required audit categories
- before/after measurement vocabulary
- security probe and attack-surface vocabulary
- visible test files and package scripts
- basic repo shape and recent commits
- labeled subjective impressions for cohort-learning dessert

## Known Gaps

- No dependency installation.
- No live app execution.
- No browser/deployed-site inspection.
- No actual TypeScript, bundle, API, database, Lighthouse, axe, or npm audit execution.
- Static keyword checks can miss well-written work that uses different language.
- Static keyword checks can over-credit superficial mentions.

This is enough to test the artifact flow and compare rough signal between the two repos. It is not enough for final grading.
