import { Langfuse } from 'langfuse';
import { randomUUID } from 'node:crypto';
import type { TraceHandle, TraceMeta, TraceProvider } from './types.js';

export class LangfuseTraceProvider implements TraceProvider {
  readonly id = 'langfuse';
  private client: Langfuse;

  constructor() {
    const publicKey = process.env.LANGFUSE_PUBLIC_KEY;
    const secretKey = process.env.LANGFUSE_SECRET_KEY;
    if (!publicKey || !secretKey) {
      throw new Error('LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY required for Langfuse provider');
    }
    this.client = new Langfuse({
      publicKey,
      secretKey,
      baseUrl: process.env.LANGFUSE_BASE_URL,
    });
  }

  startTrace(meta: TraceMeta): TraceHandle {
    const trace = this.client.trace({
      id: randomUUID(),
      name: meta.name,
      metadata: { kind: meta.kind, runId: meta.runId, sessionId: meta.sessionId, ...meta.tags },
    });

    return {
      traceId: trace.id,
      end(outcome) {
        trace.update({ output: outcome?.output });
        if (outcome?.level === 'ERROR') {
          trace.update({ tags: ['error'] });
        }
      },
      generation(input) {
        trace.generation({
          name: input.name,
          model: input.model,
          input: input.input,
          output: input.output,
          usage: {
            input: input.usage?.input,
            output: input.usage?.output,
          },
        });
      },
    };
  }
}
