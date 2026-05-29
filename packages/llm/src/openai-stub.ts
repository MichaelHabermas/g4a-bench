import type { CompletionParams, CompletionResult, LlmProvider } from './types.js';

export class OpenAiProviderStub implements LlmProvider {
  readonly id = 'openai';

  complete(_params: CompletionParams): Promise<CompletionResult> {
    return Promise.reject(new Error('OpenAI provider not implemented yet. Set LLM_PROVIDER=anthropic.'));
  }
}
