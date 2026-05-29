import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { mkdtempSync, rmSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { logDecision, readDecisionLog, filterDecisions, getDecisionById } from './index.js';

describe('decision log', () => {
  let runDir: string;

  beforeEach(() => {
    runDir = mkdtempSync(join(tmpdir(), 'yardstick-dec-'));
  });

  afterEach(() => {
    rmSync(runDir, { recursive: true, force: true });
  });

  it('appends jsonl entries', () => {
    logDecision(runDir, {
      phase: 'verify',
      subject: { team: 'team-a', metric: 'untyped' },
      decision: 'verified_remaining: 100',
      chosen: 'typescript-diagnostics',
      rejected: ['eslint'],
      why: 'AST is authoritative.',
    });
    const entries = readDecisionLog(runDir);
    expect(entries).toHaveLength(1);
    expect(entries[0]!.id).toMatch(/^dec-verify-/);
    expect(getDecisionById(runDir, entries[0]!.id)?.decision).toContain('100');
  });

  it('filters by phase and team', () => {
    logDecision(runDir, { phase: 'clone', subject: { team: 'a' }, decision: 'cloned', why: 'ok' });
    logDecision(runDir, { phase: 'verify', subject: { team: 'b' }, decision: 'verified', why: 'ok' });
    const filtered = filterDecisions(readDecisionLog(runDir), { phase: 'clone' });
    expect(filtered).toHaveLength(1);
    expect(filtered[0]!.subject.team).toBe('a');
  });
});
