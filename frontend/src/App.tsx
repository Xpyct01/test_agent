import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useTripAgent } from './useTripAgent';
import type {
  Incident,
  Mode,
  ParticipantId,
  TimelineItem,
  TripState,
} from './types';

const PARTICIPANTS: Record<ParticipantId, { label: string; role: string }> = {
  human_a: { label: 'Human A', role: 'Customer' },
  agent_a: { label: 'Agent A', role: 'Customer assistant' },
  agent_b: { label: 'Agent B', role: 'Operations assistant' },
  human_b: { label: 'Human B', role: 'Mountain guide' },
};
const ORDER: ParticipantId[] = ['human_a', 'agent_a', 'agent_b', 'human_b'];

const STATUS_LABEL: Record<string, string> = {
  idle: 'Not started',
  running: 'Running',
  awaiting_input: 'Your turn',
  converged: 'Converged',
  stalled: 'Stalled',
  timeout: 'Timed out',
  failed: 'Failed',
};

export default function App() {
  const { timeline, state, streaming, watch, say, reset, stop } = useTripAgent();
  const [mode, setMode] = useState<Mode>('watch');
  const [scenario, setScenario] = useState('');
  const status = state.status ?? 'idle';
  const active = lastSpeaker(timeline, streaming);

  const switchMode = (next: Mode) => {
    if (next === mode) return;
    reset();
    setMode(next);
  };

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="brand-mark" aria-hidden>▲</span>
          <div>
            <h1>Picos de Europa trip planner</h1>
            <p>Two LangGraph agents, two humans, streamed over AG-UI</p>
          </div>
        </div>
        <div className="controls">
          <div className="segmented" role="tablist" aria-label="Mode">
            <button
              role="tab"
              aria-selected={mode === 'watch'}
              className={mode === 'watch' ? 'on' : ''}
              onClick={() => switchMode('watch')}
            >
              Watch a simulation
            </button>
            <button
              role="tab"
              aria-selected={mode === 'play'}
              className={mode === 'play' ? 'on' : ''}
              onClick={() => switchMode('play')}
            >
              Play the customer
            </button>
          </div>
          <input
            className="scenario"
            placeholder="scenario (default)"
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
            disabled={streaming || status !== 'idle'}
            aria-label="Scenario"
          />
          {mode === 'watch' && (
            <button
              className="primary"
              disabled={streaming}
              onClick={() => watch(scenario.trim() || undefined)}
            >
              {status === 'idle' ? 'Run simulation' : 'Run again'}
            </button>
          )}
          {streaming ? (
            <button onClick={stop}>Stop</button>
          ) : (
            status !== 'idle' && <button onClick={reset}>Clear</button>
          )}
        </div>
      </header>

      <Topology active={active} mode={mode} />

      <main className="body">
        <section className="timeline-col">
          <Timeline items={timeline} mode={mode} status={status} streaming={streaming} />
          {mode === 'play' && (
            <Composer
              state={state}
              streaming={streaming}
              onSend={(text, complete) =>
                say(text, { complete, scenario: scenario.trim() || undefined })
              }
            />
          )}
        </section>
        <Sidebar state={state} streaming={streaming} />
      </main>
    </div>
  );
}

function lastSpeaker(items: TimelineItem[], streaming: boolean): ParticipantId | null {
  if (!streaming) return null;
  for (let i = items.length - 1; i >= 0; i--) {
    const item = items[i];
    if (item.kind === 'message') return item.sender;
    if (item.kind === 'tool') return item.participant;
  }
  return null;
}

function Topology({ active, mode }: { active: ParticipantId | null; mode: Mode }) {
  return (
    <nav className="topology" aria-label="Who talks to whom">
      {ORDER.map((id, i) => (
        <div className="topo-item" key={id}>
          <div className={`node ${id} ${active === id ? 'active' : ''}`}>
            <span className="node-label">{PARTICIPANTS[id].label}</span>
            <span className="node-role">
              {id === 'human_a' && mode === 'play' ? 'You' : PARTICIPANTS[id].role}
            </span>
          </div>
          {i < ORDER.length - 1 && <span className="link" aria-hidden>⇄</span>}
        </div>
      ))}
    </nav>
  );
}

function Timeline({
  items,
  mode,
  status,
  streaming,
}: {
  items: TimelineItem[];
  mode: Mode;
  status: string;
  streaming: boolean;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [items.length]);

  if (items.length === 0) {
    return (
      <div className="timeline empty">
        {mode === 'watch' ? (
          <p>
            Press <b>Run simulation</b> to watch both agents and both simulated
            humans plan a guided hike. Each run takes about 30–60 seconds.
          </p>
        ) : (
          <p>
            You are <b>Human A</b>, the customer. Tell Agent A what hike you
            want: your age, fitness, any injuries, the views you like, and
            the gear you own. Agent B and the guide work behind the scenes.
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="timeline" aria-live="polite">
      {items.map((item) => (
        <TimelineRow key={item.key} item={item} mode={mode} />
      ))}
      {streaming && status !== 'awaiting_input' && (
        <div className="thinking">
          <span className="dot" />
          <span className="dot" />
          <span className="dot" />
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}

function who(id: ParticipantId, mode: Mode) {
  return id === 'human_a' && mode === 'play' ? 'You' : PARTICIPANTS[id]?.label ?? id;
}

function TimelineRow({ item, mode }: { item: TimelineItem; mode: Mode }) {
  switch (item.kind) {
    case 'tick':
      return (
        <div className="tick">
          <span>tick {item.tick}</span>
        </div>
      );
    case 'message': {
      const side = ORDER.indexOf(item.sender) < ORDER.indexOf(item.recipient) ? 'right' : 'left';
      return (
        <div className={`msg ${item.sender} ${side}`}>
          <div className="msg-head">
            <span className={`chip ${item.sender}`}>{who(item.sender, mode)}</span>
            <span className="arrow">→</span>
            <span className={`chip ghost ${item.recipient}`}>{who(item.recipient, mode)}</span>
          </div>
          <div className="msg-body">{item.text}</div>
        </div>
      );
    }
    case 'tool':
      return <ToolCard item={item} />;
    case 'incident':
      return <IncidentRow incident={item.incident} />;
    case 'error':
      return <div className="error-row">⚠ {item.text}</div>;
  }
}

function pretty(json: string | undefined): string {
  if (!json) return '';
  try {
    return JSON.stringify(JSON.parse(json), null, 2);
  } catch {
    return json;
  }
}

function ToolCard({ item }: { item: Extract<TimelineItem, { kind: 'tool' }> }) {
  const pending = item.result === undefined;
  const state = pending ? 'pending' : item.isError ? 'error' : 'ok';
  return (
    <details className={`tool ${item.participant} ${state}`}>
      <summary>
        <span className={`chip small ${item.participant}`}>
          {PARTICIPANTS[item.participant]?.label ?? item.participant}
        </span>
        <code className="tool-name">{item.name}</code>
        <span className={`tool-state ${state}`}>
          {pending ? 'running…' : item.isError ? 'error' : 'ok'}
        </span>
      </summary>
      <div className="tool-io">
        <div>
          <h4>Arguments</h4>
          <pre>{pretty(item.args) || '{}'}</pre>
        </div>
        {!pending && (
          <div>
            <h4>Result</h4>
            <pre>{pretty(item.result)}</pre>
          </div>
        )}
      </div>
    </details>
  );
}

function describeIncident(incident: Incident): string {
  const d = incident as Record<string, unknown>;
  switch (incident.type) {
    case 'tool_failure':
      return `Injected failure in ${d.action} (attempt ${d.attempt}${d.final ? ', retries exhausted' : ''})`;
    case 'retry':
      return `Retrying ${d.action}: attempt ${d.next_attempt} in ${d.delay_s}s`;
    case 'message_rejected':
      return `${incident.participant} → ${d.recipient} rejected by the bus`;
    case 'participant_error':
      return `${incident.participant} crashed: ${d.error}`;
  }
}

function IncidentRow({ incident }: { incident: Incident }) {
  return (
    <div className={`incident ${incident.type}`}>
      <span className="incident-icon" aria-hidden>
        {incident.type === 'retry' ? '↻' : '⚡'}
      </span>
      {describeIncident(incident)}
    </div>
  );
}

function Composer({
  state,
  streaming,
  onSend,
}: {
  state: TripState;
  streaming: boolean;
  onSend: (text: string, complete: boolean) => void;
}) {
  const [text, setText] = useState('');
  const status = state.status ?? 'idle';
  const canSend = !streaming && (status === 'idle' || status === 'awaiting_input');
  const ended = ['converged', 'stalled', 'timeout', 'failed'].includes(status);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim() || !canSend) return;
    onSend(text.trim(), false);
    setText('');
  };

  if (ended) {
    return (
      <div className="composer ended">
        The run ended: <b>{STATUS_LABEL[status]}</b>. Press <b>Clear</b> to start again.
      </div>
    );
  }

  return (
    <form className="composer" onSubmit={submit}>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) submit(e);
        }}
        placeholder={
          status === 'idle'
            ? "Hi! I'd like a guided one-day hike in the next week…"
            : canSend
              ? 'Reply to Agent A…'
              : 'The agents are working…'
        }
        disabled={!canSend}
        rows={2}
        aria-label="Message to Agent A"
      />
      <div className="composer-actions">
        {state.finalPlan && (
          <button
            type="button"
            className="accept"
            disabled={!canSend}
            onClick={() => onSend(text.trim() || 'Thanks, that plan works for me!', true)}
          >
            Accept plan &amp; finish
          </button>
        )}
        <button type="submit" className="primary" disabled={!canSend || !text.trim()}>
          Send
        </button>
      </div>
    </form>
  );
}

function Sidebar({ state, streaming }: { state: TripState; streaming: boolean }) {
  const status = state.status ?? 'idle';
  const m = state.metrics;
  const tokens = m ? m.promptTokens + m.completionTokens : 0;
  return (
    <aside className="sidebar">
      <div className="card">
        <div className="status-row">
          <span className={`status ${status}`}>
            {streaming && status === 'running' && <span className="pulse" />}
            {STATUS_LABEL[status] ?? status}
          </span>
          <span className="tick-badge">tick {state.tick ?? 0}</span>
        </div>
        {state.planningDate && (
          <p className="muted">Planning from {state.planningDate}</p>
        )}
        {state.runId && <p className="muted mono">{state.runId}</p>}
      </div>

      <div className="card">
        <h3>Live metrics</h3>
        <dl className="metrics">
          <Metric label="LLM calls" value={m?.llmCalls ?? 0} />
          <Metric label="Tokens" value={tokens.toLocaleString()} />
          <Metric label="Tool calls" value={m?.toolCalls ?? 0} />
          <Metric label="Injected faults" value={m?.injectedFailures ?? 0} />
          <Metric label="Retries" value={m?.retries ?? 0} />
          {state.summary && (
            <>
              <Metric label="Wall time" value={`${state.summary.wall_time_s}s`} />
              <Metric
                label="Est. cost"
                value={`$${state.summary.estimated_cost_usd.toFixed(4)}`}
              />
            </>
          )}
        </dl>
      </div>

      <PlanCard state={state} />
    </aside>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function PlanCard({ state }: { state: TripState }) {
  const plan = state.finalPlan;
  if (!plan) {
    return (
      <div className="card plan empty">
        <h3>Final plan</h3>
        <p className="muted">Appears when Agent A delivers a checked plan.</p>
      </div>
    );
  }
  return (
    <div className="card plan">
      <h3>Final plan</h3>
      <p className="plan-trail">{plan.trail_name}</p>
      <p className="plan-when">
        {plan.date} · {plan.start_time} · with {plan.guide_name}
      </p>
      <p className="muted">{plan.weather_summary}</p>
      <GearList title="Rent" items={plan.gear_to_rent} />
      <GearList title="Bring" items={plan.gear_to_bring} />
      <GearList title="Buy" items={plan.gear_to_buy} />
      {plan.notes.length > 0 && (
        <ul className="notes">
          {plan.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      <p className="mono muted">Booking {plan.booking_id}</p>
    </div>
  );
}

function GearList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="gear">
      <span className="gear-title">{title}</span>
      <div className="gear-items">
        {items.map((g) => (
          <span key={g} className="gear-item">
            {g.replace(/_/g, ' ')}
          </span>
        ))}
      </div>
    </div>
  );
}
