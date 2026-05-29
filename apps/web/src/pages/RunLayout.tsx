import { Link, useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { cloneRunTeams, fetchCloneManifest, syncRun, type CloneManifest } from '../api';
import { RunShell } from '../layout/RunShell';

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
          : `Synced — ${syncResult.measurementCount} measurements`,
      );
    } catch (e) {
      setCloneMsg(String(e));
    } finally {
      setCloning(false);
    }
  }

  if (!cohort || !week || !runId) return null;

  const header = (
    <div className="mb-6 space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link to="/" className="text-xs text-stone-500 hover:underline">
            ← Yardstick home
          </Link>
          {cohort && week && (
            <Link
              to={`/cohorts/${cohort}/week/${week}`}
              className="ml-3 text-xs text-stone-500 hover:underline"
            >
              Week {week} hub
            </Link>
          )}
          <p className="text-sm text-stone-500">
            {cohort} · week {week}
          </p>
          <h1 className="text-2xl font-bold">{runId}</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-md bg-stone-800 px-3 py-2 text-sm text-white disabled:opacity-50"
            onClick={() => void handleClone()}
            disabled={cloning}
          >
            {cloning ? 'Cloning…' : 'Clone teams'}
          </button>
        </div>
      </div>
      {syncMsg && <p className="text-sm text-stone-500">{syncing ? 'Syncing…' : syncMsg}</p>}
      {cloneMsg && <p className="text-sm text-stone-600">{cloneMsg}</p>}
      {manifest && (
        <div className="flex flex-wrap gap-2">
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
            </span>
          ))}
        </div>
      )}
    </div>
  );

  return <RunShell header={header} runContext={{ cohort, week: Number(week), runId }} />;
}

export interface RunContext {
  cohort: string;
  week: number;
  runId: string;
}
