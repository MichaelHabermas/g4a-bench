#!/usr/bin/env python3
"""Render a tabbed benchmark workbench for a run."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path("/Users/michaelhabermas/repos/GAI/g4a-bench")
RUNS_DIR = ROOT / "g4a-benchmarks/g4a-c5-2/week-4/runs"


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_run() -> Path:
    candidates = sorted(path for path in RUNS_DIR.glob("*") if path.is_dir())
    if not candidates:
        raise SystemExit(f"No run directories found under {RUNS_DIR}")
    return candidates[-1]


def state_badge(value: str) -> str:
    css = "good" if value in {"strong", "clear", "passes", "artifact-backed"} else "bad" if value in {"blocked", "missing", "not reproduced"} else "warn"
    return f"<span class='badge {css}'>{esc(value)}</span>"


def target_label(team: dict[str, Any]) -> str:
    paths = team.get("target_paths") or []
    passing = [path for path in paths if str(path.get("state", "")).startswith("passes_")]
    total = next((path for path in paths if path.get("id") == "total-production-bundle"), {})
    initial = next((path for path in paths if path.get("id") == "initial-load-code-splitting"), {})
    if total.get("state") == "passes_markdown_math" and initial.get("state") == "passes_markdown_math":
        return "both paths reported"
    if initial.get("state") == "passes_artifact_math" and total.get("state") != "passes_artifact_math":
        return "initial path only"
    if passing:
        return "one path passes"
    return "unresolved"


def readiness(team: dict[str, Any]) -> dict[str, Any]:
    states = {item["name"]: item["value"] for item in team.get("evidence_states") or []}
    paths = team.get("target_paths") or []
    any_pass = any(str(path.get("state", "")).startswith("passes_") for path in paths)
    artifact_backed = states.get("artifact_backed") == "yes"
    markdown_backed = states.get("artifact_backed") == "markdown_backed"
    comparable = states.get("comparability") in {"plausible_not_verified", "needs_agent_review"}
    explicit = states.get("path_choice_explicit") == "yes"

    target_points = 3 if any_pass else 0
    evidence_points = 3 if artifact_backed else 1 if markdown_backed else 0
    clarity_points = 2 if explicit else 0
    comparability_points = 1 if comparable else 0
    reproduction_points = 0
    total = target_points + evidence_points + clarity_points + comparability_points + reproduction_points

    if total >= 8 and artifact_backed:
        label = "strong candidate"
    elif total >= 6:
        label = "review candidate"
    elif total >= 3:
        label = "weak candidate"
    else:
        label = "insufficient"

    return {
        "label": label,
        "points": total,
        "max_points": 12,
        "target": target_points,
        "evidence": evidence_points,
        "clarity": clarity_points,
        "comparability": comparability_points,
        "reproduction": reproduction_points,
        "target_label": target_label(team),
    }


def summary_rows(teams: list[dict[str, Any]]) -> str:
    rows = []
    for team in teams:
        rating = readiness(team)
        rows.append(
            "<tr>"
            f"<th>{esc(team['team'])}</th>"
            f"<td>{state_badge(rating['label'])}<div class='score'>{rating['points']} / {rating['max_points']}</div></td>"
            f"<td>{esc(rating['target_label'])}</td>"
            f"<td>{esc(team.get('team_shape'))}</td>"
            f"<td>{esc(team.get('provisional_judgment', {}).get('summary'))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def dimension_rows(teams: list[dict[str, Any]]) -> str:
    dims = [
        ("target", "Does extracted math satisfy an allowed spec path?"),
        ("evidence", "Is the measurement backed by raw artifacts, or only prose?"),
        ("clarity", "Does the repo make the claimed path explicit?"),
        ("comparability", "Can before/after plausibly be compared?"),
        ("reproduction", "Has the harness rerun it from a clean clone?"),
    ]
    rows = []
    for key, label in dims:
        cells = [f"<th>{esc(label)}</th>"]
        for team in teams:
            value = readiness(team)[key]
            cells.append(f"<td><div class='meter'><i style='width:{value / 3 * 100 if key in {'target', 'evidence'} else value / 2 * 100 if key == 'clarity' else value * 100}%'></i></div><strong>{value}</strong></td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    return "\n".join(rows)


def compact_trace(team: dict[str, Any]) -> str:
    targets = []
    for path in team.get("target_paths") or []:
        targets.append(
            "<tr>"
            f"<th>{esc(path['id'])}</th>"
            f"<td>{esc(path['before_kb'])}</td>"
            f"<td>{esc(path['after_kb'])}</td>"
            f"<td>{esc(path['reduction_percent'])}</td>"
            f"<td>{state_badge(str(path['state']))}</td>"
            "</tr>"
        )
    states = []
    for item in team.get("evidence_states") or []:
        states.append(
            "<tr>"
            f"<th>{esc(item['name'])}</th>"
            f"<td>{state_badge(str(item['value']))}</td>"
            f"<td>{esc(item['note'])}</td>"
            "</tr>"
        )
    inventory = team.get("discovery_inventory") or {}
    inventory_items = "".join(
        f"<li><strong>{esc(key)}</strong>: {len(value or [])}</li>"
        for key, value in inventory.items()
    )
    return f"""
    <article class="trace-card">
      <h3>{esc(team['team'])}</h3>
      <p class="muted">{esc(team.get('team_shape'))}</p>
      <div class="trace-grid">
        <div>
          <h4>Target Math</h4>
          <table><thead><tr><th>Path</th><th>Before</th><th>After</th><th>Reduction</th><th>State</th></tr></thead><tbody>{''.join(targets)}</tbody></table>
        </div>
        <div>
          <h4>Discovery Counts</h4>
          <ul class="counts">{inventory_items}</ul>
        </div>
      </div>
      <h4>Judgment States</h4>
      <table><tbody>{''.join(states)}</tbody></table>
    </article>
    """


def next_experiments() -> list[dict[str, str]]:
    return [
        {
            "name": "Markdown claim compiler",
            "recommendation": "Do this next.",
            "why": "Shiv's repo shows the common case: the evidence is in Markdown tables. The harness needs to extract claims from prose, then downgrade trust until raw artifacts or reruns exist.",
        },
        {
            "name": "Clean-clone bundle rerunner",
            "recommendation": "Do after claim compiler.",
            "why": "All three are currently not reproduced. This is the first thing that turns evidence review into benchmark measurement.",
        },
        {
            "name": "Comparability verifier",
            "recommendation": "Build as a judgment agent prompt plus deterministic checks.",
            "why": "The hard question is not only whether numbers changed. It is whether baseline/current use the same command, output scope, compression basis, and functionality.",
        },
        {
            "name": "Noise reducer",
            "recommendation": "Keep lightweight for now.",
            "why": "Discovery counts are too large. We need to classify copied specs, public duplicates, generated evidence bundles, and source-of-truth reports.",
        },
    ]


def experiment_cards() -> str:
    cards = []
    for item in next_experiments():
        cards.append(
            f"<article class='experiment'><h3>{esc(item['name'])}</h3><strong>{esc(item['recommendation'])}</strong><p>{esc(item['why'])}</p></article>"
        )
    return "\n".join(cards)


def rerun_command_plan(team: dict[str, Any]) -> list[dict[str, str]]:
    shape = team.get("team_shape")
    if shape == "structured_ledger_with_artifact_pointers":
        return [
            {
                "step": "Locate declared artifacts",
                "command": "test -f my-docs/audit-evidence/category-2-bundle/bundle-stats.json && test -f my-docs/evidence-runs/cat2-easy-wins-20260523/collectors/bundle-stats.json",
                "expected": "Both declared bundle-stat artifacts exist in the clean clone.",
            },
            {
                "step": "Rebuild current bundle",
                "command": "pnpm install --frozen-lockfile && pnpm build:web",
                "expected": "Production web build succeeds without relying on committed dist output.",
            },
            {
                "step": "Rerun collector",
                "command": "node scripts/evidence/collectors/bundle-stats.mjs",
                "expected": "Collector emits current entry chunk, total JS/CSS, largest chunks, and countable outputs.",
            },
        ]
    if shape == "before_after_bundle_json_with_delta_markdown":
        return [
            {
                "step": "Verify submitted pair",
                "command": "node scripts/category-improvements/verify-bundle-size-evidence.mjs",
                "expected": "Before/after JSON pair validates and reproduces the submitted delta table.",
            },
            {
                "step": "Rebuild current bundle",
                "command": "pnpm install --frozen-lockfile && pnpm build:web",
                "expected": "Production web build succeeds from clean clone.",
            },
            {
                "step": "Rerun measurement script",
                "command": "node scripts/category-improvements/measure-bundle-size.mjs --label harness-current",
                "expected": "New current measurement matches the submitted after directionally.",
            },
        ]
    if shape == "markdown_bundle_report_with_progressive_measurements":
        return [
            {
                "step": "Compile Markdown claim",
                "command": "parse docs/audit/category-2-bundle-size.md for scorecard, methodology, pass history, and commands",
                "expected": "Extract both reported target paths and the stated build/analysis commands.",
            },
            {
                "step": "Generate missing raw artifact",
                "command": "pnpm install --frozen-lockfile && pnpm build:web && du -sh web/dist",
                "expected": "Current total dist can be measured directly instead of trusted from Markdown.",
            },
            {
                "step": "Generate treemap",
                "command": "ANALYZE_BUNDLE=true pnpm build:web",
                "expected": "Treemap/stats artifact exists and can confirm initial chunks and package composition.",
            },
        ]
    return [
        {
            "step": "Find source of truth",
            "command": "rg -n -i 'bundle|initial|chunk|code.?split|treemap|dist|gzip|before|after' .",
            "expected": "Identify candidate reports, scripts, or artifacts before attempting measurement.",
        }
    ]


def rating_rules(team: dict[str, Any]) -> list[str]:
    states = {item["name"]: item["value"] for item in team.get("evidence_states") or []}
    rules = [
        "Upgrade reproduction from 0 when a clean-clone rerun produces comparable current measurements.",
        "Downgrade target confidence if the rerun does not match the submitted after numbers directionally.",
        "Downgrade comparability if commands, output scope, raw/gzip basis, or baseline/current commits do not line up.",
    ]
    if states.get("artifact_backed") == "markdown_backed":
        rules.insert(0, "Upgrade evidence from Markdown-backed to artifact-backed only after raw bundle artifacts are generated or found.")
    else:
        rules.insert(0, "Keep evidence artifact-backed only if the rerun can point to raw generated outputs, not just committed summaries.")
    return rules


def blocker_list(team: dict[str, Any]) -> list[str]:
    shape = team.get("team_shape")
    common = [
        "Dependency install may fail or take long in clean clone.",
        "Build may require environment variables not present in the benchmark worker.",
        "Baseline commit may not be reconstructable from submitted artifacts alone.",
    ]
    if shape == "markdown_bundle_report_with_progressive_measurements":
        common.append("Markdown report claims a baseline, but no raw before JSON was recognized.")
    if shape == "structured_ledger_with_artifact_pointers":
        common.append("Baseline and latest artifacts may have been produced by different collectors or scopes.")
    if shape == "before_after_bundle_json_with_delta_markdown":
        common.append("Submitted before/after artifacts may both come from current repo state rather than distinct commits.")
    return common


def list_items(items: list[str]) -> str:
    return "".join(f"<li>{esc(item)}</li>" for item in items)


def command_rows(commands: list[dict[str, str]]) -> str:
    rows = []
    for item in commands:
        rows.append(
            "<tr>"
            f"<th>{esc(item['step'])}</th>"
            f"<td><code>{esc(item['command'])}</code></td>"
            f"<td>{esc(item['expected'])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def rerun_plan_cards(teams: list[dict[str, Any]]) -> str:
    cards = []
    for team in teams:
        cards.append(
            f"""
            <article class="trace-card">
              <h3>{esc(team['team'])}</h3>
              <p class="muted">{esc(team.get('team_shape'))}</p>
              <h4>Commands To Try</h4>
              <table>
                <thead><tr><th>Step</th><th>Command</th><th>Expected Evidence</th></tr></thead>
                <tbody>{command_rows(rerun_command_plan(team))}</tbody>
              </table>
              <div class="rerun-grid">
                <div>
                  <h4>Blockers To Watch</h4>
                  <ul>{list_items(blocker_list(team))}</ul>
                </div>
                <div>
                  <h4>Rating Change Rules</h4>
                  <ul>{list_items(rating_rules(team))}</ul>
                </div>
              </div>
            </article>
            """
        )
    return "\n".join(cards)


def render(run_dir: Path) -> str:
    trace = read_json(run_dir / "bundle-trace.json")
    teams = trace["teams"]
    team_headers = "".join(f"<th>{esc(team['team'])}</th>" for team in teams)
    trace_cards = "\n".join(compact_trace(team) for team in teams)
    rerun_cards = rerun_plan_cards(teams)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>G4A Benchmark Workbench</title>
  <style>
    :root {{
      --ink: #171717;
      --muted: #66615b;
      --paper: #f4f0e8;
      --panel: #fffdf8;
      --line: #d2cabd;
      --good: #176b55;
      --warn: #9a5a10;
      --bad: #9c2f25;
      --blue: #274f7f;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--paper); color: var(--ink); font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.38; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 28px 22px 54px; }}
    header {{ display: flex; justify-content: space-between; gap: 20px; align-items: end; border-bottom: 2px solid var(--ink); padding-bottom: 16px; }}
    h1 {{ margin: 0; font-size: clamp(34px, 5vw, 60px); line-height: .95; letter-spacing: 0; }}
    h2 {{ margin: 0 0 14px; font-size: 24px; }}
    h3 {{ margin: 0 0 8px; font-size: 18px; }}
    h4 {{ margin: 18px 0 8px; font-size: 13px; text-transform: uppercase; letter-spacing: .08em; }}
    p {{ margin: 0 0 10px; }}
    .muted {{ color: var(--muted); }}
    .tabs {{ display: flex; gap: 8px; margin: 20px 0; border-bottom: 1px solid var(--line); }}
    .tab-button {{ appearance: none; border: 1px solid var(--line); border-bottom: 0; background: #ebe3d6; color: var(--ink); padding: 10px 14px; font-weight: 750; cursor: pointer; }}
    .tab-button.active {{ background: var(--panel); color: var(--blue); }}
    .tab {{ display: none; background: var(--panel); border: 1px solid var(--line); padding: 18px; }}
    .tab.active {{ display: block; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #eee6da; font-weight: 760; }}
    .score {{ margin-top: 4px; font-weight: 800; }}
    .badge {{ display: inline-block; padding: 3px 8px; border: 1px solid currentColor; font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; }}
    .good {{ color: var(--good); background: #e7f4ee; }}
    .warn {{ color: var(--warn); background: #fff2d8; }}
    .bad {{ color: var(--bad); background: #f9e2df; }}
    .meter {{ width: 120px; height: 8px; background: #e0d8cc; display: inline-block; margin-right: 8px; vertical-align: middle; }}
    .meter i {{ display: block; height: 100%; background: var(--blue); }}
    .trace-card, .experiment {{ border: 1px solid var(--line); padding: 14px; margin: 14px 0; background: #fffaf1; }}
    .trace-grid {{ display: grid; grid-template-columns: minmax(0, 1fr) 220px; gap: 14px; align-items: start; }}
    .rerun-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; align-items: start; }}
    .counts {{ margin: 0; padding-left: 18px; }}
    .experiments {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }}
    .note {{ max-width: 720px; }}
    @media (max-width: 860px) {{
      header, .trace-grid, .rerun-grid, .experiments {{ grid-template-columns: 1fr; display: block; }}
      table {{ display: block; overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <p class="muted">Week 4 · Bundle-size specimen · Run {esc(trace['run_id'])}</p>
        <h1>Benchmark Workbench</h1>
      </div>
      <p class="note muted">This page separates measurement readiness from final grading. It is asking: how usable is the evidence, where did it come from, and what judgment should the evaluator make next?</p>
    </header>

    <nav class="tabs">
      <button class="tab-button active" data-tab="ratings">Ratings</button>
      <button class="tab-button" data-tab="trace">Bundle Trace</button>
      <button class="tab-button" data-tab="rerun">Rerun Plan</button>
      <button class="tab-button" data-tab="next">Next Experiments</button>
    </nav>

    <section id="ratings" class="tab active">
      <h2>Measurement Readiness</h2>
      <table>
        <thead><tr><th>Team</th><th>Readiness</th><th>Target Path</th><th>Evidence Shape</th><th>Current Judgment</th></tr></thead>
        <tbody>{summary_rows(teams)}</tbody>
      </table>

      <h2 style="margin-top:22px">Why Those Ratings</h2>
      <table>
        <thead><tr><th>Dimension</th>{team_headers}</tr></thead>
        <tbody>{dimension_rows(teams)}</tbody>
      </table>
    </section>

    <section id="trace" class="tab">
      <h2>Compact Bundle Trace</h2>
      {trace_cards}
    </section>

    <section id="rerun" class="tab">
      <h2>Rerun Plan</h2>
      <p class="muted">This is the bridge from submitted evidence to benchmark measurement. These commands are not yet executed by this page; they are the next evaluator actions and the rules for changing the readiness rating.</p>
      {rerun_cards}
    </section>

    <section id="next" class="tab">
      <h2>Recommended Next Tabs / Capabilities</h2>
      <div class="experiments">{experiment_cards()}</div>
    </section>
  </main>
  <script>
    const buttons = document.querySelectorAll('.tab-button');
    const tabs = document.querySelectorAll('.tab');
    buttons.forEach((button) => {{
      button.addEventListener('click', () => {{
        buttons.forEach((item) => item.classList.remove('active'));
        tabs.forEach((item) => item.classList.remove('active'));
        button.classList.add('active');
        document.getElementById(button.dataset.tab).classList.add('active');
      }});
    }});
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=None)
    args = parser.parse_args()
    run_dir = args.run_dir or latest_run()
    out = run_dir / "workbench.html"
    out.write_text(render(run_dir), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
