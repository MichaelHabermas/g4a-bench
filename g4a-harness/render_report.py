#!/usr/bin/env python3
"""Render a static HTML report for a benchmark run."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


CATEGORIES = [
    "type safety",
    "bundle size",
    "api response time",
    "database query",
    "test coverage",
    "runtime error",
    "accessibility",
    "security",
]

CRITERIA = [
    ("W4-DOCS-01", "Deliverables"),
    ("W4-AUDIT-01", "Audit Coverage"),
    ("W4-PROOF-01", "Proof"),
    ("W4-SECURITY-01", "Security"),
    ("W4-TESTS-01", "Tests"),
    ("W4-REPO-01", "Repo Health"),
    ("W4-INSIGHT-01", "Impressions"),
]


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_run(root: Path) -> Path:
    candidates = sorted(path for path in root.glob("*") if path.is_dir())
    if not candidates:
        raise SystemExit(f"No run directories found under {root}")
    return candidates[-1]


def score_class(score: float) -> str:
    if score >= 95:
        return "score-high"
    if score >= 85:
        return "score-mid"
    return "score-low"


def criterion_rows(results: list[dict[str, Any]]) -> str:
    rows = []
    for criterion_id, label in CRITERIA:
        cells = [f"<td class='criterion'>{esc(label)}</td>"]
        for result in results:
            score = float(result["scores"].get(criterion_id, 0))
            cells.append(
                "<td>"
                f"<div class='mini-score'><span>{score:g}</span><i style='width:{min(score, 100)}%'></i></div>"
                "</td>"
            )
        rows.append(f"<tr>{''.join(cells)}</tr>")
    return "\n".join(rows)


def coverage_cells(result: dict[str, Any]) -> str:
    path_hits = result.get("category_path_hits") or {}
    ledger = result.get("submission_ledger") or {}
    ledger_metrics = {}
    for item in ledger.get("summaries") or []:
        metrics = item.get("metrics") or []
        caveats = item.get("caveats") or []
        detail = "; ".join(metrics[:2])
        if caveats:
            detail = f"{detail} | Caveat: {caveats[0]}" if detail else f"Caveat: {caveats[0]}"
        ledger_metrics[item.get("key")] = detail
    cells = []
    for category in CATEGORIES:
        count = int(path_hits.get(category, 0))
        state = "hot" if count >= 20 else "warm" if count > 0 else "cold"
        detail = ledger_metrics.get(category) or f"{count} evidence paths"
        cells.append(
            f"<div class='heat {state}' title='{esc(category)}: {esc(detail)}'>"
            f"<span>{esc(category)}<em>{esc(detail)}</em></span><strong>{count}</strong></div>"
        )
    return "\n".join(cells)


def list_items(items: list[str], empty: str) -> str:
    if not items:
        return f"<li>{esc(empty)}</li>"
    return "".join(f"<li>{esc(item)}</li>" for item in items)


def agent_review_section(results: list[dict[str, Any]]) -> str:
    questions_by_category: dict[str, list[str]] = {}
    for result in results:
        for item in result.get("category_review_items") or []:
            category = item.get("category")
            if not category:
                continue
            questions_by_category.setdefault(category, [])
            for question in item.get("review_questions") or []:
                if question not in questions_by_category[category]:
                    questions_by_category[category].append(question)

    blocks = []
    for category in CATEGORIES:
        questions = questions_by_category.get(category) or ["Agent review questions were not generated for this category."]
        blocks.append(
            f"<article><h3>{esc(category)}</h3><ul>{list_items(questions, 'No questions generated.')}</ul></article>"
        )
    return "\n".join(blocks)


def render(run_dir: Path) -> str:
    rankings = read_json(run_dir / "rankings.json")["rankings"]
    results = sorted(rankings, key=lambda item: item["total_score"], reverse=True)
    run = read_json(run_dir / "run.json")

    team_headers = "".join(f"<th>{esc(result['team'])}</th>" for result in results)
    team_cards = []
    for index, result in enumerate(results, 1):
        missing = [name for name, count in (result.get("category_path_hits") or {}).items() if count == 0]
        ledger = result.get("submission_ledger") or {}
        basis = result.get("extraction_basis", "unknown")
        not_verified = result.get("not_independently_verified") or []
        ledger_note = ""
        if ledger:
            ledger_note = (
                f"<p class='ledger'>Structured ledger: {esc(ledger.get('proven_count', 0))} / "
                f"{esc(ledger.get('category_count', 0))} categories proven.</p>"
            )
        else:
            ledger_note = "<p class='ledger muted'>No structured ledger found; heuristic parsing only.</p>"
        team_cards.append(
            f"""
            <section class="team-card">
              <div class="rank-pill">#{index}</div>
              <h2>{esc(result['team'])}</h2>
              <div class="score {score_class(float(result['total_score']))}">{float(result['total_score']):.2f}</div>
              <p class="subscore">extraction confidence, not final grade</p>
              {ledger_note}
              <p class="basis">Basis: {esc(basis.replace('_', ' '))}</p>
              <dl>
                <div><dt>Commit</dt><dd>{esc(result.get('commit_sha') or 'unknown')[:12]}</dd></div>
                <div><dt>Evidence Files</dt><dd>{esc(result.get('submission_evidence_file_count', 0))}</dd></div>
                <div><dt>Test Files</dt><dd>{esc(result.get('test_file_count', 0))}</dd></div>
              </dl>
              <div class="coverage-grid">{coverage_cells(result)}</div>
              <h3>Strengths</h3>
              <ul>{list_items(result.get('strengths') or [], 'No static standout found.')}</ul>
              <h3>Risks</h3>
              <ul>{list_items(result.get('risks') or [], 'No major static risk found.')}</ul>
              <h3>Impression Notes</h3>
              <ul>{list_items(result.get('impressions') or [], 'No impression notes triggered.')}</ul>
              <h3>Not Verified Yet</h3>
              <ul>{list_items(not_verified[:5], 'No unverified items listed.')}</ul>
              {f"<p class='missing'>Missing category evidence: {esc(', '.join(missing))}</p>" if missing else ""}
            </section>
            """
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>G4A Week 4 Prototype Findings</title>
  <style>
    :root {{
      --ink: #171717;
      --muted: #65615b;
      --paper: #f7f4ee;
      --panel: #fffcf6;
      --line: #d9d1c3;
      --green: #22745f;
      --amber: #b36b16;
      --red: #a13d2d;
      --blue: #2d5f8f;
      --shadow: 0 18px 45px rgba(35, 29, 20, .11);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        linear-gradient(90deg, rgba(23,23,23,.035) 1px, transparent 1px) 0 0 / 28px 28px,
        linear-gradient(rgba(23,23,23,.028) 1px, transparent 1px) 0 0 / 28px 28px,
        var(--paper);
      font-family: "Avenir Next", "Gill Sans", Verdana, sans-serif;
      line-height: 1.45;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 44px 24px 64px; }}
    header {{
      display: grid;
      grid-template-columns: 1.3fr .7fr;
      gap: 28px;
      align-items: end;
      border-bottom: 2px solid var(--ink);
      padding-bottom: 24px;
      margin-bottom: 28px;
    }}
    .eyebrow {{
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: .12em;
      color: var(--blue);
    }}
    h1 {{
      margin: 8px 0 12px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(38px, 6vw, 76px);
      line-height: .92;
      letter-spacing: 0;
    }}
    .lede {{ max-width: 760px; color: var(--muted); font-size: 18px; }}
    .verdict {{
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      padding: 22px;
    }}
    .verdict strong {{ display: block; font-size: 34px; }}
    .verdict span {{ color: var(--muted); }}
    .notice {{
      border: 1px solid #c9b27c;
      background: #fff4d8;
      padding: 14px 16px;
      margin: 0 0 28px;
      font-weight: 650;
    }}
    .explainer {{
      background: #f0eadf;
      border: 1px solid var(--line);
      padding: 18px 20px;
      margin-bottom: 24px;
    }}
    .explainer h2 {{ margin: 0 0 8px; font-size: 18px; }}
    .explainer p {{ margin: 8px 0; color: #38342f; }}
    .board {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
      margin: 28px 0;
    }}
    .agent-review {{
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      padding: 22px;
      margin: 28px 0;
    }}
    .agent-review h2 {{ margin: 0 0 6px; font-size: 22px; }}
    .agent-review p {{ margin: 0 0 16px; color: var(--muted); }}
    .review-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }}
    .review-grid article {{ border: 1px solid var(--line); padding: 12px; background: #faf6ed; }}
    .review-grid h3 {{ margin-top: 0; }}
    .team-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      padding: 22px;
      position: relative;
      min-width: 0;
    }}
    .rank-pill {{
      position: absolute;
      top: 18px;
      right: 18px;
      border: 1px solid var(--ink);
      padding: 4px 8px;
      font-weight: 900;
      background: var(--paper);
    }}
    h2 {{ margin: 0 48px 12px 0; font-size: 20px; overflow-wrap: anywhere; }}
    h3 {{ margin: 20px 0 8px; font-size: 13px; text-transform: uppercase; letter-spacing: .08em; }}
    .score {{ font-family: Georgia, "Times New Roman", serif; font-size: 64px; line-height: 1; }}
    .score-high {{ color: var(--green); }}
    .score-mid {{ color: var(--amber); }}
    .score-low {{ color: var(--red); }}
    .subscore {{ margin: 2px 0 16px; color: var(--muted); }}
    dl {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 0 0 18px; }}
    dt {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .07em; }}
    dd {{ margin: 0; font-weight: 800; overflow-wrap: anywhere; }}
    .coverage-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }}
    .heat {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      border: 1px solid var(--line);
      padding: 8px;
      min-height: 42px;
      align-items: center;
    }}
    .heat span {{ font-size: 12px; color: var(--muted); }}
    .heat em {{ display: block; margin-top: 4px; font-style: normal; color: var(--ink); font-size: 11px; overflow-wrap: anywhere; }}
    .heat strong {{ font-size: 15px; }}
    .heat.hot {{ background: #dfeee6; border-color: #98c2ad; }}
    .heat.warm {{ background: #fff0d2; border-color: #d8b36a; }}
    .heat.cold {{ background: #f5ded9; border-color: #d99d91; }}
    ul {{ margin: 0; padding-left: 18px; }}
    li {{ margin: 5px 0; }}
    .missing {{ color: var(--red); font-weight: 700; }}
    .ledger {{ margin: -6px 0 16px; font-weight: 800; color: var(--blue); }}
    .basis {{ margin: -8px 0 16px; color: var(--muted); font-weight: 700; }}
    .muted {{ color: var(--muted); }}
    .matrix {{
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      margin-top: 18px;
      overflow-x: auto;
    }}
    table {{ width: 100%; border-collapse: collapse; min-width: 760px; }}
    th, td {{ padding: 14px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: middle; }}
    th {{ font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }}
    .criterion {{ font-weight: 850; }}
    .mini-score {{ position: relative; height: 28px; border: 1px solid var(--line); background: #f0ebe2; overflow: hidden; }}
    .mini-score i {{ display: block; height: 100%; background: #b9d8ca; }}
    .mini-score span {{ position: absolute; inset: 4px 8px; z-index: 1; font-weight: 900; }}
    footer {{ margin-top: 28px; color: var(--muted); font-size: 13px; }}
    @media (max-width: 860px) {{
      header, .board, .review-grid {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 46px; }}
      dl {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <div class="eyebrow">G4A Bench / Week 4 / Evaluation Prototype</div>
        <h1>ShipShape Evaluation Workbench</h1>
        <p class="lede">A temporary report for debugging the benchmark process. It shows what the prototype extracted, what it trusted, what it did not verify, and where an agent must make judgment calls.</p>
      </div>
      <aside class="verdict">
        <span>Status</span>
        <strong>No final grade</strong>
        <span>Run: {esc(run.get('run_id'))}</span>
      </aside>
    </header>
    <div class="notice">Prototype caveat: the large numbers below are extraction confidence, not grades. They do not prove the reported measurements are true, comparable, or sufficient.</div>
    <section class="explainer">
      <h2>How to Read This</h2>
      <p><strong>Extraction confidence</strong> means the prototype found structured or semi-structured evidence. It is useful for triage, not for ranking teams.</p>
      <p><strong>Category tile numbers</strong> mean different things by basis. For a structured ledger, they are ledger evidence objects. For a heuristic repo, they are matching evidence paths. Those are not comparable.</p>
      <p><strong>Agent review required</strong> means a future evaluator must inspect the claim, the artifact, and the target path chosen by the team. Bundle size is the clearest example: total bundle reduction and initial-entry code splitting are both allowed, but they are not the same measurement.</p>
    </section>
    <section class="board">
      {''.join(team_cards)}
    </section>
    <section class="agent-review">
      <h2>Agent Review Required Before Scoring</h2>
      <p>These are the actual judgment calls. A script can prepare the evidence; an evaluator agent has to answer these before a grade is credible.</p>
      <div class="review-grid">{agent_review_section(results)}</div>
    </section>
    <section class="matrix">
      <table>
        <thead><tr><th>Criterion</th>{team_headers}</tr></thead>
        <tbody>{criterion_rows(results)}</tbody>
      </table>
    </section>
    <footer>
      Source artifacts: measurement plan, rubric, rankings, team summaries, and insights live beside this HTML file.
    </footer>
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", nargs="?", help="Benchmark run directory. Defaults to latest Week 4 prototype run.")
    args = parser.parse_args()

    if args.run_dir:
        run_dir = Path(args.run_dir).resolve()
    else:
        run_dir = latest_run(Path("g4a-benchmarks/g4a-c5-2/week-4/runs").resolve())

    html_text = render(run_dir)
    output = run_dir / "report.html"
    output.write_text(html_text, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
