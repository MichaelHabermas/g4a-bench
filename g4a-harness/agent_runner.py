#!/usr/bin/env python3
"""Autonomous measurement agent — the system measures a criterion on its own.

This is the piece that makes the harness independent of a human-in-the-loop.
Given a week criterion (spec text) and a cloned repo, it runs a Claude tool-use
loop that DECIDES how to measure the criterion, RUNS commands in a sandbox,
checks the result against the team's self-report, and emits a structured,
verified measurement with full provenance. No per-metric Python script — the
agent reasons from the spec and the repo, the same loop for every criterion.

Design (grounded in the claude-api skill):
  - Surface: Claude API + manual tool-use loop. We host the compute (a Docker
    sandbox over the clone), so this is the right surface — not Managed Agents,
    which would run the container on Anthropic's side.
  - Model: claude-opus-4-8, adaptive thinking, effort=high (agentic default).
  - Prompt caching: the disciplines live in a stable, cached system prompt;
    the volatile per-run content (criterion + repo) goes in the user turn.
  - Tools: `bash` (executed in the sandbox) and `submit_measurement` (strict
    schema; calling it ends the run with the verified result).

The agent's freedom is "pick the yardstick"; the system prompt holds the
disciplines that keep results trustworthy and comparable. Method choice is
recorded per run (held loosely), never codified into this file.

Run for real:   ANTHROPIC_API_KEY=... python3 agent_runner.py \
                    --criterion-file <spec.txt> --repo <clone> --run-dir <dir>
Validate wiring (no key, no API call):   add --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

MODEL = "claude-opus-4-8"
MAX_STEPS = 40
MAX_TOOL_OUTPUT = 12000  # chars of bash output fed back per call

SYSTEM_PROMPT = """\
You are a benchmark MEASUREMENT AGENT. You are given ONE evaluation criterion \
from a weekly build challenge and a clone of one team's repository. Your job is \
to MEASURE the criterion yourself and report a verified result — not to trust \
what the team claims.

How you work:
1. Read the criterion. Decide what is actually measurable and what the \
   authoritative way to measure it is FOR THIS repo (inspect the stack first — \
   package.json, lockfiles, configs). State your chosen method and why.
2. Prefer a deterministic instrument the compiler/build/test toolchain already \
   provides over the team's own reported numbers or their bespoke scripts. \
   Their numbers and scripts are evidence to cross-check, not ground truth.
3. Run commands with the bash tool to produce the measurement from the actual \
   code. Parsing/reading is always safe; building or running their code executes \
   untrusted code — you are in a sandbox, but still avoid anything destructive \
   or network-exfiltrating.
4. Compare what you measured to what the team self-reported. If they diverge \
   materially, say so and trust YOUR measurement.

Disciplines (do not violate):
- ONE YARDSTICK. If this criterion will be compared across repos, use the same \
  definition and method you would use for every repo. Note any repo-specific \
  deviation as a comparability caveat.
- MEASURE, DON'T JUDGE THE NUMBER. Numbers come from tools you run. Use your own \
  judgment only for qualitative gates the spec names (e.g. "meaningful, not \
  superficial"), and label those as judgment, not measurement.
- REPRODUCIBLE + INSPECTABLE. Every number must trace to a command you ran. \
  Record the commands.
- HELD LOOSELY. Your method is a strong default, not a codified rule. Record a \
  revisit condition: what would make a better method.
- "COULDN'T MEASURE" IS A VALID RESULT. If the build fails or the metric isn't \
  reproducible, report that honestly with the evidence.

When you have measured the criterion (or determined you cannot), you MUST call \
`submit_measurement` exactly once with your structured result. Do not finish by \
writing prose alone — the run only completes when you call that tool.\
"""

BASH_TOOL = {
    "name": "bash",
    "description": (
        "Run a bash command inside the sandbox, in the repo working directory. "
        "Returns stdout, stderr, and exit code. State persists across calls "
        "(same shell/container). Use it to inspect the stack, parse files, and "
        "run measurement tools. Long output is truncated."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The bash command to run."},
            "timeout_sec": {"type": "integer", "description": "Max seconds (default 120)."},
        },
        "required": ["command"],
    },
}

SUBMIT_TOOL = {
    "name": "submit_measurement",
    "description": "Submit the final verified measurement. Calling this ends the run.",
    "input_schema": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["measured", "could_not_measure"]},
            "method": {"type": "string", "description": "The instrument/approach you chose."},
            "method_rationale": {"type": "string", "description": "Why this method, for this repo."},
            "verified_values": {
                "type": "object",
                "description": "The numbers you measured, as key/value (e.g. {\"as_casts\": 628}). Empty if could_not_measure.",
                "additionalProperties": True,
            },
            "self_report_comparison": {"type": "string", "description": "How your measurement compares to the team's claim; flag divergence."},
            "qualitative_judgment": {"type": "string", "description": "Any spec-named qualitative gate you assessed, labeled as judgment."},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "held_loosely": {"type": "string", "description": "What would make a better method next time."},
            "commands_summary": {"type": "string", "description": "The key commands you ran to produce the numbers."},
        },
        "required": ["status", "method", "method_rationale", "verified_values", "confidence"],
    },
}


# ---------------------------------------------------------------------------
# Sandbox
# ---------------------------------------------------------------------------

class DockerSandbox:
    """Persistent container over the clone. bash calls run via `docker exec`."""

    def __init__(self, repo: Path, image: str = "node:24-bookworm"):
        self.repo = repo
        self.image = image
        self.name = f"g4a-agent-{uuid.uuid4().hex[:10]}"

    def start(self) -> None:
        subprocess.run(
            ["docker", "run", "-d", "--rm", "--name", self.name,
             "-v", f"{self.repo}:/repo", "-w", "/repo",
             "--memory", "4g", "--cpus", "2",
             self.image, "sleep", "infinity"],
            check=True, capture_output=True,
        )
        # corepack gives pnpm/yarn without a network install step.
        subprocess.run(["docker", "exec", self.name, "bash", "-lc",
                        "corepack enable >/dev/null 2>&1 || true"], capture_output=True)

    def run(self, command: str, timeout_sec: int = 120) -> dict[str, Any]:
        try:
            proc = subprocess.run(
                ["docker", "exec", self.name, "bash", "-lc", command],
                capture_output=True, text=True, timeout=timeout_sec,
            )
            return {"stdout": proc.stdout, "stderr": proc.stderr, "exit_code": proc.returncode}
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": f"timeout after {timeout_sec}s", "exit_code": 124}

    def stop(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)


class LocalSandbox:
    """DANGER: runs the clone's commands directly on this host. Opt-in only."""

    def __init__(self, repo: Path):
        self.repo = repo

    def start(self) -> None:
        print("WARNING: --sandbox none runs untrusted repo commands on this host.", file=sys.stderr)

    def run(self, command: str, timeout_sec: int = 120) -> dict[str, Any]:
        try:
            proc = subprocess.run(command, shell=True, cwd=str(self.repo),
                                  capture_output=True, text=True, timeout=timeout_sec)
            return {"stdout": proc.stdout, "stderr": proc.stderr, "exit_code": proc.returncode}
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": f"timeout after {timeout_sec}s", "exit_code": 124}

    def stop(self) -> None:
        pass


def truncate(text: str) -> str:
    if len(text) <= MAX_TOOL_OUTPUT:
        return text
    keep = MAX_TOOL_OUTPUT // 2
    return text[:keep] + f"\n...[truncated {len(text) - MAX_TOOL_OUTPUT} chars]...\n" + text[-keep:]


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def build_user_message(criterion: str, repo: Path, self_report: str | None) -> str:
    parts = [
        "## Criterion to measure\n", criterion.strip(), "\n\n",
        f"## Repo\nThe clone is the sandbox working directory (/repo). Path on host: {repo}\n",
    ]
    if self_report:
        parts += ["\n## The team's self-reported result (verify, do not trust)\n", self_report.strip(), "\n"]
    parts.append("\nInspect the repo, choose your method, measure, then call submit_measurement.")
    return "".join(parts)


def assemble_request(user_message: str) -> dict[str, Any]:
    return {
        "model": MODEL,
        "max_tokens": 8000,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "high"},
        "system": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        "tools": [BASH_TOOL, SUBMIT_TOOL],
        "messages": [{"role": "user", "content": user_message}],
    }


def run_agent(criterion: str, repo: Path, run_dir: Path, sandbox_kind: str,
              self_report: str | None, max_steps: int) -> dict[str, Any]:
    import anthropic  # imported here so --dry-run works without the SDK installed

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    sandbox = DockerSandbox(repo) if sandbox_kind == "docker" else LocalSandbox(repo)
    transcript: list[dict[str, Any]] = []
    base = assemble_request(build_user_message(criterion, repo, self_report))
    messages = base["messages"]
    result: dict[str, Any] | None = None

    sandbox.start()
    try:
        for step in range(max_steps):
            resp = client.messages.create(
                model=base["model"], max_tokens=base["max_tokens"],
                thinking=base["thinking"], output_config=base["output_config"],
                system=base["system"], tools=base["tools"], messages=messages,
            )
            messages.append({"role": "assistant", "content": resp.content})

            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            if not tool_uses:
                # No tool call and not finished — nudge once toward submitting.
                messages.append({"role": "user", "content": "Call submit_measurement with your result now."})
                continue

            tool_results = []
            for tu in tool_uses:
                if tu.name == "submit_measurement":
                    result = dict(tu.input)
                    tool_results.append({"type": "tool_result", "tool_use_id": tu.id, "content": "recorded"})
                elif tu.name == "bash":
                    cmd = tu.input.get("command", "")
                    out = sandbox.run(cmd, int(tu.input.get("timeout_sec", 120)))
                    transcript.append({"step": step, "command": cmd, **{k: (truncate(v) if isinstance(v, str) else v) for k, v in out.items()}})
                    payload = f"exit={out['exit_code']}\n--- stdout ---\n{truncate(out['stdout'])}\n--- stderr ---\n{truncate(out['stderr'])}"
                    tool_results.append({"type": "tool_result", "tool_use_id": tu.id, "content": payload})
            messages.append({"role": "user", "content": tool_results})

            if result is not None:
                break
            if step == max_steps - 2:
                messages.append({"role": "user", "content": "Step budget nearly exhausted. Call submit_measurement now with your best result."})
    finally:
        sandbox.stop()

    return {
        "criterion_excerpt": criterion.strip()[:280],
        "repo": str(repo),
        "model": MODEL,
        "sandbox": sandbox_kind,
        "steps_used": len(transcript),
        "result": result or {"status": "could_not_measure", "method": "n/a", "note": "agent did not submit a measurement"},
        "transcript": transcript,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--criterion", help="Criterion spec text")
    p.add_argument("--criterion-file", type=Path, help="File with the criterion spec text")
    p.add_argument("--repo", type=Path, required=True, help="Path to the cloned repo")
    p.add_argument("--run-dir", type=Path, required=True, help="Where to write the measurement artifact")
    p.add_argument("--self-report", help="The team's claimed result, to cross-check")
    p.add_argument("--sandbox", choices=["docker", "none"], default="docker")
    p.add_argument("--max-steps", type=int, default=MAX_STEPS)
    p.add_argument("--out-name", default=None, help="Output filename under run-dir/agent-measurements/")
    p.add_argument("--dry-run", action="store_true", help="Assemble and print the request; no API call, no key needed")
    args = p.parse_args()

    criterion = args.criterion or (args.criterion_file.read_text(encoding="utf-8") if args.criterion_file else None)
    if not criterion:
        raise SystemExit("Provide --criterion or --criterion-file")

    if args.dry_run:
        req = assemble_request(build_user_message(criterion, args.repo, args.self_report))
        preview = {
            "model": req["model"], "thinking": req["thinking"], "output_config": req["output_config"],
            "system_chars": len(req["system"][0]["text"]), "system_cached": True,
            "tools": [t["name"] for t in req["tools"]],
            "first_user_message": req["messages"][0]["content"],
            "sandbox": args.sandbox, "repo_exists": args.repo.exists(),
            "ANTHROPIC_API_KEY_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
        }
        print(json.dumps(preview, indent=2))
        return 0

    record = run_agent(criterion, args.repo, args.run_dir, args.sandbox, args.self_report, args.max_steps)
    out_dir = args.run_dir / "agent-measurements"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = args.out_name or f"measurement-{uuid.uuid4().hex[:8]}.json"
    out_path = out_dir / name
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    # Append a one-line entry to the run ledger for diffing over time.
    with (args.run_dir / "ledger.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"repo": str(args.repo), "result": record["result"], "at": record["completed_at"], "artifact": str(out_path)}) + "\n")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
