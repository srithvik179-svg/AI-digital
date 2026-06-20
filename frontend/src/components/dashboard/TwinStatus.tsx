'use client';

import React, { useMemo } from 'react';
import { TelemetryData } from '@/types';
import {
  Cpu, Thermometer, Battery, HardDrive, RefreshCw,
  ShieldCheck, ShieldAlert, ShieldX, Zap, Wifi,
  MemoryStick, TrendingUp, AlertTriangle,
} from 'lucide-react';

interface TwinStatusProps {
  latestData: TelemetryData | null;
  isConnected: boolean;
}

/* ── helpers ─────────────────────────────────────────── */
const categoryConfig = {
  Healthy:  { color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', glow: 'shadow-emerald-500/20', Icon: ShieldCheck,  ring: '#10b981' },
  Warning:  { color: 'text-amber-400',   bg: 'bg-amber-500/10',   border: 'border-amber-500/30',   glow: 'shadow-amber-500/20',  Icon: ShieldAlert,  ring: '#f59e0b' },
  Critical: { color: 'text-red-400',     bg: 'bg-red-500/10',     border: 'border-red-500/30',     glow: 'shadow-red-500/20',    Icon: ShieldX,      ring: '#ef4444' },
};

function getConfig(cat?: string) {
  return categoryConfig[(cat as keyof typeof categoryConfig) ?? ''] ?? categoryConfig.Healthy;
}

/* ── SVG Gauge ─────────────────────────────────────── */
function ScoreGauge({ score, category }: { score: number; category: string }) {
  const cfg = getConfig(category);
  const r = 54;
  const cx = 70;
  const cy = 70;
  const circumference = 2 * Math.PI * r;
  // Arc goes from 135° to 405° (270° sweep) — a 3/4 circle
  const sweep = 270;
  const arcLen = (sweep / 360) * circumference;
  const filled = (score / 100) * arcLen;
  const gap    = arcLen - filled;

  // Convert degrees to radians for path start/end
  const toRad = (d: number) => (d * Math.PI) / 180;
  const startAngle = 135;
  const endAngle   = 405;
  const sx = cx + r * Math.cos(toRad(startAngle));
  const sy = cy + r * Math.sin(toRad(startAngle));
  const ex = cx + r * Math.cos(toRad(endAngle));
  const ey = cy + r * Math.sin(toRad(endAngle));

  return (
    <div className="relative flex items-center justify-center" style={{ width: 140, height: 140 }}>
      <svg width="140" height="140" viewBox="0 0 140 140">
        {/* Background track */}
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="10" />
        {/* Score arc — stroke-dasharray trick on a full circle, rotated */}
        <circle
          cx={cx} cy={cy} r={r}
          fill="none"
          stroke={cfg.ring}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference - filled}`}
          strokeDashoffset={circumference * (1 - 135 / 360)}
          style={{ transition: 'stroke-dasharray 0.6s ease', filter: `drop-shadow(0 0 6px ${cfg.ring}88)` }}
          transform={`rotate(-90, ${cx}, ${cy})`}
        />
        {/* Tick marks */}
        {[0, 25, 50, 75, 100].map(v => {
          const angleDeg = 135 + (v / 100) * 270 - 90;
          const rad = toRad(angleDeg);
          const x1 = cx + (r - 7) * Math.cos(rad);
          const y1 = cy + (r - 7) * Math.sin(rad);
          const x2 = cx + (r + 0) * Math.cos(rad);
          const y2 = cy + (r + 0) * Math.sin(rad);
          return <line key={v} x1={x1} y1={y1} x2={x2} y2={y2} stroke="rgba(255,255,255,0.15)" strokeWidth="1.5" />;
        })}
      </svg>
      {/* Center label */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`text-3xl font-black tabular-nums ${cfg.color}`}>{score.toFixed(0)}</span>
        <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-widest mt-0.5">/ 100</span>
      </div>
    </div>
  );
}

/* ── Breakdown Bar ─────────────────────────────────── */
function BreakdownBar({ label, value, icon: Icon, color }: {
  label: string; value: number; icon: any; color: string
}) {
  return (
    <div className="flex items-center gap-2">
      <Icon className={`h-3.5 w-3.5 shrink-0 ${color}`} />
      <span className="text-[11px] text-slate-400 w-20 shrink-0">{label}</span>
      <div className="flex-1 bg-slate-800 rounded-full h-1.5 overflow-hidden">
        <div
          className="h-1.5 rounded-full transition-all duration-700"
          style={{ width: `${Math.max(2, value)}%`, background: value >= 75 ? '#10b981' : value >= 50 ? '#f59e0b' : '#ef4444' }}
        />
      </div>
      <span className={`text-[11px] font-bold tabular-nums w-8 text-right ${
        value >= 75 ? 'text-emerald-400' : value >= 50 ? 'text-amber-400' : 'text-red-400'
      }`}>{value.toFixed(0)}</span>
    </div>
  );
}

/* ── HUD metric card ───────────────────────────────── */
function HudCard({
  label, value, unit, sub, icon: Icon, iconColor, barColor, barPct, hover,
}: {
  label: string; value: string | number; unit?: string; sub?: string;
  icon: any; iconColor: string; barColor: string; barPct: number; hover: string;
}) {
  return (
    <div className={`glass-panel rounded-2xl p-5 border border-white/5 relative overflow-hidden
      transition-all duration-300 hover:scale-[1.02] ${hover}`}>
      <div className="absolute top-0 right-0 w-20 h-20 opacity-5 rounded-bl-full pointer-events-none"
        style={{ background: barColor }} />
      <div className="flex items-center justify-between mb-3">
        <span className="text-slate-400 text-[11px] font-semibold uppercase tracking-wider">{label}</span>
        <Icon className={`${iconColor} h-4.5 w-4.5`} />
      </div>
      <div className="flex items-baseline gap-1 mb-2">
        <span className="text-2xl font-bold tracking-tight">{value}</span>
        {unit && <span className="text-slate-500 text-xs">{unit}</span>}
      </div>
      <div className="w-full bg-slate-800 rounded-full h-1 overflow-hidden mb-1.5">
        <div className="h-1 rounded-full transition-all duration-500" style={{ width: `${Math.min(100, barPct)}%`, background: barColor }} />
      </div>
      {sub && <p className="text-slate-500 text-[10px]">{sub}</p>}
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   MAIN COMPONENT
══════════════════════════════════════════════════════ */
export const TwinStatus: React.FC<TwinStatusProps> = ({ latestData, isConnected }) => {
  if (!latestData) {
    return (
      <div className="glass-panel rounded-2xl p-6 flex flex-col items-center justify-center h-48 border border-white/5">
        <RefreshCw className="animate-spin text-indigo-400 mb-2 h-8 w-8" />
        <p className="text-slate-400 text-sm">Awaiting laptop telemetry connection...</p>
      </div>
    );
  }

  const score    = latestData.health_score    ?? 0;
  const category = latestData.health_category ?? 'Healthy';
  const breakdown = latestData.health_breakdown;
  const recs = latestData.health_recommendations ?? [];
  const cfg = getConfig(category);
  const { Icon: StatusIcon } = cfg;

  const tempBarPct = Math.min(100, Math.max(0, (latestData.cpu_temperature - 30) / (100 - 30) * 100));
  const batColor = latestData.battery_level < 20 ? '#ef4444' : latestData.battery_level < 50 ? '#f59e0b' : '#10b981';

  return (
    <div className="space-y-5">

      {/* ── Row 1: Health Score gauge + breakdown + recs ── */}
      <div className={`glass-panel rounded-2xl border p-5 ${cfg.border} shadow-lg ${cfg.glow}`}>
        <div className="flex flex-col lg:flex-row gap-6">

          {/* Gauge + category label */}
          <div className="flex flex-col items-center justify-center gap-2 lg:min-w-[160px]">
            <ScoreGauge score={score} category={category} />
            <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${cfg.bg} ${cfg.border} ${cfg.color}`}>
              <StatusIcon className="h-3.5 w-3.5" />
              {category}
            </div>
            <p className="text-slate-500 text-[10px] text-center">Composite Health Score</p>
          </div>

          {/* Breakdown bars */}
          {breakdown && (
            <div className="flex-1 flex flex-col justify-center gap-2.5">
              <p className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-1">Score Breakdown</p>
              <BreakdownBar label="CPU"         value={breakdown.cpu}         icon={Cpu}         color="text-indigo-400" />
              <BreakdownBar label="Memory"      value={breakdown.memory}      icon={MemoryStick} color="text-purple-400" />
              <BreakdownBar label="GPU"         value={breakdown.gpu}         icon={Zap}         color="text-violet-400" />
              <BreakdownBar label="Temperature" value={breakdown.temperature} icon={Thermometer} color="text-orange-400" />
              <BreakdownBar label="Battery"     value={breakdown.battery}     icon={Battery}     color="text-emerald-400" />
              <BreakdownBar label="Disk"        value={breakdown.disk}        icon={HardDrive}   color="text-cyan-400"   />
              <BreakdownBar label="WiFi"        value={breakdown.wifi}        icon={Wifi}        color="text-sky-400"    />
            </div>
          )}

          {/* Recommendations */}
          {recs.length > 0 && (
            <div className="flex-1 lg:max-w-xs">
              <p className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <TrendingUp className="h-3.5 w-3.5 text-indigo-400" />
                Recommendations
              </p>
              <ul className="space-y-2">
                {recs.slice(0, 4).map((rec, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <AlertTriangle className={`h-3 w-3 mt-0.5 shrink-0 ${
                      category === 'Critical' ? 'text-red-400' : category === 'Warning' ? 'text-amber-400' : 'text-emerald-400'
                    }`} />
                    <span className="text-[11px] text-slate-400 leading-tight">{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* ── Row 2: HUD metric cards ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <HudCard
          label="CPU Utilization"
          value={latestData.cpu_usage}
          unit="%"
          sub={`${latestData.active_process_count} processes · ${latestData.cpu_temperature}°C`}
          icon={Cpu}
          iconColor="text-indigo-400"
          barColor="#6366f1"
          barPct={latestData.cpu_usage}
          hover="hover:border-indigo-500/30"
        />
        <HudCard
          label="Memory (RAM)"
          value={latestData.memory_usage}
          unit="%"
          sub={`Disk: ${latestData.disk_usage}%`}
          icon={MemoryStick}
          iconColor="text-purple-400"
          barColor="#a855f7"
          barPct={latestData.memory_usage}
          hover="hover:border-purple-500/30"
        />
        <HudCard
          label="Thermals & Fan"
          value={latestData.cpu_temperature}
          unit="°C"
          sub={`Fan: ${latestData.fan_speed} RPM · ${latestData.cpu_temperature > 75 ? '⚠ Warning' : '✓ Safe'}`}
          icon={Thermometer}
          iconColor={latestData.cpu_temperature > 75 ? 'text-red-400' : latestData.cpu_temperature > 60 ? 'text-amber-400' : 'text-cyan-400'}
          barColor={latestData.cpu_temperature > 75 ? '#ef4444' : latestData.cpu_temperature > 60 ? '#f59e0b' : '#22d3ee'}
          barPct={tempBarPct}
          hover="hover:border-cyan-500/30"
        />
        <HudCard
          label="Battery Status"
          value={latestData.battery_level}
          unit="%"
          sub={`Health: ${latestData.battery_health}% · ${latestData.power_source.toUpperCase()}`}
          icon={Battery}
          iconColor={latestData.battery_level < 20 ? 'text-red-400' : latestData.battery_level < 50 ? 'text-amber-400' : 'text-emerald-400'}
          barColor={batColor}
          barPct={latestData.battery_level}
          hover="hover:border-emerald-500/30"
        />
      </div>

    </div>
  );
};

export default TwinStatus;
