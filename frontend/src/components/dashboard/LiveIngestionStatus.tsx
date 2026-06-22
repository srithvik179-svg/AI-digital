'use client';

/**
 * Phase 46 — Live Ingestion Status Dashboard.
 *
 * Displays real-time pipeline health for all registered telemetry agents:
 *   - Agent connection cards (online/offline, OS source badge, tick rate)
 *   - SSE stream indicator (real-time event counter from GET /live-stream/sse)
 *   - Source breakdown table (mac / windows-ohm / windows-wmi / linux)
 *   - Pipeline health sparkline (ticks received per 5 s window)
 *   - Agent log tail (last 20 SSE events)
 *
 * Refresh strategy: polls /live-stream/status every 5 s for agent list,
 * subscribes to /live-stream/sse (EventSource) for real-time tick stream.
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AgentStatus {
  device_id:     string;
  source:        string;
  active:        boolean;
  ticks_received:number;
  last_heartbeat: string;
  age_seconds:   number;
  registered_at: string;
}

interface PipelineStatus {
  total_agents:   number;
  active_agents:  number;
  inactive_agents:number;
  agents:         AgentStatus[];
}

interface SSEEvent {
  timestamp:      string;
  device_id:      string;
  cpu_usage:      number;
  cpu_temperature:number;
  battery_level:  number;
  power_source:   string;
  source:         string;
  tick:           number;
  collection_latency_ms: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const API_BASE   = 'http://localhost:8000/api/v1';
const POLL_MS    = 5000;
const LOG_SIZE   = 20;
const SPARK_SIZE = 30;

const SOURCE_META: Record<string, { label: string; color: string; icon: string }> = {
  mac:          { label: 'macOS',          color: '#a78bfa', icon: '🍎' },
  'windows-ohm':{ label: 'Windows (OHM)',  color: '#34d399', icon: '🪟' },
  'windows-wmi':{ label: 'Windows (WMI)',  color: '#6ee7b7', icon: '🪟' },
  linux:        { label: 'Linux',          color: '#f59e0b', icon: '🐧' },
  unknown:      { label: 'Unknown',        color: '#94a3b8', icon: '❓' },
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const SourceBadge: React.FC<{ source: string }> = ({ source }) => {
  const meta = SOURCE_META[source] ?? SOURCE_META.unknown;
  return (
    <span
      style={{
        backgroundColor: meta.color + '22',
        border: `1px solid ${meta.color}`,
        color: meta.color,
        fontSize: '0.7rem',
        fontWeight: 600,
        padding: '2px 8px',
        borderRadius: 9999,
        letterSpacing: '0.05em',
      }}
    >
      {meta.icon} {meta.label}
    </span>
  );
};

const StatusDot: React.FC<{ active: boolean }> = ({ active }) => (
  <span
    style={{
      display: 'inline-block',
      width: 10,
      height: 10,
      borderRadius: '50%',
      backgroundColor: active ? '#10b981' : '#ef4444',
      boxShadow: active ? '0 0 6px #10b98188' : 'none',
      animation: active ? 'pulse-dot 1.8s ease-in-out infinite' : 'none',
    }}
  />
);

const Sparkline: React.FC<{ data: number[]; color: string; height: number }> = ({
  data, color, height,
}) => {
  const max = Math.max(...data, 1);
  const w   = 200;
  const pts = data.map((v, i) => {
    const x = (i / (SPARK_SIZE - 1)) * w;
    const y = height - (v / max) * height;
    return `${x},${y}`;
  }).join(' ');
  return (
    <svg width={w} height={height} style={{ display: 'block', overflow: 'visible' }}>
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
};

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

const LiveIngestionStatus: React.FC = () => {
  const [status, setStatus]         = useState<PipelineStatus | null>(null);
  const [sseEvents, setSseEvents]   = useState<SSEEvent[]>([]);
  const [sseCount, setSseCount]     = useState(0);
  const [sseConnected, setSseConnected] = useState(false);
  const [ticksPerWindow, setTicksPerWindow] = useState<number[]>(Array(SPARK_SIZE).fill(0));
  const [windowBuffer, setWindowBuffer]     = useState(0);
  const logRef   = useRef<HTMLDivElement>(null);
  const windowTs = useRef<number>(Date.now());

  // ── Poll pipeline status ──────────────────────────────────────────────────
  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/live-stream/status`);
      if (res.ok) setStatus(await res.json());
    } catch {/* backend may be unreachable */}
  }, []);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, POLL_MS);
    return () => clearInterval(id);
  }, [fetchStatus]);

  // ── SSE stream subscription ───────────────────────────────────────────────
  useEffect(() => {
    let es: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      es = new EventSource(`${API_BASE}/live-stream/sse`);

      es.addEventListener('connected', () => setSseConnected(true));

      es.addEventListener('telemetry_tick', (e) => {
        try {
          const data = JSON.parse(e.data) as SSEEvent;
          setSseCount(c => c + 1);
          setWindowBuffer(b => b + 1);
          setSseEvents(prev => {
            const next = [{ ...data, timestamp: new Date().toISOString() }, ...prev];
            return next.slice(0, LOG_SIZE);
          });
        } catch {/* malformed */}
      });

      es.onerror = () => {
        setSseConnected(false);
        es?.close();
        reconnectTimer = setTimeout(connect, 5000);
      };
    }

    connect();
    return () => {
      es?.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, []);

  // ── Sparkline window accumulator (5 s buckets) ────────────────────────────
  useEffect(() => {
    const id = setInterval(() => {
      const elapsed = Date.now() - windowTs.current;
      if (elapsed >= 5000) {
        setTicksPerWindow(prev => {
          const next = [...prev.slice(1), windowBuffer];
          return next;
        });
        setWindowBuffer(0);
        windowTs.current = Date.now();
      }
    }, 1000);
    return () => clearInterval(id);
  }, [windowBuffer]);

  // ── Auto-scroll event log ─────────────────────────────────────────────────
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = 0;
  }, [sseEvents]);

  // ── Derived stats ─────────────────────────────────────────────────────────
  const sourceCounts = (status?.agents ?? []).reduce<Record<string, number>>((acc, a) => {
    acc[a.source] = (acc[a.source] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div id="live-ingestion-status-panel" style={{
      background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
      borderRadius: 16,
      border: '1px solid #334155',
      padding: '24px',
      fontFamily: '"Inter", "SF Pro Display", system-ui, sans-serif',
      color: '#e2e8f0',
    }}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10,
          background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 20,
        }}>📡</div>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700, color: '#f1f5f9' }}>
            Live Ingestion Pipeline
          </h2>
          <p style={{ margin: 0, fontSize: '0.78rem', color: '#64748b' }}>
            Phase 46 — Real-Time Telemetry Agent Registry
          </p>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <StatusDot active={sseConnected} />
          <span style={{ fontSize: '0.8rem', color: sseConnected ? '#10b981' : '#ef4444' }}>
            {sseConnected ? 'SSE Connected' : 'SSE Disconnected'}
          </span>
        </div>
      </div>

      {/* ── KPI Row ─────────────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'Total Agents',   value: status?.total_agents   ?? '—', color: '#6366f1' },
          { label: 'Online',         value: status?.active_agents  ?? '—', color: '#10b981' },
          { label: 'Offline',        value: status?.inactive_agents ?? '—', color: '#ef4444' },
          { label: 'SSE Events',     value: sseCount,                        color: '#f59e0b' },
        ].map(({ label, value, color }) => (
          <div key={label} style={{
            background: '#1e293b',
            borderRadius: 12,
            padding: '14px 16px',
            border: `1px solid ${color}33`,
            textAlign: 'center',
          }}>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color }}>{value}</div>
            <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: 2 }}>{label}</div>
          </div>
        ))}
      </div>

      {/* ── Sparkline + Source breakdown ──────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>

        {/* Tick rate sparkline */}
        <div style={{ background: '#0f172a', borderRadius: 12, padding: 16, border: '1px solid #1e293b' }}>
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: 8, fontWeight: 600 }}>
            TICK RATE (5-second windows)
          </div>
          <Sparkline data={ticksPerWindow} color="#6366f1" height={50} />
          <div style={{ fontSize: '0.7rem', color: '#475569', marginTop: 4 }}>
            Latest window: {ticksPerWindow[ticksPerWindow.length - 1]} ticks
          </div>
        </div>

        {/* Source breakdown */}
        <div style={{ background: '#0f172a', borderRadius: 12, padding: 16, border: '1px solid #1e293b' }}>
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: 10, fontWeight: 600 }}>
            AGENT SOURCES
          </div>
          {Object.keys(SOURCE_META).map(src => {
            const count = sourceCounts[src] ?? 0;
            if (count === 0) return null;
            const meta  = SOURCE_META[src];
            return (
              <div key={src} style={{
                display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6,
              }}>
                <span style={{ fontSize: '0.8rem' }}>{meta.icon}</span>
                <span style={{ fontSize: '0.78rem', color: '#cbd5e1', flex: 1 }}>{meta.label}</span>
                <span style={{
                  fontSize: '0.78rem', fontWeight: 700,
                  color: meta.color,
                  background: meta.color + '22',
                  padding: '1px 8px',
                  borderRadius: 9999,
                }}>{count}</span>
              </div>
            );
          })}
          {Object.values(sourceCounts).every(v => v === 0) && (
            <div style={{ fontSize: '0.75rem', color: '#475569', fontStyle: 'italic' }}>
              No agents registered yet
            </div>
          )}
        </div>
      </div>

      {/* ── Agent cards ──────────────────────────────────────────────────── */}
      {status?.agents && status.agents.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 600, marginBottom: 10 }}>
            REGISTERED AGENTS
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
            {status.agents.map(agent => (
              <div key={agent.device_id} style={{
                background: '#1e293b',
                borderRadius: 12,
                padding: '14px 16px',
                border: `1px solid ${agent.active ? '#10b98133' : '#ef444433'}`,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <StatusDot active={agent.active} />
                  <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#f1f5f9' }}>
                    {agent.device_id}
                  </span>
                </div>
                <SourceBadge source={agent.source} />
                <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                  {[
                    { label: 'Ticks',       value: agent.ticks_received.toLocaleString() },
                    { label: 'Age',         value: `${agent.age_seconds.toFixed(0)}s` },
                    { label: 'Last Beat',   value: new Date(agent.last_heartbeat).toLocaleTimeString() },
                    { label: 'Registered',  value: new Date(agent.registered_at).toLocaleDateString() },
                  ].map(({ label, value }) => (
                    <div key={label}>
                      <div style={{ fontSize: '0.65rem', color: '#475569' }}>{label}</div>
                      <div style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600 }}>{value}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── No agents state ───────────────────────────────────────────────── */}
      {(!status || status.total_agents === 0) && (
        <div style={{
          background: '#0f172a',
          borderRadius: 12,
          padding: '28px 20px',
          textAlign: 'center',
          border: '1px dashed #334155',
          marginBottom: 20,
        }}>
          <div style={{ fontSize: '2rem', marginBottom: 8 }}>📡</div>
          <div style={{ fontWeight: 600, color: '#64748b', marginBottom: 4 }}>
            Waiting for agents to connect
          </div>
          <div style={{ fontSize: '0.78rem', color: '#475569' }}>
            Run <code style={{ background: '#1e293b', padding: '2px 6px', borderRadius: 4 }}>
              python scripts/telemetry_agent.py
            </code> on any device to start streaming
          </div>
        </div>
      )}

      {/* ── Live event log ────────────────────────────────────────────────── */}
      <div>
        <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 600, marginBottom: 8 }}>
          LIVE EVENT LOG (last {LOG_SIZE})
        </div>
        <div
          ref={logRef}
          style={{
            background: '#0f172a',
            borderRadius: 10,
            border: '1px solid #1e293b',
            padding: '10px 12px',
            maxHeight: 220,
            overflowY: 'auto',
            fontFamily: '"JetBrains Mono", "Fira Code", monospace',
            fontSize: '0.7rem',
            lineHeight: 1.7,
          }}
        >
          {sseEvents.length === 0 ? (
            <div style={{ color: '#475569', fontStyle: 'italic' }}>
              {sseConnected ? 'Waiting for first tick...' : 'Connecting to SSE stream...'}
            </div>
          ) : sseEvents.map((ev, i) => (
            <div key={i} style={{
              borderBottom: i < sseEvents.length - 1 ? '1px solid #1e293b' : 'none',
              paddingBottom: 3,
              marginBottom: 3,
              color: ev.power_source === 'battery' ? '#fbbf24' : '#94a3b8',
            }}>
              <span style={{ color: '#475569' }}>
                {new Date(ev.timestamp).toLocaleTimeString()}
              </span>
              {' '}
              <span style={{ color: SOURCE_META[ev.source]?.color ?? '#94a3b8' }}>
                [{ev.source}]
              </span>
              {' '}
              <span style={{ color: '#f1f5f9' }}>{ev.device_id}</span>
              {' | '}CPU={ev.cpu_usage?.toFixed(1)}% Temp={ev.cpu_temperature?.toFixed(1)}°C
              {' '}Bat={ev.battery_level?.toFixed(1)}% ({ev.power_source?.toUpperCase()})
              {' '}lat={ev.collection_latency_ms?.toFixed(0)}ms
            </div>
          ))}
        </div>
      </div>

      {/* ── CSS for pulse animation ───────────────────────────────────────── */}
      <style>{`
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.6; transform: scale(1.3); }
        }
      `}</style>
    </div>
  );
};

export default LiveIngestionStatus;
