import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { fetchDecisions, type DecisionEntry } from '../api';
import { setChatFocus } from '../chatFocus';
import type { RunContext } from './RunLayout';

const phases = ['all', 'clone', 'verify', 'sync', 'agent', 'yardstick', 'orchestrator', 'baseline', 'chat'] as const;

export function DecisionTrailPage() {
  const { cohort, week, runId } = useOutletContext<RunContext>();
  const [entries, setEntries] = useState<DecisionEntry[]>([]);
  const [phase, setPhase] = useState<string>('all');
  const [team, setTeam] = useState<string>('all');
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams();
    if (phase !== 'all') params.set('phase', phase);
    if (team !== 'all') params.set('team', team);
    fetchDecisions(cohort, week, runId, params.toString())
      .then((r) => setEntries(r.entries))
      .catch(() => setEntries([]));
  }, [cohort, week, runId, phase, team]);

  const teams = [...new Set(entries.map((e) => e.subject.team).filter(Boolean))] as string[];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold">Decision Trail</h2>
        <p className="mt-1 text-sm text-stone-600">
          Append-only log of how Yardstick chose instruments, verified numbers, cloned repos, and promoted
          yardsticks. Click a row to ask chat about that decision.
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <label className="text-sm">
          Phase{' '}
          <select
            className="ml-1 rounded border border-stone-200 px-2 py-1"
            value={phase}
            onChange={(e) => setPhase(e.target.value)}
          >
            {phases.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          Team{' '}
          <select
            className="ml-1 rounded border border-stone-200 px-2 py-1"
            value={team}
            onChange={(e) => setTeam(e.target.value)}
          >
            <option value="all">all</option>
            {teams.map((t) => (
              <option key={t} value={t}>
                {t.split('-').slice(-1)[0]}
              </option>
            ))}
          </select>
        </label>
      </div>

      {!entries.length && (
        <p className="rounded-lg border border-dashed border-stone-300 bg-stone-50 p-6 text-sm text-stone-600">
          No decisions yet. Clone teams and sync the run to populate the trail, or run a dry-run plan from Run
          plan.
        </p>
      )}

      <ul className="space-y-2">
        {entries.map((d) => (
          <li
            key={d.id}
            className={`cursor-pointer rounded-xl border bg-white p-4 transition-colors ${
              d.flagged ? 'border-amber-300 bg-amber-50/50' : 'border-stone-200 hover:border-stone-300'
            }`}
            onClick={() => {
              setExpanded(expanded === d.id ? null : d.id);
              setChatFocus({
                metric_id: d.subject.metric ?? d.subject.criterion ?? 'decision',
                team: d.subject.team,
                label: d.decision.slice(0, 60),
                category: d.phase,
                decision_id: d.id,
              });
            }}
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <span className="rounded bg-stone-100 px-1.5 py-0.5 font-mono text-xs">{d.id}</span>
                <span className="ml-2 rounded bg-stone-800 px-1.5 py-0.5 text-xs text-white">{d.phase}</span>
                {d.flagged && <span className="ml-1 text-xs text-amber-700">flagged</span>}
              </div>
              <time className="text-xs text-stone-500">{new Date(d.at).toLocaleString()}</time>
            </div>
            <p className="mt-2 font-medium">{d.decision}</p>
            {(d.subject.team || d.subject.metric) && (
              <p className="mt-1 text-xs text-stone-500">
                {d.subject.team?.split('-').slice(-1)[0]}
                {d.subject.metric ? ` · ${d.subject.metric}` : ''}
                {d.subject.criterion ? ` · ${d.subject.criterion}` : ''}
              </p>
            )}
            {expanded === d.id && (
              <div className="mt-3 space-y-2 border-t border-stone-200 pt-3 text-sm text-stone-700">
                <p>
                  <strong>Why:</strong> {d.why}
                </p>
                {d.chosen && (
                  <p>
                    <strong>Chosen:</strong> {d.chosen}
                  </p>
                )}
                {d.rejected?.length ? (
                  <p>
                    <strong>Rejected:</strong> {d.rejected.join('; ')}
                  </p>
                ) : null}
                {d.held_loosely && (
                  <p>
                    <strong>Held loosely:</strong> {d.held_loosely}
                  </p>
                )}
                {d.evidence?.length ? (
                  <p>
                    <strong>Evidence:</strong>{' '}
                    <span className="font-mono text-xs">{d.evidence.join(', ')}</span>
                  </p>
                ) : null}
                <button
                  type="button"
                  className="text-xs text-stone-600 underline"
                  onClick={(e) => {
                    e.stopPropagation();
                    setChatFocus({
                      metric_id: d.subject.metric ?? 'decision',
                      team: d.subject.team,
                      label: `Decision ${d.id}`,
                      decision_id: d.id,
                    });
                  }}
                >
                  Ask chat about this decision
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
