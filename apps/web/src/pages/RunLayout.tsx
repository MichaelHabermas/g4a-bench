import { NavLink, Outlet, useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { cloneRunTeams, fetchCloneManifest, syncRun, type CloneManifest } from '../api';

const tabs = [
  { to: 'scorecard', label: 'Scorecard' },
  { to: 'compare', label: 'Compare' },
  { to: 'workbench', label: 'Workbench' },
];

export function RunLayout() {
  const { cohort, week, runId } = useParams();
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState('');
  const [cloning, setCloning] = useState(false);
  const [cloneMsg, setCloneMsg] = useState('');
  const [manifest, setManifest] = useState<CloneManifest | null>(null);

  useEffect(() => {
    if (!cohort || !week || !runId) return;
    fetchCloneManifest(cohort, Number(week), runId)
      .then((r) => setManifest(r.manifest))
      .catch(() => setManifest(null));
  }, [cohort, week, runId]);

  useEffect(() => {
    if (!cohort || !week || !runId) return;
    setSyncing(true);
    syncRun(cohort, Number(week), runId)
      .then((r) => {
        const parts = [`${r.measurementCount} measurements`];
        if (r.typesafety_verify) parts.push('type safety verified');
        setSyncMsg(`Synced — ${parts.join(', ')}`);
      })
      .catch((e) => setSyncMsg(String(e)))
      .finally(() => setSyncing(false));
  }, [cohort, week, runId]);

  async function handleClone() {
    if (!cohort || !week || !runId) return;
    setCloning(true);
    setCloneMsg('');
    try {
      const result = await cloneRunTeams(cohort, Number(week), runId, false);
      setManifest(result.manifest);
      const ok = result.manifest.entries.filter(
        (e: { status: string }) => e.status === 'cloned' || e.status === 'skipped_existing',
      ).length;
      setCloneMsg(`Cloned ${ok}/${result.manifest.entries.length} teams`);
      const syncResult = await syncRun(cohort, Number(week), runId);
      setSyncMsg(
        syncResult.typesafety_verify
          ? `Synced — type safety verified (${syncResult.measurementCount} measurements)`
          : `Synced — ${syncResult.measurementCount} measurements (verify skipped — no clones?)`,
      );
    } catch (e) {
      setCloneMsg(String(e));
    } finally {
      setCloning(false);
    }
  }

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
          {cloneMsg && <p className="mt-1 text-sm text-stone-600">{cloneMsg}</p>}
          {manifest && (
            <div className="mt-2 flex flex-wrap gap-2">
              {manifest.entries.map((e) => (
                <span
                  key={e.team}
                  className={`rounded px-2 py-0.5 text-xs ${
                    e.status === 'cloned' || e.status === 'skipped_existing'
                      ? 'bg-green-50 text-green-800'
                      : 'bg-amber-50 text-amber-900'
                  }`}
                  title={e.path}
                >
                  {e.team.split('-').slice(-1)[0]}: {e.status}
                  {e.sha ? ` @ ${e.sha.slice(0, 7)}` : ''}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="rounded-md bg-stone-800 px-3 py-2 text-sm text-white disabled:opacity-50"
            onClick={() => void handleClone()}
            disabled={cloning}
          >
            {cloning ? 'Cloning…' : 'Clone teams'}
          </button>
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
