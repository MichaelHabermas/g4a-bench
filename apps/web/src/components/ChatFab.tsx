import { useEffect, useState } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { createChatSession, fetchChatConfig, sendChatMessage } from '../api';
import { chatFocusEventName, getChatFocus, type ChatFocus } from '../chatFocus';

export function ChatFab() {
  const [open, setOpen] = useState(false);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [context, setContext] = useState<Record<string, unknown> | null>(null);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Array<{ role: string; content: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [devMode, setDevMode] = useState(false);
  const [focus, setFocus] = useState<ChatFocus | null>(getChatFocus());
  const params = useParams();
  const location = useLocation();

  const inRun =
    params.cohort && params.week && params.runId
      ? { cohort: params.cohort, week: Number(params.week), runId: params.runId }
      : null;

  useEffect(() => {
    fetchChatConfig().then((c) => setDevMode(c.devMode)).catch(() => setDevMode(false));
  }, []);

  useEffect(() => {
    const handler = (e: Event) => setFocus((e as CustomEvent<ChatFocus | null>).detail ?? null);
    window.addEventListener(chatFocusEventName(), handler);
    return () => window.removeEventListener(chatFocusEventName(), handler);
  }, []);

  function uiContext() {
    return {
      path: location.pathname,
      focus: focus ?? undefined,
    };
  }

  useEffect(() => {
    if (!open || !inRun) return;
    createChatSession(inRun.cohort, inRun.week, inRun.runId, uiContext())
      .then((r) => {
        setSessionId(r.sessionId);
        setContext(r.context);
      })
      .catch(() => setContext(null));
  }, [open, inRun?.cohort, inRun?.week, inRun?.runId, location.pathname, focus?.metric_id, focus?.team]);

  async function send() {
    if (!sessionId || !context || !input.trim()) return;
    const userMsg = input.trim();
    setInput('');
    setMessages((m) => [...m, { role: 'user', content: userMsg }]);
    setLoading(true);
    try {
      const { reply } = await sendChatMessage(sessionId, userMsg, context, uiContext());
      setMessages((m) => [...m, { role: 'assistant', content: reply }]);
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', content: `Error: ${e}` }]);
    } finally {
      setLoading(false);
    }
  }

  function askAboutFocus() {
    if (!focus) return;
    if (focus.decision_id) {
      setInput(
        `Explain decision ${focus.decision_id} ("${focus.label}"). What evidence did we use, what alternatives were rejected, and should we trust this step?`,
      );
      return;
    }
    setInput(
      `How did we get the "${focus.label}" numbers? Why are some teams blank or showing 0%? Can you find evidence in the repos for how untyped params should be measured?`,
    );
  }

  return (
    <>
      <button
        type="button"
        aria-label="Open chat"
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-stone-900 text-white shadow-lg hover:bg-stone-800"
        onClick={() => setOpen((o) => !o)}
      >
        💬
      </button>
      {open && (
        <div className="fixed bottom-24 right-6 z-50 flex h-[min(520px,75vh)] w-[min(440px,92vw)] flex-col overflow-hidden rounded-xl border border-stone-200 bg-white shadow-2xl">
          <div className="border-b border-stone-100 px-4 py-3">
            <div className="flex items-center justify-between gap-2">
              <h3 className="font-semibold">Yardstick chat</h3>
              {devMode && (
                <span className="rounded bg-violet-100 px-2 py-0.5 text-[10px] font-bold uppercase text-violet-800">
                  dev + code
                </span>
              )}
            </div>
            <p className="text-xs text-stone-500">
              {inRun
                ? devMode
                  ? 'Artifacts, coverage gaps, and clone source snippets'
                  : 'Run artifacts and measurement index'
                : 'Open a run for full context'}
            </p>
            {focus && (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="rounded bg-amber-50 px-2 py-1 text-xs text-amber-900">
                  Focus: {focus.label}
                  {focus.team ? ` · ${focus.team.split('-').slice(-1)[0]}` : ''}
                </span>
                <button type="button" className="text-xs text-stone-600 underline" onClick={askAboutFocus}>
                  Ask about this metric
                </button>
              </div>
            )}
          </div>
          <div className="flex-1 space-y-3 overflow-y-auto p-4 text-sm">
            {!messages.length && (
              <p className="text-stone-500">
                Click a scorecard cell to focus, then ask why a metric is missing or how it was measured.
                {devMode && ' Dev mode searches team repos for counting scripts and tsconfig.'}
              </p>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={`rounded-lg px-3 py-2 ${m.role === 'user' ? 'ml-8 bg-stone-100' : 'mr-8 bg-amber-50'}`}
              >
                {m.content}
              </div>
            ))}
            {loading && <p className="text-stone-400">Thinking…</p>}
          </div>
          <div className="flex gap-2 border-t border-stone-100 p-3">
            <input
              className="flex-1 rounded-md border border-stone-200 px-3 py-2 text-sm"
              placeholder={focus ? `Ask about ${focus.label}…` : 'Ask about this data…'}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void send()}
              disabled={!sessionId}
            />
            <button
              type="button"
              className="rounded-md bg-stone-900 px-3 py-2 text-sm text-white disabled:opacity-50"
              onClick={() => void send()}
              disabled={loading || !sessionId}
            >
              Send
            </button>
          </div>
        </div>
      )}
    </>
  );
}
