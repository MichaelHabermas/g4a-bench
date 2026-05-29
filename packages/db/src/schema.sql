CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cohort TEXT NOT NULL,
  week INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  artifact_path TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(cohort, week, run_id)
);

CREATE TABLE IF NOT EXISTS measurements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_row_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  criterion_id TEXT NOT NULL,
  team TEXT NOT NULL,
  artifact TEXT,
  status TEXT,
  trust_tier TEXT,
  completed_at TEXT,
  UNIQUE(run_row_id, criterion_id, team)
);

CREATE TABLE IF NOT EXISTS yardstick_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_row_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  criterion_id TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  active INTEGER NOT NULL DEFAULT 1,
  superseded_by INTEGER,
  snapshot_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS yardstick_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_row_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  criterion_id TEXT NOT NULL,
  artifact TEXT,
  method TEXT,
  verdict TEXT,
  rationale TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS baselines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cohort TEXT NOT NULL,
  week INTEGER NOT NULL,
  upstream_repo TEXT NOT NULL,
  first_commit_sha TEXT,
  cached_at TEXT NOT NULL,
  UNIQUE(cohort, week)
);

CREATE TABLE IF NOT EXISTS baseline_measurements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  baseline_id INTEGER NOT NULL REFERENCES baselines(id) ON DELETE CASCADE,
  criterion_id TEXT NOT NULL,
  metric_key TEXT NOT NULL,
  value_json TEXT NOT NULL,
  UNIQUE(baseline_id, criterion_id, metric_key)
);

CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_row_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  criterion_id TEXT NOT NULL,
  team TEXT NOT NULL,
  repo_path TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  error TEXT,
  artifact TEXT,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT
);

CREATE TABLE IF NOT EXISTS chat_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_row_id INTEGER REFERENCES runs(id) ON DELETE SET NULL,
  title TEXT,
  context_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observability_refs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ref_type TEXT NOT NULL,
  ref_id INTEGER NOT NULL,
  trace_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_measurements_run ON measurements(run_row_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
