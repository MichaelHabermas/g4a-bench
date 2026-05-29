import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchRuns, type RunSummary } from '../api';

export function RunPickerPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRuns()
      .then((d) => setRuns(d.runs.length ? d.runs : d.discovered))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-stone-500">Loading runs…</p>;

  const grouped = runs.reduce<Record<string, RunSummary[]>>((acc, r) => {
    const key = `${r.cohort} / week ${r.week}`;
    acc[key] = acc[key] ?? [];
    acc[key].push(r);
    return acc;
  }, {});

  return (
    <div>
      <h1 className="mb-2 text-2xl font-bold">Choose a run</h1>
      <p className="mb-8 text-stone-600">
        Select cohort, week, and run to view scorecard, compare, and workbench.
      </p>
      {Object.entries(grouped).map(([label, items]) => (
        <section key={label} className="mb-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-stone-500">{label}</h2>
          <ul className="space-y-2">
            {items.map((r) => (
              <li key={r.run_id}>
                <Link
                  to={`/run/${r.cohort}/${r.week}/${r.run_id}/scorecard`}
                  className="block rounded-lg border border-stone-200 bg-white px-4 py-3 hover:border-amber-400 hover:shadow-sm"
                >
                  <span className="font-medium">{r.run_id}</span>
                  <span className="ml-3 text-sm text-stone-500">{r.updated_at ?? ''}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
      {!runs.length && <p className="text-stone-500">No runs found under g4a-benchmarks/.</p>}
    </div>
  );
}
