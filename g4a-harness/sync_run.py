"""Merge cumulative run artifacts (agent measurements, verification) into traces.

The HTML renderers read *-trace.json, not agent-measurements/ directly. This module
is the adapter layer: every new measurement updates the traces, then render_run
regenerates scorecard/compare/workbench from the latest cumulative state.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CLONE_BASE = Path("/private/tmp/g4a-bench-prototype/g4a-c5-2/week-4")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def team_from_repo(repo: str | Path) -> str:
    return Path(repo).name


def kb_from_bytes(n: int | float | None) -> float | None:
    if n is None:
        return None
    return round(float(n) / 1024, 2)


def load_agent_measurements(run_dir: Path) -> list[dict[str, Any]]:
    meas_dir = run_dir / "agent-measurements"
    if not meas_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(meas_dir.glob("*.json")):
        try:
            data = read_json(path)
            data["_artifact"] = path.name
            out.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return out


def infer_criterion_id(rec: dict[str, Any]) -> str | None:
    cid = rec.get("criterion_id")
    if cid:
        return cid
    name = (rec.get("_artifact") or "").lower()
    if name.startswith("bundle-"):
        return "cat-2-bundle"
    if name.startswith("typesafety-gate-"):
        return "cat-1-typesafety-gate"
    return None


def latest_by_team_criterion(measurements: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Keep newest measurement per (criterion_id, team)."""
    best: dict[tuple[str, str], dict[str, Any]] = {}

    def sort_key(rec: dict[str, Any]) -> str:
        return rec.get("completed_at") or ""

    for rec in measurements:
        cid = infer_criterion_id(rec)
        if not cid:
            continue
        rec = {**rec, "criterion_id": cid}
        team = team_from_repo(rec.get("repo", ""))
        key = (cid, team)
        prev = best.get(key)
        if prev is None or sort_key(rec) >= sort_key(prev):
            best[key] = rec
    return best


def extract_bundle_metrics(vv: dict[str, Any]) -> dict[str, float | None]:
    initial_b = (
        vv.get("initial_load_js_raw_bytes")
        or vv.get("entry_chunk_js_bytes")
        or vv.get("entry_js_bytes")
    )
    total_b = (
        vv.get("total_js_css_bytes")
        or vv.get("total_js_bytes")
        or vv.get("total_assets_js_css_bytes")
    )
    return {
        "initial_load_kb": kb_from_bytes(initial_b),
        "initial_load_gzip_kb": vv.get("initial_load_js_gzip_KB"),
        "total_js_css_kb": kb_from_bytes(total_b),
    }


def flag_kb(verified_kb: float | None, claimed_kb: float | None) -> dict[str, Any]:
    if verified_kb is None or claimed_kb is None:
        return {"flagged": False, "discrepancy_kb": None}
    disc = verified_kb - claimed_kb
    flagged = abs(disc) > max(5.0, 0.03 * max(claimed_kb, 1))
    return {"flagged": flagged, "discrepancy_kb": round(disc, 2)}


def sync_bundle_trace(run_dir: Path, latest: dict[tuple[str, str], dict[str, Any]]) -> bool:
    path = run_dir / "bundle-trace.json"
    if not path.exists():
        return False
    trace = read_json(path)
    changed = False
    path_map = {
        "initial-load-code-splitting": "initial_load_kb",
        "total-production-bundle": "total_js_css_kb",
    }
    for team in trace.get("teams") or []:
        tid = team["team"]
        rec = latest.get(("cat-2-bundle", tid))
        if not rec or rec.get("result", {}).get("status") == "could_not_measure":
            continue
        result = rec["result"]
        if result.get("run_mode") not in (None, "establish", "replay", "challenge"):
            continue
        vv = result.get("verified_values") or {}
        metrics = extract_bundle_metrics(vv)
        for tp in team.get("target_paths") or []:
            key = path_map.get(tp["id"])
            if not key:
                continue
            after_kb = metrics.get(key)
            if after_kb is None:
                continue
            chk = flag_kb(after_kb, tp.get("after_kb"))
            tp["verified"] = {
                "after_kb": after_kb,
                "claimed_after_kb": tp.get("after_kb"),
                "artifact": rec.get("_artifact"),
                "method": result.get("method", "")[:240],
                "confidence": result.get("confidence"),
                "replay_outcome": result.get("replay_outcome"),
                **chk,
            }
            tp["state"] = f"{'passes' if str(tp.get('state', '')).startswith('passes') else 'fails'}_verified_harness"
            changed = True
        states = {s["name"]: s for s in team.get("evidence_states") or []}
        if "independent_reproduction" in states:
            states["independent_reproduction"]["value"] = "verified"
            states["independent_reproduction"]["note"] = (
                f"Harness production build + dist measurement ({rec.get('_artifact')})."
            )
        else:
            team.setdefault("evidence_states", []).append({
                "name": "independent_reproduction",
                "value": "verified",
                "note": f"Harness measured ({rec.get('_artifact')}).",
            })
        team["harness_measurement"] = {
            "artifact": rec.get("_artifact"),
            "completed_at": rec.get("completed_at"),
            "confidence": result.get("confidence"),
            "replay_outcome": result.get("replay_outcome"),
        }
        changed = True
    if changed:
        for step in trace.get("process_steps") or []:
            if step.get("id") == "independent-reproduction":
                step["output"] = "Harness has rebuilt production bundles and measured dist for some or all repos."
        write_json(path, trace)
    return changed


def judgment_state_from_text(text: str) -> str:
    t = text.lower()
    if any(x in t for x in ("fail", "superficial", "overstated", "false", "not meaningful", "partially meaningful")):
        if "partially" in t or "mixed" in t:
            return "needs_review"
        if "not meaningful" in t or "superficial" in t and "not superficial" not in t:
            return "fail"
    if any(x in t for x in ("meaningful", "pass", "genuine", "not superficial")):
        return "pass"
    return "needs_review"


def sync_typesafety_judgment(run_dir: Path, latest: dict[tuple[str, str], dict[str, Any]]) -> bool:
    path = run_dir / "typesafety-trace.json"
    if not path.exists():
        return False
    trace = read_json(path)
    changed = False
    for team in trace.get("teams") or []:
        tid = team["team"]
        rec = latest.get(("cat-1-typesafety-gate", tid))
        if not rec:
            continue
        result = rec.get("result") or {}
        qj = result.get("qualitative_judgment") or ""
        if not qj:
            continue
        state = judgment_state_from_text(qj)
        for gate in team.get("judgment_gates") or []:
            if gate.get("id") == "fixes_meaningful":
                gate["state"] = state
                gate["note"] = qj[:400]
                gate["trust"] = "verified" if result.get("replay_outcome") == "succeeded" else "artifact_backed"
                gate["artifact"] = rec.get("_artifact")
                changed = True
        team["qualitative_gate"] = {
            "artifact": rec.get("_artifact"),
            "completed_at": rec.get("completed_at"),
            "confidence": result.get("confidence"),
            "judgment_excerpt": qj[:500],
            "replay_outcome": result.get("replay_outcome"),
        }
        # Lift part judgments when agent gave explicit AST-backed qualitative read
        vv = result.get("verified_values") or {}
        if vv.get("ast_total") is not None:
            for pid, key in (("any", "ast_any"), ("as", "ast_as"), ("nonnull", "ast_nonnull"), ("total", "ast_total")):
                part = team.get("parts", {}).get(pid)
                if not part:
                    continue
                val = vv.get(key)
                if val is None:
                    continue
                part.setdefault("verified", {})
                part["verified"].update({
                    "remaining": val,
                    "method": "typescript-ast-agent",
                    "artifact": rec.get("_artifact"),
                })
                part["trust"] = "verified"
                if pid == "as" and val > 100 and "superficial" in qj.lower():
                    part["judgment"] = "needs_review"
                changed = True
    if changed:
        write_json(path, trace)
    return changed


def try_verify_typesafety(run_dir: Path) -> bool:
    trace_path = run_dir / "typesafety-trace.json"
    if not trace_path.exists():
        return False
    clone_root = CLONE_BASE / run_dir.name
    if not clone_root.is_dir():
        return False
    try:
        from verify_typesafety import verify
        verify(run_dir)
        return True
    except Exception:
        return False


def build_run_state(run_dir: Path, latest: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    ledger_lines: list[dict[str, Any]] = []
    ledger_path = run_dir / "ledger.jsonl"
    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    ledger_lines.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    yardsticks = {}
    ys_path = run_dir / "yardsticks.json"
    if ys_path.exists():
        yardsticks = read_json(ys_path).get("yardsticks", {})
    return {
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "updated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent_measurements": {
            f"{cid}:{team}": {
                "artifact": rec.get("_artifact"),
                "completed_at": rec.get("completed_at"),
                "status": rec.get("result", {}).get("status"),
                "run_mode": rec.get("result", {}).get("run_mode"),
                "replay_outcome": rec.get("result", {}).get("replay_outcome"),
            }
            for (cid, team), rec in latest.items()
        },
        "ledger_tail": ledger_lines[-20:],
        "yardstick_ids": list(yardsticks.keys()),
    }


def sync_all(run_dir: Path) -> dict[str, Any]:
    measurements = load_agent_measurements(run_dir)
    latest = latest_by_team_criterion(measurements)
    bundle = sync_bundle_trace(run_dir, latest)
    judgment = sync_typesafety_judgment(run_dir, latest)
    verified = try_verify_typesafety(run_dir)
    state = build_run_state(run_dir, latest)
    write_json(run_dir / "run-state.json", state)
    return {"bundle_trace": bundle, "typesafety_judgment": judgment, "typesafety_verify": verified, "run_state": str(run_dir / "run-state.json")}


def refresh_html(run_dir: Path) -> list[Path]:
    """Sync traces from cumulative data, then regenerate all HTML views."""
    import sys
    harness = Path(__file__).resolve().parent
    if str(harness) not in sys.path:
        sys.path.insert(0, str(harness))

    sync_all(run_dir)
    outputs: list[Path] = []
    import render_scorecard
    import render_compare
    import render_workbench

    for mod, name in (
        (render_scorecard, "scorecard.html"),
        (render_compare, "compare.html"),
        (render_workbench, "workbench.html"),
    ):
        out = run_dir / name
        out.write_text(mod.render(run_dir), encoding="utf-8")
        outputs.append(out)
    return outputs


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Sync agent data into traces and refresh HTML")
    p.add_argument("--run-dir", type=Path, required=True)
    args = p.parse_args()
    paths = refresh_html(args.run_dir)
    summary = read_json(args.run_dir / "run-state.json")
    print(json.dumps({"run_state": str(args.run_dir / "run-state.json"), "measurements": len(summary.get("agent_measurements", {}))}, indent=2))
    for p in paths:
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
