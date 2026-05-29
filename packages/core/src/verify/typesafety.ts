import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { basename, join } from 'node:path';
import { readJson, writeJson } from '../fs.js';
import { harnessDir } from '../paths.js';

const CONSIDERED_METHODS = [
  {
    method: 'regex grep',
    verdict: 'rejected',
    why: 'Counts `import { X as Y }` aliases as casts. Measured here: crude `as` ~956 vs real 284 for one repo — unusable for the `as` metric.',
  },
  {
    method: "team's ESLint output",
    verdict: 'rejected',
    why: "Self-reported, and `consistent-type-assertions` flags only a narrow subset of `as` usages — not the spec's 'type assertions (as)'.",
  },
  {
    method: 'typescript compiler AST',
    verdict: 'chosen',
    why: 'Authoritative for cast/non-null/any nodes, identical definition across all repos, and safe: it only parses, never executes the clone.',
  },
];

const HELD_LOOSELY =
  'Count is syntactic — cannot judge whether a remaining cast is justified or a removed `any` was genuinely narrowed. Revisit with a type-aware (full-program) pass or a diff-based superficiality method.';

function flag(verified: number, claimed: number | null | undefined): {
  flagged: boolean;
  discrepancy: number | null;
  note: string;
} {
  if (claimed == null) {
    return { flagged: false, discrepancy: null, note: 'no self-reported after to compare' };
  }
  const disc = verified - claimed;
  const big = Math.abs(disc) > Math.max(20, 0.15 * Math.max(verified, 1));
  return {
    flagged: big,
    discrepancy: disc,
    note: big
      ? 'self-report rejected — verified count diverges materially'
      : 'self-report roughly consistent with verified count',
  };
}

export function runTsCounter(repoPath: string, root?: string): Record<string, unknown> {
  const harness = harnessDir(root);
  const script = join(harness, 'ts_violation_counter.js');
  const env = { ...process.env, TS_LIB: process.env.TS_LIB ?? '/tmp/tsverify/node_modules/typescript' };
  const out = spawnSync('node', [script, repoPath], { encoding: 'utf8', env });
  if (out.status !== 0) {
    throw new Error(out.stderr || out.stdout || 'ts_violation_counter failed');
  }
  return JSON.parse(out.stdout.trim()) as Record<string, unknown>;
}

export function verifyTypesafety(runDir: string, cloneRoot: string): boolean {
  const tracePath = join(runDir, 'typesafety-trace.json');
  if (!existsSync(tracePath)) return false;
  const trace = readJson<Record<string, any>>(tracePath);
  const cloneBase = join(cloneRoot, basename(runDir));
  const records: Record<string, unknown>[] = [];

  for (const team of trace.teams ?? []) {
    const repo = join(cloneBase, team.team as string);
    const rec: Record<string, unknown> = {
      team: team.team,
      metric_class: 'type-safety syntactic counts (any/as/!)',
      considered_methods: CONSIDERED_METHODS,
      chosen_method: 'typescript compiler AST',
      held_loosely: HELD_LOOSELY,
    };
    if (!existsSync(repo)) {
      rec.status = 'clone_unavailable';
      rec.note = `No clone at ${repo}; cannot verify, self-report stands but remains unverified.`;
      records.push(rec);
      continue;
    }

    const result = runTsCounter(repo);
    const counts = result.counts as Record<string, number>;
    const verified: Record<'any' | 'as' | 'nonnull' | 'total', number> = {
      any: counts.any ?? 0,
      as: counts.as ?? 0,
      nonnull: counts.nonnull ?? 0,
      total: 0,
    };
    verified.total = verified.any + verified.as + verified.nonnull;
    rec.status = 'verified';
    rec.tool = {
      name: result.tool,
      ts_version: result.ts_version,
      scope: result.scope,
      files: result.files,
    };
    rec.verified_remaining = verified;
    rec.checks = {};

    for (const pid of ['any', 'as', 'nonnull', 'total'] as const) {
      const part = team.parts?.[pid];
      if (!part) continue;
      const claimedAfter = part.after as number | undefined;
      const chk = flag(verified[pid], claimedAfter);
      (rec.checks as Record<string, unknown>)[pid] = {
        verified: verified[pid],
        claimed_after: claimedAfter,
        ...chk,
      };
      part.verified = {
        remaining: verified[pid],
        claimed_after: claimedAfter,
        discrepancy: chk.discrepancy,
        flagged: chk.flagged,
        method: 'typescript-ast',
      };
      part.trust = 'verified';
    }
    team.verification = rec;
    records.push(rec);
  }

  trace.verification = {
    verified_state: 'after_only',
    baseline_gap:
      'Verified % reduction not computed — a common baseline (original ShipShape) has not been independently counted. Recorded, not faked.',
    records,
  };
  writeJson(tracePath, trace);
  writeJson(join(runDir, 'verification.json'), trace.verification);
  return true;
}
