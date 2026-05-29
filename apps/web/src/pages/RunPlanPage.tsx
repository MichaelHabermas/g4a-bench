import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { fetchRunPlan, postRunPlanDryRun, postRunPlanExecute, type RunPlan } from '../api';
import type { RunContext } from './RunLayout';

export function RunPlanPage() {
  const { cohort, week, runId } = useOutletContext<RunContext>();
  const [plan, setPlan] = useState<RunPlan | null>(null);
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(false);

  function load() {
    fetchRunPlan(cohort, week, runId)
      .then((r) => setPlan(r.plan))
      .catch(() => setPlan(null));
  }

  useEffect(() => {
    load();
  }, [cohort, week, runId]);

  async function dryRun() {
    setLoading(true);
    setMsg('');
    try {
      const r = await postRunPlanDryRun(cohort, week, runId);
      setPlan(r.plan);
      setMsg(`Dry-run logged ${r.plan.steps.length} steps to Decision Trail.`);
    } catch (e) {
      setMsg(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function execute() {
    setLoading(true);
    setMsg('');
    try {
      const r = await postRunPlanExecute(cohort, week, runId);
      setMsg(r.message ?? JSON.stringify(r));
      load();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setLoading(false);
    }
  }

  const pending = plan?.steps.filter((s) => s.status === 'pending' || s.status === 'would_run') ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold">Run plan</h2>
        <p className="mt-1 text-sm text-stone-600">
          Full Week 4 orchestration: clone all teams, verify type safety, queue agent jobs per category, sync.
          Dry-run logs the plan without spending API credits.
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          disabled={loading}
          className="rounded-md border border-stone-300 px-4 py-2 text-sm hover:bg-stone-50 disabled:opacity-50"
          onClick={() => void dryRun()}
        >
          Dry-run (log plan only)
        </button>
        <button
          type="button"
          disabled={loading}
          className="rounded-md bg-stone-900 px-4 py-2 text-sm text-white hover:bg-stone-800 disabled:opacity-50"
          onClick={() => void execute()}
        >
          Execute plan (clone + sync + queue jobs)
        </button>
      </div>
      {msg && <p className="text-sm text-stone-600">{msg}</p>}

      {plan && (
        <>
          <p className="text-sm text-stone-500">
            {plan.teams.length} teams · {plan.criteria.length} criteria · {plan.steps.length} steps
            {plan.dry_run ? ' (dry-run)' : ''}
          </p>
          <div className="overflow-x-auto rounded-xl border border-stone-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-stone-100 bg-stone-50 text-xs uppercase text-stone-500">
                <tr>
                  <th className="px-3 py-2">Phase</th>
                  <th className="px-3 py-2">Criterion</th>
                  <th className="px-3 py-2">Team</th>
                  <th className="px-3 py-2">Label</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {plan.steps.map((s) => (
                  <tr key={s.id} className="border-b border-stone-50">
                    <td className="px-3 py-2 font-mono text-xs">{s.phase}</td>
                    <td className="px-3 py-2">{s.criterion_id}</td>
                    <td className="px-3 py-2">{s.team?.split('-').slice(-1)[0] ?? '—'}</td>
                    <td className="px-3 py-2">{s.label}</td>
                    <td className="px-3 py-2">
                      <span
                        className={`rounded px-1.5 py-0.5 text-xs ${
                          s.status === 'done'
                            ? 'bg-green-100 text-green-800'
                            : s.status === 'would_run'
                              ? 'bg-violet-100 text-violet-800'
                              : 'bg-stone-100 text-stone-700'
                        }`}
                      >
                        {s.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {pending.length > 0 && (
            <p className="text-xs text-amber-800">
              {pending.length} steps still pending or would_run. Agent jobs require ANTHROPIC_API_KEY and clones.
            </p>
          )}
        </>
      )}
    </div>
  );
}
