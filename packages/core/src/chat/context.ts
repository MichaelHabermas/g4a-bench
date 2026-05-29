import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { findRepoRoot } from '../paths.js';
import { resolveTeamClonePath as resolveTeamClonePathFromClones } from '../clones/index.js';
import { readJsonIfExists } from '../fs.js';
import {
  readDecisionLog,
  filterDecisions,
  buildDecisionDigest,
  getDecisionById,
  decisionSummaryByPhase,
} from '../decisions/index.js';
import type { ScorecardModel } from '../scorecard/index.js';

export interface CoverageGap {
  category: string;
  metric_id: string;
  metric_label: string;
  team: string;
  issue: 'missing' | 'unverified' | 'not_claimed' | 'zero_change_unverified' | 'not_in_harness_scope';
  detail: string;
  trace_excerpt?: Record<string, unknown>;
}

export interface CodeMatch {
  file: string;
  line: number;
  text: string;
}

export interface DevCodeBundle {
  enabled: boolean;
  clone_paths: Record<string, string | null>;
  focus?: { metric_id?: string; team?: string; label?: string };
  coverage_gaps: CoverageGap[];
  searches: Array<{ team: string; label: string; pattern: string; matches: CodeMatch[] }>;
  file_snippets: Array<{ team: string; path: string; excerpt: string }>;
  note: string;
}

export function isDevChatMode(): boolean {
  const v = (process.env.YARDSTICK_DEV_MODE ?? process.env.CHAT_INCLUDE_CODE ?? '').toLowerCase();
  return v === '1' || v === 'true' || v === 'yes';
}

export function resolveTeamClonePath(
  cohort: string,
  week: number,
  runId: string,
  team: string,
  root = findRepoRoot(),
): string | null {
  return resolveTeamClonePathFromClones(cohort, week, runId, team, root);
}

// re-export not duplicated at package root — use clones module

export function extractCoverageGaps(
  typesafetyTrace: Record<string, unknown> | null,
  scorecard: ScorecardModel | null,
): CoverageGap[] {
  const gaps: CoverageGap[] = [];

  if (typesafetyTrace?.teams) {
    const partDefs = (typesafetyTrace.part_defs as Array<{ id: string; label: string }>) ?? [];
    const labelById = Object.fromEntries(partDefs.map((p) => [p.id, p.label]));

    for (const team of typesafetyTrace.teams as Array<Record<string, unknown>>) {
      const teamId = team.team as string;
      const parts = team.parts as Record<string, Record<string, unknown>> | undefined;
      if (!parts) continue;

      for (const [metricId, part] of Object.entries(parts)) {
        const label = labelById[metricId] ?? metricId;
        const verified = part.verified as Record<string, unknown> | undefined;
        const trust = part.trust as string | undefined;
        const value = part.value;
        const before = part.before as number | undefined;
        const after = part.after as number | undefined;
        const reduction = part.reduction_percent as number | null | undefined;
        const judgment = part.judgment as string | undefined;

        if (metricId === 'untyped') {
          if (part.verified) {
            /* harness measured — no coverage gap */
          } else if (value == null && before == null && after == null) {
            gaps.push({
              category: 'Type Safety',
              metric_id: metricId,
              metric_label: label,
              team: teamId,
              issue: judgment === 'not_claimed' ? 'not_claimed' : 'missing',
              detail:
                'No untyped-params count in trace and harness has not verified yet. Run clone + sync to measure via TypeScript diagnostics.',
              trace_excerpt: part,
            });
          } else if (!verified && before != null && after != null && reduction === 0) {
            gaps.push({
              category: 'Type Safety',
              metric_id: metricId,
              metric_label: label,
              team: teamId,
              issue: 'zero_change_unverified',
              detail: `Team artifact shows ${before} -> ${after} (0% change), not harness-verified. May mean metric not addressed or counter not run.`,
              trace_excerpt: part,
            });
          } else if (!verified && (before != null || after != null)) {
            gaps.push({
              category: 'Type Safety',
              metric_id: metricId,
              metric_label: label,
              team: teamId,
              issue: 'unverified',
              detail: 'Self-reported or artifact-backed only; harness has not independently counted untyped params.',
              trace_excerpt: part,
            });
          }
        }

        if (verified == null && trust !== 'verified' && metricId !== 'strict' && metricId !== 'untyped') {
          if (before == null && after == null && value == null) {
            gaps.push({
              category: 'Type Safety',
              metric_id: metricId,
              metric_label: label,
              team: teamId,
              issue: 'missing',
              detail: 'No before/after or remaining value recorded for this sub-metric.',
              trace_excerpt: part,
            });
          }
        }
      }
    }
  }

  if (scorecard) {
    for (const crit of scorecard.criteria) {
      for (const [teamId, tdata] of Object.entries(crit.teams)) {
        for (const [pid, cell] of Object.entries(tdata.cells)) {
          if (cell.kind === 'reduction' && cell.display === 'n/a' && !cell.verified) {
            const exists = gaps.some((g) => g.team === teamId && g.metric_id === pid);
            if (!exists) {
              gaps.push({
                category: crit.name,
                metric_id: pid,
                metric_label: crit.parts.find((p) => p.id === pid)?.label ?? pid,
                team: teamId,
                issue: 'missing',
                detail: 'Scorecard shows n/a — no comparable value at current trust tier.',
              });
            }
          }
        }
      }
    }
  }

  return gaps;
}

function rgSearch(repoPath: string, pattern: string, max = 12): CodeMatch[] {
  if (!existsSync(repoPath)) return [];
  const out = spawnSync(
    'rg',
    ['--line-number', '--max-count', String(max), '--ignore-case', pattern, repoPath],
    { encoding: 'utf8', maxBuffer: 512 * 1024 },
  );
  if (out.status !== 0 && !out.stdout) return [];
  return out.stdout
    .split('\n')
    .filter(Boolean)
    .slice(0, max)
    .map((line) => {
      const m = /^(.+?):(\d+):(.*)$/.exec(line);
      if (!m) return null;
      return { file: m[1]!, line: Number(m[2]), text: m[3]!.trim() };
    })
    .filter(Boolean) as CodeMatch[];
}

function readSnippet(repoPath: string, relPath: string, maxChars = 4000): string | null {
  const full = join(repoPath, relPath);
  if (!existsSync(full)) return null;
  try {
    return readFileSync(full, 'utf8').slice(0, maxChars);
  } catch {
    return null;
  }
}

function findFilesByName(repoPath: string, needle: string, max = 8): string[] {
  const hits: string[] = [];
  function walk(dir: string, depth: number) {
    if (depth > 6 || hits.length >= max) return;
    let entries: string[];
    try {
      entries = readdirSync(dir);
    } catch {
      return;
    }
    for (const name of entries) {
      if (name === 'node_modules' || name === '.git' || name === 'dist') continue;
      const p = join(dir, name);
      let st;
      try {
        st = statSync(p);
      } catch {
        continue;
      }
      if (st.isDirectory()) walk(p, depth + 1);
      else if (name.toLowerCase().includes(needle.toLowerCase())) {
        hits.push(p.slice(repoPath.length + 1));
      }
    }
  }
  walk(repoPath, 0);
  return hits;
}

const UNTYPED_SEARCH_PATTERNS: Array<{ label: string; pattern: string }> = [
  { label: 'untyped in scripts/docs', pattern: 'untyped' },
  { label: 'noImplicitAny tsconfig', pattern: 'noImplicitAny' },
  { label: 'type-safety count scripts', pattern: 'type-safety|typesafety' },
  { label: 'explicit-any eslint', pattern: 'no-explicit-any|explicit.any' },
];

export function gatherDevCodeContext(input: {
  cohort: string;
  week: number;
  runId: string;
  teams: string[];
  focus?: { metric_id?: string; team?: string; label?: string };
  coverageGaps?: CoverageGap[];
}): DevCodeBundle {
  if (!isDevChatMode()) {
    return {
      enabled: false,
      clone_paths: {},
      coverage_gaps: input.coverageGaps ?? [],
      searches: [],
      file_snippets: [],
      note: 'Dev code access disabled. Set YARDSTICK_DEV_MODE=true to include clone source in chat context.',
    };
  }

  const root = findRepoRoot();
  const clone_paths: Record<string, string | null> = {};
  const searches: DevCodeBundle['searches'] = [];
  const file_snippets: DevCodeBundle['file_snippets'] = [];

  const focusMetric = input.focus?.metric_id ?? 'untyped';
  const teams =
    input.focus?.team != null ? [input.focus.team] : input.teams.length ? input.teams : [];

  for (const team of teams) {
    const repo = resolveTeamClonePath(input.cohort, input.week, input.runId, team, root);
    clone_paths[team] = repo;
    if (!repo) continue;

    const patterns =
      focusMetric === 'untyped'
        ? UNTYPED_SEARCH_PATTERNS
        : [{ label: `focus:${focusMetric}`, pattern: focusMetric }];

    for (const { label, pattern } of patterns) {
      const matches = rgSearch(repo, pattern, 8);
      if (matches.length) searches.push({ team, label, pattern, matches });
    }

    const scriptHits = findFilesByName(repo, 'type-safety');
    const scriptHits2 = findFilesByName(repo, 'typesafety');
    for (const rel of [...new Set([...scriptHits, ...scriptHits2])].slice(0, 3)) {
      const excerpt = readSnippet(repo, rel);
      if (excerpt) file_snippets.push({ team, path: rel, excerpt });
    }

    for (const rel of ['tsconfig.json', 'api/tsconfig.json', 'web/tsconfig.json', 'shared/tsconfig.json']) {
      const excerpt = readSnippet(repo, rel, 2000);
      if (excerpt) file_snippets.push({ team, path: rel, excerpt });
    }
  }

  return {
    enabled: true,
    clone_paths,
    focus: input.focus,
    coverage_gaps: input.coverageGaps ?? [],
    searches,
    file_snippets: file_snippets.slice(0, 12),
    note: 'DEV MODE: clone source snippets included. Use to explain missing metrics, find team counting scripts, and propose harness yardstick improvements. Do not treat unverified team markdown as ground truth.',
  };
}

export function buildEnrichedChatContext(input: {
  cohort: string;
  week: number;
  runId: string;
  runDir: string;
  runState: unknown;
  yardsticks: unknown;
  verification: unknown;
  typesafetyTrace: Record<string, unknown> | null;
  bundleTrace: unknown;
  measurementsIndex: unknown;
  scorecard: ScorecardModel | null;
  uiContext?: Record<string, unknown>;
}): Record<string, unknown> {
  const coverage_gaps = extractCoverageGaps(input.typesafetyTrace, input.scorecard);
  const teams = input.scorecard?.team_ids ?? [];

  const focus =
    input.uiContext?.focus && typeof input.uiContext.focus === 'object'
      ? (input.uiContext.focus as { metric_id?: string; team?: string; label?: string })
      : undefined;

  const dev_code = gatherDevCodeContext({
    cohort: input.cohort,
    week: input.week,
    runId: input.runId,
    teams,
    focus,
    coverageGaps: coverage_gaps,
  });

  const spec_excerpt = input.typesafetyTrace?.spec_excerpt ?? null;

  const allDecisions = readDecisionLog(input.runDir);
  const focusDecisionId =
    input.uiContext?.focus && typeof input.uiContext.focus === 'object'
      ? (input.uiContext.focus as { decision_id?: string }).decision_id
      : undefined;
  const focusDecision = focusDecisionId ? getDecisionById(input.runDir, focusDecisionId) : null;
  const decision_trail = {
    total: allDecisions.length,
    by_phase: decisionSummaryByPhase(allDecisions),
    focus: focusDecision,
    recent_digest: buildDecisionDigest(
      filterDecisions(allDecisions, {
        team: focus?.team,
        limit: 50,
      }),
    ),
  };

  return {
    run: { cohort: input.cohort, week: input.week, runId: input.runId, path: input.runDir },
    run_state: input.runState,
    yardsticks: input.yardsticks,
    verification: input.verification,
    typesafety_trace: input.typesafetyTrace,
    bundle_trace: input.bundleTrace,
    measurements_index: input.measurementsIndex,
    spec_excerpt,
    coverage_gaps,
    dev_code,
    decision_trail,
    ui: input.uiContext ?? {},
    chat_mode: isDevChatMode() ? 'dev_with_code' : 'artifacts_only',
  };
}
