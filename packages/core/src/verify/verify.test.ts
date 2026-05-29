import { describe, expect, it } from 'vitest';
import { join } from 'node:path';
import { readFileSync } from 'node:fs';
import { findRepoRoot } from '../paths.js';
import { syncAndIndexRun } from '../registry/index.js';
import { resolveExistingRunCloneDir } from '../clones/index.js';

const RUN_DIR = join(
  findRepoRoot(),
  'g4a-benchmarks/g4a-c5-2/week-4/runs/20260527T182321Z-static-prototype',
);

describe('verify integration', () => {
  it('sync verifies untyped params when clones exist', () => {
    const root = findRepoRoot();
    const cloneBase = resolveExistingRunCloneDir(
      'g4a-c5-2',
      4,
      '20260527T182321Z-static-prototype',
      root,
    );
    if (!cloneBase) {
      expect(cloneBase).toBeTruthy();
      return;
    }

    const result = syncAndIndexRun({
      runDir: RUN_DIR,
      cohort: 'g4a-c5-2',
      week: 4,
    });
    expect(result.typesafety_verify).toBe(true);

    const trace = JSON.parse(readFileSync(join(RUN_DIR, 'typesafety-trace.json'), 'utf8')) as {
      teams: Array<{ team: string; parts: Record<string, { verified?: { remaining: number } }> }>;
    };
    for (const team of trace.teams) {
      expect(team.parts.untyped?.verified?.remaining).toBeTypeOf('number');
    }
  });
});
