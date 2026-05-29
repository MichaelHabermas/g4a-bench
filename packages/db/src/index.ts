import Database from 'better-sqlite3';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const schemaPath = join(dirname(fileURLToPath(import.meta.url)), 'schema.sql');

export type YardstickDb = Database.Database;

export function openDb(dbPath: string): YardstickDb {
  mkdirSync(dirname(dbPath), { recursive: true });
  const db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');
  const schema = readFileSync(schemaPath, 'utf8');
  db.exec(schema);
  return db;
}

export function defaultDbPath(root: string): string {
  return process.env.DATABASE_PATH ?? join(root, '.yardstick', 'db.sqlite');
}

export interface RunRow {
  id: number;
  cohort: string;
  week: number;
  run_id: string;
  artifact_path: string;
  updated_at: string;
}

export function upsertRun(
  db: YardstickDb,
  row: { cohort: string; week: number; runId: string; artifactPath: string },
): RunRow {
  const now = new Date().toISOString();
  db.prepare(
    `INSERT INTO runs (cohort, week, run_id, artifact_path, updated_at)
     VALUES (@cohort, @week, @runId, @artifactPath, @now)
     ON CONFLICT(cohort, week, run_id) DO UPDATE SET artifact_path=excluded.artifact_path, updated_at=excluded.updated_at`,
  ).run({ ...row, now });
  return db
    .prepare('SELECT * FROM runs WHERE cohort=? AND week=? AND run_id=?')
    .get(row.cohort, row.week, row.runId) as RunRow;
}

export interface RunStateIndex {
  agent_measurements?: Record<
    string,
    {
      artifact?: string;
      completed_at?: string;
      status?: string;
      run_mode?: string | null;
      replay_outcome?: string | null;
    }
  >;
}

export function indexRunState(db: YardstickDb, runRowId: number, state: RunStateIndex | null): void {
  if (!state?.agent_measurements) return;
  const insert = db.prepare(
    `INSERT INTO measurements (run_row_id, criterion_id, team, artifact, status, trust_tier, completed_at)
     VALUES (@runRowId, @criterionId, @team, @artifact, @status, @trustTier, @completedAt)
     ON CONFLICT(run_row_id, criterion_id, team) DO UPDATE SET
       artifact=excluded.artifact, status=excluded.status, trust_tier=excluded.trust_tier, completed_at=excluded.completed_at`,
  );
  for (const [key, m] of Object.entries(state.agent_measurements)) {
    const [criterionId, team] = key.split(':');
    if (!criterionId || !team) continue;
    insert.run({
      runRowId,
      criterionId,
      team,
      artifact: m.artifact ?? null,
      status: m.status ?? null,
      trustTier: m.replay_outcome === 'succeeded' ? 'verified' : 'artifact-backed',
      completedAt: m.completed_at ?? null,
    });
  }
}

export function listRuns(db: YardstickDb): RunRow[] {
  return db.prepare('SELECT * FROM runs ORDER BY updated_at DESC').all() as RunRow[];
}

export function getRun(db: YardstickDb, cohort: string, week: number, runId: string): RunRow | undefined {
  return db
    .prepare('SELECT * FROM runs WHERE cohort=? AND week=? AND run_id=?')
    .get(cohort, week, runId) as RunRow | undefined;
}

export function createJob(
  db: YardstickDb,
  job: {
    runRowId: number;
    criterionId: string;
    team: string;
    repoPath?: string;
  },
): number {
  const now = new Date().toISOString();
  const r = db
    .prepare(
      `INSERT INTO jobs (run_row_id, criterion_id, team, repo_path, status, created_at)
       VALUES (@runRowId, @criterionId, @team, @repoPath, 'pending', @now)`,
    )
    .run({ ...job, now });
  return Number(r.lastInsertRowid);
}

export function updateJob(
  db: YardstickDb,
  jobId: number,
  patch: { status: string; error?: string; artifact?: string; startedAt?: string; finishedAt?: string },
): void {
  db.prepare(
    `UPDATE jobs SET status=@status, error=COALESCE(@error, error), artifact=COALESCE(@artifact, artifact),
     started_at=COALESCE(@startedAt, started_at), finished_at=COALESCE(@finishedAt, finished_at) WHERE id=@jobId`,
  ).run({ jobId, ...patch });
}

export function listPendingJobs(db: YardstickDb, limit = 10): Array<Record<string, unknown>> {
  return db
    .prepare(
      `SELECT j.*, r.cohort, r.week, r.run_id, r.artifact_path FROM jobs j
       JOIN runs r ON r.id = j.run_row_id WHERE j.status='pending' ORDER BY j.id LIMIT ?`,
    )
    .all(limit) as Array<Record<string, unknown>>;
}

export function createChatSession(
  db: YardstickDb,
  runRowId: number | null,
  contextJson: string,
): number {
  const now = new Date().toISOString();
  const r = db
    .prepare(
      `INSERT INTO chat_sessions (run_row_id, context_json, created_at, updated_at) VALUES (?, ?, ?, ?)`,
    )
    .run(runRowId, contextJson, now, now);
  return Number(r.lastInsertRowid);
}

export function addChatMessage(db: YardstickDb, sessionId: number, role: string, content: string): void {
  const now = new Date().toISOString();
  db.prepare(`INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)`).run(
    sessionId,
    role,
    content,
    now,
  );
  db.prepare(`UPDATE chat_sessions SET updated_at=? WHERE id=?`).run(now, sessionId);
}

export function getChatMessages(db: YardstickDb, sessionId: number): Array<{ role: string; content: string }> {
  return db
    .prepare(`SELECT role, content FROM chat_messages WHERE session_id=? ORDER BY id`)
    .all(sessionId) as Array<{ role: string; content: string }>;
}

export function saveObservabilityRef(
  db: YardstickDb,
  refType: string,
  refId: number,
  traceId: string,
): void {
  const now = new Date().toISOString();
  db.prepare(
    `INSERT INTO observability_refs (ref_type, ref_id, trace_id, created_at) VALUES (?, ?, ?, ?)`,
  ).run(refType, refId, traceId, now);
}

export function upsertBaseline(
  db: YardstickDb,
  row: { cohort: string; week: number; upstreamRepo: string; firstCommitSha: string | null },
): number {
  const now = new Date().toISOString();
  db.prepare(
    `INSERT INTO baselines (cohort, week, upstream_repo, first_commit_sha, cached_at)
     VALUES (@cohort, @week, @upstreamRepo, @firstCommitSha, @now)
     ON CONFLICT(cohort, week) DO UPDATE SET upstream_repo=excluded.upstream_repo,
       first_commit_sha=excluded.first_commit_sha, cached_at=excluded.cached_at`,
  ).run({ ...row, now });
  const b = db.prepare('SELECT id FROM baselines WHERE cohort=? AND week=?').get(row.cohort, row.week) as {
    id: number;
  };
  return b.id;
}

export function getMeasurementsForRun(db: YardstickDb, runRowId: number): Array<Record<string, unknown>> {
  return db.prepare('SELECT * FROM measurements WHERE run_row_id=?').all(runRowId) as Array<
    Record<string, unknown>
  >;
}

export function dbExists(dbPath: string): boolean {
  return existsSync(dbPath);
}
