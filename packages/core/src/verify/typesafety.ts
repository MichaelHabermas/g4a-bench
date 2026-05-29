import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { readJson, writeJson } from '../fs.js';
import { harnessDir } from '../paths.js';
import { logDecision } from '../decisions/index.js';

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
    method: 'typescript compiler AST + diagnostics',
    verdict: 'chosen',
    why: 'Authoritative for cast/non-null/any nodes and implicit-any diagnostics (untyped params), consistent across repos, and safe because it only parses/typechecks — never executes the clone.',
  },
];

const HELD_LOOSELY =
  'Count is syntactic/diagnostic — cannot judge whether a remaining cast is justified or a removed `any` was genuinely narrowed. Revisit with a type-aware pass or diff-based superficiality method.';

const VERIFY_PARTS = ['any', 'as', 'nonnull', 'total', 'untyped'] as const;

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

export function ensureTypescriptLib(root?: string): void {
  const tsLib =
    process.env.TS_LIB ?? join('/tmp/tsverify/node_modules/typescript');
  if (existsSync(join(tsLib, 'package.json')) || existsSync(join(tsLib, 'lib', 'typescript.js'))) {
    return;
  }
  const parent = join('/tmp/tsverify');
  if (!existsSync(parent)) {
    spawnSync('mkdir', ['-p', parent], { encoding: 'utf8' });
  }
  spawnSync('npm', ['i', 'typescript@5.9.3', '--no-save', '--silent'], {
    cwd: parent,
    encoding: 'utf8',
  });
  void root;
}

export function runTsCounter(repoPath: string, root?: string): Record<string, unknown> {
  ensureTypescriptLib(root);
  const harness = harnessDir(root);
  const script = join(harness, 'ts_violation_counter.cjs');
  const env = { ...process.env, TS_LIB: process.env.TS_LIB ?? '/tmp/tsverify/node_modules/typescript' };
  const out = spawnSync('node', [script, repoPath], { encoding: 'utf8', env, maxBuffer: 16 * 1024 * 1024 });
  if (out.status !== 0) {
    throw new Error(out.stderr || out.stdout || 'ts_violation_counter failed');
  }
  return JSON.parse(out.stdout.trim()) as Record<string, unknown>;
}

/** cloneBase is the run-level directory containing team subfolders. */
export function verifyTypesafety(runDir: string, cloneBase: string): boolean {
  const tracePath = join(runDir, 'typesafety-trace.json');
  if (!existsSync(tracePath)) return false;
  const trace = readJson<Record<string, any>>(tracePath);
  const records: Record<string, unknown>[] = [];

  for (const team of trace.teams ?? []) {
    const repo = join(cloneBase, team.team as string);
    const rec: Record<string, unknown> = {
      team: team.team,
      metric_class: 'type-safety syntactic counts (any/as/!) + untyped params (diagnostics)',
      considered_methods: CONSIDERED_METHODS,
      chosen_method: 'typescript compiler AST + diagnostics',
      held_loosely: HELD_LOOSELY,
    };
    if (!existsSync(repo)) {
      rec.status = 'clone_unavailable';
      rec.note = `No clone at ${repo}; cannot verify, self-report stands but remains unverified.`;
      records.push(rec);
      logDecision(runDir, {
        phase: 'verify',
        subject: { team: team.team as string, criterion: 'type-safety' },
        decision: 'skipped — clone unavailable',
        why: rec.note as string,
        evidence: ['typesafety-trace.json'],
        confidence: 'low',
      });
      continue;
    }

    logDecision(runDir, {
      phase: 'verify',
      subject: { team: team.team as string, criterion: 'type-safety' },
      decision: `instrument: typescript compiler AST + diagnostics`,
      chosen: 'typescript compiler AST + diagnostics',
      rejected: CONSIDERED_METHODS.filter((m) => m.verdict === 'rejected').map((m) => m.method),
      why: CONSIDERED_METHODS.find((m) => m.verdict === 'chosen')!.why,
      evidence: ['verification.json', 'g4a-harness/ts_violation_counter.cjs'],
      held_loosely: HELD_LOOSELY,
      confidence: 'high',
    });

    const result = runTsCounter(repo);
    const counts = result.counts as Record<string, number>;
    const untypedMethod = result.untyped_method as string | undefined;
    const verified: Record<string, number> = {
      any: counts.any ?? 0,
      as: counts.as ?? 0,
      nonnull: counts.nonnull ?? 0,
      untyped: counts.untyped_params ?? 0,
      total: 0,
    };
    verified.total = (verified.any ?? 0) + (verified.as ?? 0) + (verified.nonnull ?? 0);
    rec.status = 'verified';
    rec.tool = {
      name: result.tool,
      ts_version: result.ts_version,
      scope: result.scope,
      files: result.files,
      untyped_method: untypedMethod ?? 'unknown',
      diagnostic_codes: result.diagnostic_codes,
    };
    rec.verified_remaining = verified;
    rec.checks = {};

    for (const pid of VERIFY_PARTS) {
      const part = team.parts?.[pid];
      if (!part) continue;
      const claimedAfter = part.after as number | undefined;
      const verifiedCount = verified[pid];
      if (verifiedCount == null) continue;
      const chk = flag(verifiedCount, claimedAfter);
      (rec.checks as Record<string, unknown>)[pid] = {
        verified: verifiedCount,
        claimed_after: claimedAfter,
        ...chk,
      };
      part.verified = {
        remaining: verifiedCount,
        claimed_after: claimedAfter,
        discrepancy: chk.discrepancy,
        flagged: chk.flagged,
        method: pid === 'untyped' ? (untypedMethod ?? 'typescript-diagnostics') : 'typescript-ast',
      };
      part.trust = 'verified';

      logDecision(runDir, {
        phase: 'verify',
        subject: { team: team.team as string, criterion: 'type-safety', metric: pid },
        decision: `verified_remaining: ${verifiedCount}${claimedAfter != null ? ` (claimed ${claimedAfter})` : ''}`,
        chosen: pid === 'untyped' ? (untypedMethod ?? 'typescript-diagnostics') : 'typescript-ast',
        why: chk.note,
        evidence: [`typesafety-trace.json#teams.${team.team}.parts.${pid}`, 'verification.json'],
        confidence: chk.flagged ? 'medium' : 'high',
        flagged: chk.flagged,
      });
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
