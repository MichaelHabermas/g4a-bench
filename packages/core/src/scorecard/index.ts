import { existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { readJson } from '../fs.js';
import type { TrustTier } from '../schemas/index.js';

export const TRUST_RANK: Record<TrustTier, number> = {
  claimed: 0,
  'reported-math': 1,
  'artifact-backed': 2,
  verified: 3,
};

export const TRUST_SHORT: Record<TrustTier, string> = {
  'reported-math': 'md',
  'artifact-backed': 'art',
  verified: 'ver',
  claimed: 'claim',
};

const PATH_LABELS: Record<string, string> = {
  'total-production-bundle': 'total bundle',
  'initial-load-code-splitting': 'initial load',
};

const TIE_EPS = 4;

export interface ReductionCell {
  kind: 'reduction';
  value_kind: string;
  reduction_percent?: number | null;
  remaining?: number | null;
  claimed_after?: number | null;
  before?: number | null;
  after?: number | null;
  unit: string;
  trust: TrustTier;
  outcome?: string | null;
  judgment: string;
  flagged?: boolean;
  verified: boolean;
  goodness: number | null;
  display: string;
}

export interface BooleanCell {
  kind: 'boolean';
  value?: unknown;
  trust: TrustTier;
  judgment: string;
  goodness: null;
}

export type ScoreCell = ReductionCell | BooleanCell;

export interface ScoreCriterion {
  id: string;
  name: string;
  unit: string;
  combine: string;
  headline?: string | null;
  threshold_percent?: number | null;
  parts: Array<{ id: string; label: string; threshold?: string; kind: string; headline?: boolean }>;
  teams: Record<
    string,
    {
      cells: Record<string, ScoreCell>;
      info: { claims: string[]; caveats: string[]; trust: string };
    }
  >;
  verified_kind: boolean;
}

export interface ScorecardModel {
  criteria: ScoreCriterion[];
  team_ids: string[];
  handles: Record<string, string>;
}

export function shortTeam(name: string): string {
  for (const token of ['michaelhabermas', 'daltondinderman', 'shivkanthalu']) {
    if (name.includes(token)) return token;
  }
  const tail = name.replace(/\/$/, '').split('-');
  return tail[tail.length - 1] ?? name;
}

function reductionCell(params: {
  value_kind: string;
  reduction_percent?: number | null;
  remaining?: number | null;
  claimed_after?: number | null;
  before?: number | null;
  after?: number | null;
  unit?: string;
  trust?: TrustTier;
  outcome?: string | null;
  judgment?: string;
  flagged?: boolean;
  verified?: boolean;
}): ReductionCell {
  const {
    value_kind,
    reduction_percent,
    remaining,
    claimed_after,
    before,
    after,
    unit = '',
    trust = 'claimed',
    outcome = null,
    judgment = 'needs_review',
    flagged = false,
    verified = false,
  } = params;

  let goodness: number | null;
  let display: string;
  if (value_kind === 'remaining') {
    goodness = remaining == null ? null : -remaining;
    display = remaining == null ? 'n/a' : `${remaining} left`;
  } else {
    goodness =
      reduction_percent == null || reduction_percent <= 0 ? null : reduction_percent;
    if (reduction_percent == null) display = 'n/a';
    else if (reduction_percent > 0) display = `${reduction_percent.toFixed(1)}%↓`;
    else display = reduction_percent !== 0 ? `${reduction_percent.toFixed(1)}%` : '0% flat';
  }

  return {
    kind: 'reduction',
    value_kind,
    reduction_percent,
    remaining,
    claimed_after,
    before,
    after,
    unit,
    trust,
    outcome,
    judgment,
    flagged,
    verified,
    goodness,
    display,
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function bundleCriterion(trace: Record<string, any>): ScoreCriterion {
  const parts = (trace.teams?.[0]?.target_paths ?? []).map((p: Record<string, unknown>) => ({
    id: p.id as string,
    label: PATH_LABELS[p.id as string] ?? (p.id as string),
    threshold: (p.spec_threshold as string) ?? '',
    kind: 'reduction',
  }));

  const teams: ScoreCriterion['teams'] = {};
  let anyVerified = false;

  for (const team of trace.teams ?? []) {
    const states: Record<string, string> = {};
    for (const s of team.evidence_states ?? []) states[s.name as string] = s.value as string;
    const comparability = states.comparability;
    const cells: Record<string, ScoreCell> = {};
    let teamVerified = false;

    for (const path of team.target_paths ?? []) {
      const outcome = String(path.state ?? '').startsWith('passes_') ? 'passes' : 'fails';
      const v = path.verified as Record<string, unknown> | undefined;
      if (v?.after_kb != null) {
        const afterKb = Number(v.after_kb);
        teamVerified = true;
        let judgment = outcome === 'passes' ? 'meaningful' : 'needs_review';
        if (v.flagged) judgment = 'needs_review';
        cells[path.id as string] = {
          kind: 'reduction',
          value_kind: 'verified_after',
          reduction_percent: path.reduction_percent as number | null,
          remaining: null,
          claimed_after: path.after_kb as number,
          before: (path.before_kb ?? path.before) as number,
          after: afterKb,
          unit: 'KB',
          trust: 'verified',
          outcome,
          judgment,
          flagged: Boolean(v.flagged),
          verified: true,
          goodness: -afterKb,
          display: `${afterKb.toFixed(0)} KiB ver`,
        };
        continue;
      }
      const state = String(path.state ?? '');
      const trust: TrustTier = state.includes('artifact_math')
        ? 'artifact-backed'
        : state.includes('markdown_math')
          ? 'reported-math'
          : 'claimed';
      let judgment = 'meaningful';
      if (outcome === 'fails') judgment = 'not_addressed';
      else if (trust === 'reported-math' || comparability === 'needs_agent_review')
        judgment = 'needs_review';
      cells[path.id as string] = reductionCell({
        value_kind: 'reduction_pct',
        reduction_percent: path.reduction_percent as number | null,
        before: (path.before_kb ?? path.before) as number,
        after: (path.after_kb ?? path.after) as number,
        unit: 'KB',
        trust,
        outcome,
        judgment,
      });
    }
    if (teamVerified) anyVerified = true;
    teams[team.team as string] = {
      cells,
      info: {
        claims: (team.claim_text as string[]) ?? [],
        caveats: (team.caveats as string[]) ?? [],
        trust: (team.trust as string) ?? '',
      },
    };
  }

  return {
    id: 'bundle-size',
    name: 'Bundle Size',
    unit: 'KB',
    combine: 'any_threshold',
    headline: null,
    threshold_percent: null,
    parts,
    teams,
    verified_kind: anyVerified,
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function typesafetyCriterion(trace: Record<string, any>): ScoreCriterion {
  const crit = trace.criterion;
  const parts = (trace.part_defs ?? []).map((p: Record<string, unknown>) => ({
    id: p.id as string,
    label: p.label as string,
    threshold: (p.threshold as string) ?? '',
    kind: p.kind === 'boolean' ? 'boolean' : 'reduction',
    headline: Boolean(p.headline),
  }));
  const headline = crit.headline_part as string;
  const thr = crit.threshold_percent as number;
  let verifiedKind = false;
  const teams: ScoreCriterion['teams'] = {};

  for (const team of trace.teams ?? []) {
    const cells: Record<string, ScoreCell> = {};
    for (const [pid, part] of Object.entries(team.parts ?? {}) as [string, Record<string, any>][]) {
      if (part.kind === 'boolean') {
        cells[pid] = {
          kind: 'boolean',
          value: part.value,
          trust: (part.trust ?? team.trust ?? 'claimed') as TrustTier,
          judgment: part.judgment ?? 'neutral',
          goodness: null,
        };
        continue;
      }
      const v = part.verified as Record<string, unknown> | undefined;
      if (v) {
        verifiedKind = true;
        cells[pid] = reductionCell({
          value_kind: 'remaining',
          remaining: v.remaining as number,
          claimed_after: v.claimed_after as number,
          reduction_percent: part.reduction_percent as number,
          before: part.before as number,
          after: part.after as number,
          unit: 'violations',
          trust: 'verified',
          judgment: part.judgment ?? 'needs_review',
          flagged: Boolean(v.flagged),
          verified: true,
        });
      } else {
        const rp = part.reduction_percent as number | null;
        const outcome =
          pid === headline && rp != null && thr != null && rp >= thr
            ? 'passes'
            : pid === headline && rp != null
              ? 'fails'
              : null;
        cells[pid] = reductionCell({
          value_kind: 'reduction_pct',
          reduction_percent: rp,
          before: part.before as number,
          after: part.after as number,
          unit: 'violations',
          trust: (part.trust ?? team.trust ?? 'claimed') as TrustTier,
          outcome,
          judgment: part.judgment ?? 'needs_review',
        });
      }
    }
    teams[team.team as string] = {
      cells,
      info: {
        claims: (team.claim_text as string[]) ?? [],
        caveats: (team.caveats as string[]) ?? [],
        trust: (team.trust as string) ?? '',
      },
    };
  }

  return {
    id: crit.id,
    name: crit.name,
    unit: crit.unit,
    combine: crit.combine ?? 'headline',
    headline,
    threshold_percent: thr,
    parts,
    teams,
    verified_kind: verifiedKind,
  };
}

export function loadScorecardModel(runDir: string): ScorecardModel {
  const order = ['typesafety-trace.json', 'bundle-trace.json'];
  const paths = order.filter((n) => existsSync(join(runDir, n))).map((n) => join(runDir, n));
  for (const p of readdirSync(runDir).filter((f) => f.endsWith('-trace.json')).sort()) {
    const full = join(runDir, p);
    if (!paths.includes(full)) paths.push(full);
  }

  const criteria: ScoreCriterion[] = [];
  for (const path of paths) {
    const trace = readJson<Record<string, unknown>>(path);
    const kind = trace.artifact_kind;
    if (kind === 'type_safety_process_trace') criteria.push(typesafetyCriterion(trace));
    else if (kind === 'bundle_size_process_trace') criteria.push(bundleCriterion(trace));
  }

  const team_ids: string[] = [];
  for (const crit of criteria) {
    for (const tid of Object.keys(crit.teams)) {
      if (!team_ids.includes(tid)) team_ids.push(tid);
    }
  }

  const handles: Record<string, string> = {};
  for (const tid of team_ids) handles[tid] = shortTeam(tid);

  return { criteria, team_ids, handles };
}

export function rowWinners(
  crit: ScoreCriterion,
  pid: string,
  teamIds: string[],
): Set<string> {
  const cand: Array<[string, ReductionCell]> = [];
  for (const tid of teamIds) {
    const c = crit.teams[tid]?.cells[pid];
    if (!c || c.kind !== 'reduction' || c.goodness == null) continue;
    cand.push([tid, c]);
  }
  if (!cand.length) return new Set();
  const top = Math.max(...cand.map(([, c]) => TRUST_RANK[c.trust]));
  const topCells = cand.filter(([, c]) => TRUST_RANK[c.trust] === top);
  const best = Math.max(...topCells.map(([, c]) => c.goodness!));
  return new Set(topCells.filter(([, c]) => best - c.goodness! <= TIE_EPS).map(([tid]) => tid));
}

export function categoryWinner(
  crit: ScoreCriterion,
  teamIds: string[],
): { winner: string | null; provisional: boolean; evidence: string } | null {
  if (crit.verified_kind) {
    const headline = crit.headline;
    if (!headline) return null;
    const cand = teamIds
      .map((tid) => {
        const c = crit.teams[tid]?.cells[headline];
        return c?.kind === 'reduction' && c.trust === 'verified' ? [tid, c] as const : null;
      })
      .filter(Boolean) as Array<[string, ReductionCell]>;
    if (!cand.length) return null;
    const best = Math.min(...cand.map(([, c]) => c.remaining ?? Infinity));
    const winners = cand.filter(([, c]) => (c.remaining ?? Infinity) - best <= TIE_EPS);
    return {
      winner: winners[0]?.[0] ?? null,
      provisional: true,
      evidence: 'verified',
    };
  }
  return null;
}

export function overallWinner(model: ScorecardModel): {
  winner: string | null;
  provisional: boolean;
  verifiedCategories: string[];
} {
  const scores = new Map<string, { verified: number; total: number }>();
  for (const tid of model.team_ids) scores.set(tid, { verified: 0, total: 0 });

  for (const crit of model.criteria) {
    const cat = categoryWinner(crit, model.team_ids);
    if (!cat?.winner) continue;
    const s = scores.get(cat.winner)!;
    s.total += 1;
    if (cat.evidence === 'verified') s.verified += 1;
  }

  let best: string | null = null;
  let bestScore = -1;
  for (const [tid, s] of scores) {
    const score = s.verified * 10 + s.total;
    if (score > bestScore) {
      bestScore = score;
      best = tid;
    }
  }

  const verifiedCategories = model.criteria.filter((c) => c.verified_kind).map((c) => c.name);
  return { winner: best, provisional: true, verifiedCategories };
}
