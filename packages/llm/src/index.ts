import { AnthropicProvider } from './anthropic.js';
import { OpenAiProviderStub } from './openai-stub.js';
import type { LlmProvider } from './types.js';

export * from './types.js';
export { AnthropicProvider } from './anthropic.js';
export { OpenAiProviderStub } from './openai-stub.js';

export function createLlmProvider(): LlmProvider {
  const id = (process.env.LLM_PROVIDER ?? 'anthropic').toLowerCase();
  if (id === 'openai') return new OpenAiProviderStub();
  return new AnthropicProvider();
}
