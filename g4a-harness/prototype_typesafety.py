#!/usr/bin/env python3
"""Generate a Week 4 Category 1 (Type Safety) evaluator trace.

Type safety is not one number. The spec's deliverable enumerates separate
violation classes (explicit any, `as` casts, non-null `!`, @ts-ignore, untyped
params, strict mode), and the improvement target ("eliminate 25% of type-safety
violations") applies to the aggregate while each class is its own diagnostic and
its own judgment call.

So this trace decomposes the category into PARTS. Each part carries before/after
per team plus a curated judgment state. One part ("total") is the headline that
the 25% threshold is measured against; the rest are diagnostic detail.

It still emits a single `target_paths` entry (the headline) and `judgment_gates`
so the older render_compare.py keeps working unchanged. The new render_scorecard.py
reads `parts`.

Measurements extracted 2026-05-28 from the cloned submissions, production basis
(any + as + non-null over api/web/shared, tests excluded) for the two AST repos.
Shiv used ESLint over src including tests — a different instrument/scope, recorded
as reported-math (md) and flagged in the comparability gate, not silently merged.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path("/Users/michaelhabermas/repos/GAI/g4a-bench")
RUNS_DIR = ROOT / "g4a-benchmarks/g4a-c5-2/week-4/runs"
SPEC_FILE = "g4a-specs/g4a-c5-2/week-4/GFA-Week-4-ShipShape.txt"

PART_DEFS = [
    {"id": "total", "label": "total (any + as + !)", "headline": True, "threshold": ">= 25% reduction"},
    {"id": "any", "label": "explicit any"},
    {"id": "as", "label": "as casts"},
    {"id": "nonnull", "label": "non-null !"},
    {"id": "untyped", "label": "untyped params"},
    {"id": "strict", "label": "strict mode", "kind": "boolean"},
]

GATE_DEFS = [
    {"id": "functionality_preserved", "label": "Functionality preserved (tests pass)"},
    {"id": "fixes_meaningful", "label": "Fixes meaningful (not superficial)"},
    {"id": "counting_comparable", "label": "Counting comparable (same instrument/scope)"},
]

# Each team: trust tier + per-part before/after (or boolean value) + curated judgment.
# judgment vocab: meaningful | needs_review | not_addressed | not_claimed | neutral
TEAMS = [
    {
        "team": "github-com-michaelhabermas-ship-shape",
        "team_shape": "structured_ledger_with_artifact_pointers",
        "commit_sha": "e5fed89d6c053094fbcc53d8c301dc3f98c330a2",
        "repo_url": "https://github.com/MichaelHabermas/ship-shape",
        "trust": "artifact-backed",
        "parts": {
            "total": {"before": 923, "after": 409, "judgment": "needs_review"},
            "any": {"before": 94, "after": 1, "judgment": "meaningful"},
            "as": {"before": 504, "after": 372, "judgment": "meaningful"},
            "nonnull": {"before": 325, "after": 36, "judgment": "needs_review"},
            "untyped": {"value": None, "judgment": "not_claimed"},
            "strict": {"value": "on", "kind": "boolean", "trust": "artifact-backed", "judgment": "neutral"},
        },
        "claim_text": [
            "Production type-safety violations (any + as + !) reduced 923 -> 409 (55.7%), clearing the 25% target, with all three classes down.",
        ],
        "caveats": [
            "Baseline counts are report_extracted; latest counts are artifact_parsed (AST). Confirm same counter.",
            "Reduction spans all three classes, including `as` casts (504 -> 372) — harder to fake than a single-bucket win.",
        ],
        "primary_evidence": [
            "my-docs/evidence/submission-ledger.json#categories[0]",
            "scripts/type-safety-counts.mjs",
        ],
        "evidence_states": [
            {"name": "claim_found", "value": "yes", "note": "Ledger category cat-1-type-safety."},
            {"name": "artifact_backed", "value": "yes", "note": "Baseline + latest AST counts with package breakdown."},
            {"name": "machine_readable_before_after", "value": "yes", "note": "Counts extractable as numbers."},
            {"name": "path_choice_explicit", "value": "yes", "note": "25% target stated directly."},
            {"name": "independently_reproduced", "value": "no", "note": "Counter/test suite not rerun."},
            {"name": "comparability", "value": "plausible_not_verified", "note": "Production AST baseline (923) matches Dalton's (925)."},
        ],
        "provisional_judgment": {"state": "artifact_math_passes", "summary": "Broad-based reduction clears 25% on artifacts; gates need judgment."},
        "judgment_gates": [
            {"id": "functionality_preserved", "state": "claimed", "note": "Ledger status 'proven' + pnpm-test log; not rerun."},
            {"id": "fixes_meaningful", "state": "needs_review", "note": "Across-the-board reduction lowers superficiality risk, but narrowing quality unverified."},
            {"id": "counting_comparable", "state": "pass", "note": "Production AST; baseline converges with Dalton."},
        ],
        "next_judgments": [
            {"judgment": "trust_level", "state": "artifact_backed_not_reproduced", "why": "AST counts support the claim; final confidence needs a clean-clone rerun."},
            {"judgment": "superficiality_check", "state": "lower_risk", "why": "Reducing `as` casts and `any` together is harder to game than removing only non-null assertions."},
        ],
        "agent_questions": [
            "Were the removed `as` casts replaced with meaningful narrowing?",
            "Did the test suite actually pass at the latest commit?",
        ],
    },
    {
        "team": "labs-gauntletai-com-daltondinderman-shipshape",
        "team_shape": "before_after_count_json_with_delta_markdown",
        "commit_sha": "7f394f245cd70949d05112c4dcbd02719982e56c",
        "repo_url": "(gauntlet labs submission)",
        "trust": "artifact-backed",
        "parts": {
            "total": {"before": 925, "after": 616, "judgment": "needs_review"},
            "any": {"before": 96, "after": 66, "judgment": "needs_review"},
            "as": {"before": 504, "after": 504, "judgment": "not_addressed"},
            "nonnull": {"before": 325, "after": 46, "judgment": "needs_review"},
            "untyped": {"before": 1371, "after": 1371, "judgment": "not_addressed"},
            "strict": {"value": "on", "kind": "boolean", "trust": "artifact-backed", "judgment": "neutral"},
        },
        "claim_text": [
            "Production type-safety violations reduced 925 -> 616 (33.4%), clearing the 25% target.",
        ],
        "caveats": [
            "The reduction is concentrated: non-null 325 -> 46 and some any (96 -> 66).",
            "`as` casts (504) and untyped params (1371) — the two largest buckets — are unchanged.",
        ],
        "primary_evidence": [
            "docs/category-improvements/evidence/01-type-safety/before-type-safety-counts.json",
            "docs/category-improvements/evidence/01-type-safety/after-type-safety-counts.json",
            "docs/category-improvements/evidence/01-type-safety/type-safety-delta.md",
        ],
        "evidence_states": [
            {"name": "claim_found", "value": "yes", "note": "Delta markdown states passed vs 25%."},
            {"name": "artifact_backed", "value": "yes", "note": "Distinct before/after count JSON."},
            {"name": "machine_readable_before_after", "value": "yes", "note": "production.primaryTotal extractable."},
            {"name": "path_choice_explicit", "value": "yes", "note": "25% target, explicit."},
            {"name": "independently_reproduced", "value": "no", "note": "Scan/regression not rerun."},
            {"name": "comparability", "value": "plausible_not_verified", "note": "Production AST; baseline (925) matches Michael (923)."},
        ],
        "provisional_judgment": {"state": "artifact_math_passes", "summary": "Clears 25%, but the win is narrow — almost all non-null assertions."},
        "judgment_gates": [
            {"id": "functionality_preserved", "state": "needs_review", "note": "Full-regression run dir exists; not replayed."},
            {"id": "fixes_meaningful", "state": "needs_review", "note": "Concentrated in non-null; `as` (largest bucket) untouched. Real null-safety or assertion churn?"},
            {"id": "counting_comparable", "state": "pass", "note": "Production AST; baseline converges with Michael."},
        ],
        "next_judgments": [
            {"judgment": "trust_level", "state": "artifact_backed_not_reproduced", "why": "Before/after pair is strong; may both derive from current state."},
            {"judgment": "superficiality_check", "state": "concentration_risk", "why": "A reduction dominated by non-null warrants checking real null checks vs optional chaining."},
        ],
        "agent_questions": [
            "Were 279 removed non-null assertions replaced with real null checks?",
            "Why are `as` casts (504) completely unchanged?",
        ],
    },
    {
        "team": "labs-gauntletai-com-shivkanthalu-ship",
        "team_shape": "markdown_audit_report_single_pass",
        "commit_sha": "(submission commit)",
        "repo_url": "(gauntlet labs submission)",
        "trust": "reported-math",
        "parts": {
            "total": {"before": 1219, "after": 0, "judgment": "needs_review"},
            "any": {"before": 271, "after": 0, "judgment": "needs_review"},
            "as": {"before": 619, "after": 0, "judgment": "needs_review"},
            "nonnull": {"before": 329, "after": 0, "judgment": "needs_review"},
            "untyped": {"value": None, "judgment": "not_claimed"},
            "strict": {"value": "on", "kind": "boolean", "trust": "artifact-backed", "judgment": "neutral"},
        },
        "claim_text": [
            "All 1,219 type violations eliminated in a single pass on 2026-05-21; type-check passes, 502 tests pass.",
        ],
        "caveats": [
            "Counts from ESLint over src including tests — different instrument/scope than the AST repos.",
            "Baseline 1,219 is not comparable to the production-AST baseline (~924).",
            "1,219 -> 0 in one pass is the most extreme reported outcome and the least independently supported.",
        ],
        "primary_evidence": [
            "docs/audit/category-1-type-safety.md",
        ],
        "evidence_states": [
            {"name": "claim_found", "value": "yes", "note": "Markdown scorecard claims total elimination."},
            {"name": "artifact_backed", "value": "markdown_backed", "note": "Counts in Markdown tables; no committed before/after JSON."},
            {"name": "machine_readable_before_after", "value": "no", "note": "No recognized count JSON."},
            {"name": "path_choice_explicit", "value": "yes", "note": "25% target; claims 100%."},
            {"name": "independently_reproduced", "value": "no", "note": "ESLint/type-check/tests not rerun."},
            {"name": "comparability", "value": "needs_agent_review", "note": "Different instrument/scope; baseline magnitude differs."},
        ],
        "provisional_judgment": {"state": "markdown_math_passes_pending_artifacts", "summary": "Reports 100% on the lowest trust rung; extraordinary claim, weakest support."},
        "judgment_gates": [
            {"id": "functionality_preserved", "state": "claimed", "note": "Markdown asserts 502 tests + clean type-check; not reproduced."},
            {"id": "fixes_meaningful", "state": "needs_review", "note": "1,219 -> 0 in one pass is the highest superficiality risk in the cohort."},
            {"id": "counting_comparable", "state": "fail", "note": "ESLint+tests scope; baseline 1,219 not comparable to ~924."},
        ],
        "next_judgments": [
            {"judgment": "trust_level", "state": "markdown_only_pending_artifacts", "why": "Generate ESLint JSON + committed before/after to move off prose."},
            {"judgment": "superficiality_check", "state": "high_risk", "why": "Total elimination in one pass is the strongest candidate for spot-checking fixes."},
        ],
        "agent_questions": [
            "Does ESLint actually report 0 at the submission commit?",
            "Were 619 `as` casts replaced with real types, or with `as unknown as` / disabled rules?",
            "What does the production-AST counter report, for comparison with 923/925?",
        ],
    },
]


def reduction_percent(before: float, after: float) -> float | None:
    if not before:
        return None
    return round((before - after) / before * 100, 2)


def build_trace(run_dir: Path) -> dict[str, Any]:
    teams = []
    for t in TEAMS:
        team = {k: v for k, v in t.items() if k != "parts"}
        parts = {}
        for pid, raw in t["parts"].items():
            part = dict(raw)
            if part.get("kind") == "boolean" or "value" in part:
                part.setdefault("reduction_percent", None)
            else:
                part["reduction_percent"] = reduction_percent(part["before"], part["after"])
            parts[pid] = part
        team["parts"] = parts

        # Back-compat single path = the headline (total) part, for render_compare.py.
        total = parts["total"]
        pct = total["reduction_percent"]
        state = (
            "passes_artifact_math"
            if t["trust"] == "artifact-backed" and pct is not None and pct >= 25
            else "passes_markdown_math"
            if pct is not None and pct >= 25
            else "fails_artifact_math"
        )
        team["target_paths"] = [
            {
                "id": "violation-reduction",
                "before": total["before"],
                "after": total["after"],
                "unit": "violations",
                "reduction_percent": pct,
                "spec_threshold": ">= 25% reduction",
                "interpretation": "Valid only if fixes preserve functionality and are not superficial.",
                "state": state,
            }
        ]
        team["discovery_inventory"] = {"evidence_files": len(t["primary_evidence"])}
        teams.append(team)

    return {
        "artifact_kind": "type_safety_process_trace",
        "criterion": {
            "id": "type-safety",
            "name": "Type Safety",
            "unit": "violations",
            "combine": "headline",
            "headline_part": "total",
            "threshold_percent": 25,
        },
        "part_defs": PART_DEFS,
        "gate_defs": GATE_DEFS,
        "run_dir": str(run_dir),
        "run_id": run_dir.name,
        "scope_note": "Generalized evaluator trace pointed at Category 1, decomposed into parts. Production basis = any + as + non-null over api/web/shared excluding tests.",
        "spec_excerpt": (
            "Category 1: Type Safety. Count explicit any, `as` assertions, non-null `!`, @ts-ignore, untyped "
            "params; check strict mode. Target: eliminate 25% of violations. Every fix must preserve "
            "functionality. Superficial fixes and any->unknown without narrowing do not count."
        ),
        "spec_source": SPEC_FILE,
        "teams": teams,
    }


def latest_run() -> Path:
    candidates = sorted(p for p in RUNS_DIR.glob("*") if p.is_dir())
    if not candidates:
        raise SystemExit(f"No run directories found under {RUNS_DIR}")
    return candidates[-1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=None)
    args = parser.parse_args()
    run_dir = args.run_dir or latest_run()
    out = run_dir / "typesafety-trace.json"
    out.write_text(json.dumps(build_trace(run_dir), indent=2), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
