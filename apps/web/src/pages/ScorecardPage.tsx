import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { fetchScorecard, type ScorecardModel, type ScoreCell } from '../api';
import type { RunContext } from './RunLayout';
import { setChatFocus } from '../chatFocus';

function TrustBadge({ verified }: { verified: boolean }) {
  return verified ? (
    <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-bold uppercase text-emerald-800">
      verified
    </span>
  ) : (
    <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-bold uppercase text-amber-800">
      self-reported
    </span>
  );
}

function CellView({
  cell,
  metricId,
  metricLabel,
  teamId,
  teamHandle,
  category,
}: {
  cell: ScoreCell | undefined;
  metricId: string;
  metricLabel: string;
  teamId: string;
  teamHandle: string;
  category: string;
}) {
  const isGap = !cell || cell.display === 'n/a' || cell.display === '—';
  if (!cell) {
    return (
      <td
        className="cursor-pointer px-3 py-2 text-stone-400 hover:bg-amber-50"
        title="No data — click to ask chat"
        onClick={() => setChatFocus({ metric_id: metricId, team: teamId, label: metricLabel, category })}
      >
        — <span className="text-xs text-amber-600">?</span>
      </td>
    );
  }
  return (
    <td
      className={`cursor-pointer px-3 py-2 text-sm hover:bg-stone-50 ${cell.flagged ? 'bg-amber-50' : ''} ${isGap ? 'ring-1 ring-inset ring-amber-200' : ''}`}
      title={
        (cell.claimed_after != null ? `claimed ${cell.claimed_after}, verified ${cell.remaining ?? 'n/a'}. ` : '') +
        'Click to discuss in chat'
      }
      onClick={() => setChatFocus({ metric_id: metricId, team: teamId, label: metricLabel, category })}
    >
      <span className="font-mono">{cell.display}</span>
      <span className="ml-2 rounded bg-stone-100 px-1 text-xs text-stone-600">
        {cell.trust === 'verified' ? 'ver' : cell.trust.slice(0, 4)}
      </span>
      {cell.flagged && <span className="ml-1 text-amber-600" title="self-report rejected">⚠</span>}
      {isGap && <span className="ml-1 text-xs text-amber-700">gap</span>}
    </td>
  );
}

export function ScorecardPage() {
  const { cohort, week, runId } = useOutletContext<RunContext>();
  const [model, setModel] = useState<ScorecardModel | null>(null);

  useEffect(() => {
    fetchScorecard(cohort, week, runId).then(setModel);
  }, [cohort, week, runId]);

  if (!model) return <p className="text-stone-500">Loading scorecard…</p>;

  return (
    <div className="space-y-8">
      <p className="rounded-lg border border-stone-200 bg-white p-4 text-sm text-stone-600">
        Trust-gated ranking: <strong>verified</strong> harness measurements outrank self-report. Click any cell to
        focus chat — useful for gaps like <strong>untyped params</strong> where harness did not measure all rubric
        sub-metrics.
      </p>
      {model.criteria.map((crit) => (
        <section key={crit.id} className="overflow-hidden rounded-xl border border-stone-200 bg-white">
          <div className="flex items-center gap-3 border-b border-stone-100 px-4 py-3">
            <h2 className="font-semibold">{crit.name}</h2>
            <TrustBadge verified={crit.verified_kind} />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left">
              <thead>
                <tr className="border-b border-stone-100 text-xs uppercase text-stone-500">
                  <th className="px-4 py-2">Metric</th>
                  {model.team_ids.map((tid) => (
                    <th key={tid} className="px-3 py-2">
                      {model.handles[tid]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {crit.parts.map((part) => (
                  <tr key={part.id} className="border-b border-stone-50">
                    <td className="px-4 py-2 text-sm text-stone-600">{part.label}</td>
                    {model.team_ids.map((tid) => (
                      <CellView
                        key={tid}
                        cell={crit.teams[tid]?.cells[part.id]}
                        metricId={part.id}
                        metricLabel={part.label}
                        teamId={tid}
                        teamHandle={model.handles[tid] ?? tid}
                        category={crit.name}
                      />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
