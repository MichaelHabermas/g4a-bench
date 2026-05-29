import { z } from 'zod';

export const TrustTierSchema = z.enum([
  'claimed',
  'reported-math',
  'artifact-backed',
  'verified',
]);

export const BaselineConfigSchema = z.object({
  upstream_repo_url: z.string().url(),
  ref_policy: z.literal('first-commit'),
});

export const RunStateSchema = z.object({
  run_id: z.string(),
  run_dir: z.string(),
  updated_at: z.string(),
  agent_measurements: z.record(
    z.object({
      artifact: z.string().optional(),
      completed_at: z.string().optional(),
      status: z.string().optional(),
      run_mode: z.string().nullable().optional(),
      replay_outcome: z.string().nullable().optional(),
    }),
  ),
  ledger_tail: z.array(z.record(z.unknown())).optional(),
  yardstick_ids: z.array(z.string()).optional(),
});

export const MeasurementResultSchema = z.object({
  status: z.string(),
  method: z.string().optional(),
  method_rationale: z.string().optional(),
  verified_values: z.record(z.unknown()).optional(),
  confidence: z.string().optional(),
  qualitative_judgment: z.string().optional(),
  self_report_comparison: z.string().optional(),
  run_mode: z.enum(['establish', 'replay', 'challenge']).optional(),
  replay_outcome: z.string().optional(),
  yardstick_update_proposed: z.boolean().optional(),
  yardstick_update_rationale: z.string().optional(),
  commands_summary: z.string().optional(),
  blockers: z.string().optional(),
  held_loosely: z.string().optional(),
});

export const AgentMeasurementSchema = z.object({
  repo: z.string(),
  criterion_id: z.string().optional(),
  completed_at: z.string().optional(),
  result: MeasurementResultSchema,
  _artifact: z.string().optional(),
});

export type TrustTier = z.infer<typeof TrustTierSchema>;
export type RunState = z.infer<typeof RunStateSchema>;
export type AgentMeasurement = z.infer<typeof AgentMeasurementSchema>;
export type BaselineConfig = z.infer<typeof BaselineConfigSchema>;
