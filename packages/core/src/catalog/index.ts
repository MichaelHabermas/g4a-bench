import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  benchmarksDir,
  challengerReposDir,
  findRepoRoot,
  specsDir,
  listRuns,
} from '../paths.js';
import { readJsonIfExists } from '../fs.js';
import { parseReposMd } from '../clones/index.js';
import type { RunState } from '../schemas/index.js';

export interface CatalogRun {
  run_id: string;
  label: string;
  mode: string | null;
  started_at: string | null;
  updated_at: string | null;
  measurement_count: number;
  is_primary: boolean;
}

export interface CatalogWeek {
  week: number;
  title: string;
  spec_count: number;
  team_count: number;
  has_runs: boolean;
  primary_run_id: string | null;
  runs: CatalogRun[];
}

export interface CatalogCohort {
  id: string;
  label: string;
  weeks: CatalogWeek[];
}

export interface BenchmarkCatalog {
  cohorts: CatalogCohort[];
}

function readdirSafe(path: string): string[] {
  try {
    return readdirSync(path);
  } catch {
    return [];
  }
}

/** Turn `20260527T182321Z-static-prototype` into a readable label. */
export function humanizeRunId(runId: string): string {
  const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z?-(.+)$/i.exec(runId);
  if (!m) return runId;
  const [, y, mo, d, h, mi, s, suffix] = m;
  const when = new Date(Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi), Number(s)));
  const time = when.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  const kind = (suffix ?? '').replace(/-/g, ' ');
  return `${time} · ${kind}`;
}

function cohortLabel(id: string): string {
  const m = /^g4a-c(\d+)-(\d+)$/i.exec(id);
  if (m) return `G4A Cohort ${m[1]}-${m[2]}`;
  return id;
}

function weekTitleFromSpecs(cohort: string, week: number, root: string): string {
  const dir = join(specsDir(root), cohort, `week-${week}`);
  if (!existsSync(dir)) return `Week ${week}`;
  const files = readdirSafe(dir).filter((f) => /\.(txt|md)$/i.test(f));
  const preferred =
    files.find((f) => /week[- ]?\d/i.test(f) && !/surprise|followup|advisor/i.test(f)) ??
    files.find((f) => /GFA|Week/i.test(f)) ??
    files[0];
  if (!preferred) return `Week ${week}`;
  let name = preferred.replace(/\.(txt|md)$/i, '');
  name = name.replace(/^GFA[- ]?Week[- ]?\d+[- ]?/i, '');
  name = name.replace(/^Week[- ]?\d+[- ]?/i, '');
  name = name.replace(/[-_]+/g, ' ').trim();
  if (name.length > 48) name = `${name.slice(0, 45)}…`;
  return name || `Week ${week}`;
}

function loadRunMeta(runPath: string): {
  mode: string | null;
  started_at: string | null;
  updated_at: string | null;
  measurement_count: number;
} {
  const runJson = readJsonIfExists<{
    mode?: string;
    started_at?: string;
  }>(join(runPath, 'run.json'));
  const state = readJsonIfExists<RunState>(join(runPath, 'run-state.json'));
  const measurements = state?.agent_measurements ?? {};
  return {
    mode: runJson?.mode ?? null,
    started_at: runJson?.started_at ?? null,
    updated_at: state?.updated_at ?? runJson?.started_at ?? null,
    measurement_count: Object.keys(measurements).length,
  };
}

function pickPrimaryRunId(runs: CatalogRun[]): string | null {
  if (!runs.length) return null;
  const sorted = [...runs].sort((a, b) => {
    const ta = a.updated_at ?? a.started_at ?? '';
    const tb = b.updated_at ?? b.started_at ?? '';
    return tb.localeCompare(ta) || b.run_id.localeCompare(a.run_id);
  });
  return sorted[0]?.run_id ?? null;
}

export function listBenchmarkCatalog(root = findRepoRoot()): BenchmarkCatalog {
  const specRoot = specsDir(root);
  const benchRoot = benchmarksDir(root);
  const allRuns = listRuns(root);
  const runsByWeek = new Map<string, typeof allRuns>();
  for (const r of allRuns) {
    const key = `${r.cohort}:${r.week}`;
    const list = runsByWeek.get(key) ?? [];
    list.push(r);
    runsByWeek.set(key, list);
  }

  const cohortIds = new Set<string>();
  for (const c of readdirSafe(specRoot)) {
    if (existsSync(join(specRoot, c))) cohortIds.add(c);
  }
  for (const c of readdirSafe(benchRoot)) {
    if (existsSync(join(benchRoot, c))) cohortIds.add(c);
  }

  const cohorts: CatalogCohort[] = [...cohortIds].sort().map((id) => {
    const weekNums = new Set<number>();
    const specCohort = join(specRoot, id);
    for (const d of readdirSafe(specCohort)) {
      const m = /^week-(\d+)$/.exec(d);
      if (m) weekNums.add(Number(m[1]));
    }
    const benchCohort = join(benchRoot, id);
    for (const d of readdirSafe(benchCohort)) {
      const m = /^week-(\d+)$/.exec(d);
      if (m) weekNums.add(Number(m[1]));
    }

    let teamCountDefault = 0;

    const weeks: CatalogWeek[] = [...weekNums]
      .sort((a, b) => a - b)
      .map((week) => {
        const title = weekTitleFromSpecs(id, week, root);
        const specDir = join(specRoot, id, `week-${week}`);
        const spec_count = existsSync(specDir)
          ? readdirSafe(specDir).filter((f) => /\.(txt|md|pdf)$/i.test(f)).length
          : 0;

        let team_count = 0;
        const reposPath = join(challengerReposDir(root), id, `week-${week}`, 'REPOS.md');
        if (existsSync(reposPath)) {
          try {
            team_count = parseReposMd(id, week, root).length;
          } catch {
            /* keep 0 */
          }
        }

        const weekRuns = runsByWeek.get(`${id}:${week}`) ?? [];
        const catalogRuns: CatalogRun[] = weekRuns.map((r) => {
          const meta = loadRunMeta(r.path);
          return {
            run_id: r.runId,
            label: humanizeRunId(r.runId),
            mode: meta.mode,
            started_at: meta.started_at,
            updated_at: meta.updated_at,
            measurement_count: meta.measurement_count,
            is_primary: false,
          };
        });

        const primary_run_id = pickPrimaryRunId(catalogRuns);
        for (const run of catalogRuns) {
          run.is_primary = run.run_id === primary_run_id;
        }

        return {
          week,
          title,
          spec_count,
          team_count,
          has_runs: catalogRuns.length > 0,
          primary_run_id,
          runs: catalogRuns.sort((a, b) => b.run_id.localeCompare(a.run_id)),
        };
      });

    return { id, label: cohortLabel(id), weeks };
  });

  return { cohorts };
}
