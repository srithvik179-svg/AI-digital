'use client';

import React, { useMemo } from 'react';
import { TelemetryData } from '@/types';
import {
  AreaChart, Area,
  LineChart, Line,
  ComposedChart, Bar,
  XAxis, YAxis,
  CartesianGrid, Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from 'recharts';
import {
  Cpu, Zap, Thermometer, Battery, Wifi,
  Activity, TrendingUp, TrendingDown
} from 'lucide-react';

interface TelemetryChartsProps {
  data: TelemetryData[];
  projections?: {
    timestamp: string;
    cpu_usage: number;
    cpu_temperature: number;
    battery_level: number;
    fan_speed: number;
    cpu_frequency_mhz: number;
  }[] | null;
}

/* ─── Shared chart config ─────────────────────────────── */
const GRID = <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />;

const xAxis = (
  <XAxis
    dataKey="timeStr"
    stroke="#475569"
    fontSize={10}
    tickLine={false}
    axisLine={false}
    interval="preserveStartEnd"
  />
);

/* ─── Custom dark tooltip ────────────────────────────── */
const DarkTooltip = ({ active, payload, label, unit }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#0d1424]/95 border border-white/10 rounded-xl p-3 shadow-2xl backdrop-blur-md text-xs min-w-[140px]">
      <p className="text-slate-400 font-semibold mb-2">{label}</p>
      {payload.map((entry: any, i: number) => {
        // Skip nulls or undefined values in tooltip to avoid empty rows
        if (entry.value == null) return null;
        return (
          <div key={i} className="flex items-center gap-2 mt-1">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ background: entry.color }} />
            <span className="text-slate-300">{entry.name}:</span>
            <span className="font-bold text-white ml-auto pl-2">
              {typeof entry.value === 'number' ? entry.value.toFixed(1) : entry.value}
              {unit ?? ''}
            </span>
          </div>
        );
      })}
    </div>
  );
};

/* ─── Chart panel wrapper ────────────────────────────── */
interface PanelProps {
  icon: React.ReactNode;
  title: string;
  subtitle?: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
  color?: string; // tailwind border color class
  fullWidth?: boolean;
}

const ChartPanel: React.FC<PanelProps> = ({
  icon, title, subtitle, badge, children, color = 'border-white/5', fullWidth
}) => (
  <div
    className={`
      glass-panel rounded-2xl border p-5 flex flex-col gap-4 transition-all duration-300
      hover:border-white/10 ${color} ${fullWidth ? 'col-span-full' : ''}
    `}
  >
    <div className="flex items-start justify-between gap-3">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-xl bg-white/5">{icon}</div>
        <div>
          <h3 className="text-sm font-bold text-white leading-tight">{title}</h3>
          {subtitle && <p className="text-[11px] text-slate-500 mt-0.5">{subtitle}</p>}
        </div>
      </div>
      {badge && <div className="shrink-0">{badge}</div>}
    </div>
    <div className="flex-1 w-full" style={{ minHeight: 0 }}>
      {children}
    </div>
  </div>
);

/* ─── Live value badge ───────────────────────────────── */
const LiveBadge = ({ value, unit, color = 'text-white' }: { value: string | number, unit?: string, color?: string }) => (
  <span className={`px-2.5 py-1 rounded-lg bg-white/5 border border-white/10 text-xs font-bold font-mono ${color}`}>
    {typeof value === 'number' ? value.toFixed(1) : value}{unit}
  </span>
);

/* ─── dBm to percentage helper ──────────────────────── */
const dbmToPercent = (dbm: number): number => {
  const clamped = Math.max(-100, Math.min(-30, dbm));
  return Math.round(((clamped + 100) / 70) * 100);
};

/* ─── Gradient defs ─────────────────────────────────── */
const GradientDefs = () => (
  <defs>
    <linearGradient id="gCpu" x1="0" y1="0" x2="0" y2="1">
      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
      <stop offset="95%" stopColor="#6366f1" stopOpacity={0.0} />
    </linearGradient>
    <linearGradient id="gMem" x1="0" y1="0" x2="0" y2="1">
      <stop offset="5%" stopColor="#a855f7" stopOpacity={0.35} />
      <stop offset="95%" stopColor="#a855f7" stopOpacity={0.0} />
    </linearGradient>
    <linearGradient id="gDisk" x1="0" y1="0" x2="0" y2="1">
      <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.25} />
      <stop offset="95%" stopColor="#22d3ee" stopOpacity={0.0} />
    </linearGradient>
    <linearGradient id="gGpu" x1="0" y1="0" x2="0" y2="1">
      <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.45} />
      <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.0} />
    </linearGradient>
    <linearGradient id="gGpuMem" x1="0" y1="0" x2="0" y2="1">
      <stop offset="5%" stopColor="#ec4899" stopOpacity={0.3} />
      <stop offset="95%" stopColor="#ec4899" stopOpacity={0.0} />
    </linearGradient>
    <linearGradient id="gBat" x1="0" y1="0" x2="0" y2="1">
      <stop offset="5%" stopColor="#10b981" stopOpacity={0.45} />
      <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
    </linearGradient>
    <linearGradient id="gWifi" x1="0" y1="0" x2="0" y2="1">
      <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.4} />
      <stop offset="95%" stopColor="#38bdf8" stopOpacity={0.0} />
    </linearGradient>
  </defs>
);

/* ════════════════════════════════════════════════════════
   MAIN COMPONENT
   ════════════════════════════════════════════════════════ */
export const TelemetryCharts: React.FC<TelemetryChartsProps> = ({ data, projections }) => {
  const chartData = useMemo(() => {
    const base = [...data].reverse().map(item => {
      const time = new Date(item.timestamp);
      return {
        ...item,
        timeStr: time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        gpu_usage: item.gpu_usage ?? 0,
        gpu_memory_usage: item.gpu_memory_usage ?? 0,
        signal_pct: item.signal_strength_dbm != null ? dbmToPercent(item.signal_strength_dbm) : null,
        signal_dbm: item.signal_strength_dbm ?? null,
        projected_cpu_temperature: null as number | null,
        projected_battery_level: null as number | null,
        projected_fan_speed: null as number | null,
        projected_cpu_usage: null as number | null,
      };
    });

    if (!projections || projections.length === 0) return base;

    const projStart = new Date(projections[0].timestamp);
    let splitIdx = -1;
    let minDiff = Infinity;
    
    for (let i = 0; i < base.length; i++) {
      const diff = Math.abs(new Date(base[i].timestamp).getTime() - projStart.getTime());
      if (diff < minDiff) {
        minDiff = diff;
        splitIdx = i;
      }
    }

    if (splitIdx !== -1) {
      base[splitIdx].projected_cpu_temperature = base[splitIdx].cpu_temperature;
      base[splitIdx].projected_battery_level = base[splitIdx].battery_level;
      base[splitIdx].projected_fan_speed = base[splitIdx].fan_speed;
      base[splitIdx].projected_cpu_usage = base[splitIdx].cpu_usage;
    }

    const projPoints = projections.map(proj => {
      const time = new Date(proj.timestamp);
      return {
        id: `proj-${proj.timestamp}`,
        device_id: base[0]?.device_id || 'test-laptop',
        timestamp: proj.timestamp,
        timeStr: `🔮 ` + time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        cpu_usage: null as any,
        memory_usage: null as any,
        disk_usage: null as any,
        cpu_temperature: null as any,
        battery_level: null as any,
        fan_speed: null as any,
        power_source: null as any,
        projected_cpu_temperature: proj.cpu_temperature,
        projected_battery_level: proj.battery_level,
        projected_fan_speed: proj.fan_speed,
        projected_cpu_usage: proj.cpu_usage,
      };
    });

    return [...base, ...projPoints];
  }, [data, projections]);

  const latest = data[0];

  /* Empty state */
  if (chartData.length === 0) {
    return (
      <div className="col-span-full glass-panel rounded-2xl border border-white/5 flex flex-col items-center justify-center h-64 gap-4">
        <Activity className="h-10 w-10 text-slate-600 animate-pulse" />
        <div className="text-center">
          <p className="text-slate-400 text-sm font-medium">No telemetry data yet</p>
          <p className="text-slate-600 text-xs mt-1">Start the simulation stream or upload a CSV to begin</p>
        </div>
      </div>
    );
  }

  const axisStyle = { stroke: '#475569', fontSize: 10, tickLine: false, axisLine: false } as const;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">

      {/* ── 1. CPU + MEMORY + DISK ── full width ───────────────── */}
      <ChartPanel
        fullWidth
        icon={<Cpu className="h-5 w-5 text-indigo-400" />}
        title="CPU & Memory Utilization"
        subtitle="CPU · RAM · Disk load over time"
        color="border-indigo-500/20"
        badge={
          <div className="flex items-center gap-2">
            <LiveBadge value={latest?.cpu_usage ?? 0} unit="%" color="text-indigo-300" />
            <LiveBadge value={latest?.memory_usage ?? 0} unit="%" color="text-purple-300" />
          </div>
        }
      >
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
            <GradientDefs />
            {GRID}
            {xAxis}
            <YAxis {...axisStyle} domain={[0, 100]} tickFormatter={v => `${v}%`} />
            <Tooltip content={<DarkTooltip unit="%" />} />
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, paddingBottom: 0 }} />
            <Area type="monotone" dataKey="cpu_usage" name="CPU" stroke="#6366f1" strokeWidth={2.5} fill="url(#gCpu)" dot={false} />
            <Area type="monotone" dataKey="memory_usage" name="Memory" stroke="#a855f7" strokeWidth={2} fill="url(#gMem)" dot={false} />
            <Area type="monotone" dataKey="disk_usage" name="Disk" stroke="#22d3ee" strokeWidth={1.5} fill="url(#gDisk)" dot={false} strokeDasharray="4 2" />
            <Line type="monotone" dataKey="projected_cpu_usage" name="Projected CPU" stroke="#818cf8" strokeWidth={2.5} dot={false} strokeDasharray="5 5" connectNulls />
          </AreaChart>
        </ResponsiveContainer>
      </ChartPanel>

      {/* ── 2. GPU UTILIZATION ───────────────────────────────────── */}
      <ChartPanel
        icon={<Zap className="h-5 w-5 text-violet-400" />}
        title="GPU Utilization"
        subtitle="GPU load & VRAM usage"
        color="border-violet-500/20"
        badge={<LiveBadge value={latest?.gpu_usage ?? 0} unit="%" color="text-violet-300" />}
      >
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
            <GradientDefs />
            {GRID}
            {xAxis}
            <YAxis {...axisStyle} domain={[0, 100]} tickFormatter={v => `${v}%`} />
            <Tooltip content={<DarkTooltip unit="%" />} />
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
            <Area type="monotone" dataKey="gpu_usage" name="GPU Load" stroke="#8b5cf6" strokeWidth={2.5} fill="url(#gGpu)" dot={false} />
            <Area type="monotone" dataKey="gpu_memory_usage" name="GPU VRAM" stroke="#ec4899" strokeWidth={1.5} fill="url(#gGpuMem)" dot={false} strokeDasharray="4 2" />
          </AreaChart>
        </ResponsiveContainer>
      </ChartPanel>

      {/* ── 3. TEMPERATURE & THERMALS ────────────────────────────── */}
      <ChartPanel
        icon={<Thermometer className="h-5 w-5 text-orange-400" />}
        title="Temperature & Fan"
        subtitle="Core temperature · Fan RPM"
        color="border-orange-500/20"
        badge={
          <LiveBadge
            value={latest?.cpu_temperature ?? 0}
            unit="°C"
            color={(latest?.cpu_temperature ?? 0) > 75 ? 'text-red-400' : (latest?.cpu_temperature ?? 0) > 60 ? 'text-amber-400' : 'text-cyan-300'}
          />
        }
      >
        <ResponsiveContainer width="100%" height={180}>
          <ComposedChart data={chartData} margin={{ top: 4, right: 20, left: -24, bottom: 0 }}>
            <GradientDefs />
            {GRID}
            {xAxis}
            <YAxis yAxisId="temp" {...axisStyle} domain={[30, 100]} tickFormatter={v => `${v}°`} stroke="#f97316" />
            <YAxis yAxisId="fan" orientation="right" {...axisStyle} domain={[0, 6000]} tickFormatter={v => `${(v / 1000).toFixed(1)}k`} stroke="#94a3b8" />
            <Tooltip content={<DarkTooltip />} />
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
            <ReferenceLine yAxisId="temp" y={75} stroke="#ef4444" strokeDasharray="4 2" strokeOpacity={0.6} label={{ value: '75°C', fill: '#ef4444', fontSize: 10, position: 'insideTopRight' }} />
            <ReferenceLine yAxisId="temp" y={60} stroke="#f59e0b" strokeDasharray="4 2" strokeOpacity={0.4} />
            <Line yAxisId="temp" type="monotone" dataKey="cpu_temperature" name="CPU Temp" stroke="#f97316" strokeWidth={2.5} dot={false} />
            <Bar yAxisId="fan" dataKey="fan_speed" name="Fan RPM" fill="#334155" opacity={0.6} radius={[2, 2, 0, 0]} />
            <Line yAxisId="temp" type="monotone" dataKey="projected_cpu_temperature" name="Projected Temp" stroke="#fb923c" strokeWidth={2.5} dot={false} strokeDasharray="5 5" connectNulls />
            <Line yAxisId="fan" type="monotone" dataKey="projected_fan_speed" name="Projected Fan" stroke="#94a3b8" strokeWidth={1.5} dot={false} strokeDasharray="5 5" connectNulls />
          </ComposedChart>
        </ResponsiveContainer>
      </ChartPanel>

      {/* ── 4. BATTERY ───────────────────────────────────────────── */}
      <ChartPanel
        icon={<Battery className="h-5 w-5 text-emerald-400" />}
        title="Battery"
        subtitle="Charge level & health trend"
        color="border-emerald-500/20"
        badge={
          <div className="flex items-center gap-2">
            <LiveBadge value={latest?.battery_level ?? 0} unit="%" color="text-emerald-300" />
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${latest?.power_source === 'ac' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}`}>
              {latest?.power_source === 'ac' ? '⚡ AC' : '🔋 BAT'}
            </span>
          </div>
        }
      >
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
            <GradientDefs />
            {GRID}
            {xAxis}
            <YAxis {...axisStyle} domain={[0, 100]} tickFormatter={v => `${v}%`} />
            <Tooltip content={<DarkTooltip unit="%" />} />
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
            <ReferenceLine y={20} stroke="#ef4444" strokeDasharray="4 2" strokeOpacity={0.5} label={{ value: 'Low', fill: '#ef4444', fontSize: 10, position: 'insideTopRight' }} />
            <Area type="monotone" dataKey="battery_level" name="Battery %" stroke="#10b981" strokeWidth={2.5} fill="url(#gBat)" dot={false} />
            <Line type="monotone" dataKey="battery_health" name="Health %" stroke="#f59e0b" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
            <Line type="monotone" dataKey="projected_battery_level" name="Projected Battery %" stroke="#34d399" strokeWidth={2.5} dot={false} strokeDasharray="5 5" connectNulls />
          </AreaChart>
        </ResponsiveContainer>
      </ChartPanel>

      {/* ── 5. WIFI SIGNAL ───────────────────────────────────────── */}
      <ChartPanel
        fullWidth
        icon={<Wifi className="h-5 w-5 text-sky-400" />}
        title="WiFi Signal Strength"
        subtitle={latest?.ssid ? `Connected to: ${latest.ssid} · ${latest.link_speed_mbps ?? '—'} Mbps` : 'Monitoring wireless signal quality'}
        color="border-sky-500/20"
        badge={
          <div className="flex items-center gap-2">
            {latest?.signal_strength_dbm != null && (
              <>
                <LiveBadge value={latest.signal_strength_dbm} unit=" dBm" color="text-sky-300" />
                <span className="text-[10px] text-slate-400 font-mono">{dbmToPercent(latest.signal_strength_dbm)}%</span>
              </>
            )}
            {latest?.signal_strength_dbm != null && (
              latest.signal_strength_dbm > -60
                ? <TrendingUp className="h-4 w-4 text-emerald-400" />
                : <TrendingDown className="h-4 w-4 text-amber-400" />
            )}
          </div>
        }
      >
        <ResponsiveContainer width="100%" height={160}>
          <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
            <GradientDefs />
            {GRID}
            {xAxis}
            <YAxis
              {...axisStyle}
              domain={[-100, -20]}
              tickFormatter={v => `${v}`}
              tickCount={5}
              stroke="#38bdf8"
            />
            <Tooltip
              content={({ active, payload, label }: any) => {
                if (!active || !payload?.length) return null;
                const val = payload[0]?.value;
                return (
                  <div className="bg-[#0d1424]/95 border border-white/10 rounded-xl p-3 shadow-2xl text-xs min-w-[150px]">
                    <p className="text-slate-400 font-semibold mb-1">{label}</p>
                    <p className="text-sky-300 font-bold">{val} dBm</p>
                    <p className="text-slate-500 mt-0.5">{val != null ? dbmToPercent(val) : '—'}% quality</p>
                  </div>
                );
              }}
            />
            <ReferenceLine y={-67} stroke="#f59e0b" strokeDasharray="4 2" strokeOpacity={0.5} label={{ value: 'Fair', fill: '#f59e0b', fontSize: 10, position: 'insideTopRight' }} />
            <ReferenceLine y={-80} stroke="#ef4444" strokeDasharray="4 2" strokeOpacity={0.5} label={{ value: 'Poor', fill: '#ef4444', fontSize: 10, position: 'insideTopRight' }} />
            <Area
              type="monotone"
              dataKey="signal_strength_dbm"
              name="Signal (dBm)"
              stroke="#38bdf8"
              strokeWidth={2.5}
              fill="url(#gWifi)"
              dot={false}
              connectNulls
            />
          </AreaChart>
        </ResponsiveContainer>
      </ChartPanel>

    </div>
  );
};

export default TelemetryCharts;
