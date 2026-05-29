import { existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { findRepoRoot, specsDir } from '../paths.js';
import { writeJson } from '../fs.js';
import { parseReposMd } from '../clones/index.js';
import { logDecision } from '../decisions/index.js';

export interface OrchestratorStep {
  id: string;
  phase: 'clone' | 'verify' | 'agent' | 'sync' | 'baseline';
  team?: string;
  criterion_id: string;
  label: string;
  status: 'pending' | 'would_run' | 'skipped' | 'done';
  note?: string;
}

export interface RunPlan {
  cohort: string;
  week: number;
  runId: string;
  runDir: string;
  teams: Array<{ team: string; url: string }>;
  criteria: Array<{ id: string; label: string; kind: 'deterministic' | 'agent' }>;
  steps: OrchestratorStep[];
  dry_run: boolean;
}

const WEEK4_CRITERIA: RunPlan['criteria'] = [
  { id: 'type-safety-verify', label: 'Type safety (harness verify)', kind: 'deterministic' },
  { id: 'cat-1-typesafety-gate', label: 'Type safety qualitative gate', kind: 'agent' },
  { id: 'cat-2-bundle', label: 'Bundle size', kind: 'agent' },
  { id: 'cat-3-api-perf', label: 'API response time', kind: 'agent' },
  { id: 'cat-4-db', label: 'Database performance', kind: 'agent' },
  { id: 'cat-5-lighthouse', label: 'Lighthouse', kind: 'agent' },
  { id: 'cat-6-a11y', label: 'Accessibility', kind: 'agent' },
  { id: 'cat-7-deps', label: 'Dependency audit', kind: 'agent' },
  { id: 'cat-8-security', label: 'Security probe', kind: 'agent' },
];

function listSpecFiles(cohort: string, week: number, root: string): string[] {
  const dir = join(specsDir(root), cohort, `week-${week}`);
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((f) => /\.(txt|md)$/i.test(f))
    .map((f) => join(dir, f));
}

export function buildWeek4RunPlan(
  runDir: string,
  cohort: string,
  week: number,
  runId: string,
  options: { dryRun?: boolean } = {},
  root = findRepoRoot(),
): RunPlan {
  const teams = parseReposMd(cohort, week, root).map((r) => ({ team: r.team, url: r.url }));
  const steps: OrchestratorStep[] = [];

  steps.push({
    id: 'clone-all',
    phase: 'clone',
    criterion_id: '_infra',
    label: 'Clone all team repos (pinned SHA when in trace)',
    status: options.dryRun ? 'would_run' : 'pending',
    note: 'Use Clone teams in UI or pnpm yardstick:clone',
  });

  steps.push({
    id: 'baseline-resolve',
    phase: 'baseline',
    criterion_id: '_infra',
    label: 'Resolve upstream baseline (first commit)',
    status: options.dryRun ? 'would_run' : 'pending',
  });

  steps.push({
    id: 'verify-typesafety',
    phase: 'verify',
    criterion_id: 'type-safety',
    label: 'Verify type safety (AST + untyped diagnostics)',
    status: options.dryRun ? 'would_run' : 'pending',
  });

  for (const team of teams) {
    for (const crit of WEEK4_CRITERIA) {
      if (crit.kind === 'deterministic') continue;
      steps.push({
        id: `agent-${team.team}-${crit.id}`,
        phase: 'agent',
        team: team.team,
        criterion_id: crit.id,
        label: `${crit.label} — ${team.team.split('-').slice(-1)[0]}`,
        status: options.dryRun ? 'would_run' : 'pending',
        note: 'Queues agent_runner.py job',
      });
    }
  }

  steps.push({
    id: 'sync-final',
    phase: 'sync',
    criterion_id: '_infra',
    label: 'Sync traces, run-state, decision log',
    status: options.dryRun ? 'would_run' : 'pending',
  });

  const plan: RunPlan = {
    cohort,
    week,
    runId,
    runDir,
    teams,
    criteria: WEEK4_CRITERIA,
    steps,
    dry_run: options.dryRun ?? false,
  };

  if (options.dryRun) {
    logDecision(runDir, {
      phase: 'orchestrator',
      subject: {},
      decision: `dry-run plan: ${steps.length} steps for ${teams.length} teams`,
      why: `Specs: ${listSpecFiles(cohort, week, root).length} files. Criteria: ${WEEK4_CRITERIA.length}. No API calls made.`,
      evidence: listSpecFiles(cohort, week, root).map((p) => p.replace(root + '/', '')),
      confidence: 'high',
    });
  }

  return plan;
}

export function saveRunPlan(runDir: string, plan: RunPlan): string {
  const path = join(runDir, 'run-plan.json');
  writeJson(path, plan);
  return path;
}
