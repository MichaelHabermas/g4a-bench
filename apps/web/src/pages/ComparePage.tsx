import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { fetchArtifact, fetchScorecard, type ScorecardModel } from '../api';
import type { RunContext } from './RunLayout';

export function ComparePage() {
  const { cohort, week, runId } = useOutletContext<RunContext>();
  const [model, setModel] = useState<ScorecardModel | null>(null);
  const [verification, setVerification] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    fetchScorecard(cohort, week, runId).then(setModel);
    fetchArtifact<Record<string, unknown>>(cohort, week, runId, 'verification.json').then(setVerification).catch(() => setVerification(null));
  }, [cohort, week, runId]);

  if (!model) return <p className="text-stone-500">Loading compare…</p>;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="rounded-xl border border-stone-200 bg-white p-5">
        <h2 className="mb-4 font-semibold">Category summary</h2>
        <ul className="space-y-3">
          {model.criteria.map((c) => (
            <li key={c.id} className="rounded-lg bg-stone-50 p-3">
              <div className="flex justify-between">
                <span className="font-medium">{c.name}</span>
                <span className={c.verified_kind ? 'text-emerald-700' : 'text-amber-700'}>
                  {c.verified_kind ? 'verified band' : 'unverified'}
                </span>
              </div>
              <p className="mt-1 text-sm text-stone-500">{c.parts.length} sub-metrics · {model.team_ids.length} teams</p>
            </li>
          ))}
        </ul>
      </section>
      <section className="rounded-xl border border-stone-200 bg-white p-5">
        <h2 className="mb-4 font-semibold">Verification highlights</h2>
        {!verification && <p className="text-sm text-stone-500">No verification.json</p>}
        {verification && (
          <div className="space-y-3 text-sm">
            <p className="text-stone-600">{String(verification.baseline_gap ?? '')}</p>
            {(verification.records as Array<Record<string, unknown>> | undefined)?.map((rec) => (
              <div key={String(rec.team)} className="rounded-lg border border-stone-100 p-3">
                <p className="font-mono text-xs text-stone-500">{String(rec.team)}</p>
                {rec.verified_remaining != null && (
                  <pre className="mt-2 overflow-x-auto text-xs">{JSON.stringify(rec.verified_remaining, null, 2)}</pre>
                )}
                {rec.checks != null && (
                  <ul className="mt-2 space-y-1">
                    {Object.entries(rec.checks as Record<string, { flagged?: boolean; note?: string }>).map(([k, v]) => (
                      <li key={k} className={v.flagged ? 'text-amber-800' : 'text-stone-600'}>
                        {k}: {v.note}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
