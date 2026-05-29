import { appendFileSync, existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import type { DecisionEntry, DecisionFilter, DecisionPhase, DecisionSubject } from './types.js';

export * from './types.js';

export const DECISION_LOG_FILENAME = 'decision-log.jsonl';

export function decisionLogPath(runDir: string): string {
  return join(runDir, DECISION_LOG_FILENAME);
}

function newId(phase: DecisionPhase): string {
  const slug = phase.replace(/[^a-z]/g, '');
  const ts = Date.now().toString(36);
  return `dec-${slug}-${ts}-${randomUUID().slice(0, 6)}`;
}

export type LogDecisionInput = Omit<DecisionEntry, 'id' | 'at'> & {
  id?: string;
  at?: string;
};

export function logDecision(runDir: string, input: LogDecisionInput): DecisionEntry {
  const entry: DecisionEntry = {
    id: input.id ?? newId(input.phase),
    at: input.at ?? new Date().toISOString(),
    phase: input.phase,
    subject: input.subject ?? {},
    decision: input.decision,
    chosen: input.chosen,
    rejected: input.rejected,
    why: input.why,
    evidence: input.evidence,
    confidence: input.confidence,
    held_loosely: input.held_loosely,
    trace_id: input.trace_id,
    flagged: input.flagged,
  };
  const path = decisionLogPath(runDir);
  appendFileSync(path, `${JSON.stringify(entry)}\n`, 'utf8');
  return entry;
}

export function readDecisionLog(runDir: string): DecisionEntry[] {
  const path = decisionLogPath(runDir);
  if (!existsSync(path)) return [];
  const entries: DecisionEntry[] = [];
  for (const line of readFileSync(path, 'utf8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      entries.push(JSON.parse(trimmed) as DecisionEntry);
    } catch {
      /* skip corrupt line */
    }
  }
  return entries;
}

export function filterDecisions(entries: DecisionEntry[], filter: DecisionFilter = {}): DecisionEntry[] {
  let out = [...entries];
  if (filter.phase) out = out.filter((e) => e.phase === filter.phase);
  if (filter.team) out = out.filter((e) => e.subject.team === filter.team);
  if (filter.criterion) out = out.filter((e) => e.subject.criterion === filter.criterion);
  if (filter.flaggedOnly) out = out.filter((e) => e.flagged);
  out.sort((a, b) => a.at.localeCompare(b.at));
  if (filter.limit != null && filter.limit > 0) out = out.slice(-filter.limit);
  return out;
}

export function getDecisionById(runDir: string, id: string): DecisionEntry | null {
  return readDecisionLog(runDir).find((e) => e.id === id) ?? null;
}

export function decisionSummaryByPhase(entries: DecisionEntry[]): Record<DecisionPhase, number> {
  const counts: Partial<Record<DecisionPhase, number>> = {};
  for (const e of entries) {
    counts[e.phase] = (counts[e.phase] ?? 0) + 1;
  }
  return counts as Record<DecisionPhase, number>;
}

/** Build a chat-friendly digest of recent decisions for dev mode. */
export function buildDecisionDigest(entries: DecisionEntry[], max = 40): string {
  const recent = filterDecisions(entries, { limit: max });
  if (!recent.length) return 'No decisions logged yet for this run.';
  return recent
    .map(
      (e) =>
        `[${e.id}] ${e.at} ${e.phase} ${e.subject.team ?? ''} ${e.subject.metric ?? e.subject.criterion ?? ''}: ${e.decision} — ${e.why}`,
    )
    .join('\n');
}
