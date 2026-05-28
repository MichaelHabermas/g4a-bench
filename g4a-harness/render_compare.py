#!/usr/bin/env python3
"""Render a decision-surface comparison page for a benchmark run.

Reads every *-trace.json in the run dir and reshapes them into legible decision
surfaces instead of an evidence dump. The organizing model is a *confidence
ladder* plus, where the spec demands it, *judgment gates*. Every (repo, path)
cell carries up to three orthogonal axes that are never merged into one grade:

  outcome  : passes / fails / unclaimed     (against one specific spec path)
  trust    : claimed -> reported-math -> artifact-backed -> reproduced
  gates    : qualitative bars automation cannot settle (pass/fail/needs_review/claimed)

Confidence is the rung, not a percentage. The matrix is the ladder map; the
Climb tab is how to move a cell up a rung or resolve a gate.

Criteria are modeled generically: each has 1+ target paths and 0+ gates.
- Bundle Size  : two valid paths, no gates (ambiguity = which path).
- Type Safety  : one path, three gates (ambiguity = is the fix meaningful).
Adding a criterion = dropping another *-trace.json in the run dir.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path("/Users/michaelhabermas/repos/GAI/g4a-bench")
RUNS_DIR = ROOT / "g4a-benchmarks/g4a-c5-2/week-4/runs"

TRUST_RUNGS = [
    ("claimed", "claimed"),
    ("reported-math", "reported math"),
    ("artifact-backed", "artifact-backed"),
    ("reproduced", "reproduced"),
]
TRUST_INDEX = {key: i for i, (key, _) in enumerate(TRUST_RUNGS)}

# Gate state -> (css class, glyph) and a compact letter per known gate id.
GATE_GLYPH = {"pass": "✓", "fail": "✗", "needs_review": "?", "claimed": "•"}
GATE_CSS = {"pass": "g-pass", "fail": "g-fail", "needs_review": "g-review", "claimed": "g-claimed"}
GATE_LETTER = {
    "functionality_preserved": "F",
    "fixes_meaningful": "M",
    "counting_comparable": "C",
}

PATH_LABELS = {
    "total-production-bundle": "Total bundle",
    "initial-load-code-splitting": "Initial load",
    "violation-reduction": "Violations",
}


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_run() -> Path:
    candidates = sorted(path for path in RUNS_DIR.glob("*") if path.is_dir())
    if not candidates:
        raise SystemExit(f"No run directories found under {RUNS_DIR}")
    return candidates[-1]


def short_team(name: str) -> str:
    for token in ("michaelhabermas", "daltondinderman", "shivkanthalu"):
        if token in name:
            return token
    tail = name.rstrip("/").split("-")
    return tail[-1] if tail else name


def evidence_state_map(team: dict[str, Any]) -> dict[str, str]:
    return {item["name"]: item["value"] for item in team.get("evidence_states") or []}


def path_outcome(path: dict[str, Any]) -> str:
    state = str(path.get("state", ""))
    if state.startswith("passes_"):
        return "passes"
    if state.startswith("fails_"):
        return "fails"
    return "unclaimed"


def path_trust(path: dict[str, Any], states: dict[str, str]) -> str:
    if states.get("independently_reproduced") == "yes":
        return "reproduced"
    state = str(path.get("state", ""))
    if "artifact_math" in state:
        return "artifact-backed"
    if "markdown_math" in state:
        return "reported-math"
    return "reported-math" if path_outcome(path) != "unclaimed" else "claimed"


def comparability_flag(states: dict[str, str]) -> dict[str, str] | None:
    value = states.get("comparability")
    if value in (None, "verified", "yes"):
        return None
    label = {
        "needs_agent_review": "comparability unverified — needs review",
        "plausible_not_verified": "comparability plausible, not verified",
    }.get(value, f"comparability: {value}")
    return {"label": label}


def confidence_band(trust: str, states: dict[str, str]) -> str:
    rung = TRUST_INDEX[trust]
    if rung >= 3:
        return "high"
    if rung == 2:
        return "medium" if states.get("comparability") == "plausible_not_verified" else "low-medium"
    if rung == 1:
        return "low"
    return "none"


def make_cell(path: dict[str, Any], states: dict[str, str], unit: str) -> dict[str, Any]:
    before = path.get("before", path.get("before_kb"))
    after = path.get("after", path.get("after_kb"))
    outcome = path_outcome(path)
    trust = path_trust(path, states)
    return {
        "outcome": outcome,
        "trust": trust,
        "trust_rung": TRUST_INDEX[trust],
        "confidence": confidence_band(trust, states),
        "before": before,
        "after": after,
        "unit": unit,
        "reduction_percent": path.get("reduction_percent"),
        "threshold": path.get("spec_threshold", ""),
        "interpretation": path.get("interpretation", ""),
        "comparability": comparability_flag(states),
    }


def readiness_profile(team: dict[str, Any], states: dict[str, str], gate_defs: list, gates: dict) -> dict[str, Any]:
    paths = team.get("target_paths") or []
    any_pass = any(path_outcome(p) == "passes" for p in paths)
    artifact = states.get("artifact_backed") == "yes"
    markdown = states.get("artifact_backed") == "markdown_backed"
    explicit = states.get("path_choice_explicit") == "yes"
    comparable = states.get("comparability") in {"plausible_not_verified", "needs_agent_review"}
    reproduced = states.get("independently_reproduced") == "yes"

    dims = {
        "satisfies a path": (3 if any_pass else 0, 3),
        "evidence backing": (3 if artifact else 1 if markdown else 0, 3),
        "path clarity": (2 if explicit else 0, 2),
        "comparability": (1 if comparable else 0, 1),
        "reproduced": (3 if reproduced else 0, 3),
    }
    if gate_defs:
        cleared = sum(1 for g in gates.values() if g.get("state") == "pass")
        dims["gates cleared"] = (round(3 * cleared / len(gate_defs)), 3)
    return {"dims": {k: v[0] for k, v in dims.items()}, "maxes": {k: v[1] for k, v in dims.items()}}


def load_criterion(trace: dict[str, Any]) -> dict[str, Any]:
    """Normalize one trace file into a criterion + per-team payload."""
    kind = trace.get("artifact_kind")
    if kind == "bundle_size_process_trace":
        meta = {"id": "bundle-size", "name": "Bundle Size", "unit": "KB", "gate_defs": []}
    elif kind == "type_safety_process_trace":
        crit = trace.get("criterion", {})
        meta = {
            "id": crit.get("id", "type-safety"),
            "name": crit.get("name", "Type Safety"),
            "unit": crit.get("unit", "violations"),
            "gate_defs": trace.get("gate_defs", []),
        }
    else:
        raise SystemExit(f"Unknown trace artifact_kind: {kind}")

    unit = meta["unit"]
    gate_defs = meta["gate_defs"]
    gate_label = {g["id"]: g["label"] for g in gate_defs}

    paths_meta = []
    first = trace["teams"][0]
    for p in first.get("target_paths") or []:
        paths_meta.append(
            {"id": p["id"], "label": PATH_LABELS.get(p["id"], p["id"]), "threshold": p.get("spec_threshold", "")}
        )
    meta["paths"] = paths_meta

    teams = {}
    for team in trace["teams"]:
        states = evidence_state_map(team)
        path_cells = {p["id"]: make_cell(p, states, unit) for p in team.get("target_paths") or []}
        gates = {}
        for g in team.get("judgment_gates") or []:
            gates[g["id"]] = {"state": g["state"], "note": g.get("note", ""), "label": gate_label.get(g["id"], g["id"])}
        inventory = team.get("discovery_inventory") or {}
        teams[team["team"]] = {
            "paths": path_cells,
            "gates": gates,
            "provisional": team.get("provisional_judgment", {}),
            "claims": team.get("claim_text") or [],
            "caveats": team.get("caveats") or [],
            "primary_evidence": team.get("primary_evidence") or [],
            "next_judgments": team.get("next_judgments") or [],
            "agent_questions": team.get("agent_questions") or [],
            "discovery_counts": {k: (len(v) if isinstance(v, list) else v) for k, v in inventory.items()},
            "shape": team.get("team_shape", ""),
            "commit": team.get("commit_sha", ""),
            "repo_url": team.get("repo_url", ""),
            "readiness": readiness_profile(team, states, gate_defs, gates),
        }
    return {"meta": meta, "teams": teams}


def build_model(run_dir: Path) -> dict[str, Any]:
    order = ["bundle-trace.json", "typesafety-trace.json"]
    present = [run_dir / name for name in order if (run_dir / name).exists()]
    present += [p for p in sorted(run_dir.glob("*-trace.json")) if p not in present]

    criteria = []
    loaded = []
    for path in present:
        try:
            loaded.append(load_criterion(read_json(path)))
        except SystemExit:
            continue

    # Team order from the first criterion that has teams.
    team_ids: list[str] = []
    for entry in loaded:
        for tid in entry["teams"]:
            if tid not in team_ids:
                team_ids.append(tid)

    teams = []
    for tid in team_ids:
        by_crit = {}
        repo_url = commit = ""
        for entry in loaded:
            data = entry["teams"].get(tid)
            if data:
                by_crit[entry["meta"]["id"]] = data
                repo_url = repo_url or data["repo_url"]
                commit = commit or data["commit"]
        teams.append(
            {"team": tid, "handle": short_team(tid), "repo_url": repo_url, "commit": commit, "byCriterion": by_crit}
        )

    for entry in loaded:
        m = entry["meta"]
        criteria.append({"id": m["id"], "name": m["name"], "unit": m["unit"], "paths": m["paths"], "gate_defs": m["gate_defs"]})

    return {"criteria": criteria, "teams": teams}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def gate_strip(gate_defs: list, gates: dict) -> str:
    if not gate_defs:
        return ""
    chips = []
    for g in gate_defs:
        state = gates.get(g["id"], {}).get("state", "claimed")
        letter = GATE_LETTER.get(g["id"], g["id"][:1].upper())
        chips.append(
            f"<span class='gate {GATE_CSS.get(state, 'g-claimed')}' title='{esc(g['label'])}: {esc(state)}'>"
            f"{letter}{GATE_GLYPH.get(state, '')}</span>"
        )
    return f"<div class='gate-strip'>{''.join(chips)}</div>"


def matrix_html(model: dict[str, Any]) -> str:
    cols = []
    for crit in model["criteria"]:
        for path in crit["paths"]:
            cols.append((crit, path))

    header_cells = "".join(
        f"<th><div class='col-crit'>{esc(crit['name'])}</div>"
        f"<div class='col-path'>{esc(path['label'])}</div>"
        f"<div class='col-thr'>{esc(path['threshold'])}</div></th>"
        for crit, path in cols
    )

    rows = []
    for team in model["teams"]:
        cells = [f"<th class='rowhead'>{esc(team['handle'])}</th>"]
        for crit, path in cols:
            cdata = team["byCriterion"].get(crit["id"])
            cell = cdata["paths"].get(path["id"]) if cdata else None
            if not cell:
                cells.append("<td class='cell empty'>—</td>")
                continue
            reduction = cell["reduction_percent"]
            sign = "+" if isinstance(reduction, (int, float)) and reduction >= 0 else ""
            warn = "⚠" if cell.get("comparability") else ""
            strip = gate_strip(crit["gate_defs"], cdata["gates"])
            cells.append(
                f"<td class='cell outcome-{cell['outcome']}' "
                f"data-team='{esc(team['team'])}' data-crit='{esc(crit['id'])}' data-path='{esc(path['id'])}' "
                f"tabindex='0' role='button'>"
                f"<div class='cell-top'><span class='out'>{cell['outcome']}</span>"
                f"<span class='warnflag'>{warn}</span></div>"
                f"<div class='cell-num'>{sign}{esc(reduction)}%</div>"
                f"<div class='cell-foot'><span class='rung rung-{cell['trust_rung']}'>{esc(cell['trust'])}</span></div>"
                f"{strip}"
                f"</td>"
            )
        rows.append(f"<tr>{''.join(cells)}</tr>")

    has_gates = any(c["gate_defs"] for c in model["criteria"])
    gate_legend = (
        "&nbsp;·&nbsp; gates: "
        "<span class='gate g-pass'>✓</span> pass "
        "<span class='gate g-review'>?</span> needs review "
        "<span class='gate g-fail'>✗</span> fail "
        "<span class='gate g-claimed'>•</span> claimed"
        if has_gates else ""
    )
    return f"""
    <table class="matrix">
      <thead><tr><th class="corner">repo \\ path</th>{header_cells}</tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    <p class="legend">
      <span class="chip outcome-passes">passes</span>
      <span class="chip outcome-fails">fails</span>
      &nbsp;·&nbsp; trust:
      <span class="rung rung-0">claimed</span> →
      <span class="rung rung-1">reported math</span> →
      <span class="rung rung-2">artifact-backed</span> →
      <span class="rung rung-3">reproduced</span>
      &nbsp;·&nbsp; <span class="warnflag">⚠</span> comparability unverified
      {gate_legend}
      &nbsp;·&nbsp; <em>click any cell for evidence, gates &amp; judgment</em>
    </p>
    """


def readiness_html(model: dict[str, Any]) -> str:
    cards = []
    for team in model["teams"]:
        blocks = []
        for crit in model["criteria"]:
            cdata = team["byCriterion"].get(crit["id"])
            if not cdata:
                continue
            profile = cdata["readiness"]
            bars = []
            for dim, value in profile["dims"].items():
                mx = profile["maxes"][dim]
                pct = (value / mx * 100) if mx else 0
                cls = "full" if value == mx and mx > 0 else "partial" if value > 0 else "zero"
                bars.append(
                    f"<div class='profile-row'><span class='profile-label'>{esc(dim)}</span>"
                    f"<span class='profile-track'><i class='{cls}' style='width:{pct:.0f}%'></i></span>"
                    f"<span class='profile-val'>{value}/{mx}</span></div>"
                )
            blocks.append(f"<div class='crit-block'><h4>{esc(crit['name'])}</h4>{''.join(bars)}</div>")
        cards.append(f"<article class='profile-card'><h3>{esc(team['handle'])}</h3>{''.join(blocks)}</article>")
    return (
        "<p class='muted note'>Readiness is a <strong>shape per criterion</strong>, not one number. "
        "Two things jump out: the <em>reproduced</em> row is empty everywhere (the cohort ceiling), and "
        "on Type Safety the <em>gates cleared</em> row is near-empty — the violation counts pass, but the "
        "qualitative bars are unresolved.</p>"
        f"<div class='profiles'>{''.join(cards)}</div>"
    )


def lanes_html(model: dict[str, Any]) -> str:
    DOMAIN_MIN, DOMAIN_MAX = -10.0, 100.0

    def pos(x: float) -> float:
        frac = (x - DOMAIN_MIN) / (DOMAIN_MAX - DOMAIN_MIN)
        return max(0.0, min(1.0, frac)) * 100

    lanes = []
    for crit in model["criteria"]:
        for path in crit["paths"]:
            thr = "".join(ch for ch in path["threshold"] if ch.isdigit())
            thr_val = float(thr) if thr else 0.0
            dots = []
            for team in model["teams"]:
                cdata = team["byCriterion"].get(crit["id"])
                cell = cdata["paths"].get(path["id"]) if cdata else None
                if not cell or cell["reduction_percent"] is None:
                    continue
                x = float(cell["reduction_percent"])
                dots.append(
                    f"<div class='lane-dot outcome-{cell['outcome']} rungdot-{cell['trust_rung']}' "
                    f"style='left:{pos(x):.1f}%' title='{esc(team['handle'])}: {x}% — {esc(cell['trust'])}'>"
                    f"<span class='lane-dot-label'>{esc(team['handle'])}</span></div>"
                )
            lanes.append(
                f"<div class='lane-block'>"
                f"<div class='lane-title'>{esc(crit['name'])} · {esc(path['label'])} "
                f"<span class='muted'>(needs {esc(path['threshold'])})</span></div>"
                f"<div class='lane'>"
                f"<div class='lane-zero' style='left:{pos(0.0):.1f}%'></div>"
                f"<div class='lane-thr' style='left:{pos(thr_val):.1f}%'><span>{esc(int(thr_val))}% target</span></div>"
                f"{''.join(dots)}</div>"
                f"<div class='lane-axis'><span>−10%</span><span>0</span><span>50%</span><span>100%</span></div>"
                f"</div>"
            )
    return (
        "<p class='muted note'>Each path is its own lane with its own target line. Position = measured "
        "reduction; ring = trust rung. Watch Type Safety: Shiv's dot is pinned at 100% on the thinnest ring "
        "(reported-math) while Michael and Dalton sit lower on solid rings — extreme outcome, weakest support. "
        "That is the apples-vs-Macintosh-apples problem in one picture.</p>"
        f"{''.join(lanes)}"
    )


def climb_html(model: dict[str, Any]) -> str:
    NEXT_ACTION = {
        "claimed": "Find or extract reported before/after numbers.",
        "reported-math": "Locate or regenerate raw machine-readable before/after artifacts.",
        "artifact-backed": "Rebuild/rescan from a clean clone and confirm the measurement directionally.",
        "reproduced": "Top rung — spot-check comparability only.",
    }
    rows = []
    for team in model["teams"]:
        for crit in model["criteria"]:
            cdata = team["byCriterion"].get(crit["id"])
            if not cdata:
                continue
            for path in crit["paths"]:
                cell = cdata["paths"].get(path["id"])
                if not cell:
                    continue
                actions = [esc(NEXT_ACTION.get(cell["trust"], ""))]
                comp = cell.get("comparability")
                if comp:
                    actions.append(f"<span class='climb-warn'>⚠ {esc(comp['label'])}</span>")
                for gid, g in cdata["gates"].items():
                    if g["state"] in ("needs_review", "fail", "claimed"):
                        actions.append(f"<span class='climb-gate {GATE_CSS[g['state']]}'>resolve gate: {esc(g['label'])} ({esc(g['state'])})</span>")
                rows.append(
                    f"<tr class='outcome-{cell['outcome']}'>"
                    f"<th>{esc(team['handle'])}</th>"
                    f"<td>{esc(crit['name'])} · {esc(path['label'])}</td>"
                    f"<td><span class='out'>{cell['outcome']}</span></td>"
                    f"<td><span class='rung rung-{cell['trust_rung']}'>{esc(cell['trust'])}</span></td>"
                    f"<td>{'<br>'.join(actions)}</td>"
                    f"</tr>"
                )
    return (
        "<p class='muted note'>Every cell sits on a rung and may carry unresolved gates. The benchmark's "
        "job is to move cells <em>up</em> and settle gates. Bundle cells top out at artifact-backed "
        "(nothing reproduced); Type Safety cells additionally need a human/agent to rule on whether the "
        "fixes were meaningful.</p>"
        "<table class='climb'><thead><tr><th>Repo</th><th>Criterion · Path</th><th>Outcome</th>"
        "<th>Trust rung</th><th>To climb / resolve</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render(run_dir: Path) -> str:
    model = build_model(run_dir)
    data_json = json.dumps(model)
    crit_names = ", ".join(c["name"] for c in model["criteria"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>G4A Benchmark · Compare</title>
  <style>
    :root {{
      --ink:#191919; --muted:#6b655d; --paper:#f5f1e9; --panel:#fffdf8; --line:#d6cdbf;
      --good:#1c6b54; --good-bg:#e6f3ec; --bad:#9c2f25; --bad-bg:#f8e1de;
      --grey:#7c756b; --grey-bg:#ece7dd; --blue:#274f7f; --warn:#9a5a10; --warn-bg:#fdf0d8;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--paper); color:var(--ink);
      font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; line-height:1.4; }}
    main {{ max-width:1200px; margin:0 auto; padding:26px 20px 60px; }}
    header {{ border-bottom:2px solid var(--ink); padding-bottom:14px; }}
    h1 {{ margin:0; font-size:clamp(30px,4.5vw,52px); line-height:.96; }}
    h2 {{ margin:0 0 12px; font-size:22px; }}
    h3 {{ margin:0 0 8px; font-size:16px; }}
    h4 {{ margin:0 0 6px; font-size:11px; text-transform:uppercase; letter-spacing:.07em; color:var(--muted); }}
    .muted {{ color:var(--muted); }} .small {{ font-size:12px; }}
    .note {{ max-width:820px; }}
    .tabs {{ display:flex; gap:6px; margin:20px 0 0; border-bottom:1px solid var(--line); }}
    .tab-button {{ border:1px solid var(--line); border-bottom:0; background:#ebe3d6; color:var(--ink);
      padding:9px 15px; font-weight:750; cursor:pointer; font-size:14px; }}
    .tab-button.active {{ background:var(--panel); color:var(--blue); }}
    .tab {{ display:none; background:var(--panel); border:1px solid var(--line); border-top:0; padding:20px; }}
    .tab.active {{ display:block; }}

    table.matrix {{ border-collapse:separate; border-spacing:6px; width:100%; }}
    .matrix th.corner {{ text-align:left; font-size:12px; color:var(--muted); }}
    .matrix thead th {{ background:#ece4d7; border:1px solid var(--line); padding:8px 10px; text-align:left; vertical-align:top; }}
    .col-crit {{ font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); }}
    .col-path {{ font-weight:800; font-size:15px; }}
    .col-thr {{ font-size:11px; color:var(--muted); }}
    .matrix th.rowhead {{ text-align:left; background:#ece4d7; border:1px solid var(--line); padding:8px 10px; }}
    .cell {{ border:1px solid var(--line); padding:9px 11px; cursor:pointer; min-width:150px;
      transition:transform .05s ease, box-shadow .1s ease; }}
    .cell:hover, .cell:focus {{ transform:translateY(-1px); box-shadow:0 2px 0 var(--ink); outline:none; }}
    .cell.empty {{ cursor:default; color:var(--muted); text-align:center; }}
    .cell-top {{ display:flex; justify-content:space-between; align-items:center; }}
    .cell .out {{ font-weight:850; text-transform:uppercase; letter-spacing:.04em; font-size:13px; }}
    .cell-num {{ font-size:24px; font-weight:800; margin:2px 0 4px; }}
    .warnflag {{ color:var(--warn); font-weight:800; }}
    .outcome-passes {{ background:var(--good-bg); }} .outcome-passes .out {{ color:var(--good); }}
    .outcome-fails {{ background:var(--bad-bg); }} .outcome-fails .out {{ color:var(--bad); }}
    .outcome-unclaimed {{ background:var(--grey-bg); }} .outcome-unclaimed .out {{ color:var(--grey); }}

    .rung {{ display:inline-block; font-size:11px; font-weight:700; padding:2px 7px; border-radius:10px; border:1px solid currentColor; }}
    .rung-0 {{ color:#8a8178; }} .rung-1 {{ color:#9a5a10; background:#fdf0d8; }}
    .rung-2 {{ color:#274f7f; background:#e4ecf6; }} .rung-3 {{ color:#1c6b54; background:#e6f3ec; }}

    .gate-strip {{ display:flex; gap:4px; margin-top:7px; }}
    .gate {{ display:inline-flex; align-items:center; justify-content:center; min-width:22px; height:18px;
      padding:0 4px; font-size:11px; font-weight:800; border:1px solid currentColor; border-radius:3px; }}
    .g-pass {{ color:var(--good); background:var(--good-bg); }}
    .g-fail {{ color:var(--bad); background:var(--bad-bg); }}
    .g-review {{ color:var(--warn); background:var(--warn-bg); }}
    .g-claimed {{ color:var(--grey); background:var(--grey-bg); }}

    .legend {{ font-size:12px; color:var(--muted); margin-top:16px; }}
    .chip {{ display:inline-block; padding:2px 8px; border:1px solid var(--line); font-weight:750; font-size:11px; text-transform:uppercase; }}

    .profiles {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; margin-top:8px; }}
    .profile-card {{ border:1px solid var(--line); background:#fffaf1; padding:14px; }}
    .crit-block {{ margin:12px 0 4px; }}
    .crit-block + .crit-block {{ border-top:1px dashed var(--line); padding-top:10px; }}
    .profile-row {{ display:flex; align-items:center; gap:8px; margin:6px 0; font-size:12px; }}
    .profile-label {{ width:108px; color:var(--muted); }}
    .profile-track {{ flex:1; height:9px; background:#e3dbcd; position:relative; }}
    .profile-track i {{ display:block; height:100%; }}
    .profile-track i.full {{ background:var(--good); }}
    .profile-track i.partial {{ background:var(--blue); }}
    .profile-track i.zero {{ background:transparent; }}
    .profile-val {{ width:30px; text-align:right; font-weight:700; }}

    .lane-block {{ margin:22px 0; }}
    .lane-title {{ font-weight:800; margin-bottom:10px; font-size:15px; }}
    .lane {{ position:relative; height:54px; background:#fbf6ec; border:1px solid var(--line); }}
    .lane-zero {{ position:absolute; top:0; bottom:0; width:1px; background:#c9bda9; }}
    .lane-thr {{ position:absolute; top:0; bottom:0; width:2px; background:var(--bad); }}
    .lane-thr span {{ position:absolute; top:-2px; left:5px; font-size:10px; color:var(--bad); white-space:nowrap; font-weight:700; }}
    .lane-dot {{ position:absolute; top:50%; transform:translate(-50%,-50%); width:18px; height:18px; border-radius:50%; border:3px solid var(--ink); }}
    .lane-dot.outcome-passes {{ background:var(--good); }}
    .lane-dot.outcome-fails {{ background:var(--bad); }}
    .lane-dot.outcome-unclaimed {{ background:var(--grey); }}
    .rungdot-1 {{ border-color:#d8a24a; border-style:dotted; }}
    .rungdot-2 {{ border-color:#274f7f; }}
    .rungdot-3 {{ border-color:#1c6b54; border-width:4px; }}
    .lane-dot-label {{ position:absolute; top:20px; left:50%; transform:translateX(-50%); font-size:11px; font-weight:700; white-space:nowrap; }}
    .lane-axis {{ display:flex; justify-content:space-between; font-size:10px; color:var(--muted); margin-top:4px; }}

    table.climb {{ width:100%; border-collapse:collapse; font-size:13px; margin-top:6px; }}
    .climb th, .climb td {{ border:1px solid var(--line); padding:8px 10px; text-align:left; vertical-align:top; }}
    .climb thead th {{ background:#ece4d7; }}
    .climb .out {{ font-weight:800; text-transform:uppercase; font-size:11px; }}
    .climb tr.outcome-passes .out {{ color:var(--good); }}
    .climb tr.outcome-fails .out {{ color:var(--bad); }}
    .climb-warn {{ color:var(--warn); font-size:11px; }}
    .climb-gate {{ display:inline-block; font-size:11px; padding:1px 6px; border-radius:3px; border:1px solid currentColor; margin-top:3px; }}

    .scrim {{ position:fixed; inset:0; background:rgba(20,18,14,.4); display:none; }}
    .scrim.open {{ display:block; }}
    .drawer {{ position:fixed; top:0; right:0; bottom:0; width:min(470px,93vw); background:var(--panel);
      border-left:2px solid var(--ink); padding:22px; overflow-y:auto; transform:translateX(100%); transition:transform .16s ease; }}
    .drawer.open {{ transform:translateX(0); }}
    .drawer h2 {{ margin-top:0; }}
    .drawer .kv {{ margin:14px 0; }}
    .drawer .kv h4 {{ margin:0 0 4px; }}
    .drawer ul {{ margin:4px 0; padding-left:18px; font-size:13px; }}
    .drawer code {{ font-size:12px; background:#efe8da; padding:1px 4px; word-break:break-all; }}
    .drawer .big {{ font-size:26px; font-weight:800; }}
    .drawer .close {{ position:absolute; top:14px; right:16px; border:1px solid var(--line); background:#ebe3d6; cursor:pointer; padding:4px 10px; font-weight:800; }}
    .conf {{ display:inline-block; padding:2px 9px; border:1px solid currentColor; font-weight:800; font-size:11px; text-transform:uppercase; }}
    .conf-high {{ color:var(--good); }} .conf-medium, .conf-low-medium {{ color:var(--blue); }}
    .conf-low {{ color:var(--warn); }} .conf-none {{ color:var(--grey); }}
    .gaterow {{ display:flex; gap:8px; align-items:flex-start; margin:8px 0; font-size:13px; }}

    @media (max-width:820px) {{
      .profiles {{ grid-template-columns:1fr; }}
      table.matrix {{ display:block; overflow-x:auto; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <p class="muted">Week 4 · {esc(crit_names)} · Run {esc(run_dir.name)}</p>
      <h1>Compare</h1>
      <p class="muted note" style="margin-top:8px">Three axes, never merged: <strong>outcome</strong>
      (clears a path?), <strong>trust</strong> (claimed → reported → artifact-backed → reproduced), and —
      where the spec demands judgment — <strong>gates</strong> (functionality preserved, fixes meaningful,
      counting comparable). Confidence is the rung, not a percentage.</p>
    </header>

    <nav class="tabs">
      <button class="tab-button active" data-tab="compare">Compare</button>
      <button class="tab-button" data-tab="readiness">Readiness</button>
      <button class="tab-button" data-tab="paths">Paths</button>
      <button class="tab-button" data-tab="climb">Climb</button>
    </nav>

    <section id="compare" class="tab active">
      <h2>Outcome × Trust × Gates Matrix</h2>
      {matrix_html(model)}
    </section>
    <section id="readiness" class="tab">
      <h2>Readiness Profiles</h2>
      {readiness_html(model)}
    </section>
    <section id="paths" class="tab">
      <h2>Path Lanes</h2>
      {lanes_html(model)}
    </section>
    <section id="climb" class="tab">
      <h2>Climb the Ladder</h2>
      {climb_html(model)}
    </section>
  </main>

  <div class="scrim" id="scrim"></div>
  <aside class="drawer" id="drawer" aria-hidden="true">
    <button class="close" id="drawer-close">esc</button>
    <div id="drawer-body"></div>
  </aside>

  <script>
    const DATA = {data_json};
    const GLYPH = {{pass:'✓',fail:'✗',needs_review:'?',claimed:'•'}};
    const buttons = document.querySelectorAll('.tab-button');
    const tabs = document.querySelectorAll('.tab');
    buttons.forEach((b) => b.addEventListener('click', () => {{
      buttons.forEach((x) => x.classList.remove('active'));
      tabs.forEach((x) => x.classList.remove('active'));
      b.classList.add('active');
      document.getElementById(b.dataset.tab).classList.add('active');
    }}));

    const scrim = document.getElementById('scrim');
    const drawer = document.getElementById('drawer');
    const body = document.getElementById('drawer-body');
    function esc(s) {{ const d = document.createElement('div'); d.textContent = String(s ?? ''); return d.innerHTML; }}
    function li(items) {{ return (items||[]).map((x)=>`<li>${{esc(x)}}</li>`).join('') || '<li class="muted">none</li>'; }}

    function openCell(teamId, critId, pathId) {{
      const team = DATA.teams.find((t)=>t.team===teamId);
      const crit = DATA.criteria.find((c)=>c.id===critId);
      const path = crit.paths.find((p)=>p.id===pathId);
      const cdata = team.byCriterion[critId];
      const cell = cdata.paths[pathId];
      const claimed = (cdata.claims||[])[0] || '—';
      const comp = cell.comparability ? `<div class="kv"><h4>Comparability</h4><span class="conf conf-low">⚠ ${{esc(cell.comparability.label)}}</span></div>` : '';
      const gateClass = {{pass:'g-pass',fail:'g-fail',needs_review:'g-review',claimed:'g-claimed'}};
      const gates = Object.values(cdata.gates||{{}});
      const gateHtml = gates.length ? `<div class="kv"><h4>Judgment gates</h4>${{
        gates.map((g)=>`<div class="gaterow"><span class="gate ${{gateClass[g.state]||'g-claimed'}}">${{GLYPH[g.state]||''}}</span>
          <span><strong>${{esc(g.label)}}</strong> — ${{esc(g.state)}}<br><span class="muted small">${{esc(g.note)}}</span></span></div>`).join('')
      }}</div>` : '';
      const judg = (cdata.next_judgments||[]).map((j)=>`<li><strong>${{esc(j.judgment)}}</strong>: ${{esc(j.state)}}<br><span class="muted small">${{esc(j.why)}}</span></li>`).join('');
      const qs = (cdata.agent_questions||[]).length ? `<div class="kv"><h4>Questions for review</h4><ul>${{li(cdata.agent_questions)}}</ul></div>` : '';
      body.innerHTML = `
        <p class="muted small">${{esc(team.handle)}} · commit ${{esc((team.commit||'').slice(0,8))}}</p>
        <h2>${{esc(crit.name)}} · ${{esc(path.label)}}</h2>
        <div class="big outcome-${{cell.outcome}}" style="display:inline-block;padding:2px 6px">${{esc(cell.outcome)}} · ${{esc(cell.reduction_percent)}}%</div>
        <div class="kv"><h4>Trust rung / confidence</h4>
          <span class="rung rung-${{cell.trust_rung}}">${{esc(cell.trust)}}</span>
          &nbsp;<span class="conf conf-${{cell.confidence}}">${{esc(cell.confidence)}} confidence</span></div>
        ${{comp}}
        <div class="kv"><h4>Claimed</h4><p>${{esc(claimed)}}</p></div>
        <div class="kv"><h4>Measured (extracted)</h4>
          <p>${{esc(cell.before)}} → ${{esc(cell.after)}} ${{esc(cell.unit)}} &nbsp;·&nbsp; target ${{esc(cell.threshold)}}</p>
          <p class="muted small">${{esc(cell.interpretation)}}</p></div>
        ${{gateHtml}}
        <div class="kv"><h4>Evidence provenance</h4><ul>${{li(cdata.primary_evidence)}}</ul></div>
        <div class="kv"><h4>Unresolved judgment</h4><ul>${{judg || '<li class="muted">none</li>'}}</ul></div>
        ${{qs}}
        <div class="kv"><h4>Caveats</h4><ul>${{li(cdata.caveats)}}</ul></div>
      `;
      scrim.classList.add('open'); drawer.classList.add('open'); drawer.setAttribute('aria-hidden','false');
    }}
    function closeDrawer() {{ scrim.classList.remove('open'); drawer.classList.remove('open'); drawer.setAttribute('aria-hidden','true'); }}
    document.querySelectorAll('.cell:not(.empty)').forEach((c)=>{{
      const open = ()=>openCell(c.dataset.team, c.dataset.crit, c.dataset.path);
      c.addEventListener('click', open);
      c.addEventListener('keydown', (e)=>{{ if(e.key==='Enter'||e.key===' '){{e.preventDefault(); open();}} }});
    }});
    scrim.addEventListener('click', closeDrawer);
    document.getElementById('drawer-close').addEventListener('click', closeDrawer);
    document.addEventListener('keydown', (e)=>{{ if(e.key==='Escape') closeDrawer(); }});
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=None)
    args = parser.parse_args()
    run_dir = args.run_dir or latest_run()
    out = run_dir / "compare.html"
    out.write_text(render(run_dir), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
