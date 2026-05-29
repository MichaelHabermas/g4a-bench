import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  createJob,
  fetchArtifact,
  resolveBaseline,
} from '../api';
import type { RunContext } from './RunLayout';
import { YardstickHistory } from '../components/YardstickHistory';

export function WorkbenchPage() {
  const { cohort, week, runId } = useOutletContext<RunContext>();
  const [runState, setRunState] = useState<Record<string, unknown> | null>(null);
  const [baselineMsg, setBaselineMsg] = useState('');
  const [jobMsg, setJobMsg] = useState('');

  useEffect(() => {
    fetchArtifact<Record<string, unknown>>(cohort, week, runId, 'run-state.json')
      .then(setRunState)
      .catch(() => setRunState(null));
  }, [cohort, week, runId]);

  const measurements = runState?.agent_measurements as Record<string, unknown> | undefined;

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-stone-200 bg-white p-5">
        <h2 className="mb-3 font-semibold">Measurements index</h2>
        {!measurements && <p className="text-sm text-stone-500">No run-state</p>}
        <ul className="space-y-2 text-sm">
          {measurements &&
            Object.entries(measurements).map(([key, m]) => (
              <li key={key} className="rounded bg-stone-50 px-3 py-2 font-mono text-xs">
                {key} → {JSON.stringify(m)}
              </li>
            ))}
        </ul>
      </section>

      <YardstickHistory />

      <section className="rounded-xl border border-stone-200 bg-white p-5">
        <h2 className="mb-3 font-semibold">Actions</h2>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="rounded-md bg-stone-900 px-4 py-2 text-sm text-white hover:bg-stone-800"
            onClick={() =>
              resolveBaseline(cohort, week)
                .then((r) => setBaselineMsg(JSON.stringify(r)))
                .catch((e) => setBaselineMsg(String(e)))
            }
          >
            Resolve baseline (first commit)
          </button>
          <button
            type="button"
            className="rounded-md border border-stone-300 px-4 py-2 text-sm hover:bg-stone-50"
            onClick={() =>
              createJob(cohort, week, runId, 'cat-2-bundle', 'github-com-michaelhabermas-ship-shape')
                .then((r) => setJobMsg(`Job queued: ${r.jobId}`))
                .catch((e) => setJobMsg(String(e)))
            }
          >
            Queue sample measurement job
          </button>
        </div>
        {baselineMsg && <p className="mt-3 text-xs text-stone-600">{baselineMsg}</p>}
        {jobMsg && <p className="mt-3 text-xs text-stone-600">{jobMsg}</p>}
      </section>
    </div>
  );
}
