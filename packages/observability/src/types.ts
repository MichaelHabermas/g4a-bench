export interface TraceMeta {
  name: string;
  kind: 'measurement' | 'chat' | 'sync' | 'baseline';
  runId?: string;
  sessionId?: number;
  tags?: Record<string, string>;
}

export interface TraceHandle {
  traceId: string;
  end(outcome?: { level?: 'DEFAULT' | 'ERROR'; output?: unknown }): void;
  generation(input: {
    name: string;
    model: string;
    input: unknown;
    output: unknown;
    usage?: { input?: number; output?: number };
  }): void;
}

export interface TraceProvider {
  readonly id: string;
  startTrace(meta: TraceMeta): TraceHandle;
}
