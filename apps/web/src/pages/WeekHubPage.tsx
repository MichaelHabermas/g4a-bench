import { Link, useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { fetchCatalog, type CatalogCohort, type CatalogWeek } from '../api';

export function WeekHubPage() {
  const { cohort: cohortId, week: weekStr } = useParams();
  const week = Number(weekStr);
  const [cohort, setCohort] = useState<CatalogCohort | null>(null);
  const [weekData, setWeekData] = useState<CatalogWeek | null>(null);
  const [showAllRuns, setShowAllRuns] = useState(false);

  useEffect(() => {
    if (!cohortId || !weekStr) return;
    fetchCatalog()
      .then((cat) => {
        const c = cat.cohorts.find((x) => x.id === cohortId) ?? null;
        setCohort(c);
        setWeekData(c?.weeks.find((w) => w.week === week) ?? null);
      })
      .catch(() => {
        setCohort(null);
        setWeekData(null);
      });
  }, [cohortId, week, weekStr]);

  if (!cohortId || !weekStr) return null;

  const primary = weekData?.runs.find((r) => r.is_primary);
  const archive = weekData?.runs.filter((r) => !r.is_primary) ?? [];

  return (
    <div className="space-y-8">
      <div>
        <Link to="/" className="text-xs text-stone-500 hover:underline">
          ← Home
        </Link>
        <p className="mt-2 text-sm text-stone-500">{cohort?.label ?? cohortId}</p>
        <h1 className="text-2xl font-bold">
          Week {week}
          {weekData?.title ? ` · ${weekData.title}` : ''}
        </h1>
        <p className="mt-2 max-w-2xl text-stone-600">
          This is the week hub — specs and teams for the challenge, plus measurement runs when they exist.
          Open the primary run for scorecard, Decision Trail, workbench, and orchestration.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Spec files" value={weekData?.spec_count ?? '—'} />
        <Stat label="Teams" value={weekData?.team_count ?? '—'} />
        <Stat label="Measurement runs" value={weekData?.runs.length ?? 0} />
      </div>

      {primary ? (
        <section className="rounded-xl border-2 border-stone-900 bg-white p-6">
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">Primary measurement</p>
          <h2 className="mt-1 text-lg font-bold">{primary.label}</h2>
          <dl className="mt-3 grid gap-2 text-sm text-stone-600 sm:grid-cols-2">
            {primary.mode && (
              <div>
                <dt className="text-stone-400">Mode</dt>
                <dd>{primary.mode}</dd>
              </div>
            )}
            <div>
              <dt className="text-stone-400">Measurements</dt>
              <dd>{primary.measurement_count}</dd>
            </div>
            {primary.updated_at && (
              <div>
                <dt className="text-stone-400">Last updated</dt>
                <dd>{new Date(primary.updated_at).toLocaleString()}</dd>
              </div>
            )}
          </dl>
          <Link
            to={`/run/${cohortId}/${week}/${primary.run_id}/overview`}
            className="mt-5 inline-block rounded-md bg-stone-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-stone-800"
          >
            Open run — scorecard & Decision Trail
          </Link>
        </section>
      ) : (
        <section className="rounded-xl border border-dashed border-stone-300 bg-stone-50 p-8 text-center">
          <p className="font-medium text-stone-800">No measurement run yet</p>
          <p className="mt-2 text-sm text-stone-600">
            Specs and REPOS are ready under g4a-specs and g4a-challenger-repos. Start a run from the harness,
            then sync here.
          </p>
        </section>
      )}

      {archive.length > 0 && (
        <section className="rounded-xl border border-stone-200 bg-white p-5">
          <button
            type="button"
            className="flex w-full items-center justify-between text-left text-sm font-medium"
            onClick={() => setShowAllRuns((v) => !v)}
          >
            <span>Earlier / prototype runs ({archive.length})</span>
            <span className="text-stone-400">{showAllRuns ? 'Hide' : 'Show'}</span>
          </button>
          {showAllRuns && (
            <ul className="mt-4 space-y-2 border-t border-stone-100 pt-4">
              {archive.map((r) => (
                <li key={r.run_id}>
                  <Link
                    to={`/run/${cohortId}/${week}/${r.run_id}/overview`}
                    className="block rounded-lg border border-stone-100 px-3 py-2 text-sm hover:border-stone-300"
                  >
                    <span className="font-medium">{r.label}</span>
                    <span className="ml-2 text-stone-500">
                      {r.measurement_count} measurements
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="text-sm text-stone-500">
        <p>
          <strong className="text-stone-700">Inside a run:</strong> Overview, Scorecard, Compare, Decision
          Trail, Workbench, and Run plan share one sidebar — not separate HTML files.
        </p>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-stone-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-stone-400">{label}</p>
      <p className="mt-1 text-2xl font-bold">{value}</p>
    </div>
  );
}
