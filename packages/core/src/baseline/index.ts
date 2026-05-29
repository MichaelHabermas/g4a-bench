import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { BaselineConfigSchema, type BaselineConfig } from '../schemas/index.js';
import { readJson, readJsonIfExists, writeJson } from '../fs.js';
import { weekBaselineConfigPath } from '../paths.js';

export function loadBaselineConfig(cohort: string, week: number, root?: string): BaselineConfig | null {
  const path = weekBaselineConfigPath(cohort, week, root);
  const raw = readJsonIfExists<unknown>(path);
  if (!raw) return null;
  return BaselineConfigSchema.parse(raw);
}

export function resolveFirstCommitSha(repoPath: string): string | null {
  const out = spawnSync('git', ['rev-list', '--max-parents=0', 'HEAD'], {
    cwd: repoPath,
    encoding: 'utf8',
  });
  if (out.status !== 0 || !out.stdout.trim()) return null;
  return out.stdout.trim().split('\n')[0] ?? null;
}

export function cloneUpstreamBaseline(
  config: BaselineConfig,
  destDir: string,
): { path: string; sha: string | null } {
  mkdirSync(destDir, { recursive: true });
  if (!existsSync(join(destDir, '.git'))) {
    const clone = spawnSync('git', ['clone', '--depth', '1', config.upstream_repo_url, destDir], {
      encoding: 'utf8',
    });
    if (clone.status !== 0) {
      throw new Error(clone.stderr || 'git clone failed');
    }
  }
  const sha = resolveFirstCommitSha(destDir);
  return { path: destDir, sha };
}

export interface BaselineCacheFile {
  cohort: string;
  week: number;
  upstream_repo_url: string;
  first_commit_sha: string | null;
  cached_at: string;
  note?: string;
}

export function writeBaselineCache(
  cachePath: string,
  data: BaselineCacheFile,
): void {
  writeJson(cachePath, data);
}

export function readBaselineCache(cachePath: string): BaselineCacheFile | null {
  return readJsonIfExists<BaselineCacheFile>(cachePath);
}
