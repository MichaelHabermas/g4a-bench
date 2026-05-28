#!/usr/bin/env python3
"""Render a decision-surface comparison page for a benchmark run.

Reads the existing bundle-trace.json and reshapes it into legible decision
surfaces instead of an evidence dump. The organizing model is a *confidence
ladder*: every (repo, path) cell carries two orthogonal axes —

  outcome  : passes / fails / unclaimed   (against one specific spec path)
  trust    : claimed -> reported-math -> artifact-backed -> reproduced

The page never collapses these into a single grade. Confidence is the rung,
not a percentage. The matrix is the ladder map; the Climb tab is how to move a
cell up a rung.

This is generalized: criteria are modeled as a list, each holding one or more
target paths. The bundle-size specimen is one criterion with two paths.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path("/Users/michaelhabermas/repos/GAI/g4a-bench")
RUNS_DIR = ROOT / "g4a-benchmarks/g4a-c5-2/week-4/runs"

# Trust ladder: rung index -> (key, label). Higher is stronger.
TRUST_RUNGS = [
    ("claimed", "claimed"),
    ("reported-math", "reported math"),
    ("artifact-backed", "artifact-backed"),
    ("reproduced", "reproduced"),
]
TRUST_INDEX = {key: i for i, (key, _) in enumerate(TRUST_RUNGS)}


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
    """Trim the canonical team id to a human-friendly handle."""
    tail = name.rstrip("/").split("-")
    # Names look like github-com-michaelhabermas-ship-shape or
    # labs-gauntletai-com-daltondinderman-shipshape.
    for token in ("michaelhabermas", "daltondinderman", "shivkanthalu"):
        if token in name:
            return token
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
    """Resolve the ladder rung this path currently sits on."""
    if states.get("independently_reproduced") == "yes":
        return "reproduced"
    state = str(path.get("state", ""))
    if "artifact_math" in state:
        return "artifact-backed"
    if "markdown_math" in state:
        return "reported-math"
    if path_outcome(path) != "unclaimed":
        return "reported-math"
    return "claimed"


def comparability_flag(states: dict[str, str]) -> dict[str, str] | None:
    value = states.get("comparability")
    if value in (None, "verified", "yes"):
        return None
    label = {
        "needs_agent_review": "comparability unverified — needs review",
        "plausible_not_verified": "comparability plausible, not verified",
    }.get(value, f"comparability: {value}")
    severity = "warn" if value == "plausible_not_verified" else "flag"
    return {"label": label, "severity": severity}


def confidence_band(trust: str, states: dict[str, str]) -> str:
    """Qualitative confidence — derived from rung, not invented precision."""
    rung = TRUST_INDEX[trust]
    if rung >= 3:
        return "high"
    if rung == 2:
        # Artifact-backed: medium, knocked down if comparability is unverified.
        return "medium" if states.get("comparability") == "plausible_not_verified" else "low-medium"
    if rung == 1:
        return "low"
    return "none"


def build_criteria(trace: dict[str, Any]) -> list[dict[str, Any]]:
    """Model the trace as criteria -> paths. Bundle is one criterion here."""
    # Path ids and thresholds are shared across teams; read from the first team.
    first = trace["teams"][0]
    path_defs = []
    for path in first.get("target_paths") or []:
        path_defs.append(
            {
                "id": path["id"],
                "label": {
                    "total-production-bundle": "Total bundle",
                    "initial-load-code-splitting": "Initial load",
                }.get(path["id"], path["id"]),
                "threshold": path.get("spec_threshold", ""),
            }
        )
    return [
        {
            "id": "bundle-size",
            "name": "Bundle Size",
            "spec_source": trace.get("spec_source", ""),
            "paths": path_defs,
        }
    ]


def build_cells(trace: dict[str, Any]) -> dict[str, Any]:
    """Compute the per-(team, path) cell model consumed by the page + drawer."""
    teams = []
    for team in trace["teams"]:
        states = evidence_state_map(team)
        path_by_id = {p["id"]: p for p in team.get("target_paths") or []}
        cells = {}
        for pid, path in path_by_id.items():
            outcome = path_outcome(path)
            trust = path_trust(path, states)
            cells[pid] = {
                "outcome": outcome,
                "trust": trust,
                "trust_rung": TRUST_INDEX[trust],
                "confidence": confidence_band(trust, states),
                "before_kb": path.get("before_kb"),
                "after_kb": path.get("after_kb"),
                "reduction_percent": path.get("reduction_percent"),
                "threshold": path.get("spec_threshold", ""),
                "interpretation": path.get("interpretation", ""),
                "comparability": comparability_flag(states),
            }
        inventory = team.get("discovery_inventory") or {}
        teams.append(
            {
                "team": team["team"],
                "handle": short_team(team["team"]),
                "shape": team.get("team_shape", ""),
                "commit": team.get("commit_sha", ""),
                "repo_url": team.get("repo_url", ""),
                "provisional": team.get("provisional_judgment", {}),
                "cells": cells,
                "claims": team.get("claim_text") or [],
                "non_claims": team.get("non_claims") or [],
                "caveats": team.get("caveats") or [],
                "primary_evidence": team.get("primary_evidence") or [],
                "next_judgments": team.get("next_judgments") or [],
                "agent_questions": team.get("agent_questions") or [],
                "discovery_counts": {k: len(v or []) for k, v in inventory.items()},
                "states": states,
                "readiness": readiness_profile(team, states),
            }
        )
    return {"teams": teams, "criteria": build_criteria(trace)}


def readiness_profile(team: dict[str, Any], states: dict[str, str]) -> dict[str, Any]:
    """Five-dimension shape used for the small-multiple profile bars."""
    paths = team.get("target_paths") or []
    any_pass = any(path_outcome(p) == "passes" for p in paths)
    artifact = states.get("artifact_backed") == "yes"
    markdown = states.get("artifact_backed") == "markdown_backed"
    explicit = states.get("path_choice_explicit") == "yes"
    comparable = states.get("comparability") in {"plausible_not_verified", "needs_agent_review"}
    reproduced = states.get("independently_reproduced") == "yes"

    dims = {
        "satisfies a path": 3 if any_pass else 0,
        "evidence backing": 3 if artifact else 1 if markdown else 0,
        "path clarity": 2 if explicit else 0,
        "comparability": 1 if comparable else 0,
        "reproduced": 3 if reproduced else 0,
    }
    maxes = {
        "satisfies a path": 3,
        "evidence backing": 3,
        "path clarity": 2,
        "comparability": 1,
        "reproduced": 3,
    }
    return {"dims": dims, "maxes": maxes}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def matrix_html(model: dict[str, Any]) -> str:
    teams = model["teams"]
    criteria = model["criteria"]
    cols = []
    for crit in criteria:
        for path in crit["paths"]:
            cols.append((crit, path))

    header_cells = "".join(
        f"<th><div class='col-crit'>{esc(crit['name'])}</div>"
        f"<div class='col-path'>{esc(path['label'])}</div>"
        f"<div class='col-thr'>{esc(path['threshold'])}</div></th>"
        for crit, path in cols
    )

    rows = []
    for team in teams:
        cells = [f"<th class='rowhead'>{esc(team['handle'])}</th>"]
        for crit, path in cols:
            cell = team["cells"].get(path["id"])
            if not cell:
                cells.append("<td class='cell empty'>—</td>")
                continue
            reduction = cell["reduction_percent"]
            sign = "+" if isinstance(reduction, (int, float)) and reduction >= 0 else ""
            warn = "⚠" if cell.get("comparability") else ""
            cells.append(
                f"<td class='cell outcome-{cell['outcome']}' "
                f"data-team='{esc(team['team'])}' data-path='{esc(path['id'])}' "
                f"tabindex='0' role='button'>"
                f"<div class='cell-top'>"
                f"<span class='out'>{cell['outcome']}</span>"
                f"<span class='warnflag'>{warn}</span>"
                f"</div>"
                f"<div class='cell-num'>{sign}{esc(reduction)}%</div>"
                f"<div class='cell-foot'>"
                f"<span class='rung rung-{cell['trust_rung']}'>{esc(cell['trust'])}</span>"
                f"</div>"
                f"</td>"
            )
        rows.append(f"<tr>{''.join(cells)}</tr>")

    return f"""
    <table class="matrix">
      <thead><tr><th class="corner">repo \\ path</th>{header_cells}</tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    <p class="legend">
      <span class="chip outcome-passes">passes</span>
      <span class="chip outcome-fails">fails</span>
      <span class="chip outcome-unclaimed">unclaimed</span>
      &nbsp;·&nbsp; trust climbs:
      <span class="rung rung-0">claimed</span> →
      <span class="rung rung-1">reported math</span> →
      <span class="rung rung-2">artifact-backed</span> →
      <span class="rung rung-3">reproduced</span>
      &nbsp;·&nbsp; <span class="warnflag">⚠</span> comparability unverified
      &nbsp;·&nbsp; <em>click any cell for evidence &amp; judgment</em>
    </p>
    """


def readiness_html(model: dict[str, Any]) -> str:
    cards = []
    for team in model["teams"]:
        profile = team["readiness"]
        bars = []
        for dim, value in profile["dims"].items():
            mx = profile["maxes"][dim]
            pct = (value / mx * 100) if mx else 0
            cls = "full" if value == mx and mx > 0 else "partial" if value > 0 else "zero"
            bars.append(
                f"<div class='profile-row'>"
                f"<span class='profile-label'>{esc(dim)}</span>"
                f"<span class='profile-track'><i class='{cls}' style='width:{pct:.0f}%'></i></span>"
                f"<span class='profile-val'>{value}/{mx}</span>"
                f"</div>"
            )
        cards.append(
            f"<article class='profile-card'>"
            f"<h3>{esc(team['handle'])}</h3>"
            f"<p class='muted small'>{esc(team['shape'])}</p>"
            f"{''.join(bars)}"
            f"</article>"
        )
    return (
        "<p class='muted note'>Whole-repo readiness is a <strong>shape</strong>, not a number. "
        "Compare the silhouettes: all three are tall on \"satisfies a path,\" but the bottom rung "
        "(reproduced) is empty for everyone — that is the cohort-wide ceiling.</p>"
        f"<div class='profiles'>{''.join(cards)}</div>"
    )


def lanes_html(model: dict[str, Any]) -> str:
    """The apples-vs-Macintosh view: one threshold lane per path."""
    DOMAIN_MIN, DOMAIN_MAX = -10.0, 100.0

    def pos(x: float) -> float:
        frac = (x - DOMAIN_MIN) / (DOMAIN_MAX - DOMAIN_MIN)
        return max(0.0, min(1.0, frac)) * 100

    lanes = []
    for crit in model["criteria"]:
        for path in crit["paths"]:
            # Threshold percent from spec string like ">= 15% reduction".
            thr = "".join(ch for ch in path["threshold"] if ch.isdigit())
            thr_val = float(thr) if thr else 0.0
            dots = []
            for team in model["teams"]:
                cell = team["cells"].get(path["id"])
                if not cell or cell["reduction_percent"] is None:
                    continue
                x = float(cell["reduction_percent"])
                dots.append(
                    f"<div class='lane-dot outcome-{cell['outcome']} rungdot-{cell['trust_rung']}' "
                    f"style='left:{pos(x):.1f}%' "
                    f"title='{esc(team['handle'])}: {x}% — {esc(cell['trust'])}'>"
                    f"<span class='lane-dot-label'>{esc(team['handle'])}</span></div>"
                )
            zero = pos(0.0)
            thr_pos = pos(thr_val)
            lanes.append(
                f"<div class='lane-block'>"
                f"<div class='lane-title'>{esc(crit['name'])} · {esc(path['label'])} "
                f"<span class='muted'>(needs {esc(path['threshold'])})</span></div>"
                f"<div class='lane'>"
                f"<div class='lane-zero' style='left:{zero:.1f}%'></div>"
                f"<div class='lane-thr' style='left:{thr_pos:.1f}%'><span>{esc(int(thr_val))}% target</span></div>"
                f"{''.join(dots)}"
                f"</div>"
                f"<div class='lane-axis'><span>−10%</span><span>0</span><span>50%</span><span>100%</span></div>"
                f"</div>"
            )
    return (
        "<p class='muted note'>Each path is its own lane with its own target line. A dot's "
        "<strong>position</strong> is the measured reduction; its <strong>ring</strong> is the trust rung. "
        "This is the apples-vs-Macintosh-apples view: repos clearing different paths are not interchangeable, "
        "and a dot far past the line on a thin ring (reported-math) is not the same result as one just past it "
        "on a thick ring (reproduced).</p>"
        f"{''.join(lanes)}"
    )


def climb_html(model: dict[str, Any]) -> str:
    """Rerun plan reframed as: which rung is each cell on, what unlocks the next."""
    NEXT_ACTION = {
        "claimed": "Find or extract reported before/after numbers.",
        "reported-math": "Locate or regenerate raw machine-readable before/after artifacts.",
        "artifact-backed": "Rebuild from a clean clone and confirm the measurement directionally.",
        "reproduced": "Already at the top rung — spot-check comparability only.",
    }
    rows = []
    for team in model["teams"]:
        for crit in model["criteria"]:
            for path in crit["paths"]:
                cell = team["cells"].get(path["id"])
                if not cell:
                    continue
                nxt = NEXT_ACTION.get(cell["trust"], "")
                comp = cell.get("comparability")
                comp_html = f"<div class='climb-warn'>⚠ {esc(comp['label'])}</div>" if comp else ""
                rows.append(
                    f"<tr class='outcome-{cell['outcome']}'>"
                    f"<th>{esc(team['handle'])}</th>"
                    f"<td>{esc(path['label'])}</td>"
                    f"<td><span class='out'>{cell['outcome']}</span></td>"
                    f"<td><span class='rung rung-{cell['trust_rung']}'>{esc(cell['trust'])}</span></td>"
                    f"<td>{esc(nxt)}{comp_html}</td>"
                    f"</tr>"
                )
    return (
        "<p class='muted note'>Every cell sits on a rung. The benchmark's job is to move cells "
        "<em>up</em>. This is the same rerun plan as before, but framed as the single question that "
        "matters: <strong>what unlocks the next rung of trust?</strong> Today every cell tops out at "
        "artifact-backed because nothing has been reproduced from a clean clone.</p>"
        "<table class='climb'>"
        "<thead><tr><th>Repo</th><th>Path</th><th>Outcome</th><th>Current rung</th>"
        "<th>To climb next rung</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render(run_dir: Path) -> str:
    trace = read_json(run_dir / "bundle-trace.json")
    model = build_cells(trace)
    data_json = json.dumps(model)
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
      --grey:#7c756b; --grey-bg:#ece7dd; --blue:#274f7f; --warn:#9a5a10;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--paper); color:var(--ink);
      font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; line-height:1.4; }}
    main {{ max-width:1180px; margin:0 auto; padding:26px 20px 60px; }}
    header {{ border-bottom:2px solid var(--ink); padding-bottom:14px; }}
    h1 {{ margin:0; font-size:clamp(30px,4.5vw,52px); line-height:.96; }}
    h2 {{ margin:0 0 12px; font-size:22px; }}
    h3 {{ margin:0 0 4px; font-size:16px; }}
    .muted {{ color:var(--muted); }} .small {{ font-size:12px; }}
    .note {{ max-width:780px; }}
    .tabs {{ display:flex; gap:6px; margin:20px 0 0; border-bottom:1px solid var(--line); }}
    .tab-button {{ border:1px solid var(--line); border-bottom:0; background:#ebe3d6; color:var(--ink);
      padding:9px 15px; font-weight:750; cursor:pointer; font-size:14px; }}
    .tab-button.active {{ background:var(--panel); color:var(--blue); }}
    .tab {{ display:none; background:var(--panel); border:1px solid var(--line); border-top:0; padding:20px; }}
    .tab.active {{ display:block; }}

    /* Matrix */
    table.matrix {{ border-collapse:separate; border-spacing:6px; width:100%; }}
    .matrix th.corner {{ text-align:left; font-size:12px; color:var(--muted); }}
    .matrix thead th {{ background:#ece4d7; border:1px solid var(--line); padding:8px 10px; text-align:left;
      vertical-align:top; }}
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

    .rung {{ display:inline-block; font-size:11px; font-weight:700; padding:2px 7px; border-radius:10px;
      border:1px solid currentColor; }}
    .rung-0 {{ color:#8a8178; }} .rung-1 {{ color:#9a5a10; background:#fdf0d8; }}
    .rung-2 {{ color:#274f7f; background:#e4ecf6; }} .rung-3 {{ color:#1c6b54; background:#e6f3ec; }}

    .legend {{ font-size:12px; color:var(--muted); margin-top:16px; }}
    .chip {{ display:inline-block; padding:2px 8px; border:1px solid var(--line); font-weight:750;
      font-size:11px; text-transform:uppercase; }}

    /* Readiness profiles */
    .profiles {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; margin-top:8px; }}
    .profile-card {{ border:1px solid var(--line); background:#fffaf1; padding:14px; }}
    .profile-row {{ display:flex; align-items:center; gap:8px; margin:7px 0; font-size:12px; }}
    .profile-label {{ width:108px; color:var(--muted); }}
    .profile-track {{ flex:1; height:9px; background:#e3dbcd; position:relative; }}
    .profile-track i {{ display:block; height:100%; }}
    .profile-track i.full {{ background:var(--good); }}
    .profile-track i.partial {{ background:var(--blue); }}
    .profile-track i.zero {{ background:transparent; }}
    .profile-val {{ width:30px; text-align:right; font-weight:700; }}

    /* Lanes */
    .lane-block {{ margin:22px 0; }}
    .lane-title {{ font-weight:800; margin-bottom:10px; font-size:15px; }}
    .lane {{ position:relative; height:54px; background:linear-gradient(#fbf6ec,#fbf6ec);
      border:1px solid var(--line); }}
    .lane-zero {{ position:absolute; top:0; bottom:0; width:1px; background:#c9bda9; }}
    .lane-thr {{ position:absolute; top:0; bottom:0; width:2px; background:var(--bad); }}
    .lane-thr span {{ position:absolute; top:-2px; left:5px; font-size:10px; color:var(--bad);
      white-space:nowrap; font-weight:700; }}
    .lane-dot {{ position:absolute; top:50%; transform:translate(-50%,-50%); width:18px; height:18px;
      border-radius:50%; border:3px solid var(--ink); }}
    .lane-dot.outcome-passes {{ background:var(--good); }}
    .lane-dot.outcome-fails {{ background:var(--bad); }}
    .lane-dot.outcome-unclaimed {{ background:var(--grey); }}
    .rungdot-1 {{ border-color:#d8a24a; border-style:dotted; }}
    .rungdot-2 {{ border-color:#274f7f; }}
    .rungdot-3 {{ border-color:#1c6b54; border-width:4px; }}
    .lane-dot-label {{ position:absolute; top:20px; left:50%; transform:translateX(-50%);
      font-size:11px; font-weight:700; white-space:nowrap; }}
    .lane-axis {{ display:flex; justify-content:space-between; font-size:10px; color:var(--muted);
      margin-top:4px; }}

    /* Climb */
    table.climb {{ width:100%; border-collapse:collapse; font-size:13px; margin-top:6px; }}
    .climb th, .climb td {{ border:1px solid var(--line); padding:8px 10px; text-align:left; vertical-align:top; }}
    .climb thead th {{ background:#ece4d7; }}
    .climb .out {{ font-weight:800; text-transform:uppercase; font-size:11px; }}
    .climb tr.outcome-passes .out {{ color:var(--good); }}
    .climb tr.outcome-fails .out {{ color:var(--bad); }}
    .climb-warn {{ color:var(--warn); font-size:11px; margin-top:4px; }}

    /* Drawer */
    .scrim {{ position:fixed; inset:0; background:rgba(20,18,14,.4); display:none; }}
    .scrim.open {{ display:block; }}
    .drawer {{ position:fixed; top:0; right:0; bottom:0; width:min(460px,92vw); background:var(--panel);
      border-left:2px solid var(--ink); padding:22px; overflow-y:auto; transform:translateX(100%);
      transition:transform .16s ease; }}
    .drawer.open {{ transform:translateX(0); }}
    .drawer h2 {{ margin-top:0; }}
    .drawer .kv {{ margin:14px 0; }}
    .drawer .kv h4 {{ margin:0 0 4px; font-size:11px; text-transform:uppercase; letter-spacing:.07em;
      color:var(--muted); }}
    .drawer ul {{ margin:4px 0; padding-left:18px; font-size:13px; }}
    .drawer code {{ font-size:12px; background:#efe8da; padding:1px 4px; word-break:break-all; }}
    .drawer .big {{ font-size:30px; font-weight:800; }}
    .drawer .close {{ position:absolute; top:14px; right:16px; border:1px solid var(--line);
      background:#ebe3d6; cursor:pointer; padding:4px 10px; font-weight:800; }}
    .conf {{ display:inline-block; padding:2px 9px; border:1px solid currentColor; font-weight:800;
      font-size:11px; text-transform:uppercase; }}
    .conf-high {{ color:var(--good); }} .conf-medium, .conf-low-medium {{ color:var(--blue); }}
    .conf-low {{ color:var(--warn); }} .conf-none {{ color:var(--grey); }}

    @media (max-width:820px) {{
      .profiles {{ grid-template-columns:1fr; }}
      table.matrix {{ display:block; overflow-x:auto; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <p class="muted">Week 4 · Bundle-size specimen · Run {esc(trace['run_id'])}</p>
      <h1>Compare</h1>
      <p class="muted note" style="margin-top:8px">Two axes, never merged: <strong>outcome</strong>
      (does it clear a specific path?) and <strong>trust</strong> (how do we know — claimed → reported
      math → artifact-backed → reproduced). Confidence is the rung, not a percentage.</p>
    </header>

    <nav class="tabs">
      <button class="tab-button active" data-tab="compare">Compare</button>
      <button class="tab-button" data-tab="readiness">Readiness</button>
      <button class="tab-button" data-tab="paths">Paths</button>
      <button class="tab-button" data-tab="climb">Climb</button>
    </nav>

    <section id="compare" class="tab active">
      <h2>Outcome × Trust Matrix</h2>
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

    function openCell(teamId, pathId) {{
      const team = DATA.teams.find((t)=>t.team===teamId);
      const crit = DATA.criteria.find((c)=>c.paths.some((p)=>p.id===pathId));
      const path = crit.paths.find((p)=>p.id===pathId);
      const cell = team.cells[pathId];
      const claimed = (team.claims||[]).find((c)=>/initial|total|code.?split|dist|bundle/i.test(c)) || (team.claims[0]||'—');
      const comp = cell.comparability ? `<div class="kv"><h4>Comparability</h4><span class="conf conf-low">⚠ ${{esc(cell.comparability.label)}}</span></div>` : '';
      const judg = (team.next_judgments||[]).map((j)=>`<li><strong>${{esc(j.judgment)}}</strong>: ${{esc(j.state)}}<br><span class="muted small">${{esc(j.why)}}</span></li>`).join('');
      body.innerHTML = `
        <p class="muted small">${{esc(team.handle)}} · commit ${{esc((team.commit||'').slice(0,8))}}</p>
        <h2>${{esc(crit.name)}} · ${{esc(path.label)}}</h2>
        <div class="big outcome-${{cell.outcome}}" style="display:inline-block;padding:2px 6px">${{esc(cell.outcome)}} · ${{esc(cell.reduction_percent)}}%</div>
        <div class="kv"><h4>Trust rung / confidence</h4>
          <span class="rung rung-${{cell.trust_rung}}">${{esc(cell.trust)}}</span>
          &nbsp;<span class="conf conf-${{cell.confidence}}">${{esc(cell.confidence)}} confidence</span></div>
        ${{comp}}
        <div class="kv"><h4>Claimed path</h4><p>${{esc(claimed)}}</p></div>
        <div class="kv"><h4>Measured (extracted artifact math)</h4>
          <p>${{esc(cell.before_kb)}} KB → ${{esc(cell.after_kb)}} KB &nbsp;·&nbsp; target ${{esc(cell.threshold)}}</p>
          <p class="muted small">${{esc(cell.interpretation)}}</p></div>
        <div class="kv"><h4>Evidence provenance</h4><ul>${{li(team.primary_evidence)}}</ul></div>
        <div class="kv"><h4>Discovery (signal volume)</h4>
          <p class="small">${{Object.entries(team.discovery_counts).map(([k,v])=>`${{esc(k)}}: ${{v}}`).join(' · ')}}</p></div>
        <div class="kv"><h4>Unresolved judgment</h4><ul>${{judg || '<li class="muted">none</li>'}}</ul></div>
        <div class="kv"><h4>Caveats</h4><ul>${{li(team.caveats)}}</ul></div>
      `;
      scrim.classList.add('open'); drawer.classList.add('open'); drawer.setAttribute('aria-hidden','false');
    }}
    function closeDrawer() {{ scrim.classList.remove('open'); drawer.classList.remove('open'); drawer.setAttribute('aria-hidden','true'); }}
    document.querySelectorAll('.cell:not(.empty)').forEach((c)=>{{
      c.addEventListener('click', ()=>openCell(c.dataset.team, c.dataset.path));
      c.addEventListener('keydown', (e)=>{{ if(e.key==='Enter'||e.key===' '){{e.preventDefault(); openCell(c.dataset.team,c.dataset.path);}} }});
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
