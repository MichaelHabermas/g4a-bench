import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { fetchArtifact } from '../api';
import type { RunContext } from '../pages/RunLayout';

interface YardstickEntry {
  criterion_id: string;
  kind: string;
  established_from: string;
  established_at: string;
  yardstick: { instrument?: string; method_rationale?: string };
  alternatives_considered?: Array<{ method?: string; verdict?: string; rationale?: string; at?: string }>;
  definition_history?: Array<{ at: string; note: string }>;
}

export function YardstickHistory() {
  const { cohort, week, runId } = useOutletContext<RunContext>();
  const [entries, setEntries] = useState<YardstickEntry[]>([]);

  useEffect(() => {
    fetchArtifact<{ yardsticks?: Record<string, YardstickEntry> }>(cohort, week, runId, 'yardsticks.json')
      .then((ys) => setEntries(Object.values(ys.yardsticks ?? {})))
      .catch(() => setEntries([]));
  }, [cohort, week, runId]);

  if (!entries.length) return null;

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-5">
      <h2 className="mb-3 font-semibold">Yardstick history</h2>
      <div className="space-y-4">
        {entries.map((e) => (
          <article key={e.criterion_id} className="rounded-lg border border-stone-100 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm font-semibold">{e.criterion_id}</span>
              <span className="rounded bg-stone-100 px-2 py-0.5 text-xs">{e.kind}</span>
              <span className="text-xs text-stone-500">from {e.established_from}</span>
            </div>
            <p className="mt-2 text-sm text-stone-600 line-clamp-3">{e.yardstick.instrument}</p>
            {(e.alternatives_considered?.length ?? 0) > 0 && (
              <div className="mt-3">
                <p className="text-xs font-semibold uppercase text-stone-500">Superseded / rejected</p>
                <ul className="mt-1 space-y-1 text-xs text-stone-600">
                  {e.alternatives_considered!.map((a, i) => (
                    <li key={i}>
                      [{a.verdict}] {a.method?.slice(0, 120)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {(e.definition_history?.length ?? 0) > 0 && (
              <div className="mt-2 text-xs text-stone-500">
                {e.definition_history!.map((h) => (
                  <p key={h.at}>{h.at}: {h.note}</p>
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
