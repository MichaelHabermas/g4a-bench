import { NavLink, Outlet, useParams } from 'react-router-dom';
import type { ReactNode } from 'react';
import type { RunContext } from '../pages/RunLayout';

const runNav = [
  { to: 'overview', label: 'Overview', description: 'Run status and quick actions' },
  { to: 'scorecard', label: 'Scorecard', description: 'Trust-gated rankings' },
  { to: 'compare', label: 'Compare', description: 'Side-by-side criteria' },
  { to: 'decisions', label: 'Decision Trail', description: 'How and why each step was decided' },
  { to: 'workbench', label: 'Workbench', description: 'Measurements, yardsticks, jobs' },
  { to: 'plan', label: 'Run plan', description: 'Full Week 4 orchestration' },
] as const;

export function RunShell({ header, runContext }: { header?: ReactNode; runContext: RunContext }) {
  const { cohort, week, runId } = useParams();
  if (!cohort || !week || !runId) return null;
  const base = `/run/${cohort}/${week}/${runId}`;

  return (
    <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
      <aside className="w-full shrink-0 lg:w-56">
        <nav className="rounded-xl border border-stone-200 bg-white p-2" aria-label="Run navigation">
          <p className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-stone-400">This run</p>
          <ul className="space-y-0.5">
            {runNav.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={`${base}/${item.to}`}
                  className={({ isActive }) =>
                    `block rounded-lg px-3 py-2 text-sm transition-colors ${
                      isActive
                        ? 'bg-stone-900 font-medium text-white'
                        : 'text-stone-700 hover:bg-stone-100'
                    }`
                  }
                  title={item.description}
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <div className="min-w-0 flex-1">
        {header}
        <Outlet context={runContext} />
      </div>
    </div>
  );
}
