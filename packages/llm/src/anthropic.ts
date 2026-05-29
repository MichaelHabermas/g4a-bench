import Anthropic from '@anthropic-ai/sdk';
import type { CompletionParams, CompletionResult, LlmProvider } from './types.js';

export class AnthropicProvider implements LlmProvider {
  readonly id = 'anthropic';
  private client: Anthropic;
  private defaultModel: string;

  constructor(apiKey?: string, defaultModel?: string) {
    const key = apiKey ?? process.env.ANTHROPIC_API_KEY;
    if (!key) throw new Error('ANTHROPIC_API_KEY not configured');
    this.client = new Anthropic({ apiKey: key });
    this.defaultModel = defaultModel ?? process.env.ANTHROPIC_MODEL ?? 'claude-sonnet-4-20250514';
  }

  async complete(params: CompletionParams): Promise<CompletionResult> {
    const system = params.messages.find((m) => m.role === 'system')?.content;
    const messages = params.messages
      .filter((m) => m.role !== 'system')
      .map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content }));

    const res = await this.client.messages.create({
      model: params.model ?? this.defaultModel,
      max_tokens: params.maxTokens ?? 4096,
      temperature: params.temperature ?? 0.3,
      system,
      messages,
    });

    const text = res.content
      .filter((b) => b.type === 'text')
      .map((b) => (b.type === 'text' ? b.text : ''))
      .join('');

    return {
      content: text,
      model: res.model,
      usage: {
        inputTokens: res.usage.input_tokens,
        outputTokens: res.usage.output_tokens,
      },
    };
  }
}
