#!/usr/bin/env python3
"""Generate a Week 4 bundle-size evaluator trace.

This artifact is intentionally not a scoreboard. It shows the generalized
measurement process pointed at one ambiguous category.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path("/Users/michaelhabermas/repos/GAI/g4a-bench")
RUNS_DIR = ROOT / "g4a-benchmarks/g4a-c5-2/week-4/runs"
SPEC_FILE = ROOT / "g4a-specs/g4a-c5-2/week-4/GFA-Week-4-ShipShape.txt"

PROCESS_STEPS = [
    {
        "id": "criterion-decomposition",
        "question": "What does the spec actually allow?",
        "output": "Two valid target paths: 15% total production bundle reduction, or 20% initial-load reduction via code splitting.",
    },
    {
        "id": "evidence-discovery",
        "question": "Where does this repo keep measurement evidence?",
        "output": "Search for structured ledgers, Markdown reports, before/after bundle JSON, delta reports, build logs, treemaps, evals, measurement-over-time artifacts, and measurement scripts.",
    },
    {
        "id": "claim-extraction",
        "question": "What path is the team claiming?",
        "output": "Extract stated claims, but mark them self-reported until artifacts or reruns support them.",
    },
    {
        "id": "artifact-extraction",
        "question": "Can raw before/after numbers be read from artifacts?",
        "output": "Prefer machine-readable JSON. Treat Markdown as a likely claim/explanation surface, not as proof by itself. Copied specs are noise.",
    },
    {
        "id": "target-resolution",
        "question": "Which allowed target path, if any, do the numbers satisfy?",
        "output": "Evaluate total and initial-load paths independently instead of collapsing them into one bundle score.",
    },
    {
        "id": "comparability-check",
        "question": "Are before and after measurements comparable?",
        "output": "Check same build command, same output scope, same compression basis, same app functionality, and no deletion-as-optimization.",
    },
    {
        "id": "independent-reproduction",
        "question": "Has the harness reproduced the measurement?",
        "output": "This prototype has not rerun builds. It can only mark artifact-backed, not independently verified.",
    },
]


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def latest_run() -> Path:
    candidates = sorted(path for path in RUNS_DIR.glob("*") if path.is_dir())
    if not candidates:
        raise SystemExit(f"No run directories found under {RUNS_DIR}")
    return candidates[-1]


def repo_path_for(run: dict[str, Any], team: str) -> Path:
    return Path(run["work_dir"]) / team


def spec_excerpt() -> str:
    text = SPEC_FILE.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"Category 2: Bundle Size(.+?)Category 3:", text, flags=re.S)
    if not match:
        return "Category 2 bundle-size source text was not found."
    excerpt = re.sub(r"\n{3,}", "\n\n", match.group(1)).strip()
    return "Category 2: Bundle Size\n\n" + excerpt


def pct_change(before: float, after: float) -> float | None:
    if before == 0:
        return None
    return round(((after - before) / before) * 100, 2)


def reduction_percent(before: float, after: float) -> float | None:
    change = pct_change(before, after)
    if change is None:
        return None
    return round(-change, 2)


def target_status(reduction: float | None, threshold: float) -> str:
    if reduction is None:
        return "unmeasured"
    return "passes_artifact_math" if reduction >= threshold else "fails_artifact_math"


def rel(repo_path: Path, path: Path) -> str:
    return str(path.relative_to(repo_path)).replace("/", "/")


def find_files(repo_path: Path, patterns: list[str]) -> list[str]:
    matches: list[str] = []
    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        relative = rel(repo_path, path)
        lowered = relative.lower()
        if any(pattern in lowered for pattern in patterns):
            matches.append(relative)
    return sorted(matches)


def discovery_inventory(repo_path: Path) -> dict[str, list[str]]:
    return {
        "markdown_reports": find_files(repo_path, ["bundle", "performance", "improvement", "audit", "delta"]),
        "bundle_json": [item for item in find_files(repo_path, ["bundle", "chunk", "treemap"]) if item.endswith(".json")],
        "evals": find_files(repo_path, ["eval", "evaluation", "benchmark", "measure"]),
        "measurement_over_time": find_files(repo_path, ["history", "timeline", "trend", "runs/", "evidence-runs", "measurements"]),
    }


def michael_trace(repo_path: Path) -> dict[str, Any] | None:
    ledger_path = repo_path / "my-docs/evidence/submission-ledger.json"
    ledger = read_json(ledger_path)
    if not ledger:
        return None
    category = next(
        (
            item
            for item in ledger.get("categories", [])
            if str(item.get("id")) == "cat-2-bundle-size" or "bundle" in str(item.get("title", "")).lower()
        ),
        None,
    )
    if not category:
        return None

    measurements = {item.get("id"): item for item in category.get("measurements", [])}
    baseline = measurements.get("cat2-baseline-bundle", {}).get("values", {})
    latest = measurements.get("cat2-latest-bundle", {}).get("values", {})
    total_before = float(baseline.get("total_js_css_kb", 0) or 0)
    total_after = float(latest.get("total_js_css_kb", 0) or 0)
    initial_before = float(baseline.get("largest_chunk_kb", 0) or 0)
    initial_after = float(latest.get("initial_entry_chunk_kb", 0) or 0)
    largest_after = float(latest.get("largest_reported_chunk_kb", 0) or 0)

    return {
        "team_shape": "structured_ledger_with_artifact_pointers",
        "primary_evidence": [
            str(ledger_path.relative_to(repo_path)),
            "my-docs/audit-evidence/category-2-bundle/bundle-stats.json",
            "my-docs/evidence-runs/cat2-easy-wins-20260523/collectors/bundle-stats.json",
            "my-docs/evidence-runs/cat2-easy-wins-20260523/collectors/bundle-analysis.html",
        ],
        "claim_text": [claim.get("statement") for claim in category.get("claims", []) if claim.get("statement")],
        "non_claims": category.get("non_claims") or [],
        "caveats": category.get("caveats") or [],
        "raw_metrics": {
            "total_js_css_kb_before": total_before,
            "total_js_css_kb_after": total_after,
            "initial_or_entry_kb_before": initial_before,
            "initial_or_entry_kb_after": initial_after,
            "largest_chunk_kb_after": largest_after,
            "chunk_count_before": baseline.get("chunk_count"),
            "chunk_count_after": latest.get("chunk_count_reported"),
        },
        "target_paths": build_target_paths(total_before, total_after, initial_before, initial_after),
        "evidence_states": [
            state("claim_found", "yes", "Structured claim exists in submission ledger."),
            state("artifact_backed", "yes", "Ledger points to baseline and latest bundle JSON artifacts."),
            state("machine_readable_before_after", "yes", "Raw KB values are extractable without reading prose."),
            state("path_choice_explicit", "yes", "Claim explicitly says initial-load/code-splitting, not total bundle."),
            state("independently_reproduced", "no", "Harness has not rerun pnpm build:web or the collector."),
            state("comparability", "needs_agent_review", "Baseline is report-extracted; latest is collector-extracted. Need command/environment confirmation."),
        ],
    }


def dalton_trace(repo_path: Path) -> dict[str, Any] | None:
    evidence_dir = repo_path / "docs/category-improvements/evidence/02-bundle-size"
    before_path = evidence_dir / "before-bundle-size.json"
    after_path = evidence_dir / "after-bundle-size.json"
    delta_path = evidence_dir / "bundle-size-delta.md"
    before = read_json(before_path)
    after = read_json(after_path)
    if not before or not after:
        return None

    total_before = float(before["totals"]["dist"]["rawKb"])
    total_after = float(after["totals"]["dist"]["rawKb"])
    total_js_before = float(before["totals"]["js"]["rawKb"])
    total_js_after = float(after["totals"]["js"]["rawKb"])
    initial_before = float(before["totals"]["initialJs"]["rawKb"])
    initial_after = float(after["totals"]["initialJs"]["rawKb"])
    delta_text = delta_path.read_text(encoding="utf-8", errors="replace") if delta_path.exists() else ""

    return {
        "team_shape": "before_after_bundle_json_with_delta_markdown",
        "primary_evidence": [
            str(before_path.relative_to(repo_path)),
            str(after_path.relative_to(repo_path)),
            str(delta_path.relative_to(repo_path)),
            "scripts/category-improvements/measure-bundle-size.mjs",
            "scripts/category-improvements/verify-bundle-size-evidence.mjs",
        ],
        "claim_text": extract_claim_lines(delta_text),
        "non_claims": ["No explicit non-claims file found by this prototype."],
        "caveats": [
            "Total dist and total JS both increased in the submitted artifacts.",
            "Initial JS reduction is large, but the harness has not confirmed preserved functionality or identical build inputs.",
            "Evidence is duplicated under web/public; the docs path appears to be the cleaner source of truth.",
        ],
        "raw_metrics": {
            "total_dist_kb_before": total_before,
            "total_dist_kb_after": total_after,
            "total_js_kb_before": total_js_before,
            "total_js_kb_after": total_js_after,
            "initial_js_kb_before": initial_before,
            "initial_js_kb_after": initial_after,
            "initial_js_file_before": before.get("initialJsFiles", []),
            "initial_js_file_after": after.get("initialJsFiles", []),
        },
        "target_paths": build_target_paths(total_before, total_after, initial_before, initial_after),
        "evidence_states": [
            state("claim_found", "yes", "Delta markdown declares pass/fail target and before/after result."),
            state("artifact_backed", "yes", "Before and after bundle JSON artifacts exist."),
            state("machine_readable_before_after", "yes", "Raw KB values are extractable from JSON."),
            state("path_choice_explicit", "yes", "Delta says total dist failed but initial JS passed."),
            state("independently_reproduced", "no", "Harness has not rerun the measurement script."),
            state("comparability", "plausible_not_verified", "Both artifacts share the same script shape and timestamps two minutes apart, but build inputs still need confirmation."),
        ],
    }


def shiv_trace(repo_path: Path) -> dict[str, Any] | None:
    report_path = repo_path / "docs/audit/category-2-bundle-size.md"
    if not report_path.exists():
        return None
    text = report_path.read_text(encoding="utf-8", errors="replace")
    if "Initial JS" not in text or "Total `dist/` size" not in text:
        return None

    initial_match = re.search(
        r"Initial JS[^\n]*\|\s*[^|]+\|\s*([\d.]+)\s*KB\s*\|\s*([\d.]+)\s*KB",
        text,
        flags=re.I,
    )
    total_match = re.search(
        r"Total `dist/` size[^\n]*\|\s*[^|]+\|\s*([\d.]+)\s*MB\s*\|\s*([\d.]+)\s*MB",
        text,
        flags=re.I,
    )
    if not initial_match or not total_match:
        return None

    initial_before = float(initial_match.group(1))
    initial_after = float(initial_match.group(2))
    total_before = round(float(total_match.group(1)) * 1024, 2)
    total_after = round(float(total_match.group(2)) * 1024, 2)
    target_paths = build_target_paths(total_before, total_after, initial_before, initial_after)
    for path in target_paths:
        if path["state"] == "passes_artifact_math":
            path["state"] = "passes_markdown_math"
        path["interpretation"] = path["interpretation"] + " Values are extracted from Markdown, not raw bundle artifacts."

    return {
        "team_shape": "markdown_bundle_report_with_progressive_measurements",
        "primary_evidence": [
            str(report_path.relative_to(repo_path)),
            "memory/project-treasury-audit.md",
            "web/vite.config.ts",
            "web/src/main.tsx",
        ],
        "claim_text": extract_markdown_claims(text),
        "non_claims": ["No explicit non-claims section found by this prototype."],
        "caveats": [
            "Numbers are extracted from a Markdown audit report, not from committed before/after bundle JSON.",
            "Initial JS uses gzip KB while total dist uses raw MB converted to KB in the target table.",
            "The report says a mid-pass 4.1 MB figure included stats.html; the evaluator should verify this from build artifacts or reruns.",
            "Progressive pass history is useful process signal, but it can also hide cherry-picking unless rerun from clean baseline/current commits.",
        ],
        "raw_metrics": {
            "initial_js_gzip_kb_before": initial_before,
            "initial_js_gzip_kb_after": initial_after,
            "total_dist_kb_before_from_markdown_mb": total_before,
            "total_dist_kb_after_from_markdown_mb": total_after,
            "reported_route_lazy_count": "15 routes lazy",
            "reported_measurement_command": "pnpm build:shared && pnpm --filter @ship/web build",
            "reported_treemap_command": "ANALYZE_BUNDLE=true pnpm build:web",
        },
        "target_paths": target_paths,
        "evidence_states": [
            state("claim_found", "yes", "Category 2 Markdown report makes explicit before/after bundle claims."),
            state("artifact_backed", "markdown_backed", "The report includes methodology and tables, but no recognized before/after bundle JSON was found."),
            state("machine_readable_before_after", "no", "Raw values came from Markdown parsing, not JSON artifacts."),
            state("path_choice_explicit", "yes", "Report claims both total dist reduction and initial JS reduction."),
            state("measurements_over_time", "yes", "Report includes Pass 1 through Pass 4 progressive metrics."),
            state("independently_reproduced", "no", "Harness has not rerun the stated build or treemap commands."),
            state("comparability", "needs_agent_review", "Need to verify baseline/current commits, stats.html exclusion, compression basis, and functionality preservation."),
        ],
    }


def build_target_paths(total_before: float, total_after: float, initial_before: float, initial_after: float) -> list[dict[str, Any]]:
    total_reduction = reduction_percent(total_before, total_after)
    initial_reduction = reduction_percent(initial_before, initial_after)
    return [
        {
            "id": "total-production-bundle",
            "spec_threshold": ">= 15% reduction",
            "before_kb": total_before,
            "after_kb": total_after,
            "reduction_percent": total_reduction,
            "state": target_status(total_reduction, 15),
            "interpretation": "Comparable only if both totals use the same production output scope.",
        },
        {
            "id": "initial-load-code-splitting",
            "spec_threshold": ">= 20% reduction",
            "before_kb": initial_before,
            "after_kb": initial_after,
            "reduction_percent": initial_reduction,
            "state": target_status(initial_reduction, 20),
            "interpretation": "Valid only if the reduction came from code splitting/lazy loading without removing functionality.",
        },
    ]


def state(name: str, value: str, note: str) -> dict[str, str]:
    return {"name": name, "value": value, "note": note}


def extract_claim_lines(text: str) -> list[str]:
    claims: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if clean.startswith("Status:") or clean.startswith("Target:") or "Initial JS raw" in clean:
            claims.append(clean)
    return claims


def extract_markdown_claims(text: str) -> list[str]:
    claims: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        if clean.startswith("This audit measured"):
            claims.append(clean)
        if clean.startswith("| Initial JS") or clean.startswith("| Total `dist/` size"):
            claims.append(clean)
        if "Both GFA targets are met" in clean:
            claims.append(clean)
    return claims[:6]


def generic_trace(team: str, repo_path: Path) -> dict[str, Any]:
    inventory = discovery_inventory(repo_path)
    candidate_paths = []
    for key in ["bundle_json", "markdown_reports", "evals", "measurement_over_time"]:
        candidate_paths.extend(inventory[key][:4])
    return {
        "team_shape": "generic_bundle_evidence_scan",
        "primary_evidence": candidate_paths[:12],
        "discovery_inventory": inventory,
        "claim_text": [],
        "non_claims": [],
        "caveats": ["No recognized before/after bundle artifact pattern was found."],
        "raw_metrics": {},
        "target_paths": build_target_paths(0, 0, 0, 0),
        "evidence_states": [
            state("claim_found", "unknown", "No category-specific claim parser matched this repo."),
            state("artifact_backed", "weak", f"Found {len(inventory['bundle_json'])} bundle-ish JSON paths and {len(inventory['markdown_reports'])} Markdown report candidates, but no recognized before/after pair."),
            state("machine_readable_before_after", "no", "No comparable before/after metric pair extracted."),
            state("path_choice_explicit", "unknown", "Target path cannot be resolved."),
            state("independently_reproduced", "no", "Harness has not rerun builds."),
            state("comparability", "blocked", "Cannot compare until artifacts are identified."),
        ],
    }


def build_team_trace(team_result: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    team = team_result["team"]
    repo_path = repo_path_for(run, team)
    trace = michael_trace(repo_path) or dalton_trace(repo_path) or shiv_trace(repo_path) or generic_trace(team, repo_path)
    copied_specs = find_files(repo_path, ["gfa-week-4-shipshape", "shipshape-kickoff", "reviewer-evidence-bundle"])
    duplicate_public = find_files(repo_path, ["web/public/docs/category-improvements/evidence/02-bundle-size"])
    inventory = discovery_inventory(repo_path)
    trace.setdefault("discovery_inventory", inventory)
    supplemental_signal = (
        [{"kind": "markdown_candidate", "item": item} for item in inventory["markdown_reports"][:5]]
        + [{"kind": "eval_candidate", "item": item} for item in inventory["evals"][:5]]
        + [{"kind": "measurement_over_time", "item": item} for item in inventory["measurement_over_time"][:5]]
    )
    trace.update(
        {
            "team": team,
            "repo_url": team_result.get("repo_url"),
            "commit_sha": team_result.get("commit_sha"),
            "repo_path": str(repo_path),
            "signal_inventory": [
                {"kind": "signal", "item": item}
                for item in trace.get("primary_evidence", [])
            ]
            + supplemental_signal,
            "noise_inventory": [
                {"kind": "noise", "item": item}
                for item in copied_specs[:8]
            ]
            + [
                {"kind": "possible_duplicate", "item": item}
                for item in duplicate_public[:8]
            ],
            "agent_questions": [
                "Which of the two spec paths is the repo actually claiming?",
                "Are before/after artifacts generated by the same command, same codebase scope, and same compression/raw basis?",
                "Did code splitting preserve the user-facing feature set?",
                "Can the harness rerun the measurement from a clean clone and get the same directionally correct result?",
                "Should total bundle increase reduce confidence even when initial-load path passes?",
            ],
            "provisional_judgment": provisional_judgment(trace),
            "next_judgments": next_judgments(trace),
        }
    )
    return trace


def provisional_judgment(trace: dict[str, Any]) -> dict[str, str]:
    target_paths = trace.get("target_paths", [])
    passing = [path for path in target_paths if str(path.get("state", "")).startswith("passes_")]
    total = next((path for path in target_paths if path.get("id") == "total-production-bundle"), {})
    initial = next((path for path in target_paths if path.get("id") == "initial-load-code-splitting"), {})
    if not passing:
        return {
            "state": "no_artifact_math_pass_yet",
            "summary": "The prototype did not extract a passing target path from artifacts.",
        }
    if initial.get("state") == "passes_artifact_math" and total.get("state") != "passes_artifact_math":
        return {
            "state": "artifact_math_passes_initial_path_only",
            "summary": "Artifact math supports the initial-load/code-splitting path, while total bundle does not pass.",
        }
    if any(path.get("state") == "passes_markdown_math" for path in target_paths):
        return {
            "state": "markdown_math_passes_pending_artifacts",
            "summary": "Markdown-reported math supports a passing path, but raw bundle artifacts or reruns are still needed.",
        }
    return {
        "state": "artifact_math_passes",
        "summary": "At least one spec target path passes by extracted artifact math.",
    }


def next_judgments(trace: dict[str, Any]) -> list[dict[str, str]]:
    target_paths = trace.get("target_paths", [])
    total = next((path for path in target_paths if path.get("id") == "total-production-bundle"), {})
    initial = next((path for path in target_paths if path.get("id") == "initial-load-code-splitting"), {})
    states = {item["name"]: item["value"] for item in trace.get("evidence_states", [])}
    judgments = [
        {
            "judgment": "candidate_path",
            "state": "initial_load_only" if initial.get("state") == "passes_artifact_math" and total.get("state") != "passes_artifact_math" else "markdown_reported_pass" if any(path.get("state") == "passes_markdown_math" for path in target_paths) else "unresolved",
            "why": "The evaluator should preserve both target paths and avoid comparing total-bundle failures against initial-load wins as if they were the same metric.",
        },
        {
            "judgment": "trust_level",
            "state": "artifact_backed_not_reproduced" if states.get("artifact_backed") == "yes" else "markdown_backed_not_reproduced" if states.get("artifact_backed") == "markdown_backed" else "weak_extraction",
            "why": "Submitted artifacts can support a candidate judgment, but final confidence requires rerunning the measurement from a clean clone.",
        },
        {
            "judgment": "comparison_risk",
            "state": "needs_agent_review" if states.get("comparability") in {"needs_agent_review", "plausible_not_verified"} else "blocked",
            "why": "The next agent step is to verify command parity, output scope, compression/raw basis, and functionality preservation.",
        },
    ]
    if trace.get("discovery_inventory", {}).get("measurement_over_time"):
        judgments.append(
            {
                "judgment": "time_series_signal",
                "state": "candidate_signal_found",
                "why": "Measurement-over-time artifacts may show process quality or cherry-picking risk, but this prototype only inventories them.",
            }
        )
    return judgments


def build_trace(run_dir: Path) -> dict[str, Any]:
    run = read_json(run_dir / "run.json")
    rankings = read_json(run_dir / "rankings.json")
    if not run or not rankings:
        raise SystemExit(f"Missing run.json or rankings.json in {run_dir}")
    results = rankings.get("rankings", [])
    return {
        "artifact_kind": "bundle_size_process_trace",
        "run_id": run.get("run_id"),
        "run_dir": str(run_dir),
        "spec_source": str(SPEC_FILE.relative_to(ROOT)),
        "spec_excerpt": spec_excerpt(),
        "process_steps": PROCESS_STEPS,
        "scope_note": "This is a generalized evaluator trace pointed at bundle size. It is not a bundle-size product and it is not a final score.",
        "teams": [build_team_trace(result, run) for result in results],
    }


def render_status(value: str) -> str:
    css = {
        "yes": "good",
        "passes_artifact_math": "good",
        "passes_markdown_math": "warn",
        "candidate_signal_found": "good",
        "plausible_not_verified": "warn",
        "needs_agent_review": "warn",
        "initial_load_only": "warn",
        "markdown_reported_pass": "warn",
        "artifact_backed_not_reproduced": "warn",
        "markdown_backed": "warn",
        "markdown_backed_not_reproduced": "warn",
        "markdown_math_passes_pending_artifacts": "warn",
        "weak_extraction": "warn",
        "unresolved": "warn",
        "weak": "warn",
        "unknown": "warn",
        "fails_artifact_math": "bad",
        "no": "bad",
        "blocked": "bad",
        "unmeasured": "bad",
    }.get(value, "warn")
    return f"<span class='status {css}'>{esc(value)}</span>"


def list_html(items: list[Any], empty: str = "None") -> str:
    if not items:
        return f"<li class='muted'>{esc(empty)}</li>"
    out = []
    for item in items:
        if isinstance(item, dict):
            out.append(f"<li><code>{esc(item.get('kind', 'item'))}</code> {esc(item.get('item', item))}</li>")
        else:
            out.append(f"<li>{esc(item)}</li>")
    return "".join(out)


def metrics_table(metrics: dict[str, Any]) -> str:
    rows = []
    for key, value in metrics.items():
        rows.append(f"<tr><th>{esc(key)}</th><td>{esc(value)}</td></tr>")
    return "\n".join(rows) or "<tr><td colspan='2' class='muted'>No metrics extracted.</td></tr>"


def target_table(paths: list[dict[str, Any]]) -> str:
    rows = []
    for path in paths:
        rows.append(
            "<tr>"
            f"<th>{esc(path['id'])}</th>"
            f"<td>{esc(path['spec_threshold'])}</td>"
            f"<td>{esc(path['before_kb'])}</td>"
            f"<td>{esc(path['after_kb'])}</td>"
            f"<td>{esc(path['reduction_percent'])}</td>"
            f"<td>{render_status(path['state'])}</td>"
            f"<td>{esc(path['interpretation'])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def states_table(states: list[dict[str, str]]) -> str:
    rows = []
    for item in states:
        rows.append(
            "<tr>"
            f"<th>{esc(item['name'])}</th>"
            f"<td>{render_status(item['value'])}</td>"
            f"<td>{esc(item['note'])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def judgments_table(judgments: list[dict[str, str]]) -> str:
    rows = []
    for item in judgments:
        rows.append(
            "<tr>"
            f"<th>{esc(item['judgment'])}</th>"
            f"<td>{render_status(item['state'])}</td>"
            f"<td>{esc(item['why'])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def inventory_table(inventory: dict[str, list[str]]) -> str:
    rows = []
    for key in ["markdown_reports", "bundle_json", "evals", "measurement_over_time"]:
        items = inventory.get(key) or []
        preview = ", ".join(items[:4]) if items else "none found"
        rows.append(f"<tr><th>{esc(key)}</th><td>{len(items)}</td><td>{esc(preview)}</td></tr>")
    return "\n".join(rows)


def render_html(trace: dict[str, Any]) -> str:
    steps = "".join(
        f"<tr><th>{esc(step['id'])}</th><td>{esc(step['question'])}</td><td>{esc(step['output'])}</td></tr>"
        for step in trace["process_steps"]
    )
    team_sections = []
    for team in trace["teams"]:
        team_sections.append(
            f"""
      <section class="team">
        <div class="team-head">
          <div>
            <p class="eyebrow">repo trace</p>
            <h2>{esc(team['team'])}</h2>
            <p class="muted">{esc(team['team_shape'])} | commit {esc(str(team.get('commit_sha') or 'unknown')[:12])}</p>
          </div>
          <div class="judgment">
            {render_status(team['provisional_judgment']['state'])}
            <p>{esc(team['provisional_judgment']['summary'])}</p>
          </div>
        </div>

        <div class="grid two">
          <div>
            <h3>Signal</h3>
            <ul>{list_html(team['signal_inventory'], 'No signal paths extracted.')}</ul>
          </div>
          <div>
            <h3>Noise / Duplicates</h3>
            <ul>{list_html(team['noise_inventory'], 'No obvious copied-spec or duplicate-public paths found.')}</ul>
          </div>
        </div>

        <h3>Extracted Claim</h3>
        <ul>{list_html(team.get('claim_text') or [], 'No explicit claim text extracted.')}</ul>

        <h3>Raw Metrics</h3>
        <table class="kv">{metrics_table(team.get('raw_metrics') or {})}</table>

        <h3>Target Path Resolution</h3>
        <table>
          <thead><tr><th>Path</th><th>Threshold</th><th>Before KB</th><th>After KB</th><th>Reduction %</th><th>State</th><th>Interpretation</th></tr></thead>
          <tbody>{target_table(team['target_paths'])}</tbody>
        </table>

        <h3>Judgment State Machine</h3>
        <table>
          <thead><tr><th>State</th><th>Value</th><th>Why</th></tr></thead>
          <tbody>{states_table(team['evidence_states'])}</tbody>
        </table>

        <h3>Discovery Inventory</h3>
        <table>
          <thead><tr><th>Bucket</th><th>Count</th><th>Examples</th></tr></thead>
          <tbody>{inventory_table(team.get('discovery_inventory') or {})}</tbody>
        </table>

        <h3>Next Judgments</h3>
        <table>
          <thead><tr><th>Judgment</th><th>State</th><th>Why</th></tr></thead>
          <tbody>{judgments_table(team.get('next_judgments') or [])}</tbody>
        </table>

        <div class="grid two">
          <div>
            <h3>Caveats</h3>
            <ul>{list_html(team.get('caveats') or [])}</ul>
          </div>
          <div>
            <h3>Agent Questions</h3>
            <ul>{list_html(team.get('agent_questions') or [])}</ul>
          </div>
        </div>
      </section>
            """
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundle Size Process Trace</title>
  <style>
    :root {{
      --ink: #161616;
      --muted: #666;
      --paper: #f6f2ea;
      --panel: #fffdfa;
      --line: #d6cfc2;
      --good: #176b55;
      --warn: #9a5a10;
      --bad: #9c2f25;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: var(--paper);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.4;
    }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 32px 24px 56px; }}
    header {{ border-bottom: 2px solid var(--ink); padding-bottom: 18px; margin-bottom: 22px; }}
    h1 {{ margin: 4px 0 8px; font-size: clamp(34px, 5vw, 58px); line-height: 1; letter-spacing: 0; }}
    h2 {{ margin: 0; font-size: 28px; letter-spacing: 0; }}
    h3 {{ margin: 22px 0 8px; font-size: 15px; text-transform: uppercase; letter-spacing: .08em; }}
    p {{ margin: 0 0 10px; }}
    .eyebrow {{ margin: 0; color: #244d83; font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: .12em; }}
    .muted {{ color: var(--muted); }}
    .note {{ max-width: 850px; color: #34302b; font-size: 17px; }}
    .spec {{ white-space: pre-wrap; max-height: 240px; overflow: auto; background: #fff8e8; border: 1px solid #d7bb7c; padding: 14px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; }}
    section.process, section.team {{ background: var(--panel); border: 1px solid var(--line); padding: 18px; margin: 18px 0; }}
    .team-head {{ display: grid; grid-template-columns: 1fr minmax(260px, 380px); gap: 18px; align-items: start; border-bottom: 1px solid var(--line); padding-bottom: 14px; }}
    .judgment {{ border-left: 4px solid var(--line); padding-left: 14px; }}
    .grid {{ display: grid; gap: 16px; }}
    .two {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #eee7dc; font-weight: 750; }}
    .kv th {{ width: 280px; }}
    ul {{ margin: 0; padding-left: 22px; }}
    li {{ margin: 4px 0; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .92em; }}
    .status {{ display: inline-block; padding: 3px 8px; border: 1px solid currentColor; font-weight: 750; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    .good {{ color: var(--good); background: #e7f4ee; }}
    .warn {{ color: var(--warn); background: #fff2d8; }}
    .bad {{ color: var(--bad); background: #f9e2df; }}
    @media (max-width: 820px) {{
      .two, .team-head {{ grid-template-columns: 1fr; }}
      main {{ padding: 22px 14px 40px; }}
      table {{ display: block; overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <p class="eyebrow">G4A Week 4 prototype</p>
      <h1>Bundle Size Process Trace</h1>
      <p class="note">{esc(trace['scope_note'])}</p>
    </header>

    <section class="process">
      <h3>Generalized Process</h3>
      <table>
        <thead><tr><th>Step</th><th>Question</th><th>Output Contract</th></tr></thead>
        <tbody>{steps}</tbody>
      </table>
    </section>

    <section class="process">
      <h3>Spec Anchor</h3>
      <div class="spec">{esc(trace['spec_excerpt'])}</div>
    </section>

    {''.join(team_sections)}
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=None)
    args = parser.parse_args()
    run_dir = args.run_dir or latest_run()
    trace = build_trace(run_dir)
    write_json(run_dir / "bundle-trace.json", trace)
    (run_dir / "bundle-trace.html").write_text(render_html(trace), encoding="utf-8")
    print(run_dir / "bundle-trace.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
