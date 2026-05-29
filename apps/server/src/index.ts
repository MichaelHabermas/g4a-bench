import { serve } from '@hono/node-server';
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import {
  loadScorecardModel,
  listRuns as coreListRuns,
  runDir,
} from '@yardstick/core';
import {
  registerAllRuns,
  syncRun,
  listRunsFromDb,
  getRunByKey,
  queueJob,
  startChatSession,
  buildChatContext,
  chatReply,
  processPendingJobs,
  resolveBaseline,
  loadYardstickStore,
  getChatConfig,
} from './services.js';
import { root } from './env.js';

const app = new Hono();
app.use('/*', cors());

app.get('/api/health', (c) => c.json({ ok: true, tracer: process.env.TRACE_PROVIDER ?? 'auto' }));

app.get('/api/runs', (c) => {
  registerAllRuns();
  const dbRuns = listRunsFromDb();
  const discovered = coreListRuns(root);
  return c.json({ runs: dbRuns, discovered });
});

app.get('/api/runs/:cohort/:week/:runId', (c) => {
  const { cohort, week, runId } = c.req.param();
  const row = getRunByKey(cohort, Number(week), runId);
  if (!row) return c.json({ error: 'not found' }, 404);
  return c.json(row);
});

app.post('/api/runs/:cohort/:week/:runId/sync', async (c) => {
  const { cohort, week, runId } = c.req.param();
  try {
    const payload = syncRun(cohort, Number(week), runId);
    return c.json(payload);
  } catch (e) {
    return c.json({ error: String(e) }, 500);
  }
});

app.get('/api/runs/:cohort/:week/:runId/scorecard', (c) => {
  const { cohort, week, runId } = c.req.param();
  const row = getRunByKey(cohort, Number(week), runId);
  const path = row?.artifact_path ?? runDir(cohort, Number(week), runId, root);
  if (!existsSync(path)) return c.json({ error: 'run not found' }, 404);
  return c.json(loadScorecardModel(path));
});

app.get('/api/runs/:cohort/:week/:runId/artifact/*', (c) => {
  const { cohort, week, runId } = c.req.param();
  const subpath = c.req.path.split(`/artifact/`)[1] ?? '';
  const row = getRunByKey(cohort, Number(week), runId);
  const base = row?.artifact_path ?? runDir(cohort, Number(week), runId, root);
  const file = join(base, subpath);
  if (!file.startsWith(base) || !existsSync(file)) return c.json({ error: 'not found' }, 404);
  const body = readFileSync(file, 'utf8');
  try {
    return c.json(JSON.parse(body));
  } catch {
    return c.text(body);
  }
});

app.get('/api/runs/:cohort/:week/:runId/yardsticks', (c) => {
  const { cohort, week, runId } = c.req.param();
  const row = getRunByKey(cohort, Number(week), runId);
  const path = row?.artifact_path ?? runDir(cohort, Number(week), runId, root);
  return c.json(loadYardstickStore(path));
});

app.post('/api/runs/:cohort/:week/:runId/jobs', async (c) => {
  const { cohort, week, runId } = c.req.param();
  const body = await c.req.json<{ criterionId: string; team: string; repoPath?: string }>();
  const row = getRunByKey(cohort, Number(week), runId);
  if (!row) return c.json({ error: 'run not found' }, 404);
  const jobId = queueJob({
    runRowId: row.id,
    criterionId: body.criterionId,
    team: body.team,
    repoPath: body.repoPath,
  });
  setImmediate(() => processPendingJobs());
  return c.json({ jobId });
});

app.post('/api/runs/:cohort/:week/:runId/chat/sessions', async (c) => {
  const { cohort, week, runId } = c.req.param();
  const body = await c.req.json<{ uiContext?: Record<string, unknown> }>().catch(() => ({ uiContext: {} }));
  const row = getRunByKey(cohort, Number(week), runId);
  const ctx = buildChatContext(cohort, Number(week), runId, body.uiContext);
  const sessionId = startChatSession(row?.id ?? null, JSON.stringify(ctx));
  return c.json({ sessionId, context: ctx });
});

app.get('/api/chat/config', (c) => c.json(getChatConfig()));

app.post('/api/chat/:sessionId/messages', async (c) => {
  const sessionId = Number(c.req.param('sessionId'));
  const body = await c.req.json<{
    message: string;
    context?: Record<string, unknown>;
    uiContext?: Record<string, unknown>;
  }>();
  if (!body.context) return c.json({ error: 'context required' }, 400);
  try {
    const reply = await chatReply(sessionId, body.message, body.context, body.uiContext);
    return c.json({ reply });
  } catch (e) {
    return c.json({ error: String(e) }, 500);
  }
});

app.post('/api/baseline/:cohort/:week/resolve', (c) => {
  const { cohort, week } = c.req.param();
  try {
    return c.json(resolveBaseline(cohort, Number(week)));
  } catch (e) {
    return c.json({ error: String(e), configured: false }, 500);
  }
});

registerAllRuns();

const port = Number(process.env.PORT ?? 8787);
console.log(`Yardstick server on http://localhost:${port}`);
serve({ fetch: app.fetch, port });
