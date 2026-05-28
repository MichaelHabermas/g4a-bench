#!/usr/bin/env python3
"""Prototype Week 4 benchmark harness.

This is intentionally narrow: it exercises the artifact contract against the
current Week 4 inputs without trying to run each Ship fork end-to-end.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COHORT = "g4a-c5-2"
WEEK = "week-4"
WEEK_NUMBER = 4
SPEC_DIR = ROOT / "g4a-specs" / COHORT / WEEK
REPOS_FILE = ROOT / "g4a-challenger-repos" / COHORT / WEEK / "REPOS.md"
BENCHMARK_DIR = ROOT / "g4a-benchmarks" / COHORT / WEEK / "runs"
WORK_DIR = Path("/private/tmp/g4a-bench-prototype") / COHORT / WEEK


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

RUBRIC = [
    {
        "id": "W4-DOCS-01",
        "name": "Required deliverables and orientation",
        "weight": 15,
        "method": "static",
        "description": "README/setup, audit/improvement/discovery/cost docs, and evidence that the team oriented around Ship.",
    },
    {
        "id": "W4-AUDIT-01",
        "name": "Audit coverage across categories",
        "weight": 20,
        "method": "static_text",
        "description": "Coverage of the seven required ShipShape categories plus the security audit extension.",
    },
    {
        "id": "W4-PROOF-01",
        "name": "Before/after improvement evidence",
        "weight": 25,
        "method": "static_text",
        "description": "Concrete baseline/after language, benchmarks, measurements, and reproducibility signals.",
    },
    {
        "id": "W4-SECURITY-01",
        "name": "Security probe deliverable",
        "weight": 15,
        "method": "static_code",
        "description": "Runnable security probe or audit tooling covering auth/session, WebSocket validation, input sanitization, dependency audit, and manual review concerns.",
    },
    {
        "id": "W4-TESTS-01",
        "name": "Testing and regression protection",
        "weight": 10,
        "method": "static_code",
        "description": "Presence of meaningful tests and scripts connected to the improvement work.",
    },
    {
        "id": "W4-REPO-01",
        "name": "Repo health and runnable shape",
        "weight": 10,
        "method": "static_code",
        "description": "Basic project health: package metadata, workspace/config files, source tree, and recent commit availability.",
    },
    {
        "id": "W4-INSIGHT-01",
        "name": "Cohort learning signal",
        "weight": 5,
        "method": "impression",
        "description": "Interesting choices, standout polish, or transferable ideas visible from static review.",
    },
]

AGENT_REVIEW_QUESTIONS = {
    "type safety": [
        "Rerun or independently reproduce the submitted type-safety counts.",
        "Inspect whether reductions came from meaningful narrowing and boundary typing, not superficial syntax churn.",
    ],
    "bundle size": [
        "Determine which allowed target the team is claiming: total bundle reduction or initial-load/code-splitting reduction.",
        "Verify before/after bundle artifacts were produced under comparable build conditions.",
    ],
    "api response time": [
        "Verify P95 improvements on at least two endpoints under identical data volume, concurrency, hardware, and bypass/rate-limit conditions.",
        "Check whether excluded or failed benchmark artifacts change the conclusion.",
    ],
    "database query": [
        "Verify the measured flow satisfies the Week 4 database-query target.",
        "Check whether EXPLAIN/query-count evidence compares like with like.",
    ],
    "test coverage": [
        "Inspect whether the new tests are meaningful regression tests, not page-load or superficial assertions.",
        "Check flake/RCA claims when the team uses flake-fix path instead of new-test path.",
    ],
    "runtime error": [
        "Inspect the three claimed error-handling fixes and confirm at least one addresses real user-facing data loss or confusion.",
        "Check before/after reproduction steps or screenshots.",
    ],
    "accessibility": [
        "Determine whether the team chose Lighthouse improvement or Critical/Serious axe closeout.",
        "Verify scope covers the top pages claimed and does not overstate manual screen-reader/keyboard coverage.",
    ],
    "security": [
        "Run or inspect the security probe tool and confirm it covers all four required attack surfaces.",
        "Verify at least two vulnerability fixes with before/after proof and no broken tests.",
    ],
}


@dataclass
class RepoSpec:
    team: str
    url: str


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": cmd,
            "cwd": str(cwd) if cwd else None,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "started_at": started.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": cmd,
            "cwd": str(cwd) if cwd else None,
            "exit_code": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "command timed out",
            "started_at": started.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }


def slugify(value: str) -> str:
    cleaned = re.sub(r"^https?://", "", value.strip())
    cleaned = re.sub(r"\.git$", "", cleaned)
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", cleaned).strip("-").lower()
    return cleaned or "unknown-team"


def parse_repos() -> list[RepoSpec]:
    text = REPOS_FILE.read_text(encoding="utf-8")
    repos: list[RepoSpec] = []
    for line in text.splitlines():
        urls = re.findall(r"https?://[^>\s|]+", line)
        if not urls:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        url = urls[0]
        team = ""
        if len(cells) >= 2 and "http" not in cells[0].lower() and set(cells[0]) != {"-"}:
            team = slugify(cells[0])
        if not team:
            team = slugify(url)
        repos.append(RepoSpec(team=team, url=url))
    return repos


def read_specs() -> dict[str, str]:
    specs = {}
    for path in sorted(SPEC_DIR.glob("*.txt")):
        specs[str(path.relative_to(ROOT))] = path.read_text(encoding="utf-8", errors="replace")
    return specs


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def iter_files(repo_path: Path) -> list[Path]:
    ignored_parts = {".git", "node_modules", "dist", "build", ".next", "coverage", ".turbo"}
    files: list[Path] = []
    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignored_parts for part in path.relative_to(repo_path).parts):
            continue
        if path.stat().st_size > 750_000:
            continue
        files.append(path)
    return files


def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def find_matching_files(files: list[Path], patterns: list[str]) -> list[str]:
    lowered = [(path, str(path).lower()) for path in files]
    matches = []
    for path, value in lowered:
        if any(pattern in value for pattern in patterns):
            matches.append(str(path))
    return matches


def relative_to(repo_path: Path, path: Path) -> str:
    return str(path.relative_to(repo_path)).replace(os.sep, "/")


def is_generated_or_copied_spec(rel_path: str) -> bool:
    value = rel_path.lower()
    copied_spec_markers = [
        "w4-specs",
        "week-4/spec",
        "reviewer-evidence-bundle",
        "shipshape-kickoff",
        "shipshape-security-audit.txt",
        "shipshape-security-audit.pdf",
        "gfa-week-4-shipshape",
    ]
    return any(marker in value for marker in copied_spec_markers)


def is_submission_evidence_file(repo_path: Path, path: Path) -> bool:
    rel = relative_to(repo_path, path)
    value = rel.lower()
    if is_generated_or_copied_spec(rel):
        return False
    if path.suffix.lower() not in {".md", ".txt", ".json", ".html"}:
        return False
    top_level_submission_docs = {
        "audit report.md",
        "audit_report.md",
        "improvement documentation.md",
        "improvement_report.md",
        "discovery write up.md",
        "discovery.md",
        "ai cost analysis.md",
        "ai_cost_analysis.md",
        "presearch.md",
    }
    submission_markers = [
        "audit",
        "improvement",
        "discovery",
        "cost",
        "evidence",
        "lighthouse",
        "axe",
        "benchmark",
        "security-probe",
        "category-improvements",
        "project-weeks-sot/week-4",
    ]
    return Path(value).name in top_level_submission_docs or any(marker in value for marker in submission_markers)


def category_file_hits(repo_path: Path, files: list[Path]) -> dict[str, int]:
    aliases = {
        "type safety": ["type-safety", "type_safety", "category-1", "category_1", "cat-1", "cat_1"],
        "bundle size": ["bundle", "category-2", "category_2", "cat-2", "cat_2"],
        "api response time": ["api-response", "api_response", "response-time", "category-3", "category_3", "cat-3", "cat_3"],
        "database query": ["database", "db-query", "query", "category-4", "category_4", "cat-4", "cat_4"],
        "test coverage": ["test-coverage", "test_quality", "coverage", "category-5", "category_5", "cat-5", "cat_5"],
        "runtime error": ["runtime", "error-handling", "edge-case", "category-6", "category_6", "cat-6", "cat_6"],
        "accessibility": ["accessibility", "a11y", "lighthouse", "axe", "category-7", "category_7", "cat-7", "cat_7"],
        "security": ["security", "probe", "category-8", "category_8", "cat-8", "cat_8"],
    }
    hits = {category: 0 for category in CATEGORIES}
    for path in files:
        rel = relative_to(repo_path, path).lower()
        if is_generated_or_copied_spec(rel):
            continue
        for category, category_aliases in aliases.items():
            if any(alias in rel for alias in category_aliases):
                hits[category] += 1
    return hits


def load_submission_ledger(repo_path: Path) -> dict[str, Any] | None:
    candidates = [
        repo_path / "my-docs" / "evidence" / "submission-ledger.json",
        repo_path / "submission-ledger.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and isinstance(data.get("categories"), list):
            data["_path"] = str(path)
            return data
    return None


def category_key_from_ledger(category: dict[str, Any]) -> str:
    title = str(category.get("title", "")).lower()
    category_id = str(category.get("id", "")).lower()
    combined = f"{category_id} {title}"
    if "type" in combined and "safety" in combined:
        return "type safety"
    if "bundle" in combined:
        return "bundle size"
    if "api" in combined and "response" in combined:
        return "api response time"
    if "database" in combined or "query" in combined:
        return "database query"
    if "test" in combined:
        return "test coverage"
    if "runtime" in combined or "error" in combined:
        return "runtime error"
    if "accessibility" in combined:
        return "accessibility"
    if "security" in combined:
        return "security"
    return ""


def metric_value_text(metric: dict[str, Any]) -> str:
    if "change_percent" in metric:
        return f"{metric.get('id')}: {metric['change_percent']}%"
    if "value" in metric and "threshold" in metric:
        return f"{metric.get('id')}: {metric['value']} / {metric['threshold']}"
    if "value" in metric:
        return f"{metric.get('id')}: {metric['value']}"
    values = metric.get("values")
    if isinstance(values, dict):
        parts = []
        for key, value in values.items():
            if isinstance(value, dict) and "change_percent" in value:
                parts.append(f"{key} {value['change_percent']}%")
        if parts:
            return f"{metric.get('id')}: " + ", ".join(parts[:3])
    return str(metric.get("id", "metric"))


def summarize_submission_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    category_hits = {category: False for category in CATEGORIES}
    category_counts = {category: 0 for category in CATEGORIES}
    summaries = []

    for category in ledger.get("categories", []):
        key = category_key_from_ledger(category)
        if not key:
            continue
        status = str(category.get("status", "")).lower()
        measurements = category.get("measurements") or []
        derived_metrics = category.get("derived_metrics") or []
        claims = category.get("claims") or []
        acceptance_tests = category.get("acceptance_tests") or []
        evidence_count = len(measurements) + len(derived_metrics) + len(claims) + len(acceptance_tests)
        category_hits[key] = status in {"proven", "present", "passed", "verified", "partial"}
        category_counts[key] = evidence_count
        summaries.append(
            {
                "key": key,
                "id": category.get("id"),
                "title": category.get("title"),
                "status": category.get("status"),
                "evidence_count": evidence_count,
                "measurements": len(measurements),
                "derived_metrics": len(derived_metrics),
                "claims": len(claims),
                "acceptance_tests": len(acceptance_tests),
                "metrics": [metric_value_text(metric) for metric in derived_metrics[:4]],
                "caveats": category.get("caveats") or [],
            }
        )

    proven_count = sum(1 for item in summaries if str(item.get("status", "")).lower() == "proven")
    return {
        "path": ledger.get("_path"),
        "category_hits": category_hits,
        "category_counts": category_counts,
        "summaries": summaries,
        "proven_count": proven_count,
        "category_count": len(summaries),
    }


def category_review_items(category_hits: dict[str, bool], category_counts: dict[str, int], basis: str) -> list[dict[str, Any]]:
    items = []
    for category in CATEGORIES:
        items.append(
            {
                "category": category,
                "extraction_basis": basis,
                "extracted_evidence_count": category_counts.get(category, 0),
                "extracted_claim_present": bool(category_hits.get(category)),
                "independently_verified": False,
                "agent_review_required": True,
                "review_questions": AGENT_REVIEW_QUESTIONS[category],
            }
        )
    return items


def score_ratio(hits: int, possible: int, weight: int) -> float:
    if possible == 0:
        return 0.0
    return round(weight * min(hits / possible, 1.0), 2)


def analyze_repo(team: RepoSpec, repo_path: Path, clone_result: dict[str, Any]) -> dict[str, Any]:
    files = iter_files(repo_path) if repo_path.exists() else []
    relative_files = [str(path.relative_to(repo_path)) for path in files]
    markdown_files = [path for path in files if path.suffix.lower() in {".md", ".txt"}]
    code_files = [path for path in files if path.suffix.lower() in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}]
    submission_files = [path for path in files if is_submission_evidence_file(repo_path, path)]
    markdown_text = "\n".join(read_file(path) for path in markdown_files).lower()
    submission_text = "\n".join(read_file(path) for path in submission_files).lower()
    code_text = "\n".join(read_file(path) for path in code_files).lower()
    all_text = f"{markdown_text}\n{code_text}"

    docs = {
        "readme": any(path.name.lower() == "readme.md" for path in files),
        "audit": [str(path) for path in submission_files if "audit" in relative_to(repo_path, path).lower()],
        "improvement": [
            str(path)
            for path in submission_files
            if any(marker in relative_to(repo_path, path).lower() for marker in ["improvement", "before-after", "before_after"])
        ],
        "discovery": [str(path) for path in submission_files if "discovery" in relative_to(repo_path, path).lower()],
        "cost": [str(path) for path in submission_files if "cost" in relative_to(repo_path, path).lower()],
        "security": [
            str(path)
            for path in submission_files
            if any(marker in relative_to(repo_path, path).lower() for marker in ["security", "probe"])
        ],
    }

    category_path_hits = category_file_hits(repo_path, submission_files)
    category_hits = {
        category: category_path_hits[category] > 0
        or category in submission_text
        or category.replace(" ", "_") in submission_text
        or category.replace(" ", "-") in submission_text
        for category in CATEGORIES
    }
    proof_terms = [
        "before",
        "after",
        "baseline",
        "measurement",
        "benchmark",
        "p95",
        "p99",
        "lighthouse",
        "axe",
        "explain analyze",
        "reproduction",
        "root cause",
    ]
    security_terms = [
        "session",
        "websocket",
        "xss",
        "sql injection",
        "npm audit",
        "cors",
        "csp",
        "rate limit",
        "secret",
        "severity",
    ]
    test_files = [
        path
        for path in files
        if re.search(r"(\.test\.|\.spec\.|__tests__|/tests?/|/e2e/)", str(path.relative_to(repo_path)).lower())
    ]

    package_json = repo_path / "package.json"
    package_data: dict[str, Any] = {}
    if package_json.exists():
        try:
            package_data = json.loads(package_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            package_data = {}

    ledger_summary = None
    ledger = load_submission_ledger(repo_path)
    if ledger:
        ledger_summary = summarize_submission_ledger(ledger)
        category_hits = ledger_summary["category_hits"]
        category_path_hits = ledger_summary["category_counts"]
    extraction_basis = "structured_submission_ledger_self_reported" if ledger_summary else "heuristic_static_path_and_text_scan"

    commit_result = run(["git", "log", "--oneline", "-n", "5"], cwd=repo_path, timeout=30)
    sha_result = run(["git", "rev-parse", "HEAD"], cwd=repo_path, timeout=30)

    doc_hits = sum(
        [
            docs["readme"],
            bool(docs["audit"]),
            bool(docs["improvement"]),
            bool(docs["discovery"]),
            bool(docs["cost"]),
        ]
    )
    audit_hits = sum(1 for value in category_hits.values() if value)
    proof_hits = sum(1 for term in proof_terms if term in submission_text)
    security_hits = sum(1 for term in security_terms if term in submission_text)
    category_evidence_hits = sum(1 for value in category_path_hits.values() if value > 0)
    package_scripts = package_data.get("scripts") or {}
    has_security_script = any(script.startswith("security:probe") for script in package_scripts)
    has_security_probe_file = any("security-probe" in relative_to(repo_path, path).lower() for path in files)
    health_hits = sum(
        [
            package_json.exists(),
            (repo_path / "pnpm-workspace.yaml").exists(),
            any(path.name == "tsconfig.json" for path in files),
            any(part in {"web", "api", "shared"} for path in files for part in path.relative_to(repo_path).parts),
            sha_result["exit_code"] == 0,
        ]
    )

    scores = {
        "W4-DOCS-01": score_ratio(doc_hits, 5, 15),
        "W4-AUDIT-01": score_ratio(audit_hits, len(CATEGORIES), 20),
        "W4-PROOF-01": round(
            score_ratio(proof_hits, len(proof_terms), 12)
            + score_ratio(category_evidence_hits, len(CATEGORIES), 13),
            2,
        ),
        "W4-SECURITY-01": round(
            score_ratio(security_hits, len(security_terms), 7)
            + (4 if has_security_script else 0)
            + (4 if has_security_probe_file else 0),
            2,
        ),
        "W4-TESTS-01": score_ratio(min(len(test_files), 10), 10, 10),
        "W4-REPO-01": score_ratio(health_hits, 5, 10),
    }
    if ledger_summary:
        proven_count = ledger_summary["proven_count"]
        scores["W4-AUDIT-01"] = score_ratio(proven_count, len(CATEGORIES), 20)
        scores["W4-PROOF-01"] = score_ratio(category_evidence_hits, len(CATEGORIES), 25)
        scores["W4-SECURITY-01"] = 15 if category_hits.get("security") else scores["W4-SECURITY-01"]

    strengths = []
    risks = []
    impressions = []
    if audit_hits >= 6:
        strengths.append("Broad audit language covers most Week 4 categories.")
    if ledger_summary:
        strengths.append(
            f"Structured submission ledger found with {ledger_summary['proven_count']} proven categories."
        )
    if proof_hits >= 7:
        strengths.append("Strong before/after and measurement vocabulary appears across submission evidence.")
    if category_evidence_hits >= len(CATEGORIES):
        strengths.append("Category-specific evidence files appear for every required Week 4 category.")
    if security_hits >= 6:
        strengths.append("Security probe language appears to cover several required attack surfaces.")
    if len(test_files) >= 5:
        strengths.append("Repo includes a visible test surface for regression protection.")
    if doc_hits <= 2:
        risks.append("Required submission docs are hard to find by static scan.")
    if audit_hits < 4:
        risks.append("Static scan found weak coverage of required audit categories.")
    if not ledger_summary:
        risks.append("No structured submission ledger found; this run falls back to heuristic evidence parsing.")
    if proof_hits < 5:
        risks.append("Before/after proof may be thin or not named consistently.")
    if category_evidence_hits < len(CATEGORIES):
        missing = [category for category, count in category_path_hits.items() if count == 0]
        risks.append("Category-specific evidence files were not found for: " + ", ".join(missing) + ".")
    if security_hits < 4:
        risks.append("Security probe coverage is weak by static keyword scan.")
    if "notification" in all_text:
        impressions.append("Impression: notification-related work may be a reusable pattern worth inspecting.")
    if "lighthouse" in all_text or "axe" in all_text:
        impressions.append("Impression: accessibility work appears to use recognizable tools.")
    if "playwright" in all_text:
        impressions.append("Impression: Playwright appears in the submission and may indicate runnable regression work.")

    total_without_insight = sum(scores.values())
    insight_score = 0.0
    if strengths:
        insight_score += 2.5
    if impressions:
        insight_score += 2.5
    scores["W4-INSIGHT-01"] = insight_score
    extraction_confidence_score = round(sum(scores.values()), 2)

    return {
        "team": team.team,
        "repo_url": team.url,
        "commit_sha": sha_result["stdout"].strip() if sha_result["exit_code"] == 0 else None,
        "clone": clone_result,
        "score_kind": "extraction_confidence_not_grade",
        "final_grade": None,
        "extraction_basis": extraction_basis,
        "independent_checks_completed": [
            "repo cloned",
            "commit SHA recorded",
            "files enumerated",
            "package scripts read",
            "submission/evidence text scanned",
        ],
        "not_independently_verified": [
            "reported measurements are truthful",
            "before/after artifacts are comparable",
            "chosen target path satisfies the spec when multiple target paths exist",
            "tests are meaningful",
            "UI/deployed app behavior works",
            "security probe actually runs against a fresh instance",
        ],
        "file_count": len(files),
        "markdown_file_count": len(markdown_files),
        "submission_evidence_file_count": len(submission_files),
        "code_file_count": len(code_files),
        "test_file_count": len(test_files),
        "package_scripts": sorted(package_scripts.keys()),
        "docs": docs,
        "submission_ledger": ledger_summary,
        "category_hits": category_hits,
        "category_path_hits": category_path_hits,
        "category_evidence_hits": category_evidence_hits,
        "category_review_items": category_review_items(category_hits, category_path_hits, extraction_basis),
        "proof_term_hits": [term for term in proof_terms if term in submission_text],
        "security_term_hits": [term for term in security_terms if term in submission_text],
        "has_security_script": has_security_script,
        "has_security_probe_file": has_security_probe_file,
        "scores": scores,
        "total_score": extraction_confidence_score,
        "extraction_confidence_score": extraction_confidence_score,
        "total_without_insight": round(total_without_insight, 2),
        "strengths": strengths,
        "risks": risks,
        "impressions": impressions,
        "recent_commits": commit_result["stdout"].strip().splitlines(),
        "sample_files": relative_files[:200],
    }


def clone_repo(team: RepoSpec, destination: Path) -> dict[str, Any]:
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    return run(["git", "clone", "--depth", "1", team.url, str(destination)], timeout=180)


def build_measurement_plan(specs: dict[str, str], repos: list[RepoSpec]) -> str:
    spec_list = "\n".join(f"- `{path}`" for path in specs)
    repo_list = "\n".join(f"- `{repo.team}`: {repo.url}" for repo in repos)
    criteria = "\n".join(
        f"- `{item['id']}` ({item['weight']} pts): {item['name']} - {item['description']}"
        for item in RUBRIC
    )
    return f"""# Week 4 Prototype Measurement Plan

This run is a quick prototype of the generated-evaluator flow. It measures the two Week 4 repos with static checks only. It does not install dependencies, start the apps, run Playwright, measure bundle size, or benchmark live API/database behavior yet.

## Inputs

Specs:

{spec_list}

Repos:

{repo_list}

## What Week 4 Tests

Week 4 asks challengers to inherit the Treasury Ship codebase, orient deeply, audit all required quality categories, improve the system with measurable before/after proof, and document the work. The security addendum adds an eighth category requiring a runnable security probe and fixes for at least two verified vulnerabilities.

## Prototype Criteria

{criteria}

## Evidence This Prototype Collects

- repository clone status and commit SHA
- visible markdown deliverables
- mentions of required audit categories
- before/after measurement vocabulary
- security probe and attack-surface vocabulary
- visible test files and package scripts
- basic repo shape and recent commits
- labeled subjective impressions for cohort-learning dessert

## Known Gaps

- No dependency installation.
- No live app execution.
- No browser/deployed-site inspection.
- No actual TypeScript, bundle, API, database, Lighthouse, axe, or npm audit execution.
- Static keyword checks can miss well-written work that uses different language.
- Static keyword checks can over-credit superficial mentions.

This is enough to test the artifact flow and compare rough signal between the two repos. It is not enough for final grading.
"""


def build_rankings(results: list[dict[str, Any]]) -> str:
    lines = ["# Week 4 Prototype Extraction Workbench", ""]
    lines.append("This is not a final ranking. The numeric value is extraction confidence: how much potentially relevant evidence the prototype found and structured. It is not an evaluation score.")
    lines.append("")
    lines.append("| Order | Team | Extraction Confidence | Basis | Setup | Main Strength | Main Risk |")
    lines.append("| ---: | --- | ---: | --- | --- | --- | --- |")
    for index, result in enumerate(sorted(results, key=lambda item: item["total_score"], reverse=True), 1):
        setup = "ok" if result["clone"]["exit_code"] == 0 else "failed"
        strength = (result["strengths"] or ["No standout found by static scan."])[0]
        risk = (result["risks"] or ["No major static risk found."])[0]
        lines.append(
            f"| {index} | {result['team']} | {result['total_score']} | {result.get('extraction_basis', 'unknown')} | {setup} | {strength} | {risk} |"
        )
    lines.append("")
    return "\n".join(lines)


def build_insights(results: list[dict[str, Any]]) -> str:
    sorted_results = sorted(results, key=lambda item: item["total_score"], reverse=True)
    lines = ["# Week 4 Cohort Learning Insights", ""]
    lines.append("This is a prototype cohort-learning report. It separates measured static signals from impression notes.")
    lines.append("")
    lines.append("## Evidence-Backed Signals")
    lines.append("")
    for result in sorted_results:
        lines.append(f"### {result['team']}")
        lines.append("")
        if result["strengths"]:
            for strength in result["strengths"]:
                lines.append(f"- Strength: {strength}")
        else:
            lines.append("- Strength: No strong static standout found.")
        if result["risks"]:
            for risk in result["risks"]:
                lines.append(f"- Risk: {risk}")
        else:
            lines.append("- Risk: No major static risk found.")
        lines.append(f"- Extraction confidence: {result['total_score']} / 100 ({result['total_without_insight']} before impression notes).")
        lines.append("- Final grade: not assigned by this prototype.")
        lines.append(f"- Extraction basis: {result.get('extraction_basis', 'unknown')}.")
        lines.append(f"- Submission/evidence files scanned: {result.get('submission_evidence_file_count', 0)}.")
        if result.get("independent_checks_completed"):
            lines.append("- Independently checked: " + ", ".join(result["independent_checks_completed"]) + ".")
        if result.get("not_independently_verified"):
            lines.append("- Not independently verified: " + ", ".join(result["not_independently_verified"][:4]) + ".")
        categories = ", ".join(name for name, hit in result["category_hits"].items() if hit) or "none"
        lines.append(f"- Category coverage found: {categories}.")
        path_hits = result.get("category_path_hits") or {}
        if path_hits:
            strongest = sorted(path_hits.items(), key=lambda item: item[1], reverse=True)[:3]
            weakest = [name for name, count in path_hits.items() if count == 0]
            lines.append(
                "- Strongest category evidence paths: "
                + ", ".join(f"{name} ({count})" for name, count in strongest)
                + "."
            )
            if weakest:
                lines.append("- Missing category-specific evidence paths: " + ", ".join(weakest) + ".")
        lines.append("")
    lines.append("## Agent Review Required")
    lines.append("")
    lines.append("The next evaluator needs category-specific judgment. These questions are generated from the Week 4 rubric and should be answered before any final score exists.")
    lines.append("")
    for category in CATEGORIES:
        lines.append(f"### {category}")
        for question in AGENT_REVIEW_QUESTIONS[category]:
            lines.append(f"- {question}")
        lines.append("")
    lines.append("## Impression Notes")
    lines.append("")
    any_impressions = False
    for result in sorted_results:
        for impression in result["impressions"]:
            any_impressions = True
            lines.append(f"- {result['team']}: {impression}")
    if not any_impressions:
        lines.append("- No subjective impression notes were triggered by the static prototype.")
    lines.append("")
    lines.append("## Follow-Up Questions")
    lines.append("")
    for result in sorted_results:
        lines.append(f"- Ask `{result['team']}` to show the concrete before/after evidence behind its highest-scoring categories.")
    return "\n".join(lines) + "\n"


def write_generated_evaluator(run_dir: Path) -> None:
    evaluator_dir = run_dir / "evaluator"
    write_text(
        evaluator_dir / "README.md",
        """# Generated Week 4 Prototype Evaluator

This evaluator was generated by `g4a-harness/prototype_week4.py`.

It performs static checks only:

- required markdown deliverables
- Week 4 category vocabulary
- before/after proof vocabulary
- security probe vocabulary
- test files and package scripts
- basic repository health

It deliberately does not install dependencies or run the app.
""",
    )
    write_json(evaluator_dir / "checks.json", {"rubric": RUBRIC, "categories": CATEGORIES})


def main() -> int:
    if not REPOS_FILE.exists():
        print(f"Missing repo list: {REPOS_FILE}", file=sys.stderr)
        return 1

    repos = parse_repos()
    specs = read_specs()
    if not repos:
        print(f"No repos found in {REPOS_FILE}", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%SZ-static-prototype")
    run_dir = BENCHMARK_DIR / run_id
    work_dir = WORK_DIR / run_id

    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    write_json(
        run_dir / "run.json",
        {
            "cohort": COHORT,
            "week": WEEK_NUMBER,
            "run_id": run_id,
            "mode": "static-prototype",
            "started_at": now.isoformat(),
            "repos_file": str(REPOS_FILE.relative_to(ROOT)),
            "spec_files": sorted(specs.keys()),
            "work_dir": str(work_dir),
        },
    )
    write_text(run_dir / "measurement-plan.md", build_measurement_plan(specs, repos))
    write_json(run_dir / "rubric.json", {"criteria": RUBRIC})
    write_generated_evaluator(run_dir)

    results = []
    for repo in repos:
        repo_path = work_dir / repo.team
        clone_result = clone_repo(repo, repo_path)
        team_dir = run_dir / "teams" / repo.team
        write_json(team_dir / "logs" / "clone.json", clone_result)
        if clone_result["exit_code"] != 0:
            result = {
                "team": repo.team,
                "repo_url": repo.url,
                "commit_sha": None,
                "clone": clone_result,
                "score_kind": "extraction_confidence_not_grade",
                "final_grade": None,
                "extraction_basis": "clone_failed",
                "independent_checks_completed": [],
                "not_independently_verified": [
                    "repo contents",
                    "reported measurements",
                    "before/after artifacts",
                    "deployed behavior",
                ],
                "file_count": 0,
                "markdown_file_count": 0,
                "submission_evidence_file_count": 0,
                "code_file_count": 0,
                "test_file_count": 0,
                "package_scripts": [],
                "docs": {},
                "submission_ledger": None,
                "category_hits": {category: False for category in CATEGORIES},
                "category_path_hits": {category: 0 for category in CATEGORIES},
                "category_evidence_hits": 0,
                "category_review_items": category_review_items(
                    {category: False for category in CATEGORIES},
                    {category: 0 for category in CATEGORIES},
                    "clone_failed",
                ),
                "proof_term_hits": [],
                "security_term_hits": [],
                "has_security_script": False,
                "has_security_probe_file": False,
                "scores": {item["id"]: 0 for item in RUBRIC},
                "total_score": 0,
                "extraction_confidence_score": 0,
                "total_without_insight": 0,
                "strengths": [],
                "risks": ["Repository could not be cloned."],
                "impressions": [],
                "recent_commits": [],
                "sample_files": [],
            }
        else:
            result = analyze_repo(repo, repo_path, clone_result)
        results.append(result)
        write_json(team_dir / "summary.json", result)
        write_json(team_dir / "evidence" / "static-scan.json", result)

    sorted_results = sorted(results, key=lambda item: item["total_score"], reverse=True)
    write_json(run_dir / "rankings.json", {"rankings": sorted_results})
    write_text(run_dir / "rankings.md", build_rankings(results))
    write_text(run_dir / "insights.md", build_insights(results))

    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
