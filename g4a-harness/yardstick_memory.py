"""Cohort yardstick memory — minimal, durable recipes across repos in a run.

Two yardstick kinds:
  instrument — replay commands/tools (AST counter, production build + stat).
  judgment   — replay an inspection protocol (sample diffs, qualitative gates,
               browser/Playwright passes). Outcomes vary; comparability comes
               from the same rubric and evidence requirements, not identical numbers.

Workflow:
  establish — first repo for a criterion_id; may promote to yardsticks.json.
  replay    — later repos follow the frozen yardstick first.
  challenge — replay failed or revisit_if fired; propose better method (logged,
              not auto-adopted unless replay never existed).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

YARDSTICKS_FILENAME = "yardsticks.json"


def yardsticks_path(run_dir: Path) -> Path:
    return run_dir / YARDSTICKS_FILENAME


def load_store(run_dir: Path) -> dict[str, Any]:
    path = yardsticks_path(run_dir)
    if not path.exists():
        return {"version": 1, "yardsticks": {}, "pending_updates": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_store(run_dir: Path, store: dict[str, Any]) -> None:
    path = yardsticks_path(run_dir)
    path.write_text(json.dumps(store, indent=2), encoding="utf-8")


def load_yardstick(run_dir: Path, criterion_id: str) -> dict[str, Any] | None:
    store = load_store(run_dir)
    return store.get("yardsticks", {}).get(criterion_id)


def patch_yardstick(
    run_dir: Path,
    criterion_id: str,
    *,
    instrument: str | None = None,
    definitions: dict[str, Any] | None = None,
    commands: list[str] | None = None,
    revisit_if: list[str] | None = None,
    note: str = "",
) -> dict[str, Any] | None:
    """Apply a cohort-wide definition patch (logged in definition_history)."""
    store = load_store(run_dir)
    entry = store.get("yardsticks", {}).get(criterion_id)
    if entry is None:
        return None
    body = entry.setdefault("yardstick", {})
    if instrument is not None:
        body["instrument"] = instrument
    if definitions:
        body.setdefault("definitions", {}).update(definitions)
    if commands is not None:
        body["commands"] = commands
    if revisit_if is not None:
        entry["revisit_if"] = revisit_if
    entry.setdefault("definition_history", []).append({
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": note,
        "definitions": definitions or {},
    })
    save_store(run_dir, store)
    return entry


def infer_kind(criterion: str, result: dict[str, Any] | None = None) -> str:
    text = criterion.lower()
    judgment_markers = (
        "qualitative gate",
        "judgment only",
        "meaningful",
        "superficial",
        "what do you think",
        "inspect the actual code",
        "look at",
        "playwright",
        "browser",
        "lighthouse",
        "axe ",
        "accessibility",
        "visual",
        "screenshot",
        "ui ",
    )
    instrument_markers = (
        "typescript ast",
        "compiler ast",
        " tsc ",
        "build the production",
        "pnpm install",
        "dist/",
        "measure dist",
        "byte",
        "count explicit",
        "violation counter",
    )
    is_judgment = any(m in text for m in judgment_markers)
    is_instrument = any(m in text for m in instrument_markers)
    if result:
        if result.get("qualitative_judgment") and not result.get("verified_values"):
            is_judgment = True
        cmds = result.get("commands_summary") or ""
        if cmds and result.get("verified_values"):
            is_instrument = True
    if is_judgment and is_instrument:
        return "hybrid"
    if is_judgment:
        return "judgment"
    if is_instrument:
        return "instrument"
    return "hybrid"


def _split_commands(commands_summary: str) -> list[str]:
    if not commands_summary.strip():
        return []
    parts = re.split(r";\s*|\n+", commands_summary.strip())
    return [p.strip() for p in parts if p.strip()]


def yardstick_from_measurement(
    criterion_id: str,
    criterion: str,
    result: dict[str, Any],
    artifact_name: str,
) -> dict[str, Any]:
    kind = infer_kind(criterion, result)
    held = (result.get("held_loosely") or "").strip()
    revisit: list[str] = [held] if held else []
    blockers = (result.get("blockers") or "").strip()
    if blockers:
        revisit.append(f"Blocker encountered: {blockers[:240]}")

    body: dict[str, Any] = {
        "instrument": result.get("method", ""),
        "method_rationale": result.get("method_rationale", ""),
        "definitions": {},
        "commands": _split_commands(result.get("commands_summary") or ""),
        "inspection_protocol": "",
        "judgment_rubric": "",
        "evidence_requirements": [],
    }
    if kind in ("judgment", "hybrid"):
        body["inspection_protocol"] = result.get("method", "")
        body["judgment_rubric"] = result.get("qualitative_judgment") or criterion.strip()[:500]
        body["evidence_requirements"] = [
            "Label conclusions as judgment, not measurement.",
            "State confidence and what would raise it.",
            "Say I don't know rather than invent numbers.",
        ]
    if kind in ("instrument", "hybrid"):
        body["evidence_requirements"].append(
            "Numbers must trace to commands run in the sandbox."
        )

    return {
        "criterion_id": criterion_id,
        "kind": kind,
        "established_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "established_from": artifact_name,
        "yardstick": body,
        "revisit_if": revisit,
        "alternatives_considered": [],
    }


def promote_if_first(
    run_dir: Path,
    criterion_id: str,
    criterion: str,
    result: dict[str, Any],
    artifact_name: str,
    run_mode: str,
) -> dict[str, Any] | None:
    if run_mode != "establish":
        return None
    if result.get("status") == "could_not_measure":
        return None
    store = load_store(run_dir)
    if criterion_id in store.get("yardsticks", {}):
        return None
    entry = yardstick_from_measurement(criterion_id, criterion, result, artifact_name)
    store.setdefault("yardsticks", {})[criterion_id] = entry
    save_store(run_dir, store)
    return entry


def log_challenge(
    run_dir: Path,
    criterion_id: str,
    result: dict[str, Any],
    artifact_name: str,
) -> None:
    store = load_store(run_dir)
    entry = store.get("yardsticks", {}).get(criterion_id)
    alt = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifact": artifact_name,
        "method": result.get("method", ""),
        "rationale": result.get("yardstick_update_rationale") or result.get("method_rationale", ""),
        "verdict": "proposed_not_adopted",
        "replay_outcome": result.get("replay_outcome"),
    }
    if entry is not None:
        entry.setdefault("alternatives_considered", []).append(alt)
        save_store(run_dir, store)
        return
    store.setdefault("pending_updates", []).append({"criterion_id": criterion_id, **alt})
    save_store(run_dir, store)


def build_yardstick_user_section(
    criterion_id: str,
    yardstick: dict[str, Any] | None,
) -> str:
    if yardstick is None:
        return (
            f"\n## Cohort yardstick — ESTABLISH (`{criterion_id}`)\n"
            "No yardstick exists yet for this criterion in this run. Prefer a method "
            "that will work across every repo in the cohort (comparability over cleverness). "
            "Submit with `run_mode`: `establish`.\n"
            "If the criterion mixes hard instruments and qualitative gates, say which "
            "parts are instrument vs judgment in your method.\n"
        )

    kind = yardstick.get("kind", "hybrid")
    body = yardstick.get("yardstick", {})
    lines = [
        f"\n## Cohort yardstick — REPLAY FIRST (`{criterion_id}`)\n",
        f"Kind: **{kind}** (established from `{yardstick.get('established_from', '?')}`).\n",
        "Phases:\n",
        "1. **Replay** — apply the yardstick below on this repo before exploring alternatives.\n",
        "2. **Challenge** (optional, bounded) — only if replay fails, confidence would be "
        "low, or a `revisit_if` condition clearly applies. Compare side-by-side; do not "
        "silently replace the cohort yardstick.\n",
        "3. **Submit** with `run_mode`: `replay` or `challenge`.\n\n",
    ]
    if kind in ("instrument", "hybrid"):
        lines.append("### Instrument (deterministic)\n")
        lines.append(f"{body.get('instrument', '')}\n\n")
        defs = body.get("definitions") or {}
        if defs:
            lines.append("### Pinned definitions\n")
            for key, val in defs.items():
                lines.append(f"- **{key}**: {val}\n")
            lines.append("\n")
        cmds = body.get("commands") or []
        if cmds:
            lines.append("Commands to replay (adapt paths only if the repo layout demands it):\n")
            for cmd in cmds:
                lines.append(f"- `{cmd}`\n")
            lines.append("\n")
    if kind in ("judgment", "hybrid"):
        lines.append("### Judgment (inspection protocol)\n")
        lines.append(
            "Follow the same rubric and evidence bar. Browser/Playwright/visual passes "
            "are allowed when the spec requires them — outcomes will differ by repo; "
            "comparability is the protocol, not identical scores.\n\n"
        )
        if body.get("inspection_protocol"):
            lines.append(f"Protocol: {body['inspection_protocol']}\n\n")
        if body.get("judgment_rubric"):
            lines.append(f"Rubric anchor: {body['judgment_rubric'][:800]}\n\n")
        for req in body.get("evidence_requirements") or []:
            lines.append(f"- {req}\n")
        lines.append("\n")
    revisit = yardstick.get("revisit_if") or []
    if revisit:
        lines.append("### Revisit if\n")
        for item in revisit:
            if item:
                lines.append(f"- {item}\n")
        lines.append("\n")
    alts = yardstick.get("alternatives_considered") or []
    if alts:
        lines.append("### Prior alternatives (not adopted)\n")
        for alt in alts[-3:]:
            lines.append(f"- {alt.get('method', '')[:200]} — {alt.get('verdict', '')}\n")
        lines.append("\n")
    return "".join(lines)


def seed_from_measurement_artifact(run_dir: Path, criterion_id: str, artifact_path: Path) -> dict[str, Any] | None:
    """Promote an existing agent-measurements/*.json into yardsticks.json if empty."""
    store = load_store(run_dir)
    if criterion_id in store.get("yardsticks", {}):
        return store["yardsticks"][criterion_id]
    data = json.loads(artifact_path.read_text(encoding="utf-8"))
    result = data.get("result") or {}
    if result.get("status") == "could_not_measure":
        return None
    criterion = data.get("criterion_excerpt") or criterion_id
    entry = yardstick_from_measurement(criterion_id, criterion, result, artifact_path.name)
    store.setdefault("yardsticks", {})[criterion_id] = entry
    save_store(run_dir, store)
    return entry
