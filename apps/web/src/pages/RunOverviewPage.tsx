import { useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import {
  fetchCloneManifest,
  fetchDecisions,
  fetchScorecard,
  type CloneManifest,
  type DecisionEntry,
} from '../api';
import type { RunContext } from './RunLayout';

export function RunOverviewPage() {
  const { cohort, week, runId } = useOutletContext<RunContext>();
  const base = `/run/${cohort}/${week}/${runId}`;
  const [manifest, setManifest] = useState<CloneManifest | null>(null);
  const [decisions, setDecisions] = useState<DecisionEntry[]>([]);
  const [teamCount, setTeamCount] = useState(0);

  useEffect(() => {
    fetchCloneManifest(cohort, week, runId).then((r) => setManifest(r.manifest));
    fetchDecisions(cohort, week, runId).then((r) => setDecisions(r.entries));
    fetchScorecard(cohort, week, runId)
      .then((m) => setTeamCount(m.team_ids.length))
      .catch(() => setTeamCount(0));
  }, [cohort, week, runId]);

  const byPhase = decisions.reduce<Record<string, number>>((acc, d) => {
    acc[d.phase] = (acc[d.phase] ?? 0) + 1;
    return acc;
  }, {});

  const cards = [
    { label: 'Teams', value: teamCount || '—', to: 'scorecard' },
    { label: 'Decisions logged', value: decisions.length, to: 'decisions' },
    { label: 'Clones', value: manifest?.entries.length ?? '—', to: 'workbench' },
    { label: 'Verify events', value: byPhase.verify ?? 0, to: 'decisions' },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-bold">Run overview</h2>
        <p className="mt-1 text-sm text-stone-600">
          One place for this benchmark run. Use the sidebar to open scorecard, decision trail, workbench, or the
          full run plan.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((c) => (
          <Link
            key={c.label}
            to={`${base}/${c.to}`}
            className="rounded-xl border border-stone-200 bg-white p-4 hover:border-amber-400 hover:shadow-sm"
          >
            <p className="text-xs font-medium uppercase tracking-wide text-stone-500">{c.label}</p>
            <p className="mt-1 text-2xl font-bold">{c.value}</p>
          </Link>
        ))}
      </div>

      {manifest && (
        <section className="rounded-xl border border-stone-200 bg-white p-5">
          <h3 className="font-semibold">Clone status</h3>
          <ul className="mt-3 flex flex-wrap gap-2">
            {manifest.entries.map((e) => (
              <li
                key={e.team}
                className={`rounded px-2 py-1 text-xs ${
                  e.status === 'cloned' || e.status === 'skipped_existing'
                    ? 'bg-green-50 text-green-900'
                    : 'bg-amber-50 text-amber-900'
                }`}
              >
                {e.team.split('-').slice(-1)[0]}: {e.status}
              </li>
            ))}
          </ul>
        </section>
      )}

      {decisions.length > 0 && (
        <section className="rounded-xl border border-stone-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold">Latest decisions</h3>
            <Link to={`${base}/decisions`} className="text-sm text-stone-600 underline">
              View Decision Trail
            </Link>
          </div>
          <ul className="mt-3 space-y-2 text-sm">
            {decisions.slice(-5).map((d) => (
              <li key={d.id} className="rounded bg-stone-50 px-3 py-2">
                <span className="font-mono text-xs text-stone-500">{d.phase}</span>{' '}
                <span className="font-medium">{d.decision}</span>
                <p className="mt-0.5 text-stone-600 line-clamp-2">{d.why}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
