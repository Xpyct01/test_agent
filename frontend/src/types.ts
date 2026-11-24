// Shapes of what the trip planner streams over AG-UI.

export type Mode = 'watch' | 'play';

export type ParticipantId = 'human_a' | 'agent_a' | 'agent_b' | 'human_b';

export type RunStatus =
  | 'idle'
  | 'running'
  | 'awaiting_input'
  | 'converged'
  | 'stalled'
  | 'timeout'
  | 'failed';

export interface Incident {
  tick: number;
  type: 'tool_failure' | 'retry' | 'message_rejected' | 'participant_error';
  participant: string;
  [key: string]: unknown;
}

export interface TripPlan {
  booking_id: string;
  trail_id: string;
  trail_name: string;
  date: string;
  start_time: string;
  guide_name: string;
  weather_summary: string;
  gear_to_bring: string[];
  gear_to_rent: string[];
  gear_to_buy: string[];
  notes: string[];
}

export interface LiveMetrics {
  llmCalls: number;
  promptTokens: number;
  completionTokens: number;
  toolCalls: number;
  injectedFailures: number;
  retries: number;
}

/** Shared state the backend keeps in sync with STATE_SNAPSHOT / STATE_DELTA. */
export interface TripState {
  mode?: Mode;
  scenario?: string;
  runId?: string | null;
  status?: RunStatus;
  tick?: number;
  planningDate?: string | null;
  finalPlan?: TripPlan | null;
  outcomeKey?: string | null;
  metrics?: LiveMetrics;
  incidents?: Incident[];
  summary?: { wall_time_s: number; estimated_cost_usd: number } & Record<
    string,
    unknown
  >;
}

export type TimelineItem =
  | { kind: 'tick'; key: string; tick: number }
  | {
      kind: 'message';
      key: string;
      sender: ParticipantId;
      recipient: ParticipantId;
      tick?: number;
      text: string;
    }
  | {
      kind: 'tool';
      key: string;
      name: string;
      participant: ParticipantId;
      tick: number;
      args: string;
      result?: string;
      isError?: boolean;
    }
  | { kind: 'incident'; key: string; incident: Incident }
  | { kind: 'error'; key: string; text: string };
