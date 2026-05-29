import { randomUUID } from 'node:crypto';
import type { TraceHandle, TraceMeta, TraceProvider } from './types.js';

export class NoopTraceProvider implements TraceProvider {
  readonly id = 'noop';

  startTrace(_meta: TraceMeta): TraceHandle {
    const traceId = randomUUID();
    return {
      traceId,
      end() {},
      generation() {},
    };
  }
}
