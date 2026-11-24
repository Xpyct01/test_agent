import { useCallback, useRef, useState } from 'react';
import {
  EventType,
  HttpAgent,
  type BaseEvent,
  type StateDeltaEvent,
  type TextMessageContentEvent,
  type TextMessageStartEvent,
  type ToolCallArgsEvent,
  type ToolCallResultEvent,
  type ToolCallStartEvent,
  type RunErrorEvent,
} from '@ag-ui/client';
import type {
  Incident,
  Mode,
  ParticipantId,
  TimelineItem,
  TripState,
} from './types';

const AGUI_URL = import.meta.env.VITE_AGUI_URL ?? '/agui';

function newAgent(): HttpAgent {
  return new HttpAgent({ url: AGUI_URL, threadId: crypto.randomUUID() });
}

/**
 * Drives the trip planner's AG-UI agent and turns its event stream into a
 * timeline (ticks, messages, tool calls, incidents) plus the shared state.
 */
export function useTripAgent() {
  const agentRef = useRef<HttpAgent>(newAgent());
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [state, setState] = useState<TripState>({ status: 'idle' });
  const [streaming, setStreaming] = useState(false);

  const push = useCallback((item: TimelineItem) => {
    setTimeline((items) => [...items, item]);
  }, []);

  const update = useCallback(
    <K extends TimelineItem['kind']>(
      key: string,
      patch: (item: Extract<TimelineItem, { kind: K }>) => TimelineItem,
    ) => {
      setTimeline((items) =>
        items.map((item) =>
          item.key === key
            ? patch(item as Extract<TimelineItem, { kind: K }>)
            : item,
        ),
      );
    },
    [],
  );

  const onEvent = useCallback(
    (event: BaseEvent) => {
      switch (event.type) {
        case EventType.STEP_STARTED: {
          const tick = Number(
            (event as BaseEvent & { stepName: string }).stepName.split(' ')[1],
          );
          setTimeline((items) =>
            items.some((i) => i.kind === 'tick' && i.tick === tick)
              ? items
              : [...items, { kind: 'tick', key: `tick-${tick}`, tick }],
          );
          break;
        }
        case EventType.TEXT_MESSAGE_START: {
          const e = event as TextMessageStartEvent & {
            name?: string;
            metadata?: { recipient?: string; tick?: number };
          };
          push({
            kind: 'message',
            key: e.messageId,
            sender: (e.name ?? 'agent_a') as ParticipantId,
            recipient: (e.metadata?.recipient ?? 'human_a') as ParticipantId,
            tick: e.metadata?.tick,
            text: '',
          });
          break;
        }
        case EventType.TEXT_MESSAGE_CONTENT: {
          const e = event as TextMessageContentEvent;
          update<'message'>(e.messageId, (item) => ({
            ...item,
            text: item.text + e.delta,
          }));
          break;
        }
        case EventType.TOOL_CALL_START: {
          const e = event as ToolCallStartEvent & {
            metadata?: { participant?: string; tick?: number };
          };
          push({
            kind: 'tool',
            key: e.toolCallId,
            name: e.toolCallName,
            participant: (e.metadata?.participant ?? 'agent_a') as ParticipantId,
            tick: e.metadata?.tick ?? 0,
            args: '',
          });
          break;
        }
        case EventType.TOOL_CALL_ARGS: {
          const e = event as ToolCallArgsEvent;
          update<'tool'>(e.toolCallId, (item) => ({
            ...item,
            args: item.args + e.delta,
          }));
          break;
        }
        case EventType.TOOL_CALL_RESULT: {
          const e = event as ToolCallResultEvent & {
            metadata?: { isError?: boolean };
          };
          update<'tool'>(e.toolCallId, (item) => ({
            ...item,
            result: typeof e.content === 'string' ? e.content : JSON.stringify(e.content),
            isError: Boolean(e.metadata?.isError),
          }));
          break;
        }
        case EventType.STATE_DELTA: {
          for (const op of (event as StateDeltaEvent).delta) {
            if (op.op === 'add' && op.path === '/incidents/-') {
              const incident = op.value as Incident;
              push({
                kind: 'incident',
                key: crypto.randomUUID(),
                incident,
              });
            }
          }
          break;
        }
        case EventType.RUN_ERROR: {
          push({
            kind: 'error',
            key: crypto.randomUUID(),
            text: (event as RunErrorEvent).message,
          });
          setState((s) => ({ ...s, status: 'failed' }));
          break;
        }
      }
    },
    [push, update],
  );

  const run = useCallback(
    async (mode: Mode, extraProps: Record<string, unknown> = {}) => {
      setStreaming(true);
      try {
        await agentRef.current.runAgent(
          { forwardedProps: { mode, ...extraProps } },
          {
            onEvent: ({ event }) => onEvent(event),
            onStateChanged: ({ state: next }) =>
              setState({ ...(next as TripState) }),
            onRunFailed: ({ error }) => {
              push({ kind: 'error', key: crypto.randomUUID(), text: error.message });
              setState((s) => ({ ...s, status: 'failed' }));
            },
          },
        );
      } catch (error) {
        // runAgent rejects on transport errors; onRunFailed already shows it.
        console.error(error);
      } finally {
        setStreaming(false);
      }
    },
    [onEvent, push],
  );

  /** Starts a fresh thread: a new simulation on the next request. */
  const reset = useCallback(() => {
    agentRef.current.abortRun();
    agentRef.current = newAgent();
    setTimeline([]);
    setState({ status: 'idle' });
  }, []);

  /** Watch mode: plays one fully simulated run. */
  const watch = useCallback(
    async (scenario?: string) => {
      reset();
      await run('watch', scenario ? { scenario } : {});
    },
    [reset, run],
  );

  /** Play mode: sends one message as Human A (the customer). */
  const say = useCallback(
    async (text: string, opts: { complete?: boolean; scenario?: string } = {}) => {
      const id = crypto.randomUUID();
      agentRef.current.addMessage({ id, role: 'user', content: text });
      push({
        kind: 'message',
        key: id,
        sender: 'human_a',
        recipient: 'agent_a',
        text,
      });
      setState((s) => ({ ...s, status: 'running' }));
      await run('play', {
        conversationComplete: Boolean(opts.complete),
        ...(opts.scenario ? { scenario: opts.scenario } : {}),
      });
    },
    [push, run],
  );

  const stop = useCallback(() => {
    agentRef.current.abortRun();
  }, []);

  return { timeline, state, streaming, watch, say, reset, stop };
}
