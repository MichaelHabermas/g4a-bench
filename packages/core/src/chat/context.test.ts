import { describe, expect, it } from 'vitest';
import { join } from 'node:path';
import { readFileSync } from 'node:fs';
import { findRepoRoot } from '../paths.js';
import { loadScorecardModel } from '../scorecard/index.js';
import { extractCoverageGaps } from './context.js';
import { runTsCounter } from '../verify/typesafety.js';
import { resolveTeamClonePath } from '../clones/index.js';

const RUN_DIR = join(
  findRepoRoot(),
  'g4a-benchmarks/g4a-c5-2/week-4/runs/20260527T182321Z-static-prototype',
);

describe('extractCoverageGaps', () => {
  it('reports no untyped gaps after harness verification', () => {
    const trace = JSON.parse(readFileSync(join(RUN_DIR, 'typesafety-trace.json'), 'utf8')) as Record<
      string,
      unknown
    >;
    const scorecard = loadScorecardModel(RUN_DIR);
    const gaps = extractCoverageGaps(trace, scorecard);
    const untyped = gaps.filter((g) => g.metric_id === 'untyped');
    expect(untyped.length).toBe(0);

    const teams = trace.teams as Array<{ parts: Record<string, { verified?: unknown }> }>;
    for (const team of teams) {
      expect(team.parts.untyped?.verified).toBeTruthy();
    }
  });
});

describe('runTsCounter', () => {
  it('returns untyped_params when a team clone exists', () => {
    const root = findRepoRoot();
    const clone = resolveTeamClonePath(
      'g4a-c5-2',
      4,
      '20260527T182321Z-static-prototype',
      'github-com-michaelhabermas-ship-shape',
      root,
    );
    if (!clone) {
      expect(clone).toBeTruthy();
      return;
    }
    const result = runTsCounter(clone, root);
    const counts = result.counts as Record<string, number>;
    expect(typeof counts.untyped_params).toBe('number');
    expect(counts.untyped_params).toBeGreaterThanOrEqual(0);
  });
});
