import { basename, join } from 'node:path';
import { existsSync } from 'node:fs';
import { syncAll } from '../sync/index.js';
import { verifyTypesafety } from '../verify/typesafety.js';
import { findRepoRoot } from '../paths.js';
import { resolveExistingRunCloneDir } from '../clones/index.js';
import { loadScorecardModel } from '../scorecard/index.js';
import type { RunState } from '../schemas/index.js';
import { readJsonIfExists } from '../fs.js';

export interface IndexRunInput {
  runDir: string;
  cohort: string;
  week: number;
  indexFn?: (payload: RunIndexPayload) => void;
}

export interface RunIndexPayload {
  runId: string;
  cohort: string;
  week: number;
  runDir: string;
  runState: RunState | null;
  measurementCount: number;
  scorecardTeamCount: number;
  bundle_trace?: boolean;
  typesafety_judgment?: boolean;
  typesafety_verify?: boolean;
}

export function syncAndIndexRun(input: IndexRunInput): RunIndexPayload {
  const root = findRepoRoot();
  const runName = basename(input.runDir);
  const cloneBase = resolveExistingRunCloneDir(input.cohort, input.week, runName, root);

  const syncResult = syncAll({
    runDir: input.runDir,
    cloneRoot: cloneBase ?? undefined,
    verifyTypesafety: cloneBase
      ? (runDir, cr) => {
          try {
            return verifyTypesafety(runDir, cr);
          } catch {
            return false;
          }
        }
      : undefined,
  });

  const runState = readJsonIfExists<RunState>(join(input.runDir, 'run-state.json'));
  const model = loadScorecardModel(input.runDir);
  const payload: RunIndexPayload = {
    runId: runName,
    cohort: input.cohort,
    week: input.week,
    runDir: input.runDir,
    runState,
    measurementCount: Object.keys(runState?.agent_measurements ?? {}).length,
    scorecardTeamCount: model.team_ids.length,
    bundle_trace: syncResult.bundle_trace,
    typesafety_judgment: syncResult.typesafety_judgment,
    typesafety_verify: syncResult.typesafety_verify,
  };
  input.indexFn?.(payload);
  return payload;
}
