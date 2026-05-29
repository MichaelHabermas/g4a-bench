import { describe, expect, it } from 'vitest';
import { join } from 'node:path';
import { findRepoRoot } from '../paths.js';
import {
  parseReposMd,
  slugify,
  resolveRunCloneDir,
  buildClonePlan,
} from './index.js';

describe('clones', () => {
  it('slugify matches Week 4 trace team ids', () => {
    expect(slugify('https://github.com/MichaelHabermas/ship-shape')).toBe(
      'github-com-michaelhabermas-ship-shape',
    );
    expect(slugify('https://labs.gauntletai.com/daltondinderman/shipshape')).toBe(
      'labs-gauntletai-com-daltondinderman-shipshape',
    );
  });

  it('parseReposMd yields 3 Week 4 repos', () => {
    const repos = parseReposMd('g4a-c5-2', 4);
    expect(repos).toHaveLength(3);
    expect(repos.map((r) => r.team)).toContain('github-com-michaelhabermas-ship-shape');
  });

  it('resolveRunCloneDir has expected shape', () => {
    const p = resolveRunCloneDir('g4a-c5-2', 4, '20260527T182321Z-static-prototype');
    expect(p).toMatch(/g4a-c5-2\/week-4\/20260527T182321Z-static-prototype$/);
  });

  it('buildClonePlan merges trace team ids and commit shas', () => {
    const root = findRepoRoot();
    const runDir = join(
      root,
      'g4a-benchmarks/g4a-c5-2/week-4/runs/20260527T182321Z-static-prototype',
    );
    const plan = buildClonePlan(runDir, 'g4a-c5-2', 4, '20260527T182321Z-static-prototype', root);
    expect(plan.entries).toHaveLength(3);
    const michael = plan.entries.find((e) => e.team.includes('michaelhabermas'));
    expect(michael?.commitSha).toBeTruthy();
    expect(michael?.destPath).toContain('github-com-michaelhabermas-ship-shape');
  });
});
