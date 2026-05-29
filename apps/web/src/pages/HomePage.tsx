import { Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { fetchCatalog, type BenchmarkCatalog } from '../api';

export function HomePage() {
  const [catalog, setCatalog] = useState<BenchmarkCatalog | null>(null);

  useEffect(() => {
    fetchCatalog().then(setCatalog).catch(() => setCatalog(null));
  }, []);

  const featured = catalog?.cohorts.flatMap((c) =>
    c.weeks.filter((w) => w.has_runs).map((w) => ({ cohort: c, week: w })),
  );

  return (
    <div className="space-y-10">
      <section>
        <h1 className="text-3xl font-bold tracking-tight text-stone-900">Yardstick</h1>
        <p className="mt-3 max-w-2xl text-lg text-stone-600">
          Measurement platform for G4A weekly challenges. Each week has its own specs, teams, and
          criteria — Yardstick clones repos, verifies claims, ranks with trust gates, and records a{' '}
          <strong className="font-medium text-stone-800">Decision Trail</strong> of every choice.
        </p>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        {[
          {
            title: 'By week',
            body: 'Navigate cohort → week → open the active measurement run. Not a flat list of prototype IDs.',
          },
          {
            title: 'Trust-gated',
            body: 'Harness-verified numbers outrank self-report. Gaps stay visible.',
          },
          {
            title: 'Auditable',
            body: 'Decision Trail, workbench artifacts, and dev chat share one run context.',
          },
        ].map((card) => (
          <div key={card.title} className="rounded-xl border border-stone-200 bg-white p-5">
            <h2 className="font-semibold">{card.title}</h2>
            <p className="mt-2 text-sm text-stone-600">{card.body}</p>
          </div>
        ))}
      </section>

      {catalog?.cohorts.map((cohort) => (
        <section key={cohort.id} className="rounded-xl border border-stone-200 bg-white p-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold">{cohort.label}</h2>
              <p className="mt-1 text-sm text-stone-500">{cohort.id}</p>
            </div>
            <p className="text-sm text-stone-500">{cohort.weeks.length} weeks with specs</p>
          </div>

          <ul className="mt-6 divide-y divide-stone-100">
            {cohort.weeks.map((w) => (
              <li key={w.week} className="flex flex-wrap items-center justify-between gap-4 py-4">
                <div>
                  <p className="font-medium">
                    <span className="text-stone-500">Week {w.week}</span> · {w.title}
                  </p>
                  <p className="mt-1 text-sm text-stone-500">
                    {w.spec_count} spec files · {w.team_count} teams
                    {w.has_runs
                      ? ` · ${w.runs.length} measurement run${w.runs.length === 1 ? '' : 's'}`
                      : ' · not measured yet'}
                  </p>
                </div>
                <div className="flex gap-2">
                  {w.primary_run_id ? (
                    <Link
                      to={`/run/${cohort.id}/${w.week}/${w.primary_run_id}/overview`}
                      className="rounded-md bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800"
                    >
                      Open measurement
                    </Link>
                  ) : null}
                  <Link
                    to={`/cohorts/${cohort.id}/week/${w.week}`}
                    className="rounded-md border border-stone-300 px-4 py-2 text-sm hover:bg-stone-50"
                  >
                    Week hub
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}

      {featured && featured.length > 0 && (
        <section className="rounded-xl border border-amber-200 bg-amber-50/60 p-5">
          <h2 className="font-semibold text-amber-950">Continue measuring</h2>
          <ul className="mt-3 space-y-2">
            {featured.map(({ cohort, week }) => (
              <li key={`${cohort.id}-${week.week}`}>
                <Link
                  className="text-sm font-medium text-amber-900 underline"
                  to={`/run/${cohort.id}/${week.week}/${week.primary_run_id}/overview`}
                >
                  {cohort.label} · Week {week.week} — {week.title}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!catalog && <p className="text-stone-500">Loading catalog…</p>}
    </div>
  );
}
