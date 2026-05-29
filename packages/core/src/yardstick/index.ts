import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { readJson, writeJson } from '../fs.js';
import type { AgentMeasurement } from '../schemas/index.js';
import { logDecision } from '../decisions/index.js';

export interface YardstickStore {
  version: number;
  yardsticks: Record<string, YardstickEntry>;
  pending_updates: Record<string, unknown>[];
}

export interface YardstickEntry {
  criterion_id: string;
  kind: 'instrument' | 'judgment' | 'hybrid';
  established_at: string;
  established_from: string;
  yardstick: Record<string, unknown>;
  revisit_if: string[];
  alternatives_considered: Record<string, unknown>[];
  definition_history: Array<{ at: string; note: string; definitions?: Record<string, unknown> }>;
}

export function loadYardstickStore(runDir: string): YardstickStore {
  const path = join(runDir, 'yardsticks.json');
  if (!existsSync(path)) {
    return { version: 1, yardsticks: {}, pending_updates: [] };
  }
  return readJson<YardstickStore>(path);
}

export function saveYardstickStore(runDir: string, store: YardstickStore): void {
  writeJson(join(runDir, 'yardsticks.json'), store);
}

export function loadYardstick(runDir: string, criterionId: string): YardstickEntry | null {
  return loadYardstickStore(runDir).yardsticks[criterionId] ?? null;
}

export interface PromoteInput {
  criterionId: string;
  measurement: AgentMeasurement & { _artifact?: string };
  rationale?: string;
}

/** Auto-promote when challenge succeeds with high confidence. Returns true if promoted. */
export function tryAutoPromote(runDir: string, input: PromoteInput): boolean {
  const result = input.measurement.result;
  if (result.run_mode !== 'challenge' && !result.yardstick_update_proposed) return false;
  if (result.replay_outcome !== 'succeeded') return false;
  if (result.confidence !== 'high') return false;
  if (result.status === 'could_not_measure') return false;

  const store = loadYardstickStore(runDir);
  const existing = store.yardsticks[input.criterionId];
  const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
  const artifact = input.measurement._artifact ?? 'unknown';

  if (existing) {
    store.yardsticks[input.criterionId] = buildEntry(input, artifact, now);
    existing.alternatives_considered = existing.alternatives_considered ?? [];
    existing.alternatives_considered.push({
      at: now,
      artifact,
      method: result.method,
      rationale: input.rationale ?? result.yardstick_update_rationale ?? result.method_rationale,
      verdict: 'superseded',
      replay_outcome: result.replay_outcome,
    });
    store.yardsticks[input.criterionId]!.definition_history = [
      ...(existing.definition_history ?? []),
      {
        at: now,
        note: `Auto-promoted from challenge (${artifact})`,
        definitions: {},
      },
    ];
  } else {
    store.yardsticks[input.criterionId] = buildEntry(input, artifact, now);
  }

  saveYardstickStore(runDir, store);

  logDecision(runDir, {
    phase: 'yardstick',
    subject: { criterion: input.criterionId },
    decision: existing ? `yardstick superseded for ${input.criterionId}` : `yardstick established for ${input.criterionId}`,
    chosen: result.method ?? 'agent measurement',
    why: input.rationale ?? result.method_rationale ?? 'Auto-promoted after successful challenge with high confidence.',
    evidence: [`agent-measurements/${artifact}`, 'yardsticks.json'],
    confidence: 'high',
  });

  return true;
}

function buildEntry(
  input: PromoteInput,
  artifact: string,
  establishedAt: string,
): YardstickEntry {
  const result = input.measurement.result;
  const kind = inferKind(result);
  return {
    criterion_id: input.criterionId,
    kind,
    established_at: establishedAt,
    established_from: artifact,
    yardstick: {
      instrument: result.method ?? '',
      method_rationale: result.method_rationale ?? '',
      definitions: {},
      commands: splitCommands(result.commands_summary ?? ''),
      inspection_protocol: kind !== 'instrument' ? result.method : '',
      judgment_rubric: result.qualitative_judgment ?? '',
      evidence_requirements: [
        'Numbers must trace to commands run in the sandbox.',
        'Label conclusions as judgment when not instrument-backed.',
      ],
    },
    revisit_if: result.held_loosely ? [result.held_loosely] : [],
    alternatives_considered: [],
    definition_history: [],
  };
}

function inferKind(result: AgentMeasurement['result']): YardstickEntry['kind'] {
  if (result.qualitative_judgment && !result.verified_values) return 'judgment';
  if (result.verified_values && result.commands_summary) return 'instrument';
  return 'hybrid';
}

function splitCommands(summary: string): string[] {
  if (!summary.trim()) return [];
  return summary
    .split(/;\s*|\n+/)
    .map((p) => p.trim())
    .filter(Boolean);
}

export function logSupersededAttempt(
  runDir: string,
  criterionId: string,
  measurement: AgentMeasurement & { _artifact?: string },
  verdict: string,
): void {
  const store = loadYardstickStore(runDir);
  const entry = store.yardsticks[criterionId];
  const alt = {
    at: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
    artifact: measurement._artifact,
    method: measurement.result.method,
    rationale: measurement.result.method_rationale,
    verdict,
    replay_outcome: measurement.result.replay_outcome,
  };
  if (entry) {
    entry.alternatives_considered.push(alt);
  } else {
    store.pending_updates.push({ criterion_id: criterionId, ...alt });
  }
  saveYardstickStore(runDir, store);
}
