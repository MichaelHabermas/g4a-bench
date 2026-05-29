import { describe, expect, it } from 'vitest';
import { join } from 'node:path';
import { findRepoRoot } from '../paths.js';
import { loadAgentMeasurements, latestByTeamCriterion, syncAll } from '../sync/index.js';
import { loadScorecardModel } from '../scorecard/index.js';

const RUN_DIR = join(
  findRepoRoot(),
  'g4a-benchmarks/g4a-c5-2/week-4/runs/20260527T182321Z-static-prototype',
);

describe('sync', () => {
  it('loads agent measurements with inferred criterion ids', () => {
    const ms = loadAgentMeasurements(RUN_DIR);
    expect(ms.length).toBeGreaterThan(0);
    const latest = latestByTeamCriterion(ms);
    expect(latest.has('cat-2-bundle:github-com-michaelhabermas-ship-shape')).toBe(true);
  });

  it('sync produces run-state with measurements', () => {
    syncAll({ runDir: RUN_DIR });
    const ms = loadAgentMeasurements(RUN_DIR);
    const latest = latestByTeamCriterion(ms);
    expect(latest.size).toBeGreaterThanOrEqual(5);
  });
});

describe('scorecard model', () => {
  it('loads criteria from traces', () => {
    const model = loadScorecardModel(RUN_DIR);
    expect(model.criteria.length).toBeGreaterThanOrEqual(2);
    expect(model.team_ids.length).toBe(3);
  });

  it('flags shiv as verified with high as count when verification present', () => {
    const model = loadScorecardModel(RUN_DIR);
    const ts = model.criteria.find((c) => c.id === 'type-safety');
    expect(ts?.verified_kind).toBe(true);
    const shiv = ts?.teams['labs-gauntletai-com-shivkanthalu-ship'];
    const total = shiv?.cells.total;
    expect(total?.kind).toBe('reduction');
    if (total?.kind === 'reduction' && total.verified) {
      expect(total.remaining).toBeGreaterThan(100);
    }
  });
});
