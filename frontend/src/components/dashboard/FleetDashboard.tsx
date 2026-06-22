'use client';

/**
 * Phase 47 — Multi-Device Fleet Management Dashboard.
 *
 * Shows a unified, live view of every registered telemetry agent:
 *   - Fleet KPI cards (total / online / offline / avg health / alerts)
 *   - Health ranking bar chart (horizontal gradient bars per device)
 *   - Device grid cards (color-coded by health category)
 *   - Anomaly spotlight list (critical + warning issues across fleet)
 *   - Quick bulk-action buttons (ECO_MODE / KILL_HIGH_CPU)
 *   - Source distribution donut (mac / windows-ohm / windows-wmi / linux)
 *
 * Data: polls /fleet/summary + /fleet/devices + /fleet/anomalies every 5 s.
 */

import React, { useEffect, useState, useCallback } from 'react';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface DeviceHealthCard {
  device_id:           string;
  source:              string;
  online:              boolean;
  last_seen:           string;
  age_seconds:         number;
  ticks_received:      number;
  cpu_usage:           number | null;
  memory_usage:        number | null;
  cpu_temperature:     number | null;
  battery_level:       number | null;
  battery_health:      number | null;
  power_source:        string | null;
  fan_speed:           number | null;
  gpu_usage:           number | null;
  signal_strength_dbm: number | null;
  health_score:        number | null;
  health_category:     string | null;
  active_alert_count:  number;
  recommendations:     string[];
}

interface FleetSummary {
  total_devices:    number;
  online_devices:   number;
  offline_devices:  number;
  fleet_avg_health: number | null;
  fleet_min_health: number | null;
  healthy_count:    number;
  warning_count:    number;
  critical_count:   number;
  total_alerts:     number;
  sources:          Record<string, number>;
  generated_at:     string;
}

interface FleetAnomaly {
  device_id: string;
  reason:    string;
  severity:  'critical' | 'warning';
  metric:    string;
  value:     number | null;
  threshold: number | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const API = 'http://localhost:8000/api/v1';
const POLL = 5000;

const HEALTH_COLOR = (cat: string | null) =>
  cat === 'Healthy'  ? '#10b981' :
  cat === 'Warning'  ? '#f59e0b' :
  cat === 'Critical' ? '#ef4444' : '#64748b';

const SOURCE_ICON: Record<string, string> = {
  mac:           '🍎',
  'windows-ohm': '🪟',
  'windows-wmi': '🪟',
  linux:         '🐧',
  unknown:       '❓',
};

const SOURCE_COLOR: Record<string, string> = {
  mac:           '#a78bfa',
  'windows-ohm': '#34d399',
  'windows-wmi': '#6ee7b7',
  linux:         '#f59e0b',
  unknown:       '#64748b',
};

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

const Metric: React.FC<{
  label: string; value: string | number | null; unit?: string; color?: string
}> = ({ label, value, unit = '', color = '#94a3b8' }) => (
  <div style={{ textAlign: 'center' }}>
    <div style={{ fontSize: '0.75rem', color, fontWeight: 700 }}>
      {value !== null && value !== undefined ? `${value}${unit}` : '—'}
    </div>
    <div style={{ fontSize: '0.6rem', color: '#475569', marginTop: 1 }}>{label}</div>
  </div>
);

const HealthBar: React.FC<{ score: number | null; width?: number }> = ({
  score, width = 120,
}) => {
  const pct = score ?? 0;
  const col = pct >= 75 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#ef4444';
  return (
    <div style={{
      width, height: 6, borderRadius: 3,
      background: '#1e293b', overflow: 'hidden',
    }}>
      <div style={{
        width: `${pct}%`, height: '100%', borderRadius: 3,
        background: `linear-gradient(90deg, ${col}88, ${col})`,
        transition: 'width 0.6s ease',
      }} />
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

const FleetDashboard: React.FC = () => {
  const [summary,   setSummary]   = useState<FleetSummary | null>(null);
  const [devices,   setDevices]   = useState<DeviceHealthCard[]>([]);
  const [anomalies, setAnomalies] = useState<FleetAnomaly[]>([]);
  const [loading,   setLoading]   = useState(true);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [selectedDevice, setSelectedDevice] = useState<DeviceHealthCard | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [sumRes, devRes, anoRes] = await Promise.all([
        fetch(`${API}/fleet/summary`),
        fetch(`${API}/fleet/devices?sort_by=health_score`),
        fetch(`${API}/fleet/anomalies`),
      ]);
      if (sumRes.ok) setSummary(await sumRes.json());
      if (devRes.ok) setDevices(await devRes.json());
      if (anoRes.ok) setAnomalies(await anoRes.json());
    } catch { /* backend may be unreachable */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, POLL);
    return () => clearInterval(id);
  }, [fetchAll]);

  const handleBulkAction = async (action: string) => {
    try {
      const res = await fetch(`${API}/fleet/bulk-action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
      if (res.ok) {
        const data = await res.json();
        const acked = Object.values(data.results).filter(v => v === 'ack').length;
        setActionMsg(`✅ ${action} sent to ${acked} device(s)`);
        setTimeout(() => setActionMsg(null), 4000);
      }
    } catch {
      setActionMsg(`❌ Failed to send ${action}`);
      setTimeout(() => setActionMsg(null), 4000);
    }
  };

  // ── Derived: source distribution for mini-donut ──────────────────────────
  const sourceEntries = Object.entries(summary?.sources ?? {});
  const totalSources  = sourceEntries.reduce((s, [, v]) => s + v, 0);

  return (
    <div
      id="fleet-management-dashboard"
      style={{
        background:   'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
        borderRadius: 16,
        border:       '1px solid #334155',
        padding:      '24px',
        fontFamily:   '"Inter", "SF Pro Display", system-ui, sans-serif',
        color:        '#e2e8f0',
      }}
    >
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10,
          background: 'linear-gradient(135deg, #06b6d4, #3b82f6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20,
        }}>🖥️</div>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700, color: '#f1f5f9' }}>
            Fleet Management
          </h2>
          <p style={{ margin: 0, fontSize: '0.78rem', color: '#64748b' }}>
            Phase 47 — Multi-Device Health Monitor
          </p>
        </div>

        {/* Bulk actions */}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          {actionMsg && (
            <span style={{ fontSize: '0.78rem', color: '#10b981', fontWeight: 600 }}>
              {actionMsg}
            </span>
          )}
          {[
            { label: '🌿 Eco Mode',      action: 'ECO_MODE' },
            { label: '🔪 Kill High CPU', action: 'KILL_HIGH_CPU' },
          ].map(({ label, action }) => (
            <button
              key={action}
              onClick={() => handleBulkAction(action)}
              style={{
                background: '#1e293b',
                border: '1px solid #334155',
                borderRadius: 8,
                color: '#94a3b8',
                fontSize: '0.75rem',
                fontWeight: 600,
                padding: '6px 12px',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={e => {
                (e.target as HTMLButtonElement).style.borderColor = '#6366f1';
                (e.target as HTMLButtonElement).style.color = '#a5b4fc';
              }}
              onMouseLeave={e => {
                (e.target as HTMLButtonElement).style.borderColor = '#334155';
                (e.target as HTMLButtonElement).style.color = '#94a3b8';
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* ── KPI Cards ──────────────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10, marginBottom: 20 }}>
        {[
          { label: 'Total',    value: summary?.total_devices   ?? '—', color: '#6366f1' },
          { label: 'Online',   value: summary?.online_devices  ?? '—', color: '#10b981' },
          { label: 'Offline',  value: summary?.offline_devices ?? '—', color: '#ef4444' },
          { label: 'Avg Health', value: summary?.fleet_avg_health != null ? `${summary.fleet_avg_health}` : '—', color: '#06b6d4' },
          { label: 'Alerts',   value: summary?.total_alerts    ?? '—', color: '#f59e0b' },
          { label: 'Critical', value: summary?.critical_count  ?? '—', color: '#ef4444' },
        ].map(({ label, value, color }) => (
          <div key={label} style={{
            background: '#1e293b', borderRadius: 12, padding: '12px 10px',
            border: `1px solid ${color}33`, textAlign: 'center',
          }}>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color }}>{value}</div>
            <div style={{ fontSize: '0.65rem', color: '#64748b', marginTop: 2 }}>{label}</div>
          </div>
        ))}
      </div>

      {/* ── Health category badges ────────────────────────────────────────── */}
      {summary && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
          {[
            { label: `✅ ${summary.healthy_count} Healthy`,  bg: '#10b98122', border: '#10b981' },
            { label: `⚠️ ${summary.warning_count} Warning`,  bg: '#f59e0b22', border: '#f59e0b' },
            { label: `🔴 ${summary.critical_count} Critical`, bg: '#ef444422', border: '#ef4444' },
          ].map(({ label, bg, border }) => (
            <div key={label} style={{
              background: bg, border: `1px solid ${border}`,
              borderRadius: 9999, padding: '4px 14px',
              fontSize: '0.75rem', fontWeight: 600,
              color: '#e2e8f0',
            }}>{label}</div>
          ))}

          {/* Source distribution */}
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
            {sourceEntries.map(([src, cnt]) => (
              <span key={src} style={{
                fontSize: '0.72rem', fontWeight: 600,
                color: SOURCE_COLOR[src] ?? '#94a3b8',
                background: (SOURCE_COLOR[src] ?? '#94a3b8') + '22',
                border: `1px solid ${SOURCE_COLOR[src] ?? '#94a3b8'}`,
                borderRadius: 9999, padding: '3px 10px',
              }}>
                {SOURCE_ICON[src] ?? '❓'} {src} ×{cnt}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Device Grid ──────────────────────────────────────────────────────── */}
      {loading ? (
        <div style={{ textAlign: 'center', color: '#475569', padding: 40, fontSize: '0.85rem' }}>
          Loading fleet data…
        </div>
      ) : devices.length === 0 ? (
        <div style={{
          background: '#0f172a', borderRadius: 12, padding: '32px',
          textAlign: 'center', border: '1px dashed #334155', marginBottom: 20,
        }}>
          <div style={{ fontSize: '2rem', marginBottom: 8 }}>🖥️</div>
          <div style={{ color: '#64748b', fontWeight: 600 }}>No devices in fleet yet</div>
          <div style={{ fontSize: '0.78rem', color: '#475569', marginTop: 4 }}>
            Start <code style={{ background: '#1e293b', padding: '2px 6px', borderRadius: 4 }}>
              python scripts/telemetry_agent.py
            </code> on any machine
          </div>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
          gap: 14, marginBottom: 20,
        }}>
          {devices.map(dev => {
            const hc   = HEALTH_COLOR(dev.health_category);
            const isSelected = selectedDevice?.device_id === dev.device_id;
            return (
              <div
                key={dev.device_id}
                onClick={() => setSelectedDevice(isSelected ? null : dev)}
                style={{
                  background:   '#1e293b',
                  borderRadius: 12,
                  border:       `1px solid ${isSelected ? hc : hc + '44'}`,
                  padding:      '16px',
                  cursor:       'pointer',
                  transition:   'all 0.2s',
                  boxShadow:    isSelected ? `0 0 16px ${hc}33` : 'none',
                }}
              >
                {/* Device header */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                  <span style={{
                    width: 8, height: 8, borderRadius: '50%',
                    background: dev.online ? '#10b981' : '#ef4444',
                    boxShadow:  dev.online ? '0 0 6px #10b98188' : 'none',
                    display: 'inline-block',
                    animation: dev.online ? 'fleet-pulse 1.8s infinite' : 'none',
                  }} />
                  <span style={{ fontWeight: 700, fontSize: '0.88rem', color: '#f1f5f9', flex: 1 }}>
                    {dev.device_id}
                  </span>
                  <span style={{
                    fontSize: '0.65rem', fontWeight: 600,
                    color: SOURCE_COLOR[dev.source] ?? '#94a3b8',
                    background: (SOURCE_COLOR[dev.source] ?? '#94a3b8') + '22',
                    border: `1px solid ${SOURCE_COLOR[dev.source] ?? '#94a3b8'}`,
                    borderRadius: 9999, padding: '2px 7px',
                  }}>
                    {SOURCE_ICON[dev.source] ?? '❓'} {dev.source}
                  </span>
                </div>

                {/* Health score bar */}
                <div style={{ marginBottom: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Health Score</span>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: hc }}>
                      {dev.health_score != null ? `${dev.health_score}` : '—'}
                      {dev.health_category ? ` · ${dev.health_category}` : ''}
                    </span>
                  </div>
                  <HealthBar score={dev.health_score} width={268} />
                </div>

                {/* Metric grid */}
                <div style={{
                  display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6,
                  background: '#0f172a', borderRadius: 8, padding: '8px 4px',
                }}>
                  <Metric label="CPU"  value={dev.cpu_usage?.toFixed(1) ?? null}    unit="%" color="#6366f1" />
                  <Metric label="RAM"  value={dev.memory_usage?.toFixed(1) ?? null} unit="%" color="#06b6d4" />
                  <Metric label="Temp" value={dev.cpu_temperature?.toFixed(1) ?? null} unit="°C" color="#f59e0b" />
                  <Metric label="Bat"  value={dev.battery_level?.toFixed(1) ?? null} unit="%" color="#10b981" />
                </div>

                {/* Footer */}
                <div style={{
                  display: 'flex', justifyContent: 'space-between',
                  marginTop: 10, fontSize: '0.68rem', color: '#475569',
                }}>
                  <span>
                    {dev.active_alert_count > 0
                      ? <span style={{ color: '#ef4444' }}>⚠ {dev.active_alert_count} alert{dev.active_alert_count !== 1 ? 's' : ''}</span>
                      : <span style={{ color: '#10b981' }}>✓ No alerts</span>
                    }
                  </span>
                  <span>{dev.ticks_received.toLocaleString()} ticks</span>
                  <span title={dev.last_seen ?? ''}>
                    {dev.online ? `${dev.age_seconds.toFixed(0)}s ago` : 'Offline'}
                  </span>
                </div>

                {/* Expanded recommendations */}
                {isSelected && dev.recommendations.length > 0 && (
                  <div style={{
                    marginTop: 12, borderTop: '1px solid #334155', paddingTop: 10,
                  }}>
                    <div style={{ fontSize: '0.68rem', color: '#64748b', marginBottom: 6 }}>
                      RECOMMENDATIONS
                    </div>
                    {dev.recommendations.map((r, i) => (
                      <div key={i} style={{
                        fontSize: '0.72rem', color: '#94a3b8', marginBottom: 4,
                        paddingLeft: 8, borderLeft: '2px solid #6366f1',
                      }}>
                        {r}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Health Ranking Bars ────────────────────────────────────────────── */}
      {devices.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 600, marginBottom: 10 }}>
            FLEET HEALTH RANKING (worst → best)
          </div>
          <div style={{
            background: '#0f172a', borderRadius: 12, padding: '14px 16px',
            border: '1px solid #1e293b',
          }}>
            {[...devices]
              .sort((a, b) => (a.health_score ?? 0) - (b.health_score ?? 0))
              .map((dev, i) => {
                const score = dev.health_score ?? 0;
                const col   = HEALTH_COLOR(dev.health_category);
                return (
                  <div key={dev.device_id} style={{
                    display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8,
                  }}>
                    <span style={{ fontSize: '0.65rem', color: '#475569', width: 14, textAlign: 'right' }}>
                      {i + 1}
                    </span>
                    <span style={{ fontSize: '0.75rem', color: '#94a3b8', width: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {SOURCE_ICON[dev.source] ?? '❓'} {dev.device_id}
                    </span>
                    <div style={{ flex: 1, height: 8, background: '#1e293b', borderRadius: 4, overflow: 'hidden' }}>
                      <div style={{
                        width: `${score}%`, height: '100%', borderRadius: 4,
                        background: `linear-gradient(90deg, ${col}66, ${col})`,
                        transition: 'width 0.6s ease',
                      }} />
                    </div>
                    <span style={{ fontSize: '0.72rem', fontWeight: 700, color: col, width: 36, textAlign: 'right' }}>
                      {score.toFixed(0)}
                    </span>
                    {!dev.online && (
                      <span style={{ fontSize: '0.65rem', color: '#ef4444' }}>OFFLINE</span>
                    )}
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* ── Anomaly Spotlight ────────────────────────────────────────────────── */}
      {anomalies.length > 0 && (
        <div>
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 600, marginBottom: 8 }}>
            ANOMALY SPOTLIGHT ({anomalies.length} issue{anomalies.length !== 1 ? 's' : ''})
          </div>
          <div style={{
            background: '#0f172a', borderRadius: 12,
            border: '1px solid #1e293b', overflow: 'hidden',
          }}>
            {anomalies.slice(0, 10).map((a, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 14px',
                borderBottom: i < Math.min(anomalies.length, 10) - 1 ? '1px solid #1e293b' : 'none',
                background: a.severity === 'critical' ? '#ef444408' : 'transparent',
              }}>
                <span style={{ fontSize: '0.85rem' }}>
                  {a.severity === 'critical' ? '🔴' : '⚠️'}
                </span>
                <span style={{
                  fontSize: '0.72rem', fontWeight: 700,
                  color: a.severity === 'critical' ? '#ef4444' : '#f59e0b',
                  width: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {a.device_id}
                </span>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8', flex: 1 }}>
                  {a.reason}
                </span>
                <span style={{
                  fontSize: '0.65rem', color: '#475569',
                  background: '#1e293b', padding: '2px 6px', borderRadius: 4,
                }}>
                  {a.metric}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {anomalies.length === 0 && devices.length > 0 && (
        <div style={{
          textAlign: 'center', padding: '16px',
          background: '#10b98108', borderRadius: 10,
          border: '1px solid #10b98133', color: '#10b981',
          fontSize: '0.8rem', fontWeight: 600,
        }}>
          ✅ Fleet is healthy — no anomalies detected
        </div>
      )}

      <style>{`
        @keyframes fleet-pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.6; transform: scale(1.4); }
        }
      `}</style>
    </div>
  );
};

export default FleetDashboard;
