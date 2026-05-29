import { describe, expect, it } from 'vitest';
import { humanizeRunId, listBenchmarkCatalog } from './index.js';
import { findRepoRoot } from '../paths.js';

describe('catalog', () => {
  it('humanizes prototype run ids', () => {
    const label = humanizeRunId('20260527T182321Z-static-prototype');
    expect(label).toContain('static prototype');
    expect(label).toMatch(/2026/);
  });

  it('lists cohorts and week 4 ShipShape title', () => {
    const catalog = listBenchmarkCatalog(findRepoRoot());
    const c52 = catalog.cohorts.find((c) => c.id === 'g4a-c5-2');
    expect(c52).toBeDefined();
    const w4 = c52!.weeks.find((w) => w.week === 4);
    expect(w4?.title.toLowerCase()).toContain('ship');
    expect(w4?.has_runs).toBe(true);
    expect(w4?.primary_run_id).toBeTruthy();
  });
});
