#!/usr/bin/env python3
"""Verification runner for Category 1 (Type Safety).

The point: do not trust self-reported numbers. As the system measures each
metric, IT decides how to verify — looking at the actual repo — records why it
chose that method, runs it, sanity-checks the result against the claim, and
keeps the choice loosely held (a revisit condition, not a frozen rule).

This run's decision, per the type-safety violation metrics:
  - Project is a TypeScript monorepo (tsconfig + pnpm workspace).
  - Metric class is syntactic counts of `any` / `as` / `!`.
  - Considered: regex grep (rejected — counts import aliases as casts; proven on
    these repos: crude `as` ~956 vs real 284), the team's own ESLint output
    (rejected — self-reported AND a narrower definition than the spec), and the
    TypeScript compiler's parser (chosen — authoritative for what a cast node is,
    consistent across all repos, and safe because it only parses).
  - Held loosely: this count is SYNTACTIC. It cannot tell a justified cast from a
    lazy one, nor whether a removed `any` was truly narrowed. Revisit if a
    type-aware pass (full program + checker) or a diff-based superficiality
    method becomes available.

It writes verified remaining-counts into the type-safety trace (a real
`verified` rung) and a standalone verification.json capturing the reasoning.
It verifies the AFTER state (the submission clone). Verified % reduction is NOT
computed here because we have not yet verified a common baseline — that gap is
recorded honestly rather than filled with the team's baseline.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path("/Users/michaelhabermas/repos/GAI/g4a-bench")
HARNESS = ROOT / "g4a-harness"
RUNS_DIR = ROOT / "g4a-benchmarks/g4a-c5-2/week-4/runs"
CLONE_BASE = Path("/private/tmp/g4a-bench-prototype/g4a-c5-2/week-4")
TS_LIB = Path("/tmp/tsverify/node_modules/typescript")

CONSIDERED_METHODS = [
    {"method": "regex grep", "verdict": "rejected",
     "why": "Counts `import { X as Y }` aliases as casts. Measured here: crude `as` ~956 vs real 284 for one repo — unusable for the `as` metric."},
    {"method": "team's ESLint output", "verdict": "rejected",
     "why": "Self-reported, and `consistent-type-assertions` flags only a narrow subset of `as` usages — not the spec's 'type assertions (as)'."},
    {"method": "typescript compiler AST", "verdict": "chosen",
     "why": "Authoritative for cast/non-null/any nodes, identical definition across all repos, and safe: it only parses, never executes the clone."},
]
HELD_LOOSELY = (
    "Count is syntactic — cannot judge whether a remaining cast is justified or a "
    "removed `any` was genuinely narrowed. Revisit with a type-aware (full-program) "
    "pass or a diff-based superficiality method."
)


def ensure_typescript() -> None:
    if TS_LIB.exists():
        return
    TS_LIB.parent.parent.mkdir(parents=True, exist_ok=True)
    print("typescript lib missing; installing standalone...")
    subprocess.run(["npm", "i", "typescript@5.9.3", "--no-save", "--silent"],
                   cwd=str(TS_LIB.parent.parent), check=True)


def run_counter(repo: Path) -> dict[str, Any]:
    env = dict(os.environ, TS_LIB=str(TS_LIB))
    out = subprocess.run(
        ["node", str(HARNESS / "ts_violation_counter.js"), str(repo)],
        capture_output=True, text=True, env=env, check=True,
    )
    return json.loads(out.stdout.strip())


def flag(verified: int, claimed: int | None) -> dict[str, Any]:
    if claimed is None:
        return {"flagged": False, "discrepancy": None, "note": "no self-reported after to compare"}
    disc = verified - claimed
    big = abs(disc) > max(20, 0.15 * max(verified, 1))
    note = "self-report rejected — verified count diverges materially" if big else "self-report roughly consistent with verified count"
    return {"flagged": big, "discrepancy": disc, "note": note}


def latest_run() -> Path:
    candidates = sorted(p for p in RUNS_DIR.glob("*") if p.is_dir())
    if not candidates:
        raise SystemExit(f"No run directories under {RUNS_DIR}")
    return candidates[-1]


def verify(run_dir: Path) -> dict[str, Any]:
    ensure_typescript()
    trace_path = run_dir / "typesafety-trace.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    clone_root = CLONE_BASE / run_dir.name

    records = []
    for team in trace["teams"]:
        repo = clone_root / team["team"]
        rec: dict[str, Any] = {
            "team": team["team"],
            "metric_class": "type-safety syntactic counts (any/as/!)",
            "considered_methods": CONSIDERED_METHODS,
            "chosen_method": "typescript compiler AST",
            "held_loosely": HELD_LOOSELY,
        }
        if not repo.exists():
            rec["status"] = "clone_unavailable"
            rec["note"] = f"No clone at {repo}; cannot verify, self-report stands but remains unverified."
            records.append(rec)
            continue

        result = run_counter(repo)
        counts = result["counts"]
        verified = {"any": counts["any"], "as": counts["as"], "nonnull": counts["nonnull"]}
        verified["total"] = verified["any"] + verified["as"] + verified["nonnull"]
        rec["status"] = "verified"
        rec["tool"] = {"name": result["tool"], "ts_version": result["ts_version"],
                       "scope": result["scope"], "files": result["files"]}
        rec["verified_remaining"] = verified
        rec["checks"] = {}

        # Enrich the trace: each measured part gets a verified remaining-count,
        # a comparison to the claim, and its trust rung lifts to "verified".
        for pid in ("any", "as", "nonnull", "total"):
            part = team["parts"].get(pid)
            if not part:
                continue
            claimed_after = part.get("after")
            chk = flag(verified[pid], claimed_after)
            rec["checks"][pid] = {"verified": verified[pid], "claimed_after": claimed_after, **chk}
            part["verified"] = {
                "remaining": verified[pid],
                "claimed_after": claimed_after,
                "discrepancy": chk["discrepancy"],
                "flagged": chk["flagged"],
                "method": "typescript-ast",
            }
            part["trust"] = "verified"
        team["verification"] = rec
        records.append(rec)

    trace["verification"] = {
        "verified_state": "after_only",
        "baseline_gap": "Verified % reduction not computed — a common baseline (original ShipShape) has not been independently counted. Recorded, not faked.",
        "records": records,
    }
    trace_path.write_text(json.dumps(trace, indent=2), encoding="utf-8")
    (run_dir / "verification.json").write_text(
        json.dumps(trace["verification"], indent=2), encoding="utf-8")
    return trace["verification"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=None)
    args = parser.parse_args()
    run_dir = args.run_dir or latest_run()
    summary = verify(run_dir)
    for rec in summary["records"]:
        if rec.get("status") != "verified":
            print(f"  {rec['team']}: {rec['status']}")
            continue
        v = rec["verified_remaining"]
        flags = [pid for pid, c in rec["checks"].items() if c["flagged"]]
        print(f"  {rec['team']}: verified remaining any={v['any']} as={v['as']} !={v['nonnull']} total={v['total']}"
              + (f"  ⚠ self-report rejected on: {', '.join(flags)}" if flags else ""))
    print(f"\nWrote {run_dir/'verification.json'} and enriched typesafety-trace.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
