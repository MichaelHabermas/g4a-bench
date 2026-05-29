import { existsSync, readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const packageDir = dirname(fileURLToPath(import.meta.url));

/** Walk up from packages/core to repo root (contains g4a-benchmarks). */
export function findRepoRoot(start = join(packageDir, '../..')): string {
  const envRoot = process.env.YARDSTICK_REPO_ROOT;
  if (envRoot) {
    const abs = resolve(envRoot);
    if (existsSync(join(abs, 'g4a-benchmarks'))) return abs;
  }
  let dir = resolve(start);
  for (let i = 0; i < 8; i++) {
    if (existsSync(join(dir, 'g4a-benchmarks')) && existsSync(join(dir, 'g4a-specs'))) {
      return dir;
    }
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  throw new Error('Could not find repo root (expected g4a-benchmarks/ and g4a-specs/)');
}

export function benchmarksDir(root = findRepoRoot()): string {
  return join(root, 'g4a-benchmarks');
}

export function specsDir(root = findRepoRoot()): string {
  return join(root, 'g4a-specs');
}

export function challengerReposDir(root = findRepoRoot()): string {
  return join(root, 'g4a-challenger-repos');
}

export function harnessDir(root = findRepoRoot()): string {
  return join(root, 'g4a-harness');
}

export function cloneRoot(root = findRepoRoot()): string {
  const base = process.env.YARDSTICK_CLONE_ROOT ?? join(root, '.yardstick', 'clones');
  return resolve(base);
}

export function runDir(cohort: string, week: number, runId: string, root = findRepoRoot()): string {
  return join(benchmarksDir(root), cohort, `week-${week}`, 'runs', runId);
}

export function weekBaselineConfigPath(cohort: string, week: number, root = findRepoRoot()): string {
  return join(specsDir(root), cohort, `week-${week}`, 'baseline.json');
}

export function listRuns(root = findRepoRoot()): Array<{ cohort: string; week: number; runId: string; path: string }> {
  const base = benchmarksDir(root);
  const runs: Array<{ cohort: string; week: number; runId: string; path: string }> = [];
  if (!existsSync(base)) return runs;

  for (const cohort of readdirSafe(base)) {
    const cohortPath = join(base, cohort);
    for (const weekDir of readdirSafe(cohortPath)) {
      const m = /^week-(\d+)$/.exec(weekDir);
      if (!m) continue;
      const week = Number(m[1]);
      const runsPath = join(cohortPath, weekDir, 'runs');
      if (!existsSync(runsPath)) continue;
      for (const runId of readdirSafe(runsPath)) {
        const path = join(runsPath, runId);
        if (existsSync(join(path, 'run.json')) || existsSync(join(path, 'run-state.json'))) {
          runs.push({ cohort, week, runId, path });
        }
      }
    }
  }
  return runs.sort((a, b) => a.runId.localeCompare(b.runId));
}

function readdirSafe(path: string): string[] {
  try {
    return readdirSync(path);
  } catch {
    return [];
  }
}
