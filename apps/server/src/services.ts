import { join } from 'node:path';
import {
  loadYardstickStore,
  readJsonIfExists,
  loadScorecardModel,
  buildEnrichedChatContext,
  isDevChatMode,
} from '@yardstick/core';
import {
  defaultDbPath,
  openDb,
  upsertRun,
  indexRunState,
  listRuns as dbListRuns,
  getRun,
  createJob,
  updateJob,
  listPendingJobs,
  createChatSession,
  addChatMessage,
  getChatMessages,
  saveObservabilityRef,
  upsertBaseline,
  getMeasurementsForRun,
} from '@yardstick/db';
import { createLlmProvider } from '@yardstick/llm';
import { createTraceProvider } from '@yardstick/observability';
import { root } from './env.js';
import {
  syncAndIndexRun,
  tryAutoPromote,
  loadAgentMeasurements,
  listRuns as coreListRuns,
  loadBaselineConfig,
  cloneUpstreamBaseline,
  harnessDir,
  cloneAllForRun,
  loadCloneManifest,
  buildClonePlan,
} from '@yardstick/core';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';

const db = openDb(defaultDbPath(root));
export const tracer = createTraceProvider();

export function getLlm() {
  return createLlmProvider();
}

export function registerAllRuns(): void {
  for (const r of coreListRuns(root)) {
    upsertRun(db, {
      cohort: r.cohort,
      week: r.week,
      runId: r.runId,
      artifactPath: r.path,
    });
  }
}

export function listRunsFromDb() {
  return dbListRuns(db);
}

export function getRunByKey(cohort: string, week: number, runId: string) {
  return getRun(db, cohort, week, runId);
}

export function queueJob(input: {
  runRowId: number;
  criterionId: string;
  team: string;
  repoPath?: string;
}): number {
  return createJob(db, input);
}

export function startChatSession(runRowId: number | null, contextJson: string): number {
  return createChatSession(db, runRowId, contextJson);
}

export { loadYardstickStore };

export function syncRun(cohort: string, week: number, runId: string) {
  const trace = tracer.startTrace({ name: 'sync', kind: 'sync', runId, tags: { cohort, week: String(week) } });
  try {
    const runRow = getRun(db, cohort, week, runId);
    if (!runRow) throw new Error('Run not found');
    const payload = syncAndIndexRun({
      runDir: runRow.artifact_path,
      cohort,
      week,
      indexFn: (p) => {
        const row = upsertRun(db, { cohort, week, runId, artifactPath: p.runDir });
        indexRunState(db, row.id, p.runState);
      },
    });
    trace.end({ output: payload });
    return payload;
  } catch (e) {
    trace.end({ level: 'ERROR', output: String(e) });
    throw e;
  }
}

export async function runPythonAgent(job: Record<string, unknown>): Promise<void> {
  const jobId = job.id as number;
  const runPath = job.artifact_path as string;
  const criterionId = job.criterion_id as string;
  const repoPath = job.repo_path as string;
  const harness = harnessDir(root);
  const venvPython = join(harness, '.venv/bin/python');
  const python = existsSync(venvPython) ? venvPython : 'python3';
  const script = join(harness, 'agent_runner.py');

  updateJob(db, jobId, { status: 'running', startedAt: new Date().toISOString() });

  const trace = tracer.startTrace({
    name: 'measurement',
    kind: 'measurement',
    runId: job.run_id as string,
    tags: { criterionId, team: job.team as string },
  });
  saveObservabilityRef(db, 'job', jobId, trace.traceId);

  const args = [
    script,
    '--criterion-id',
    criterionId,
    '--criterion',
    `Measure criterion ${criterionId}`,
    '--repo',
    repoPath,
    '--run-dir',
    runPath,
    '--out-name',
    `job-${jobId}.json`,
  ];

  await new Promise<void>((resolve, reject) => {
    const proc = spawn(python, args, {
      cwd: root,
      env: { ...process.env },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stderr = '';
    proc.stderr.on('data', (d) => {
      stderr += d.toString();
    });
    proc.on('close', (code) => {
      if (code !== 0) {
        updateJob(db, jobId, {
          status: 'failed',
          error: stderr || `exit ${code}`,
          finishedAt: new Date().toISOString(),
        });
        trace.end({ level: 'ERROR', output: stderr });
        reject(new Error(stderr || `Agent failed with code ${code}`));
        return;
      }
      const artifact = `job-${jobId}.json`;
      const measurements = loadAgentMeasurements(runPath);
      const latest = measurements.find((m) => m._artifact === artifact);
      if (latest && latest.criterion_id) {
        tryAutoPromote(runPath, {
          criterionId: latest.criterion_id,
          measurement: latest,
        });
      }
      syncRun(job.cohort as string, job.week as number, job.run_id as string);
      updateJob(db, jobId, {
        status: 'done',
        artifact,
        finishedAt: new Date().toISOString(),
      });
      trace.end({ output: { artifact } });
      resolve();
    });
  });
}

export function processPendingJobs(): void {
  const pending = listPendingJobs(db, 1);
  for (const job of pending) {
    void runPythonAgent(job).catch(() => {});
  }
}

export function buildChatContext(cohort: string, week: number, runId: string, uiContext?: Record<string, unknown>) {
  const runRow = getRun(db, cohort, week, runId);
  if (!runRow) return null;
  const runDir = runRow.artifact_path;
  const typesafetyTrace = readJsonIfExists<Record<string, unknown>>(join(runDir, 'typesafety-trace.json'));
  let scorecard = null;
  try {
    scorecard = loadScorecardModel(runDir);
  } catch {
    scorecard = null;
  }

  return buildEnrichedChatContext({
    cohort,
    week,
    runId,
    runDir,
    runState: readJsonIfExists(join(runDir, 'run-state.json')),
    yardsticks: readJsonIfExists(join(runDir, 'yardsticks.json')),
    verification: readJsonIfExists(join(runDir, 'verification.json')),
    typesafetyTrace,
    bundleTrace: readJsonIfExists(join(runDir, 'bundle-trace.json')),
    measurementsIndex: getMeasurementsForRun(db, runRow.id),
    scorecard,
    uiContext,
  });
}

export function getChatConfig() {
  return { devMode: isDevChatMode(), chatMode: isDevChatMode() ? 'dev_with_code' : 'artifacts_only' };
}

export async function chatReply(
  sessionId: number,
  userMessage: string,
  context: Record<string, unknown>,
  uiContext?: Record<string, unknown>,
): Promise<string> {
  const trace = tracer.startTrace({ name: 'chat', kind: 'chat', sessionId });
  saveObservabilityRef(db, 'chat_session', sessionId, trace.traceId);

  addChatMessage(db, sessionId, 'user', userMessage);
  const history = getChatMessages(db, sessionId);

  const runMeta = context.run as { cohort?: string; week?: number; runId?: string } | undefined;
  let enriched = context;
  if (runMeta?.cohort && runMeta.week != null && runMeta.runId) {
    const fresh = buildChatContext(runMeta.cohort, runMeta.week, runMeta.runId, {
      ...(typeof context.ui === 'object' ? (context.ui as Record<string, unknown>) : {}),
      ...uiContext,
    });
    if (fresh) enriched = fresh;
  }

  const devMode = isDevChatMode();
  const system = devMode
    ? `You are Yardstick, an adversarial benchmark assistant in DEV MODE.

You have run artifacts PLUS cloned repo source snippets and ripgrep search hits (dev_code).

Your job:
- Explain HOW numbers were derived and WHY gaps exist (e.g. untyped params missing because harness AST only counts any/as/!).
- Use coverage_gaps — call out missing/unverified metrics explicitly before answering.
- Search dev_code.file_snippets and dev_code.searches for team counting scripts, tsconfig strict flags, eslint rules.
- Propose what the measurement agent SHOULD do next — never invent counts.
- Flag self-report rejections. Say "I don't know" when clones are absent.

When user asks about a blank cell (—) or 0% flat, start by stating whether harness measured it, team claimed it, or nobody reported it.`
    : `You are Yardstick, an adversarial benchmark assistant. Answer using run artifacts, measurements, yardsticks, verification records, and coverage_gaps. Never invent numbers. If data is missing, say so. Flag when self-report was rejected.`;

  const llm = getLlm();
  const payload = JSON.stringify(enriched, null, 2);
  const maxLen = devMode ? 180000 : 120000;

  const result = await llm.complete({
    messages: [
      { role: 'system', content: system },
      {
        role: 'user',
        content: `Context JSON:\n${payload.slice(0, maxLen)}\n\nConversation:\n${history.map((m) => `${m.role}: ${m.content}`).join('\n')}`,
      },
    ],
    maxTokens: 4096,
  });

  trace.generation({
    name: 'chat-turn',
    model: result.model,
    input: userMessage,
    output: result.content,
    usage: { input: result.usage?.inputTokens, output: result.usage?.outputTokens },
  });
  trace.end({ output: { length: result.content.length, devMode } });

  addChatMessage(db, sessionId, 'assistant', result.content);
  return result.content;
}

export function resolveBaseline(cohort: string, week: number) {
  const config = loadBaselineConfig(cohort, week, root);
  if (!config) return { configured: false as const };
  const dest = join(root, '.yardstick', 'baselines', cohort, `week-${week}`);
  const { sha } = cloneUpstreamBaseline(config, dest);
  const id = upsertBaseline(db, {
    cohort,
    week,
    upstreamRepo: config.upstream_repo_url,
    firstCommitSha: sha,
  });
  return { configured: true as const, baselineId: id, sha, path: dest };
}

export function cloneRunTeams(
  cohort: string,
  week: number,
  runId: string,
  options: { install?: boolean } = {},
) {
  const runRow = getRun(db, cohort, week, runId);
  const runPath = runRow?.artifact_path ?? join(root, 'g4a-benchmarks', cohort, `week-${week}`, 'runs', runId);
  const plan = buildClonePlan(runPath, cohort, week, runId, root);
  const manifest = cloneAllForRun(runPath, cohort, week, runId, options, root);
  return { plan: { warnings: plan.warnings, entries: plan.entries.map((e) => ({ team: e.team, url: e.url, sha: e.commitSha })) }, manifest };
}

export function getCloneManifestForRun(cohort: string, week: number, runId: string) {
  const runRow = getRun(db, cohort, week, runId);
  const runPath = runRow?.artifact_path ?? join(root, 'g4a-benchmarks', cohort, `week-${week}`, 'runs', runId);
  return loadCloneManifest(runPath);
}
