#!/usr/bin/env python3
"""Append one structured entry to {run_dir}/decision-log.jsonl."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def log_decision(run_dir: Path, entry: dict[str, Any]) -> dict[str, Any]:
    phase = str(entry.get("phase", "agent"))
    slug = "".join(c for c in phase if c.isalnum()) or "x"
    ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    full: dict[str, Any] = {
        "id": entry.get("id") or f"dec-{slug}-{ts:x}-{uuid.uuid4().hex[:6]}",
        "at": entry.get("at") or datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "subject": entry.get("subject") or {},
        "decision": entry["decision"],
        "why": entry["why"],
    }
    for key in ("chosen", "rejected", "evidence", "confidence", "held_loosely", "trace_id", "flagged"):
        if key in entry and entry[key] is not None:
            full[key] = entry[key]
    path = run_dir / "decision-log.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(full) + "\n")
    return full


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--phase", default="agent")
    p.add_argument("--decision", required=True)
    p.add_argument("--why", required=True)
    p.add_argument("--json", help="Full entry as JSON object")
    args = p.parse_args()
    if args.json:
        payload = json.loads(args.json)
    else:
        payload = {"phase": args.phase, "decision": args.decision, "why": args.why, "subject": {}}
    print(json.dumps(log_decision(args.run_dir, payload), indent=2))
