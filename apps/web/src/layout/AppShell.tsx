import { NavLink, Outlet, useLocation, useParams } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import { fetchCatalog, type BenchmarkCatalog } from '../api';

const platformNav = [{ to: '/', label: 'Home', end: true }] as const;

export function AppShell({ children }: { children?: ReactNode }) {
  const [catalog, setCatalog] = useState<BenchmarkCatalog | null>(null);
  const location = useLocation();
  const params = useParams();
  const inRun = Boolean(params.cohort && params.week && params.runId);

  useEffect(() => {
    fetchCatalog()
      .then(setCatalog)
      .catch(() => setCatalog(null));
  }, []);

  const activeCohort = params.cohort ?? catalog?.cohorts[0]?.id;
  const activeWeek = params.week ? Number(params.week) : undefined;
  const cohort = catalog?.cohorts.find((c) => c.id === activeCohort);

  return (
    <div className="min-h-screen bg-stone-50">
      <header className="border-b border-stone-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <NavLink to="/" className="text-xl font-bold tracking-tight text-stone-900">
            Yardstick
          </NavLink>
          <p className="hidden text-sm text-stone-500 sm:block">
            Adversarial G4A measurement
          </p>
        </div>
      </header>

      <div className="mx-auto flex max-w-7xl gap-8 px-6 py-8">
        <aside className="hidden w-56 shrink-0 lg:block">
          <nav className="sticky top-8 space-y-6" aria-label="Platform navigation">
            <div>
              <p className="px-3 text-xs font-semibold uppercase tracking-wide text-stone-400">Platform</p>
              <ul className="mt-1 space-y-0.5">
                {platformNav.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.end}
                      className={({ isActive }) =>
                        `block rounded-lg px-3 py-2 text-sm ${
                          isActive
                            ? 'bg-stone-900 font-medium text-white'
                            : 'text-stone-700 hover:bg-stone-100'
                        }`
                      }
                    >
                      {item.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>

            {catalog?.cohorts.map((c) => (
              <div key={c.id}>
                <p className="px-3 text-xs font-semibold uppercase tracking-wide text-stone-400">
                  {c.label}
                </p>
                <ul className="mt-1 max-h-[min(420px,50vh)] space-y-0.5 overflow-y-auto">
                  {c.weeks.map((w) => {
                    const weekPath = `/cohorts/${c.id}/week/${w.week}`;
                    const isWeekActive =
                      location.pathname.startsWith(weekPath) ||
                      (params.cohort === c.id && activeWeek === w.week);
                    return (
                      <li key={w.week}>
                        <NavLink
                          to={weekPath}
                          className={() =>
                            `block rounded-lg px-3 py-2 text-sm leading-snug ${
                              isWeekActive && !inRun
                                ? 'bg-stone-900 font-medium text-white'
                                : isWeekActive
                                  ? 'bg-stone-200 font-medium text-stone-900'
                                  : 'text-stone-700 hover:bg-stone-100'
                            }`
                          }
                        >
                          <span className="text-stone-500">W{w.week}</span>{' '}
                          {w.title}
                          {w.has_runs && (
                            <span className="mt-0.5 block text-xs opacity-70">
                              {w.runs.length === 1 ? 'measured' : `${w.runs.length} runs`}
                            </span>
                          )}
                        </NavLink>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </nav>
        </aside>

        <main className="min-w-0 flex-1">{children ?? <Outlet context={{ catalog, cohort }} />}</main>
      </div>
    </div>
  );
}
