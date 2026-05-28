#!/usr/bin/env python3
"""Render the condensed "who did best" scorecard for a benchmark run.

Layout: metric labels once on the left, repos as columns. Read across a row to
see who won that metric (star), scan a category band to see the category winner
(trophy), check the banner for the overall lead. The justification — the measure
and the pros — lives in a hover, out of the way.

THE "BEST" RULE (explicit and inspectable, applied identically everywhere):

  Trust tiers rank claimed < reported-math < artifact-backed < reproduced.

  Best in a row (one metric, across repos):
    Only repos that actually improved (reduction > 0) compete. Among them, you
    compete ONLY within the highest trust tier present. So a reported-math 100%
    cannot beat an artifact-backed 31% — it only wins a row where no
    artifact-backed repo improved at all. Within the top tier, highest reduction
    wins; results within TIE_EPS points are co-winners (a tie, not a forced pick).

  Best in a category:
    A repo's category outcome is decided by the criterion's combine rule
    (headline part vs 25% threshold, or any thresholded path passing). Among
    repos that PASS on artifact-backed evidence, highest headline reduction wins
    (tie-break: breadth = how many parts it improved). If only reported-math
    repos pass, the winner is marked provisional.

  Best overall:
    Count categories led on artifact-backed evidence. Tie-break: total
    artifact-backed row stars. Always provisional until something is reproduced.

Nothing here is a single blended grade. Trust gates the comparison so the most
extreme raw number cannot win on the weakest evidence.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path("/Users/michaelhabermas/repos/GAI/g4a-bench")
RUNS_DIR = ROOT / "g4a-benchmarks/g4a-c5-2/week-4/runs"

TRUST_RANK = {"claimed": 0, "reported-math": 1, "artifact-backed": 2, "reproduced": 3}
TRUST_SHORT = {"reported-math": "md", "artifact-backed": "art", "reproduced": "repro", "claimed": "claim"}
TIE_EPS = 4.0  # percentage points within which two reductions are called a tie

JUDGMENT_GLYPH = {"meaningful": "✓", "needs_review": "?", "not_addressed": "✗", "not_claimed": "—", "neutral": ""}
JUDGMENT_CSS = {"meaningful": "j-ok", "needs_review": "j-q", "not_addressed": "j-x", "not_claimed": "j-na", "neutral": ""}

PATH_LABELS = {"total-production-bundle": "total bundle", "initial-load-code-splitting": "initial load"}


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def tip(text: str) -> str:
    return html.escape(text, quote=True).replace("\n", "&#10;")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_run() -> Path:
    candidates = sorted(p for p in RUNS_DIR.glob("*") if p.is_dir())
    if not candidates:
        raise SystemExit(f"No run directories found under {RUNS_DIR}")
    return candidates[-1]


def short_team(name: str) -> str:
    for token in ("michaelhabermas", "daltondinderman", "shivkanthalu"):
        if token in name:
            return token
    tail = name.rstrip("/").split("-")
    return tail[-1] if tail else name


# ---------------------------------------------------------------------------
# Normalize each trace into criterion -> parts -> per-team cells
# ---------------------------------------------------------------------------

def bundle_criterion(trace: dict[str, Any]) -> dict[str, Any]:
    parts = [
        {"id": p["id"], "label": PATH_LABELS.get(p["id"], p["id"]), "threshold": p.get("spec_threshold", ""), "kind": "reduction"}
        for p in trace["teams"][0]["target_paths"]
    ]
    teams = {}
    for team in trace["teams"]:
        states = {s["name"]: s["value"] for s in team.get("evidence_states") or []}
        comparability = states.get("comparability")
        cells = {}
        for path in team["target_paths"]:
            outcome = "passes" if str(path["state"]).startswith("passes_") else "fails"
            trust = "artifact-backed" if "artifact_math" in path["state"] else "reported-math" if "markdown_math" in path["state"] else "claimed"
            if outcome == "fails":
                judgment = "not_addressed"
            elif trust == "reported-math" or comparability == "needs_agent_review":
                judgment = "needs_review"
            else:
                judgment = "meaningful"
            cells[path["id"]] = {
                "kind": "reduction",
                "before": path.get("before_kb", path.get("before")),
                "after": path.get("after_kb", path.get("after")),
                "unit": "KB",
                "reduction_percent": path.get("reduction_percent"),
                "trust": trust,
                "outcome": outcome,
                "judgment": judgment,
                "threshold": path.get("spec_threshold", ""),
            }
        teams[team["team"]] = {"cells": cells, "info": team_info(team)}
    return {
        "id": "bundle-size", "name": "Bundle Size", "unit": "KB",
        "combine": "any_threshold", "headline": None, "threshold_percent": None,
        "parts": parts, "teams": teams,
    }


def typesafety_criterion(trace: dict[str, Any]) -> dict[str, Any]:
    crit = trace["criterion"]
    parts = [
        {"id": p["id"], "label": p["label"], "threshold": p.get("threshold", ""),
         "kind": "boolean" if p.get("kind") == "boolean" else "reduction", "headline": p.get("headline", False)}
        for p in trace["part_defs"]
    ]
    headline = crit.get("headline_part")
    thr = crit.get("threshold_percent")
    teams = {}
    for team in trace["teams"]:
        cells = {}
        for pid, part in team["parts"].items():
            trust = part.get("trust", team.get("trust", "claimed"))
            if part.get("kind") == "boolean":
                cells[pid] = {"kind": "boolean", "value": part.get("value"), "trust": trust,
                              "judgment": part.get("judgment", "neutral"), "outcome": None, "reduction_percent": None}
                continue
            rp = part.get("reduction_percent")
            outcome = None
            if pid == headline and rp is not None and thr is not None:
                outcome = "passes" if rp >= thr else "fails"
            cells[pid] = {
                "kind": "reduction", "before": part.get("before"), "after": part.get("after"),
                "unit": "violations", "reduction_percent": rp, "trust": trust,
                "outcome": outcome, "judgment": part.get("judgment", "needs_review"),
                "threshold": parts_threshold(parts, pid),
            }
        teams[team["team"]] = {"cells": cells, "info": team_info(team)}
    return {
        "id": crit["id"], "name": crit["name"], "unit": crit["unit"],
        "combine": crit.get("combine", "headline"), "headline": headline, "threshold_percent": thr,
        "parts": parts, "teams": teams,
    }


def parts_threshold(parts: list[dict], pid: str) -> str:
    for p in parts:
        if p["id"] == pid:
            return p.get("threshold", "")
    return ""


def team_info(team: dict[str, Any]) -> dict[str, Any]:
    return {
        "claims": team.get("claim_text") or [],
        "caveats": team.get("caveats") or [],
        "primary_evidence": team.get("primary_evidence") or [],
        "next_judgments": team.get("next_judgments") or [],
        "agent_questions": team.get("agent_questions") or [],
        "trust": team.get("trust", ""),
    }


def load_model(run_dir: Path) -> dict[str, Any]:
    order = ["typesafety-trace.json", "bundle-trace.json"]
    paths = [run_dir / n for n in order if (run_dir / n).exists()]
    paths += [p for p in sorted(run_dir.glob("*-trace.json")) if p not in paths]

    criteria = []
    for path in paths:
        trace = read_json(path)
        kind = trace.get("artifact_kind")
        if kind == "type_safety_process_trace":
            criteria.append(typesafety_criterion(trace))
        elif kind == "bundle_size_process_trace":
            criteria.append(bundle_criterion(trace))

    team_ids: list[str] = []
    for crit in criteria:
        for tid in crit["teams"]:
            if tid not in team_ids:
                team_ids.append(tid)

    return {"criteria": criteria, "team_ids": team_ids, "handles": {tid: short_team(tid) for tid in team_ids}}


# ---------------------------------------------------------------------------
# The "best" rule
# ---------------------------------------------------------------------------

def row_winners(crit: dict[str, Any], pid: str, team_ids: list[str]) -> set[str]:
    cells = [(tid, crit["teams"][tid]["cells"].get(pid)) for tid in team_ids if tid in crit["teams"]]
    improved = [
        (tid, c) for tid, c in cells
        if c and c["kind"] == "reduction" and c.get("reduction_percent") is not None and c["reduction_percent"] > 0
    ]
    if not improved:
        return set()
    top_rank = max(TRUST_RANK[c["trust"]] for _, c in improved)
    top = [(tid, c) for tid, c in improved if TRUST_RANK[c["trust"]] == top_rank]
    best_val = max(c["reduction_percent"] for _, c in top)
    return {tid for tid, c in top if best_val - c["reduction_percent"] <= TIE_EPS}


def team_category_outcome(crit: dict[str, Any], tid: str) -> tuple[str, str, float]:
    """Return (outcome, deciding_trust, headline_reduction)."""
    cells = crit["teams"][tid]["cells"]
    if crit["combine"] == "headline":
        cell = cells.get(crit["headline"], {})
        rp = cell.get("reduction_percent")
        return (cell.get("outcome") or "fails", cell.get("trust", "claimed"), rp if rp is not None else -999)
    # any_threshold: passes if any thresholded path passes; deciding trust = best passing path's trust
    passing = [c for c in cells.values() if c.get("outcome") == "passes"]
    if passing:
        best = max(passing, key=lambda c: (TRUST_RANK[c["trust"]], c.get("reduction_percent") or 0))
        return ("passes", best["trust"], best.get("reduction_percent") or 0)
    return ("fails", "claimed", -999)


def breadth(crit: dict[str, Any], tid: str) -> int:
    cells = crit["teams"][tid]["cells"]
    return sum(1 for c in cells.values() if c.get("kind") == "reduction" and (c.get("reduction_percent") or 0) > 0)


def category_winner(crit: dict[str, Any], team_ids: list[str]) -> dict[str, Any]:
    outcomes = {tid: team_category_outcome(crit, tid) for tid in team_ids if tid in crit["teams"]}
    artifact_pass = {tid: o for tid, o in outcomes.items() if o[0] == "passes" and TRUST_RANK[o[1]] >= 2}
    pool, provisional = (artifact_pass, False) if artifact_pass else (
        {tid: o for tid, o in outcomes.items() if o[0] == "passes"}, True)
    if not pool:
        return {"winner": None, "provisional": True, "measure": "No repo cleared this category's bar on any evidence."}
    winner = max(pool, key=lambda tid: (pool[tid][2], breadth(crit, tid)))
    return {"winner": winner, "provisional": provisional, "measure": category_measure(crit, winner, team_ids, provisional)}


def category_measure(crit: dict[str, Any], winner: str, team_ids: list[str], provisional: bool) -> str:
    handle = short_team(winner)
    if crit["combine"] == "headline":
        rule = f"BEST BY: largest artifact-backed reduction clearing the {crit['threshold_percent']}% target."
    else:
        rule = "BEST BY: highest artifact-backed reduction on a passing spec path."
    wins = sum(1 for p in crit["parts"] if winner in row_winners(crit, p["id"], team_ids))
    n_reduction = sum(1 for p in crit["parts"] if p["kind"] == "reduction")
    facts = [f"Leads {wins} of {n_reduction} measured sub-metrics on the top trust tier."]
    # Sub-metrics where the winner is the only artifact-backed improver.
    solo = []
    for p in crit["parts"]:
        if p["kind"] != "reduction":
            continue
        w = row_winners(crit, p["id"], team_ids)
        if w == {winner}:
            others = [tid for tid in team_ids if tid != winner and tid in crit["teams"]]
            cell = crit["teams"][winner]["cells"].get(p["id"], {})
            if any((crit["teams"][o]["cells"].get(p["id"], {}).get("reduction_percent") or 0) <= 0 for o in others) and (cell.get("reduction_percent") or 0) > 0:
                solo.append(p["label"])
    if solo:
        facts.append("Only top-tier repo to move: " + ", ".join(solo) + ".")
    # A lower-trust repo reporting a higher headline number.
    if crit["combine"] == "headline":
        win_rp = crit["teams"][winner]["cells"][crit["headline"]].get("reduction_percent") or 0
        for tid in team_ids:
            if tid == winner or tid not in crit["teams"]:
                continue
            o = team_category_outcome(crit, tid)
            if o[0] == "passes" and TRUST_RANK[o[1]] < 2 and o[2] > win_rp:
                facts.append(f"WHY NOT {short_team(tid)}: reports {o[2]:.0f}% but on {o[1]} only.")
    note = ""
    cav = crit["teams"][winner]["info"]["caveats"]
    if cav:
        note = "\nNote: " + cav[0]
    prov = "\n(Provisional — only reported-math evidence passed.)" if provisional else ""
    return f"{rule}\n\nPROS — {handle}\n• " + "\n• ".join(facts) + note + prov


def overall_winner(model: dict[str, Any], cat_winners: dict[str, dict]) -> dict[str, Any]:
    team_ids = model["team_ids"]
    led = {tid: 0 for tid in team_ids}
    for crit in model["criteria"]:
        cw = cat_winners[crit["id"]]
        if cw["winner"] and not cw["provisional"]:
            led[cw["winner"]] += 1
    stars = {tid: 0 for tid in team_ids}
    for crit in model["criteria"]:
        for p in crit["parts"]:
            for tid in row_winners(crit, p["id"], team_ids):
                if TRUST_RANK[crit["teams"][tid]["cells"][p["id"]]["trust"]] >= 2:
                    stars[tid] += 1
    winner = max(team_ids, key=lambda tid: (led[tid], stars[tid]))
    measure = (
        "BEST BY: categories led on artifact-backed evidence (tie-break: artifact-backed metric wins).\n\n"
        f"PROS — {short_team(winner)}\n"
        f"• Leads {led[winner]} categor{'y' if led[winner] == 1 else 'ies'} on artifact evidence.\n"
        f"• {stars[winner]} artifact-backed metric wins across the week.\n\n"
        "CAVEAT\n• Provisional — nothing reproduced from a clean clone yet.\n"
        "• Repos with bigger raw numbers on reported-math evidence are not counted ahead of verified ones."
    )
    return {"winner": winner, "measure": measure, "led": led, "stars": stars}


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def cell_html(cell: dict[str, Any] | None, is_winner: bool) -> str:
    if not cell:
        return "<td class='cell na'>—</td>"
    star = "<span class='star'>★</span> " if is_winner else ""
    rung = cell.get("trust", "")
    rung_html = f"<span class='rung {TRUST_SHORT.get(rung, '')}'>{esc(TRUST_SHORT.get(rung, rung))}</span>"
    jcss = JUDGMENT_CSS.get(cell.get("judgment", ""), "")
    jg = JUDGMENT_GLYPH.get(cell.get("judgment", ""), "")
    jhtml = f" <span class='j {jcss}'>{jg}</span>" if jg else ""
    if cell["kind"] == "boolean":
        return f"<td class='cell'><span class='num'>{esc(cell.get('value'))}</span> {rung_html}</td>"
    rp = cell.get("reduction_percent")
    if rp is None:
        return f"<td class='cell na'>{'—' if cell.get('judgment') == 'not_claimed' else 'n/a'}</td>"
    cls = "down" if rp > 0 else "flat"
    label = f"{rp:.1f}%↓" if rp > 0 else (f"{rp:.1f}%" if rp != 0 else "0% flat")
    cls_cell = "cell best" if is_winner else "cell"
    return f"<td class='{cls_cell}'>{star}<span class='num {cls}'>{esc(label)}</span> {rung_html}{jhtml}</td>"


def render(run_dir: Path) -> str:
    model = load_model(run_dir)
    team_ids = model["team_ids"]
    handles = model["handles"]

    cat_winners = {crit["id"]: category_winner(crit, team_ids) for crit in model["criteria"]}
    overall = overall_winner(model, cat_winners)

    head_cols = "".join(f"<th class='repohead'>{esc(handles[tid])}</th>" for tid in team_ids)

    bands = []
    for crit in model["criteria"]:
        cw = cat_winners[crit["id"]]
        if cw["winner"]:
            trophy = f"🏆 {esc(handles[cw['winner']])}" + (" <span class='prov'>(prov.)</span>" if cw["provisional"] else "")
            badge = f"<span class='catbest tip' data-tip='{tip(cw['measure'])}'>{trophy}</span>"
        else:
            badge = "<span class='catbest'>no winner</span>"
        rows = [f"<tr class='catrow'><td colspan='{len(team_ids) + 1}'><span class='catname'>{esc(crit['name'])}</span>{badge}</td></tr>"]
        for p in crit["parts"]:
            winners = row_winners(crit, p["id"], team_ids)
            cells = "".join(cell_html(crit["teams"].get(tid, {}).get("cells", {}).get(p["id"]), tid in winners) for tid in team_ids)
            rows.append(f"<tr><td class='mlabel'>{esc(p['label'])}</td>{cells}</tr>")
        bands.append("".join(rows))

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>G4A Week 4 — who did best</title>
<style>
  :root{{
    --ink:#191919;--muted:#6b655d;--paper:#f5f1e9;--panel:#fffdf8;--line:#d6cdbf;
    --good:#1c6b54;--good-bg:#e6f3ec;--bad:#9c2f25;--bad-bg:#f8e1de;
    --grey:#7c756b;--grey-bg:#ece7dd;--blue:#274f7f;--warn:#9a5a10;--warn-bg:#fdf0d8;
    --gold:#9a7a16;--gold-bg:#fbf3d6;
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--paper);color:var(--ink);font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.4}}
  main{{max-width:980px;margin:0 auto;padding:26px 20px 90px}}
  h1{{font-size:30px;margin:0 0 4px}}
  .lead{{color:var(--muted);max-width:760px;margin:0 0 18px;font-size:14px}}
  .overall{{display:flex;align-items:center;gap:12px;background:var(--gold-bg);border:1px solid var(--gold);padding:12px 16px;margin-bottom:18px}}
  .overall .lbl{{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}}
  .overall .who{{font-size:22px;font-weight:850;color:var(--gold)}}
  table{{width:100%;border-collapse:collapse}}
  thead .repohead{{text-align:center;font-weight:850;font-size:16px;border-bottom:2px solid var(--ink);width:24%;padding:8px 10px}}
  thead .metrichead{{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.06em;width:28%;text-align:left;padding:8px 10px}}
  tr.catrow td{{background:#ece4d7;border-top:1px solid var(--line);padding:8px 10px}}
  .catname{{font-weight:850;font-size:13px;text-transform:uppercase;letter-spacing:.05em}}
  .catbest{{float:right;font-weight:800;font-size:12px;color:var(--gold)}}
  .prov{{color:var(--muted);font-weight:600}}
  tbody td{{border-bottom:1px solid var(--line);padding:7px 10px;vertical-align:middle}}
  .mlabel{{color:var(--muted);font-size:13px}}
  .cell{{text-align:center;width:24%}}
  .num{{font-weight:800;font-size:15px}}
  .down{{color:var(--good)}}.flat{{color:var(--bad)}}.na{{color:var(--grey);font-weight:600;text-align:center}}
  .rung{{display:inline-block;font-size:9px;font-weight:700;padding:0 5px;border-radius:8px;border:1px solid currentColor;vertical-align:middle}}
  .md{{color:var(--warn);background:var(--warn-bg)}}.art{{color:var(--blue);background:#e4ecf6}}.repro{{color:var(--good);background:var(--good-bg)}}.claim{{color:var(--grey);background:var(--grey-bg)}}
  .j{{font-size:10px;font-weight:800;vertical-align:middle}}
  .j-ok{{color:var(--good)}}.j-q{{color:var(--warn)}}.j-x{{color:var(--bad)}}.j-na{{color:var(--grey)}}
  .best{{background:var(--gold-bg);box-shadow:inset 3px 0 0 var(--gold)}}
  .star{{color:var(--gold)}}
  .tip{{position:relative;cursor:help}}
  .tip::before{{content:"ⓘ";font-size:11px;color:var(--muted);margin-left:5px;font-weight:700}}
  .tip:hover::after{{content:attr(data-tip);position:absolute;right:0;top:130%;white-space:pre-line;width:320px;background:#1d1b16;color:#f4efe6;padding:10px 12px;font-size:12px;line-height:1.4;border-radius:5px;z-index:30;font-weight:500;box-shadow:0 6px 20px rgba(0,0,0,.3);text-transform:none;letter-spacing:0;text-align:left}}
  .legend{{font-size:12px;color:var(--muted);margin-top:18px}}
</style>
</head>
<body>
<main>
  <h1>Week 4 — who did best</h1>
  <p class="lead">Labels once on the left, repos across the top: scan a row for the metric winner (★), a band
  for the category winner (🏆). "Best" is <strong>trust-weighted</strong> — a reported-math number can't outrank
  artifact-backed evidence. Hover any <span style="color:var(--muted)">ⓘ</span> for the measure and the pros.</p>

  <div class="overall">
    <span class="lbl">Overall lead</span>
    <span class="who">{esc(handles[overall['winner']])} 🏆</span>
    <span class="prov tip" data-tip="{tip(overall['measure'])}">provisional</span>
  </div>

  <table>
    <thead><tr><th class="metrichead">metric</th>{head_cols}</tr></thead>
    <tbody>{''.join(bands)}</tbody>
  </table>

  <p class="legend">
    ★ best in row (trust-weighted, ties within {int(TIE_EPS)} pts shown together) &nbsp;·&nbsp; 🏆 best in category &nbsp;·&nbsp;
    rung: <span class="rung art">art</span> artifact-backed, <span class="rung md">md</span> reported-math &nbsp;·&nbsp;
    judgment: <span class="j j-ok">✓</span> meaningful, <span class="j j-q">?</span> needs judgment, <span class="j j-x">✗</span> not addressed &nbsp;·&nbsp;
    hover <span style="color:var(--muted)">ⓘ</span> for "best by what measure" + pros
  </p>
</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=None)
    args = parser.parse_args()
    run_dir = args.run_dir or latest_run()
    out = run_dir / "scorecard.html"
    out.write_text(render(run_dir), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
