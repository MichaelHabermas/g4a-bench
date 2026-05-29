import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { basename, join } from 'node:path';
import { readJson, writeJson } from '../fs.js';
import type { AgentMeasurement } from '../schemas/index.js';

export type LatestMap = Map<string, AgentMeasurement & { criterion_id: string }>;

function teamFromRepo(repo: string): string {
  return basename(repo);
}

function kbFromBytes(n: number | null | undefined): number | null {
  if (n == null) return null;
  return Math.round((Number(n) / 1024) * 100) / 100;
}

export function loadAgentMeasurements(runDir: string): Array<AgentMeasurement & { _artifact?: string }> {
  const measDir = join(runDir, 'agent-measurements');
  if (!existsSync(measDir)) return [];
  const out: Array<AgentMeasurement & { _artifact?: string }> = [];
  for (const name of readdirSync(measDir).filter((f) => f.endsWith('.json')).sort()) {
    try {
      const data = readJson<AgentMeasurement & { _artifact?: string }>(join(measDir, name));
      data._artifact = name;
      out.push(data);
    } catch {
      /* skip corrupt */
    }
  }
  return out;
}

export function inferCriterionId(rec: AgentMeasurement & { _artifact?: string }): string | null {
  if (rec.criterion_id) return rec.criterion_id;
  const name = (rec._artifact ?? '').toLowerCase();
  if (name.startsWith('bundle-')) return 'cat-2-bundle';
  if (name.startsWith('typesafety-gate-')) return 'cat-1-typesafety-gate';
  return null;
}

export function latestByTeamCriterion(
  measurements: Array<AgentMeasurement & { _artifact?: string }>,
): LatestMap {
  const best = new Map<string, AgentMeasurement & { criterion_id: string }>();
  for (const rec of measurements) {
    const cid = inferCriterionId(rec);
    if (!cid) continue;
    const enriched = { ...rec, criterion_id: cid };
    const team = teamFromRepo(rec.repo);
    const key = `${cid}:${team}`;
    const prev = best.get(key);
    const sortKey = rec.completed_at ?? '';
    const prevKey = prev?.completed_at ?? '';
    if (!prev || sortKey >= prevKey) best.set(key, enriched);
  }
  return best;
}

function extractBundleMetrics(vv: Record<string, unknown>): Record<string, number | null | undefined> {
  const initialB =
    (vv.initial_load_js_raw_bytes as number | undefined) ??
    (vv.entry_chunk_js_bytes as number | undefined) ??
    (vv.entry_js_bytes as number | undefined);
  const totalB =
    (vv.total_js_css_bytes as number | undefined) ??
    (vv.total_js_bytes as number | undefined) ??
    (vv.total_assets_js_css_bytes as number | undefined);
  return {
    initial_load_kb: kbFromBytes(initialB ?? null),
    initial_load_gzip_kb: vv.initial_load_js_gzip_KB as number | undefined,
    total_js_css_kb: kbFromBytes(totalB ?? null),
  };
}

function flagKb(verifiedKb: number | null, claimedKb: number | null | undefined): {
  flagged: boolean;
  discrepancy_kb: number | null;
} {
  if (verifiedKb == null || claimedKb == null) return { flagged: false, discrepancy_kb: null };
  const disc = verifiedKb - claimedKb;
  const flagged = Math.abs(disc) > Math.max(5, 0.03 * Math.max(claimedKb, 1));
  return { flagged, discrepancy_kb: Math.round(disc * 100) / 100 };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function syncBundleTrace(runDir: string, latest: LatestMap): boolean {
  const path = join(runDir, 'bundle-trace.json');
  if (!existsSync(path)) return false;
  const trace = readJson<Record<string, any>>(path);
  let changed = false;
  const pathMap: Record<string, string> = {
    'initial-load-code-splitting': 'initial_load_kb',
    'total-production-bundle': 'total_js_css_kb',
  };

  for (const team of trace.teams ?? []) {
    const tid = team.team as string;
    const rec = latest.get(`cat-2-bundle:${tid}`);
    if (!rec || rec.result.status === 'could_not_measure') continue;
    const result = rec.result;
    const mode = result.run_mode;
    if (mode && !['establish', 'replay', 'challenge'].includes(mode)) continue;
    const vv = (result.verified_values ?? {}) as Record<string, unknown>;
    const metrics = extractBundleMetrics(vv);

    for (const tp of team.target_paths ?? []) {
      const key = pathMap[tp.id as string];
      if (!key) continue;
      const afterKb = metrics[key] as number | null | undefined;
      if (afterKb == null) continue;
      const chk = flagKb(afterKb, tp.after_kb as number | undefined);
      tp.verified = {
        after_kb: afterKb,
        claimed_after_kb: tp.after_kb,
        artifact: rec._artifact,
        method: (result.method ?? '').slice(0, 240),
        confidence: result.confidence,
        replay_outcome: result.replay_outcome,
        ...chk,
      };
      const state = String(tp.state ?? '');
      tp.state = `${state.startsWith('passes') ? 'passes' : 'fails'}_verified_harness`;
      changed = true;
    }

    const states: Record<string, { value?: string; note?: string }> = {};
    for (const s of team.evidence_states ?? []) states[s.name as string] = s;
    if (states.independent_reproduction) {
      states.independent_reproduction.value = 'verified';
      states.independent_reproduction.note = `Harness production build + dist measurement (${rec._artifact}).`;
    } else {
      team.evidence_states = team.evidence_states ?? [];
      team.evidence_states.push({
        name: 'independent_reproduction',
        value: 'verified',
        note: `Harness measured (${rec._artifact}).`,
      });
    }
    team.harness_measurement = {
      artifact: rec._artifact,
      completed_at: rec.completed_at,
      confidence: result.confidence,
      replay_outcome: result.replay_outcome,
    };
    changed = true;
  }

  if (changed) {
    for (const step of trace.process_steps ?? []) {
      if (step.id === 'independent-reproduction') {
        step.output =
          'Harness has rebuilt production bundles and measured dist for some or all repos.';
      }
    }
    writeJson(path, trace);
  }
  return changed;
}

function judgmentStateFromText(text: string): string {
  const t = text.toLowerCase();
  if (['fail', 'superficial', 'overstated', 'false', 'not meaningful', 'partially meaningful'].some((x) => t.includes(x))) {
    if (t.includes('partially') || t.includes('mixed')) return 'needs_review';
    if (t.includes('not meaningful') || (t.includes('superficial') && !t.includes('not superficial'))) return 'fail';
  }
  if (['meaningful', 'pass', 'genuine', 'not superficial'].some((x) => t.includes(x))) return 'pass';
  return 'needs_review';
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function syncTypesafetyJudgment(runDir: string, latest: LatestMap): boolean {
  const path = join(runDir, 'typesafety-trace.json');
  if (!existsSync(path)) return false;
  const trace = readJson<Record<string, any>>(path);
  let changed = false;

  for (const team of trace.teams ?? []) {
    const tid = team.team as string;
    const rec = latest.get(`cat-1-typesafety-gate:${tid}`);
    if (!rec) continue;
    const result = rec.result;
    const qj = result.qualitative_judgment ?? '';
    if (!qj) continue;
    const state = judgmentStateFromText(qj);
    for (const gate of team.judgment_gates ?? []) {
      if (gate.id === 'fixes_meaningful') {
        gate.state = state;
        gate.note = qj.slice(0, 400);
        gate.trust = result.replay_outcome === 'succeeded' ? 'verified' : 'artifact_backed';
        gate.artifact = rec._artifact;
        changed = true;
      }
    }
    team.qualitative_gate = {
      artifact: rec._artifact,
      completed_at: rec.completed_at,
      confidence: result.confidence,
      judgment_excerpt: qj.slice(0, 500),
      replay_outcome: result.replay_outcome,
    };
    const vv = (result.verified_values ?? {}) as Record<string, number | undefined>;
    if (vv.ast_total != null) {
      for (const [pid, key] of [
        ['any', 'ast_any'],
        ['as', 'ast_as'],
        ['nonnull', 'ast_nonnull'],
        ['total', 'ast_total'],
      ] as const) {
        const part = team.parts?.[pid];
        if (!part) continue;
        const val = vv[key];
        if (val == null) continue;
        part.verified = {
          ...(part.verified ?? {}),
          remaining: val,
          method: 'typescript-ast-agent',
          artifact: rec._artifact,
        };
        part.trust = 'verified';
        if (pid === 'as' && val > 100 && qj.toLowerCase().includes('superficial')) {
          part.judgment = 'needs_review';
        }
        changed = true;
      }
    }
  }

  if (changed) writeJson(path, trace);
  return changed;
}

export function buildRunState(runDir: string, latest: LatestMap): Record<string, unknown> {
  const ledgerLines: Record<string, unknown>[] = [];
  const ledgerPath = join(runDir, 'ledger.jsonl');
  if (existsSync(ledgerPath)) {
    for (const line of readFileLines(ledgerPath)) {
      if (!line.trim()) continue;
      try {
        ledgerLines.push(JSON.parse(line) as Record<string, unknown>);
      } catch {
        /* skip */
      }
    }
  }
  let yardstickIds: string[] = [];
  const ysPath = join(runDir, 'yardsticks.json');
  if (existsSync(ysPath)) {
    const ys = readJson<{ yardsticks?: Record<string, unknown> }>(ysPath);
    yardstickIds = Object.keys(ys.yardsticks ?? {});
  }

  const agent_measurements: Record<string, unknown> = {};
  for (const [key, rec] of latest) {
    agent_measurements[key] = {
      artifact: rec._artifact,
      completed_at: rec.completed_at,
      status: rec.result.status,
      run_mode: rec.result.run_mode ?? null,
      replay_outcome: rec.result.replay_outcome ?? null,
    };
  }

  return {
    run_id: basename(runDir),
    run_dir: runDir,
    updated_at: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
    agent_measurements,
    ledger_tail: ledgerLines.slice(-20),
    yardstick_ids: yardstickIds,
  };
}

function readFileLines(path: string): string[] {
  return readFileSync(path, 'utf8').split('\n');
}

export interface SyncOptions {
  runDir: string;
  cloneRoot?: string;
  verifyTypesafety?: (runDir: string, cloneRoot: string) => boolean;
}

export function syncAll(options: SyncOptions): {
  bundle_trace: boolean;
  typesafety_judgment: boolean;
  typesafety_verify: boolean;
  run_state: string;
} {
  const { runDir } = options;
  const measurements = loadAgentMeasurements(runDir);
  const latest = latestByTeamCriterion(measurements);
  const bundle = syncBundleTrace(runDir, latest);
  const judgment = syncTypesafetyJudgment(runDir, latest);
  let verified = false;
  if (options.verifyTypesafety && options.cloneRoot) {
    try {
      verified = options.verifyTypesafety(runDir, options.cloneRoot);
    } catch {
      verified = false;
    }
  }
  const state = buildRunState(runDir, latest);
  const statePath = join(runDir, 'run-state.json');
  writeJson(statePath, state);
  return {
    bundle_trace: bundle,
    typesafety_judgment: judgment,
    typesafety_verify: verified,
    run_state: statePath,
  };
}
