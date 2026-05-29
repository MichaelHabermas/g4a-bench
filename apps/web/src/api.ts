export interface RunSummary {
  id?: number;
  cohort: string;
  week: number;
  run_id: string;
  artifact_path: string;
  updated_at: string;
}

export interface ScoreCell {
  kind: string;
  display: string;
  trust: string;
  verified?: boolean;
  flagged?: boolean;
  judgment?: string;
  remaining?: number | null;
  claimed_after?: number | null;
}

export interface ScoreCriterion {
  id: string;
  name: string;
  verified_kind: boolean;
  parts: Array<{ id: string; label: string }>;
  teams: Record<string, { cells: Record<string, ScoreCell> }>;
}

export interface ScorecardModel {
  criteria: ScoreCriterion[];
  team_ids: string[];
  handles: Record<string, string>;
}

const api = (path: string, init?: RequestInit) => fetch(path, init).then(async (r) => {
  if (!r.ok) throw new Error(await r.text());
  return r.json();
});

export function fetchRuns(): Promise<{ runs: RunSummary[]; discovered: RunSummary[] }> {
  return api('/api/runs');
}

export function syncRun(cohort: string, week: number, runId: string) {
  return api(`/api/runs/${cohort}/${week}/${runId}/sync`, { method: 'POST' });
}

export function fetchScorecard(cohort: string, week: number, runId: string): Promise<ScorecardModel> {
  return api(`/api/runs/${cohort}/${week}/${runId}/scorecard`);
}

export function fetchArtifact<T>(cohort: string, week: number, runId: string, name: string): Promise<T> {
  return api(`/api/runs/${cohort}/${week}/${runId}/artifact/${name}`);
}

export function createChatSession(cohort: string, week: number, runId: string, uiContext?: Record<string, unknown>) {
  return api(`/api/runs/${cohort}/${week}/${runId}/chat/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ uiContext }),
  });
}

export function sendChatMessage(
  sessionId: number,
  message: string,
  context: Record<string, unknown>,
  uiContext?: Record<string, unknown>,
) {
  return api(`/api/chat/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, context, uiContext }),
  });
}

export function fetchChatConfig(): Promise<{ devMode: boolean; chatMode: string }> {
  return api('/api/chat/config');
}

export function createJob(cohort: string, week: number, runId: string, criterionId: string, team: string, repoPath?: string) {
  return api(`/api/runs/${cohort}/${week}/${runId}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ criterionId, team, repoPath }),
  });
}

export function resolveBaseline(cohort: string, week: number) {
  return api(`/api/baseline/${cohort}/${week}/resolve`, { method: 'POST' });
}

export interface CloneManifestEntry {
  team: string;
  url: string;
  sha: string | null;
  path: string;
  status: string;
  error?: string;
}

export interface CloneManifest {
  cloned_at: string;
  entries: CloneManifestEntry[];
  clone_base: string;
}

export function cloneRunTeams(cohort: string, week: number, runId: string, install = false) {
  return api(`/api/runs/${cohort}/${week}/${runId}/clones`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ install }),
  });
}

export function fetchCloneManifest(cohort: string, week: number, runId: string): Promise<{ manifest: CloneManifest | null }> {
  return api(`/api/runs/${cohort}/${week}/${runId}/clones`);
}

export function shortTeam(handle: string): string {
  return handle.split('-').slice(-1)[0] ?? handle;
}

export interface DecisionEntry {
  id: string;
  at: string;
  phase: string;
  subject: {
    team?: string;
    criterion?: string;
    metric?: string;
    job_id?: number;
  };
  decision: string;
  chosen?: string;
  rejected?: string[];
  why: string;
  evidence?: string[];
  confidence?: string;
  held_loosely?: string;
  flagged?: boolean;
}

export function fetchDecisions(
  cohort: string,
  week: number,
  runId: string,
  query = '',
): Promise<{ entries: DecisionEntry[]; total: number }> {
  const q = query ? `?${query}` : '';
  return api(`/api/runs/${cohort}/${week}/${runId}/decisions${q}`);
}

export interface OrchestratorStep {
  id: string;
  phase: string;
  team?: string;
  criterion_id: string;
  label: string;
  status: string;
  note?: string;
}

export interface RunPlan {
  cohort: string;
  week: number;
  runId: string;
  runDir: string;
  teams: Array<{ team: string; url: string }>;
  criteria: Array<{ id: string; label: string; kind: string }>;
  steps: OrchestratorStep[];
  dry_run: boolean;
}

export function fetchRunPlan(cohort: string, week: number, runId: string): Promise<{ plan: RunPlan | null }> {
  return api(`/api/runs/${cohort}/${week}/${runId}/plan`);
}

export function postRunPlanDryRun(cohort: string, week: number, runId: string): Promise<{ plan: RunPlan }> {
  return api(`/api/runs/${cohort}/${week}/${runId}/plan/dry-run`, { method: 'POST' });
}

export function postRunPlanExecute(
  cohort: string,
  week: number,
  runId: string,
  body: { install?: boolean } = {},
): Promise<{ plan: RunPlan; queued: number; message: string }> {
  return api(`/api/runs/${cohort}/${week}/${runId}/plan/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

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

export function fetchCatalog(): Promise<BenchmarkCatalog> {
  return api('/api/catalog');
}
