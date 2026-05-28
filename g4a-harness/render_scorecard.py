#!/usr/bin/env python3
"""Render the condensed "who did best" scorecard for a benchmark run.

Layout: metric labels once on the left, repos as columns. Read across a row for
the metric winner (star), scan a band for the category winner (trophy). The
measure + pros live in a hover, out of the way.

RANKING IS TRUST-GATED, and verification beats self-report. Trust tiers:
  claimed < reported-math < artifact-backed < verified
where `verified` means THE HARNESS measured it (e.g. counted casts with the TS
compiler), not the team. You only compete within the highest tier present in a
row, so a self-reported number cannot outrank a verified one.

Type-safety cells, once verified, show *remaining violations* (lower = better) —
that is what the harness can count today. Verified % reduction is intentionally
absent: it needs a verified common baseline we have not measured yet, and we
record that gap rather than borrow the team's baseline.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path("/Users/michaelhabermas/repos/GAI/g4a-bench")
RUNS_DIR = ROOT / "g4a-benchmarks/g4a-c5-2/week-4/runs"

TRUST_RANK = {"claimed": 0, "reported-math": 1, "artifact-backed": 2, "verified": 3}
TRUST_SHORT = {"reported-math": "md", "artifact-backed": "art", "verified": "ver", "claimed": "claim"}
TRUST_STRENGTH = {"verified": 3, "artifact-backed": 2, "reported-math": 1, "claimed": 0}
TIE_EPS = 4.0

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


def reduction_cell(value_kind: str, *, reduction_percent=None, remaining=None, claimed_after=None,
                   before=None, after=None, unit="", trust="claimed", outcome=None,
                   judgment="needs_review", flagged=False, verified=False) -> dict[str, Any]:
    if value_kind == "remaining":
        goodness = None if remaining is None else float(-remaining)
        display = "n/a" if remaining is None else f"{remaining} left"
    else:
        goodness = None if reduction_percent is None or reduction_percent <= 0 else float(reduction_percent)
        if reduction_percent is None:
            display = "n/a"
        elif reduction_percent > 0:
            display = f"{reduction_percent:.1f}%↓"
        else:
            display = f"{reduction_percent:.1f}%" if reduction_percent != 0 else "0% flat"
    return {
        "kind": "reduction", "value_kind": value_kind, "reduction_percent": reduction_percent,
        "remaining": remaining, "claimed_after": claimed_after, "before": before, "after": after,
        "unit": unit, "trust": trust, "outcome": outcome, "judgment": judgment, "flagged": flagged,
        "verified": verified, "goodness": goodness, "display": display,
    }


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
            cells[path["id"]] = reduction_cell(
                "reduction_pct", reduction_percent=path.get("reduction_percent"),
                before=path.get("before_kb", path.get("before")), after=path.get("after_kb", path.get("after")),
                unit="KB", trust=trust, outcome=outcome, judgment=judgment, verified=False)
        teams[team["team"]] = {"cells": cells, "info": team_info(team)}
    return {"id": "bundle-size", "name": "Bundle Size", "unit": "KB", "combine": "any_threshold",
            "headline": None, "threshold_percent": None, "parts": parts, "teams": teams, "verified_kind": False}


def typesafety_criterion(trace: dict[str, Any]) -> dict[str, Any]:
    crit = trace["criterion"]
    parts = [
        {"id": p["id"], "label": p["label"], "threshold": p.get("threshold", ""),
         "kind": "boolean" if p.get("kind") == "boolean" else "reduction", "headline": p.get("headline", False)}
        for p in trace["part_defs"]
    ]
    headline = crit.get("headline_part")
    thr = crit.get("threshold_percent")
    verified_kind = False
    teams = {}
    for team in trace["teams"]:
        cells = {}
        for pid, part in team["parts"].items():
            if part.get("kind") == "boolean":
                cells[pid] = {"kind": "boolean", "value": part.get("value"),
                              "trust": part.get("trust", team.get("trust", "claimed")),
                              "judgment": part.get("judgment", "neutral"), "goodness": None}
                continue
            v = part.get("verified")
            if v:
                verified_kind = True
                cells[pid] = reduction_cell(
                    "remaining", remaining=v["remaining"], claimed_after=v.get("claimed_after"),
                    reduction_percent=part.get("reduction_percent"),
                    before=part.get("before"), after=part.get("after"), unit="violations",
                    trust="verified", outcome=None, judgment=part.get("judgment", "needs_review"),
                    flagged=v.get("flagged", False), verified=True)
            else:
                rp = part.get("reduction_percent")
                outcome = "passes" if (pid == headline and rp is not None and thr is not None and rp >= thr) else \
                          ("fails" if pid == headline and rp is not None else None)
                cells[pid] = reduction_cell(
                    "reduction_pct", reduction_percent=rp, before=part.get("before"), after=part.get("after"),
                    unit="violations", trust=part.get("trust", team.get("trust", "claimed")),
                    outcome=outcome, judgment=part.get("judgment", "needs_review"), verified=False)
        teams[team["team"]] = {"cells": cells, "info": team_info(team)}
    return {"id": crit["id"], "name": crit["name"], "unit": crit["unit"], "combine": crit.get("combine", "headline"),
            "headline": headline, "threshold_percent": thr, "parts": parts, "teams": teams, "verified_kind": verified_kind}


def team_info(team: dict[str, Any]) -> dict[str, Any]:
    return {"claims": team.get("claim_text") or [], "caveats": team.get("caveats") or [],
            "trust": team.get("trust", "")}


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

def row_candidates(crit, pid, team_ids):
    out = []
    for tid in team_ids:
        c = crit["teams"].get(tid, {}).get("cells", {}).get(pid)
        if not c or c["kind"] != "reduction" or c.get("goodness") is None:
            continue
        out.append((tid, c))
    return out


def row_winners(crit, pid, team_ids) -> set[str]:
    cand = row_candidates(crit, pid, team_ids)
    if not cand:
        return set()
    top = max(TRUST_RANK[c["trust"]] for _, c in cand)
    top_cells = [(tid, c) for tid, c in cand if TRUST_RANK[c["trust"]] == top]
    best = max(c["goodness"] for _, c in top_cells)
    return {tid for tid, c in top_cells if best - c["goodness"] <= TIE_EPS}


def headline_cell(crit, tid):
    cells = crit["teams"][tid]["cells"]
    if crit["combine"] == "headline":
        return cells.get(crit["headline"])
    passing = [c for c in cells.values() if c.get("outcome") == "passes"]
    if passing:
        return max(passing, key=lambda c: (TRUST_RANK[c["trust"]], c.get("goodness") or 0))
    return None


def category_winner(crit, team_ids) -> dict[str, Any]:
    # Verified-remaining categories: rank by fewest remaining within the verified tier.
    if crit.get("verified_kind"):
        cand = [(tid, headline_cell(crit, tid)) for tid in team_ids if tid in crit["teams"]]
        cand = [(tid, c) for tid, c in cand if c and c.get("goodness") is not None and c["trust"] == "verified"]
        if cand:
            best = max(c["goodness"] for _, c in cand)
            winner = max(cand, key=lambda kc: kc[1]["goodness"])[0]
            return {"winner": winner, "provisional": True, "evidence": "verified",
                    "measure": verified_measure(crit, winner, team_ids)}
    # Multi-path category (the spec allows either path): clearing MORE of the
    # goal wins, then total magnitude. Doing both paths beats the single highest
    # number on one. Trust does not gate this — it sets how provisional the win is.
    if crit["combine"] == "any_threshold":
        cleared = {}
        for tid in team_ids:
            if tid not in crit["teams"]:
                continue
            passed = [(pid, c) for pid, c in crit["teams"][tid]["cells"].items() if c.get("outcome") == "passes"]
            if passed:
                cleared[tid] = {
                    "n": len(passed),
                    "mag": sum((c.get("reduction_percent") or 0) for _, c in passed),
                    "weakest": min(TRUST_RANK[c["trust"]] for _, c in passed),
                    "labels": [pid for pid, _ in passed],
                }
        if not cleared:
            return {"winner": None, "provisional": True, "evidence": "none", "measure": "No repo cleared this category's bar on any evidence."}
        winner = max(cleared, key=lambda t: (cleared[t]["n"], cleared[t]["mag"]))
        rank = cleared[winner]["weakest"]
        evidence = {0: "claimed", 1: "reported-math", 2: "artifact-backed", 3: "verified"}[rank]
        return {"winner": winner, "provisional": rank < 3, "evidence": evidence,
                "measure": breadth_measure(crit, winner, team_ids, cleared)}

    # Headline pass-based fallback (single-path thresholded categories).
    outcomes = {}
    for tid in team_ids:
        if tid not in crit["teams"]:
            continue
        c = headline_cell(crit, tid)
        if c and c.get("outcome") == "passes":
            outcomes[tid] = (TRUST_RANK[c["trust"]], c.get("goodness") or 0, c["trust"])
    if not outcomes:
        return {"winner": None, "provisional": True, "evidence": "none", "measure": "No repo cleared this category's bar on any evidence."}
    art = {t: v for t, v in outcomes.items() if v[0] >= 2}
    pool, provisional = (art, False) if art else (outcomes, True)
    winner = max(pool, key=lambda t: (pool[t][1], breadth(crit, t)))
    return {"winner": winner, "provisional": provisional, "evidence": pool[winner][2],
            "measure": pass_measure(crit, winner, team_ids, provisional)}


def breadth(crit, tid) -> int:
    return sum(1 for c in crit["teams"][tid]["cells"].values()
               if c.get("kind") == "reduction" and (c.get("goodness") or -1) > 0)


def verified_measure(crit, winner, team_ids) -> str:
    handle = short_team(winner)
    wins = sum(1 for p in crit["parts"] if winner in row_winners(crit, p["id"], team_ids))
    nred = sum(1 for p in crit["parts"] if p["kind"] == "reduction")
    hc = headline_cell(crit, winner)
    facts = [
        "BEST BY: fewest verified remaining violations — the harness counted them with the TypeScript",
        "compiler, the same way for every repo. (% reduction pending a verified baseline.)",
        "",
        f"PROS — {handle}",
        f"• Fewest remaining of any repo: {hc['remaining']} total.",
        f"• Wins {wins} of {nred} measured sub-metrics on verified evidence.",
    ]
    for tid in team_ids:
        if tid == winner or tid not in crit["teams"]:
            continue
        c = headline_cell(crit, tid)
        if c and c.get("flagged"):
            facts.append(f"WHY NOT {short_team(tid)}: self-reported {c.get('claimed_after')} but the compiler "
                         f"finds {c['remaining']}. Self-report rejected.")
    return "\n".join(facts)


def breadth_measure(crit, winner, team_ids, cleared) -> str:
    handle = short_team(winner)
    w = cleared[winner]
    by_id = {p["id"]: p for p in crit["parts"]}
    def desc(tid, pid):
        cell = crit["teams"][tid]["cells"][pid]
        return f"{by_id[pid]['label']} {cell['display']}"
    cleared_desc = " AND ".join(desc(winner, pid) for pid in w["labels"])
    lines = [
        "BEST BY: clearing the most of the category goal (spec allows either path — doing both is more), then total reduction.",
        "UNVERIFIED — self-reported; the harness has not built these bundles.",
        "",
        f"PROS — {handle}",
        f"• Cleared {w['n']} of {len(crit['parts'])} paths: {cleared_desc}.",
    ]
    for tid in team_ids:
        if tid == winner or tid not in crit["teams"]:
            continue
        oc = cleared.get(tid)
        lines.append(f"• {short_team(tid)} cleared {oc['n']} path(s) only." if oc else f"• {short_team(tid)} cleared none.")
    lines += [
        "",
        "CAVEAT",
        "• All bundle numbers are self-reported; no independent build yet.",
        "• Self-reports were wrong this week — type-safety claims got rejected on verification — so verify before trusting.",
    ]
    return "\n".join(lines)


def pass_measure(crit, winner, team_ids, provisional) -> str:
    handle = short_team(winner)
    rule = "BEST BY: highest reduction on a passing spec path (UNVERIFIED — self-reported)."
    facts = [rule, "", f"PROS — {handle}"]
    wins = sum(1 for p in crit["parts"] if winner in row_winners(crit, p["id"], team_ids))
    facts.append(f"• Leads {wins} path(s) on the top evidence tier present.")
    cav = crit["teams"][winner]["info"]["caveats"]
    if cav:
        facts.append("Note: " + cav[0])
    facts.append("• Not yet verified by the harness — no method has measured bundle size independently.")
    if provisional:
        facts.append("(Provisional — only reported-math evidence passed.)")
    return "\n".join(facts)


def overall_winner(model, cat_winners) -> dict[str, Any]:
    team_ids = model["team_ids"]
    strength = {tid: 0 for tid in team_ids}
    for crit in model["criteria"]:
        cw = cat_winners[crit["id"]]
        if cw["winner"]:
            strength[cw["winner"]] += TRUST_STRENGTH.get(cw["evidence"], 0)
    stars = {tid: 0 for tid in team_ids}
    for crit in model["criteria"]:
        for p in crit["parts"]:
            for tid in row_winners(crit, p["id"], team_ids):
                stars[tid] += 1
    winner = max(team_ids, key=lambda tid: (strength[tid], stars[tid]))
    led = [crit["name"] for crit in model["criteria"] if cat_winners[crit["id"]]["winner"] == winner]
    measure = (
        "BEST BY: categories led, weighted by evidence strength (verified > artifact > reported).\n"
        "Leading a VERIFIED category outranks leading an unverified one.\n\n"
        f"PROS — {short_team(winner)}\n"
        f"• Leads: {', '.join(led) or 'none'}.\n"
        f"• {stars[winner]} metric wins across the week.\n\n"
        "CAVEAT\n• Only Type Safety is harness-verified so far; Bundle Size is still self-reported.\n"
        "• % reduction is pending a verified baseline."
    )
    return {"winner": winner, "measure": measure, "strength": strength, "stars": stars}


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def cell_html(cell: dict[str, Any] | None, is_winner: bool) -> str:
    if not cell:
        return "<td class='cell na'>—</td>"
    star = "<span class='star'>★</span> " if is_winner else ""
    rung = cell.get("trust", "")
    rung_html = f"<span class='rung {TRUST_SHORT.get(rung, '')}'>{esc(TRUST_SHORT.get(rung, rung))}</span>"
    if cell["kind"] == "boolean":
        return f"<td class='cell'><span class='num'>{esc(cell.get('value'))}</span> {rung_html}</td>"
    if cell.get("goodness") is None and cell.get("display") == "n/a":
        return f"<td class='cell na'>{'—' if cell.get('judgment') == 'not_claimed' else 'n/a'}</td>"

    jcss = JUDGMENT_CSS.get(cell.get("judgment", ""), "")
    jg = JUDGMENT_GLYPH.get(cell.get("judgment", ""), "")
    jhtml = f" <span class='j {jcss}'>{jg}</span>" if jg else ""
    flag = ""
    title = ""
    if cell.get("verified"):
        if cell.get("flagged"):
            flag = " <span class='flagmark' title='self-report rejected'>⚠</span>"
        title = f" title='claimed after {cell.get('claimed_after')}, verified {cell.get('remaining')}'"
    num_cls = "down" if (cell.get("value_kind") == "remaining" or (cell.get("reduction_percent") or 0) > 0) else "flat"
    cls_cell = "cell best" if is_winner else "cell"
    return (f"<td class='{cls_cell}'{title}>{star}<span class='num {num_cls}'>{esc(cell['display'])}</span> "
            f"{rung_html}{jhtml}{flag}</td>")


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
        ver = " <span class='vbadge'>verified</span>" if crit.get("verified_kind") else " <span class='ubadge'>self-reported</span>"
        if cw["winner"]:
            prov = " <span class='prov'>(prov.)</span>" if cw["provisional"] else ""
            badge = f"<span class='catbest tip' data-tip='{tip(cw['measure'])}'>🏆 {esc(handles[cw['winner']])}{prov}</span>"
        else:
            badge = "<span class='catbest'>no winner</span>"
        rows = [f"<tr class='catrow'><td colspan='{len(team_ids)+1}'><span class='catname'>{esc(crit['name'])}</span>{ver}{badge}</td></tr>"]
        for p in crit["parts"]:
            winners = row_winners(crit, p["id"], team_ids)
            cells = "".join(cell_html(crit["teams"].get(tid, {}).get("cells", {}).get(p["id"]), tid in winners) for tid in team_ids)
            rows.append(f"<tr><td class='mlabel'>{esc(p['label'])}</td>{cells}</tr>")
        bands.append("".join(rows))

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>G4A Week 4 — who did best</title>
<style>
  :root{{--ink:#191919;--muted:#6b655d;--paper:#f5f1e9;--panel:#fffdf8;--line:#d6cdbf;--good:#1c6b54;--good-bg:#e6f3ec;--bad:#9c2f25;--bad-bg:#f8e1de;--grey:#7c756b;--grey-bg:#ece7dd;--blue:#274f7f;--warn:#9a5a10;--warn-bg:#fdf0d8;--gold:#9a7a16;--gold-bg:#fbf3d6;}}
  *{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.4}}
  main{{max-width:1000px;margin:0 auto;padding:26px 20px 90px}} h1{{font-size:30px;margin:0 0 4px}}
  .lead{{color:var(--muted);max-width:780px;margin:0 0 18px;font-size:14px}}
  .overall{{display:flex;align-items:center;gap:12px;background:var(--gold-bg);border:1px solid var(--gold);padding:12px 16px;margin-bottom:18px}}
  .overall .lbl{{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}} .overall .who{{font-size:22px;font-weight:850;color:var(--gold)}}
  table{{width:100%;border-collapse:collapse}}
  thead .repohead{{text-align:center;font-weight:850;font-size:16px;border-bottom:2px solid var(--ink);width:24%;padding:8px 10px}}
  thead .metrichead{{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.06em;width:28%;text-align:left;padding:8px 10px}}
  tr.catrow td{{background:#ece4d7;border-top:1px solid var(--line);padding:8px 10px}}
  .catname{{font-weight:850;font-size:13px;text-transform:uppercase;letter-spacing:.05em}}
  .vbadge{{font-size:10px;font-weight:800;color:var(--good);background:var(--good-bg);border:1px solid var(--good);padding:1px 6px;border-radius:8px;text-transform:uppercase;margin-left:8px}}
  .ubadge{{font-size:10px;font-weight:800;color:var(--warn);background:var(--warn-bg);border:1px solid var(--warn);padding:1px 6px;border-radius:8px;text-transform:uppercase;margin-left:8px}}
  .catbest{{float:right;font-weight:800;font-size:12px;color:var(--gold)}} .prov{{color:var(--muted);font-weight:600}}
  tbody td{{border-bottom:1px solid var(--line);padding:7px 10px;vertical-align:middle}} .mlabel{{color:var(--muted);font-size:13px}}
  .cell{{text-align:center;width:24%}} .num{{font-weight:800;font-size:15px}} .down{{color:var(--good)}} .flat{{color:var(--bad)}} .na{{color:var(--grey);font-weight:600;text-align:center}}
  .rung{{display:inline-block;font-size:9px;font-weight:700;padding:0 5px;border-radius:8px;border:1px solid currentColor;vertical-align:middle}}
  .md{{color:var(--warn);background:var(--warn-bg)}} .art{{color:var(--blue);background:#e4ecf6}} .ver{{color:var(--good);background:var(--good-bg)}} .claim{{color:var(--grey);background:var(--grey-bg)}}
  .j{{font-size:10px;font-weight:800;vertical-align:middle}} .j-ok{{color:var(--good)}} .j-q{{color:var(--warn)}} .j-x{{color:var(--bad)}} .j-na{{color:var(--grey)}}
  .flagmark{{color:var(--bad);font-weight:900}} .best{{background:var(--gold-bg);box-shadow:inset 3px 0 0 var(--gold)}} .star{{color:var(--gold)}}
  .tip{{position:relative;cursor:help}} .tip::before{{content:"ⓘ";font-size:11px;color:var(--muted);margin-left:5px;font-weight:700}}
  .tip:hover::after{{content:attr(data-tip);position:absolute;right:0;top:130%;white-space:pre-line;width:340px;background:#1d1b16;color:#f4efe6;padding:10px 12px;font-size:12px;line-height:1.4;border-radius:5px;z-index:30;font-weight:500;box-shadow:0 6px 20px rgba(0,0,0,.3);text-transform:none;letter-spacing:0;text-align:left}}
  .legend{{font-size:12px;color:var(--muted);margin-top:18px}}
</style></head>
<body><main>
  <h1>Week 4 — who did best</h1>
  <p class="lead">Scan a row for the metric winner (★), a band for the category winner (🏆). Ranking is
  <strong>trust-gated and verification beats self-report</strong>: a <span class="vbadge">verified</span> band was
  measured by the harness; a <span class="ubadge">self-reported</span> one was not. Type-safety cells show
  <strong>remaining violations</strong> (fewer is better) the harness counted with the TS compiler. Hover any
  <span style="color:var(--muted)">ⓘ</span> for the measure + pros.</p>

  <div class="overall">
    <span class="lbl">Overall lead</span>
    <span class="who">{esc(handles[overall['winner']])} 🏆</span>
    <span class="prov tip" data-tip="{tip(overall['measure'])}">provisional</span>
  </div>

  <table><thead><tr><th class="metrichead">metric</th>{head_cols}</tr></thead>
  <tbody>{''.join(bands)}</tbody></table>

  <p class="legend">
    ★ best in row (trust-gated) &nbsp;·&nbsp; 🏆 best in category &nbsp;·&nbsp;
    rung: <span class="rung ver">ver</span> harness-verified, <span class="rung art">art</span> artifact, <span class="rung md">md</span> reported-math &nbsp;·&nbsp;
    <span class="flagmark">⚠</span> self-report rejected &nbsp;·&nbsp; hover <span style="color:var(--muted)">ⓘ</span> for measure + pros
  </p>
</main></body></html>
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
