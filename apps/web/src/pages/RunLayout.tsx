import { NavLink, Outlet, useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { syncRun } from '../api';

const tabs = [
  { to: 'scorecard', label: 'Scorecard' },
  { to: 'compare', label: 'Compare' },
  { to: 'workbench', label: 'Workbench' },
];

export function RunLayout() {
  const { cohort, week, runId } = useParams();
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState('');

  useEffect(() => {
    if (!cohort || !week || !runId) return;
    setSyncing(true);
    syncRun(cohort, Number(week), runId)
      .then((r) => setSyncMsg(`Synced — ${r.measurementCount} measurements`))
      .catch((e) => setSyncMsg(String(e)))
      .finally(() => setSyncing(false));
  }, [cohort, week, runId]);

  if (!cohort || !week || !runId) return null;
  const base = `/run/${cohort}/${week}/${runId}`;

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-stone-500">
            {cohort} · week {week}
          </p>
          <h1 className="text-2xl font-bold">{runId}</h1>
          {syncMsg && <p className="mt-1 text-sm text-stone-500">{syncing ? 'Syncing…' : syncMsg}</p>}
        </div>
        <nav className="flex gap-2">
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={`${base}/${t.to}`}
              className={({ isActive }) =>
                `rounded-md px-3 py-2 text-sm font-medium ${
                  isActive ? 'bg-stone-900 text-white' : 'bg-white text-stone-700 ring-1 ring-stone-200'
                }`
              }
            >
              {t.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <Outlet context={{ cohort, week: Number(week), runId }} />
    </div>
  );
}

export interface RunContext {
  cohort: string;
  week: number;
  runId: string;
}
