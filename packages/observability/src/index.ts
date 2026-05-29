import { LangfuseTraceProvider } from './langfuse.js';
import { NoopTraceProvider } from './noop.js';
import type { TraceProvider } from './types.js';

export * from './types.js';
export { LangfuseTraceProvider } from './langfuse.js';
export { NoopTraceProvider } from './noop.js';

export function createTraceProvider(): TraceProvider {
  const mode = (process.env.TRACE_PROVIDER ?? 'langfuse').toLowerCase();
  if (mode === 'noop') return new NoopTraceProvider();
  try {
    if (process.env.LANGFUSE_PUBLIC_KEY && process.env.LANGFUSE_SECRET_KEY) {
      return new LangfuseTraceProvider();
    }
  } catch {
    /* fall through */
  }
  return new NoopTraceProvider();
}
