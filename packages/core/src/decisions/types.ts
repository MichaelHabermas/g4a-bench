export type DecisionPhase =
  | 'clone'
  | 'verify'
  | 'sync'
  | 'agent'
  | 'yardstick'
  | 'baseline'
  | 'orchestrator'
  | 'chat';

export interface DecisionSubject {
  team?: string;
  criterion?: string;
  metric?: string;
  job_id?: number;
}

export interface DecisionEntry {
  id: string;
  at: string;
  phase: DecisionPhase;
  subject: DecisionSubject;
  decision: string;
  chosen?: string;
  rejected?: string[];
  why: string;
  evidence?: string[];
  confidence?: 'high' | 'medium' | 'low';
  held_loosely?: string;
  trace_id?: string;
  flagged?: boolean;
}

export interface DecisionFilter {
  phase?: DecisionPhase;
  team?: string;
  criterion?: string;
  flaggedOnly?: boolean;
  limit?: number;
}
