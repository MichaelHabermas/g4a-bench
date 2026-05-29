import { describe, expect, it } from 'vitest';
import { join } from 'node:path';
import { readFileSync } from 'node:fs';
import { findRepoRoot } from '../paths.js';
import { loadScorecardModel } from '../scorecard/index.js';
import { extractCoverageGaps } from './context.js';

const RUN_DIR = join(
  findRepoRoot(),
  'g4a-benchmarks/g4a-c5-2/week-4/runs/20260527T182321Z-static-prototype',
);

describe('extractCoverageGaps', () => {
  it('flags untyped params gaps for all three Week 4 teams', () => {
    const trace = JSON.parse(readFileSync(join(RUN_DIR, 'typesafety-trace.json'), 'utf8')) as Record<
      string,
      unknown
    >;
    const scorecard = loadScorecardModel(RUN_DIR);
    const gaps = extractCoverageGaps(trace, scorecard);

    const untyped = gaps.filter((g) => g.metric_id === 'untyped');
    expect(untyped.length).toBeGreaterThanOrEqual(3);

    const notClaimed = untyped.filter((g) => g.issue === 'not_claimed');
    expect(notClaimed.length).toBe(2);

    const zeroUnverified = untyped.filter((g) => g.issue === 'zero_change_unverified');
    expect(zeroUnverified.length).toBe(1);
    expect(zeroUnverified[0]?.team).toContain('dalton');
  });
});
