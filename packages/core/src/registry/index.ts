import { basename, join } from 'node:path';
import { syncAll } from '../sync/index.js';
import { verifyTypesafety } from '../verify/typesafety.js';
import { cloneRoot, findRepoRoot } from '../paths.js';
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
}

export function syncAndIndexRun(input: IndexRunInput): RunIndexPayload {
  const root = findRepoRoot();
  const runName = basename(input.runDir);
  const legacyClone = join(cloneRoot(root), input.cohort, `week-${input.week}`, runName);
  const prototypeClone = `/private/tmp/g4a-bench-prototype/${input.cohort}/week-${input.week}/${runName}`;

  syncAll({
    runDir: input.runDir,
    cloneRoot: prototypeClone,
    verifyTypesafety: (runDir, cr) => {
      try {
        return verifyTypesafety(runDir, cr);
      } catch {
        try {
          return verifyTypesafety(runDir, legacyClone);
        } catch {
          return false;
        }
      }
    },
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
  };
  input.indexFn?.(payload);
  return payload;
}
