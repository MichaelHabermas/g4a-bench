import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { cloneRoot, findRepoRoot, challengerReposDir } from '../paths.js';
import { readJsonIfExists, writeJson } from '../fs.js';
import { logDecision } from '../decisions/index.js';

export interface RepoSpec {
  team: string;
  url: string;
}

export interface ClonePlanEntry {
  team: string;
  url: string;
  commitSha?: string | null;
  destPath: string;
  warnings?: string[];
}

export interface ClonePlan {
  cohort: string;
  week: number;
  runId: string;
  runDir: string;
  cloneBase: string;
  entries: ClonePlanEntry[];
  warnings: string[];
}

export interface CloneManifestEntry {
  team: string;
  url: string;
  sha: string | null;
  path: string;
  status: 'cloned' | 'skipped_existing' | 'failed' | 'checkout_failed';
  error?: string;
}

export interface CloneManifest {
  cloned_at: string;
  cohort: string;
  week: number;
  runId: string;
  clone_base: string;
  entries: CloneManifestEntry[];
}

/** Same slug rules as g4a-harness/prototype_week4.py slugify(). */
export function slugify(value: string): string {
  let cleaned = value.trim().replace(/^https?:\/\//i, '');
  cleaned = cleaned.replace(/\.git$/i, '');
  cleaned = cleaned.replace(/[^A-Za-z0-9]+/g, '-').replace(/^-+|-+$/g, '').toLowerCase();
  return cleaned || 'unknown-team';
}

export function reposMdPath(cohort: string, week: number, root = findRepoRoot()): string {
  return join(challengerReposDir(root), cohort, `week-${week}`, 'REPOS.md');
}

export function parseReposMd(cohort: string, week: number, root = findRepoRoot()): RepoSpec[] {
  const path = reposMdPath(cohort, week, root);
  if (!existsSync(path)) {
    throw new Error(`REPOS.md not found: ${path}`);
  }
  const text = readFileSync(path, 'utf8');
  const repos: RepoSpec[] = [];
  const urlRe = /https?:\/\/[^>\s|]+/g;

  for (const line of text.split('\n')) {
    const urls = line.match(urlRe);
    if (!urls?.length) continue;
    const cells = line
      .trim()
      .replace(/^\|/, '')
      .replace(/\|$/, '')
      .split('|')
      .map((c) => c.trim());
    const url = urls[0]!;
    let team = '';
    if (cells.length >= 2 && !/^https?:\/\//i.test(cells[0]!) && cells[0] !== '-') {
      team = slugify(cells[0]!);
    }
    if (!team) team = slugify(url);
    repos.push({ team, url });
  }
  return repos;
}

export function resolveRunCloneDir(
  cohort: string,
  week: number,
  runId: string,
  root = findRepoRoot(),
): string {
  return join(cloneRoot(root), cohort, `week-${week}`, runId);
}

export function legacyPrototypeRunCloneDir(
  cohort: string,
  week: number,
  runId: string,
): string {
  return join('/private/tmp/g4a-bench-prototype', cohort, `week-${week}`, runId);
}

/** First existing run-level clone dir (local preferred, then legacy prototype). */
export function resolveExistingRunCloneDir(
  cohort: string,
  week: number,
  runId: string,
  root = findRepoRoot(),
): string | null {
  const local = resolveRunCloneDir(cohort, week, runId, root);
  if (existsSync(local)) return local;
  const legacy = legacyPrototypeRunCloneDir(cohort, week, runId);
  if (existsSync(legacy)) return legacy;
  return null;
}

export function resolveTeamClonePath(
  cohort: string,
  week: number,
  runId: string,
  team: string,
  root = findRepoRoot(),
): string | null {
  const local = join(resolveRunCloneDir(cohort, week, runId, root), team);
  if (existsSync(local)) return local;
  const legacy = join(legacyPrototypeRunCloneDir(cohort, week, runId), team);
  if (existsSync(legacy)) return legacy;
  return null;
}

export function buildClonePlan(
  runDir: string,
  cohort: string,
  week: number,
  runId: string,
  root = findRepoRoot(),
): ClonePlan {
  const repos = parseReposMd(cohort, week, root);
  const trace = readJsonIfExists<Record<string, unknown>>(join(runDir, 'typesafety-trace.json'));
  const traceTeams = (trace?.teams as Array<Record<string, unknown>>) ?? [];
  const byUrl = new Map<string, { team: string; commitSha?: string | null }>();

  for (const t of traceTeams) {
    const url = t.repo_url as string | undefined;
    if (url) {
      byUrl.set(url.replace(/\.git$/i, '').toLowerCase(), {
        team: t.team as string,
        commitSha: (t.commit_sha as string) ?? null,
      });
    }
  }

  const cloneBase = resolveRunCloneDir(cohort, week, runId, root);
  const warnings: string[] = [];
  const entries: ClonePlanEntry[] = [];

  for (const repo of repos) {
    const normUrl = repo.url.replace(/\.git$/i, '').toLowerCase();
    const fromTrace = byUrl.get(normUrl);
    const entryWarnings: string[] = [];
    let team = repo.team;
    let commitSha: string | null = null;

    if (fromTrace) {
      team = fromTrace.team;
      commitSha = fromTrace.commitSha ?? null;
      if (fromTrace.team !== repo.team) {
        entryWarnings.push(
          `REPOS slug "${repo.team}" differs from trace team "${fromTrace.team}" — using trace id.`,
        );
      }
    } else if (traceTeams.length) {
      entryWarnings.push('No matching repo_url in typesafety-trace — using REPOS slug.');
    }

    entries.push({
      team,
      url: repo.url,
      commitSha,
      destPath: join(cloneBase, team),
      warnings: entryWarnings.length ? entryWarnings : undefined,
    });
    warnings.push(...entryWarnings);
  }

  if (traceTeams.length && entries.length !== traceTeams.length) {
    warnings.push(
      `REPOS.md has ${entries.length} repos but trace has ${traceTeams.length} teams.`,
    );
  }

  return { cohort, week, runId, runDir, cloneBase, entries, warnings };
}

function git(args: string[], cwd?: string): { ok: boolean; stdout: string; stderr: string } {
  const out = spawnSync('git', args, { encoding: 'utf8', cwd, maxBuffer: 8 * 1024 * 1024 });
  return {
    ok: out.status === 0,
    stdout: (out.stdout ?? '').trim(),
    stderr: (out.stderr ?? '').trim(),
  };
}

export function cloneTeamRepos(
  plan: ClonePlan,
  options: { install?: boolean } = {},
): CloneManifest {
  mkdirSync(plan.cloneBase, { recursive: true });
  const entries: CloneManifestEntry[] = [];

  for (const entry of plan.entries) {
    const parent = join(entry.destPath, '..');
    mkdirSync(parent, { recursive: true });

    if (existsSync(join(entry.destPath, '.git'))) {
      entries.push({
        team: entry.team,
        url: entry.url,
        sha: entry.commitSha ?? null,
        path: entry.destPath,
        status: 'skipped_existing',
      });
      continue;
    }

    const clone = spawnSync('git', ['clone', entry.url, entry.destPath], {
      encoding: 'utf8',
      maxBuffer: 8 * 1024 * 1024,
    });

    if (clone.status !== 0) {
      entries.push({
        team: entry.team,
        url: entry.url,
        sha: null,
        path: entry.destPath,
        status: 'failed',
        error: clone.stderr?.trim() || clone.stdout?.trim() || `exit ${clone.status}`,
      });
      continue;
    }

    let sha: string | null = entry.commitSha ?? null;
    if (entry.commitSha) {
      const co = git(['checkout', entry.commitSha], entry.destPath);
      if (!co.ok) {
        entries.push({
          team: entry.team,
          url: entry.url,
          sha: entry.commitSha ?? null,
          path: entry.destPath,
          status: 'checkout_failed',
          error: co.stderr || co.stdout,
        });
        continue;
      }
      sha = entry.commitSha;
    } else {
      const head = git(['rev-parse', 'HEAD'], entry.destPath);
      sha = head.ok ? head.stdout : null;
    }

    if (options.install && existsSync(join(entry.destPath, 'package.json'))) {
      const hasPnpm = existsSync(join(entry.destPath, 'pnpm-lock.yaml'));
      const cmd = hasPnpm ? 'pnpm' : 'npm';
      const args = hasPnpm
        ? ['install', '--ignore-scripts']
        : ['install', '--ignore-scripts', '--no-audit', '--no-fund'];
      spawnSync(cmd, args, { cwd: entry.destPath, encoding: 'utf8', stdio: 'ignore' });
    }

    entries.push({
      team: entry.team,
      url: entry.url,
      sha,
      path: entry.destPath,
      status: 'cloned',
    });
  }

  const manifest: CloneManifest = {
    cloned_at: new Date().toISOString(),
    cohort: plan.cohort,
    week: plan.week,
    runId: plan.runId,
    clone_base: plan.cloneBase,
    entries,
  };

  writeJson(join(plan.runDir, 'clone-manifest.json'), manifest);

  for (const e of entries) {
    logDecision(plan.runDir, {
      phase: 'clone',
      subject: { team: e.team },
      decision: `clone ${e.status}${e.sha ? ` @ ${e.sha.slice(0, 7)}` : ''}`,
      chosen: e.path,
      why: e.error ?? `Repository cloned to ${e.path}`,
      evidence: ['clone-manifest.json'],
      confidence: e.status === 'cloned' || e.status === 'skipped_existing' ? 'high' : 'low',
      flagged: e.status === 'failed' || e.status === 'checkout_failed',
    });
  }

  logDecision(plan.runDir, {
    phase: 'clone',
    subject: {},
    decision: `clone batch: ${entries.filter((e) => e.status === 'cloned' || e.status === 'skipped_existing').length}/${entries.length} teams ready`,
    why: `Clone base: ${plan.cloneBase}`,
    evidence: ['clone-manifest.json'],
    confidence: 'high',
  });

  return manifest;
}

export function loadCloneManifest(runDir: string): CloneManifest | null {
  return readJsonIfExists<CloneManifest>(join(runDir, 'clone-manifest.json'));
}

export function cloneAllForRun(
  runDir: string,
  cohort: string,
  week: number,
  runId: string,
  options: { install?: boolean } = {},
  root = findRepoRoot(),
): CloneManifest {
  const plan = buildClonePlan(runDir, cohort, week, runId, root);
  return cloneTeamRepos(plan, options);
}
