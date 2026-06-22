'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts';
import {
  TrendingUp, Thermometer, Battery, Wifi, Cpu, Play,
  AlertTriangle, Clock, Activity, Zap, RefreshCw,
} from 'lucide-react';

/* ─────────────────────────────────────────────────────────
   Types
───────────────────────────────────────────────────────── */

interface ThermalForecast {
  cpu_temperature_forecast: number[];
  gpu_temperature_forecast: number[];
  tick_seconds: number;
  horizon_ticks: number;
  model: string;
}

interface BatteryForecast {
  battery_soc_forecast: number[];
  battery_temp_forecast: number[];
  tick_seconds: number;
  horizon_ticks: number;
  model: string;
}

interface NetworkForecast {
  wifi_rssi_forecast: number[];
  packet_loss_forecast: number[];
  wifi_quality_forecast: string[];
  tick_seconds: number;
  horizon_ticks: number;
  model: string;
}

interface FutureStatePrediction {
  thermal: ThermalForecast;
  battery: BatteryForecast;
  network: NetworkForecast;
  horizon_ticks: number;
  tick_seconds: number;
  horizon_minutes: number;
}

/* ─────────────────────────────────────────────────────────
   Chart tooltip
───────────────────────────────────────────────────────── */

const CustomTooltip = ({ active, payload, label, unit }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#0c1525]/95 backdrop-blur border border-white/10 rounded-xl px-3 py-2 shadow-xl text-xs">
      <p className="text-slate-400 mb-1 font-mono">t+{label}s</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} style={{ color: p.color }} className="font-bold font-mono">
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(1) : p.value}{unit}
        </p>
      ))}
    </div>
  );
};

/* ─────────────────────────────────────────────────────────
   Slider helper
───────────────────────────────────────────────────────── */

const Slider = ({
  label, value, min, max, step = 1, unit,
  color = 'indigo', onChange,
}: {
  label: string; value: number; min: number; max: number;
  step?: number; unit?: string; color?: string;
  onChange: (v: number) => void;
}) => (
  <div className="flex flex-col gap-1">
    <div className="flex justify-between text-[11px]">
      <span className="text-slate-400">{label}</span>
      <span className="text-white font-bold font-mono">{value}{unit}</span>
    </div>
    <input
      type="range" min={min} max={max} step={step} value={value}
      onChange={e => onChange(parseFloat(e.target.value))}
      className={`h-1 rounded-full appearance-none cursor-pointer bg-white/10 accent-${color}-500`}
      style={{ accentColor: color === 'emerald' ? '#10b981' : color === 'rose' ? '#f43f5e' : color === 'amber' ? '#f59e0b' : '#6366f1' }}
    />
  </div>
);

/* ─────────────────────────────────────────────────────────
   Quality badge
───────────────────────────────────────────────────────── */

const qualityColor: Record<string, string> = {
  Good: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
  Fair: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  Poor: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
  Critical: 'text-red-400 bg-red-500/15 border-red-500/30',
};

const QualityBadge = ({ q }: { q: string }) => (
  <span className={`text-[10px] font-bold border rounded px-1.5 py-0.5 ${qualityColor[q] ?? 'text-slate-400 bg-white/5 border-white/10'}`}>
    {q}
  </span>
);

/* ─────────────────────────────────────────────────────────
   Build chart data from forecast arrays
───────────────────────────────────────────────────────── */

function buildChartData<T extends Record<string, number[]>>(
  arrays: T,
  tickSec: number,
): Array<{ t: number } & { [K in keyof T]: number }> {
  const n = Math.max(...Object.values(arrays).map(a => a.length));
  return Array.from({ length: n }, (_, i) => {
    const row: any = { t: (i + 1) * tickSec };
    for (const key of Object.keys(arrays) as (keyof T)[]) {
      row[key as string] = arrays[key][i] ?? 0;
    }
    return row;
  });
}

/* ─────────────────────────────────────────────────────────
   Main Component
───────────────────────────────────────────────────────── */

export const FutureStateDashboard: React.FC = () => {
  /* Input state */
  const [cpuTempBase,   setCpuTempBase]   = useState(58);
  const [gpuTempBase,   setGpuTempBase]   = useState(52);
  const [cpuUsageBase,  setCpuUsageBase]  = useState(45);
  const [gpuUsageBase,  setGpuUsageBase]  = useState(30);
  const [fanRpmBase,    setFanRpmBase]    = useState(2500);
  const [ambientTemp,   setAmbientTemp]   = useState(25);
  const [batterySoc,    setBatterySoc]    = useState(70);
  const [cpuWatts,      setCpuWatts]      = useState(12);
  const [gpuWatts,      setGpuWatts]      = useState(5);
  const [isCharging,    setIsCharging]    = useState(false);
  const [rssi,          setRssi]          = useState(-65);
  const [horizon,       setHorizon]       = useState(30);

  /* Result state */
  const [result,     setResult]     = useState<FutureStatePrediction | null>(null);
  const [isLoading,  setIsLoading]  = useState(false);
  const [error,      setError]      = useState<string | null>(null);
  const [activeTab,  setActiveTab]  = useState<'thermal' | 'battery' | 'network'>('thermal');

  /* ── Build request payload ── */
  const buildPayload = useCallback(() => {
    const make = (v: number, n = 10) => Array.from({ length: n }, () => v);
    return {
      cpu_temp_history:   make(cpuTempBase),
      gpu_temp_history:   make(gpuTempBase),
      cpu_usage_history:  make(cpuUsageBase),
      gpu_usage_history:  make(gpuUsageBase),
      fan_rpm_history:    make(fanRpmBase),
      ambient_temp:       ambientTemp,
      battery_soc_history: make(batterySoc),
      cpu_watts_history:  make(cpuWatts),
      gpu_watts_history:  make(gpuWatts),
      is_charging:        isCharging,
      wifi_rssi_history:  make(rssi, 15),
      horizon,
    };
  }, [
    cpuTempBase, gpuTempBase, cpuUsageBase, gpuUsageBase, fanRpmBase,
    ambientTemp, batterySoc, cpuWatts, gpuWatts, isCharging, rssi, horizon,
  ]);

  /* ── Run prediction ── */
  const runPrediction = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/future-state/predict`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(buildPayload()),
        }
      );
      if (!resp.ok) throw new Error(`API error ${resp.status}`);
      const data: FutureStatePrediction = await resp.json();
      setResult(data);
    } catch (e: any) {
      setError(e.message ?? 'Prediction failed');
    } finally {
      setIsLoading(false);
    }
  }, [buildPayload]);

  /* ── Derived chart data ── */
  const thermalData = result
    ? buildChartData(
        {
          cpu: result.thermal.cpu_temperature_forecast,
          gpu: result.thermal.gpu_temperature_forecast,
        },
        result.tick_seconds
      )
    : [];

  const batteryData = result
    ? buildChartData(
        {
          soc:  result.battery.battery_soc_forecast,
          temp: result.battery.battery_temp_forecast,
        },
        result.tick_seconds
      )
    : [];

  const networkData = result
    ? buildChartData(
        {
          rssi: result.network.wifi_rssi_forecast,
          loss: result.network.packet_loss_forecast,
        },
        result.tick_seconds
      )
    : [];

  /* ── Summary stats ── */
  const peakCpu  = result ? Math.max(...result.thermal.cpu_temperature_forecast).toFixed(1) : '--';
  const minSoc   = result ? Math.min(...result.battery.battery_soc_forecast).toFixed(1) : '--';
  const avgRssi  = result
    ? (result.network.wifi_rssi_forecast.reduce((a, b) => a + b, 0) / result.network.wifi_rssi_forecast.length).toFixed(1)
    : '--';
  const lastQuality = result
    ? result.network.wifi_quality_forecast[result.network.wifi_quality_forecast.length - 1]
    : null;

  /* ── Tab config ── */
  const tabs: { key: 'thermal' | 'battery' | 'network'; label: string; icon: React.ReactNode }[] = [
    { key: 'thermal', label: 'Thermal',  icon: <Thermometer className="h-3.5 w-3.5" /> },
    { key: 'battery', label: 'Battery',  icon: <Battery      className="h-3.5 w-3.5" /> },
    { key: 'network', label: 'Network',  icon: <Wifi         className="h-3.5 w-3.5" /> },
  ];

  return (
    <div className="glass-panel rounded-2xl border border-white/5 p-6 flex flex-col gap-6">
      {/* ── Header ── */}
      <div className="flex justify-between items-start gap-4">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2 leading-tight">
            <TrendingUp className="h-4 w-4 text-violet-400" />
            Future-State Prediction Engine
          </h3>
          <p className="text-[11px] text-slate-500 mt-0.5">
            XGBoost · LSTM · Prophet — {horizon}-tick ({result?.horizon_minutes ?? (horizon * 5 / 60).toFixed(1)} min) lookahead
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isLoading && (
            <span className="text-[10px] bg-violet-500/20 text-violet-300 px-2 py-0.5 rounded border border-violet-500/30 font-bold font-mono animate-pulse">
              RUNNING MODELS
            </span>
          )}
          <button
            id="run-future-state-prediction"
            onClick={runPrediction}
            disabled={isLoading}
            className="flex items-center gap-1.5 text-[11px] font-bold px-3 py-1.5 rounded-xl
              bg-violet-600/20 hover:bg-violet-600/40 border border-violet-500/30 text-violet-300
              transition disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {isLoading ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            {isLoading ? 'Running...' : 'Run Forecast'}
          </button>
        </div>
      </div>

      {/* ── Input Grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Thermal inputs */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-4 flex flex-col gap-3">
          <h4 className="text-[10px] uppercase tracking-wider text-slate-500 font-bold flex items-center gap-1.5">
            <Thermometer className="h-3 w-3 text-rose-400" /> Thermal Inputs
          </h4>
          <Slider label="CPU Temp (current)" value={cpuTempBase}  min={25} max={100} unit="°C" color="rose"   onChange={setCpuTempBase} />
          <Slider label="GPU Temp (current)" value={gpuTempBase}  min={25} max={95}  unit="°C" color="orange" onChange={setGpuTempBase} />
          <Slider label="CPU Usage"          value={cpuUsageBase} min={0}  max={100} unit="%"  color="indigo" onChange={setCpuUsageBase} />
          <Slider label="GPU Usage"          value={gpuUsageBase} min={0}  max={100} unit="%"  color="purple" onChange={setGpuUsageBase} />
          <Slider label="Fan RPM"            value={fanRpmBase}   min={1000} max={6500} step={100} color="slate" onChange={setFanRpmBase} />
          <Slider label="Ambient Temp"       value={ambientTemp}  min={15} max={45}  unit="°C" color="amber" onChange={setAmbientTemp} />
        </div>

        {/* Battery inputs */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-4 flex flex-col gap-3">
          <h4 className="text-[10px] uppercase tracking-wider text-slate-500 font-bold flex items-center gap-1.5">
            <Battery className="h-3 w-3 text-emerald-400" /> Battery Inputs
          </h4>
          <Slider label="Battery SoC" value={batterySoc} min={0}  max={100} unit="%"  color="emerald" onChange={setBatterySoc} />
          <Slider label="CPU Draw"    value={cpuWatts}   min={1}  max={60}  unit="W"  color="indigo"  onChange={setCpuWatts} />
          <Slider label="GPU Draw"    value={gpuWatts}   min={0}  max={35}  unit="W"  color="purple"  onChange={setGpuWatts} />
          <div className="mt-1 flex items-center justify-between">
            <span className="text-[11px] text-slate-400">AC Adapter</span>
            <button
              onClick={() => setIsCharging(v => !v)}
              className={`relative w-10 h-5 rounded-full transition-colors ${isCharging ? 'bg-emerald-500' : 'bg-white/10'}`}
            >
              <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${isCharging ? 'translate-x-5' : ''}`} />
            </button>
          </div>
          <Slider label="Forecast Horizon" value={horizon} min={5} max={120} step={5} unit=" ticks" color="violet" onChange={setHorizon} />
        </div>

        {/* Network inputs */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-4 flex flex-col gap-3">
          <h4 className="text-[10px] uppercase tracking-wider text-slate-500 font-bold flex items-center gap-1.5">
            <Wifi className="h-3 w-3 text-sky-400" /> Network Inputs
          </h4>
          <Slider label="WiFi RSSI (current)" value={rssi} min={-95} max={-20} unit=" dBm" color="sky" onChange={setRssi} />
          <div className="text-[10px] text-slate-500 mt-1">
            Current signal:{' '}
            <QualityBadge q={rssi >= -60 ? 'Good' : rssi >= -70 ? 'Fair' : rssi >= -80 ? 'Poor' : 'Critical'} />
          </div>

          {/* Summary stats */}
          {result && (
            <div className="mt-auto pt-3 border-t border-white/10 flex flex-col gap-2">
              <h5 className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">Forecast Summary</h5>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-white/5 rounded-xl p-2.5 text-center">
                  <span className="text-[9px] text-slate-500 uppercase block">Peak CPU</span>
                  <span className="text-xs font-bold font-mono text-rose-400">{peakCpu}°C</span>
                </div>
                <div className="bg-white/5 rounded-xl p-2.5 text-center">
                  <span className="text-[9px] text-slate-500 uppercase block">Min SoC</span>
                  <span className="text-xs font-bold font-mono text-emerald-400">{minSoc}%</span>
                </div>
                <div className="bg-white/5 rounded-xl p-2.5 text-center">
                  <span className="text-[9px] text-slate-500 uppercase block">Avg RSSI</span>
                  <span className="text-xs font-bold font-mono text-sky-400">{avgRssi} dBm</span>
                </div>
                <div className="bg-white/5 rounded-xl p-2.5 text-center">
                  <span className="text-[9px] text-slate-500 uppercase block">End Quality</span>
                  {lastQuality && <QualityBadge q={lastQuality} />}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Error ── */}
      {error && (
        <div className="flex items-center gap-2 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl p-3">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* ── Chart Tabs ── */}
      {result ? (
        <div className="flex flex-col gap-4">
          {/* Tab bar */}
          <div className="flex gap-1.5 bg-white/5 p-1 rounded-xl w-fit">
            {tabs.map(tab => (
              <button
                key={tab.key}
                id={`future-state-tab-${tab.key}`}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-1.5 text-[11px] font-bold px-3 py-1.5 rounded-lg transition ${
                  activeTab === tab.key
                    ? 'bg-violet-600/30 text-violet-300 border border-violet-500/30'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>

          {/* Thermal chart */}
          {activeTab === 'thermal' && (
            <div className="bg-white/5 border border-white/10 rounded-2xl p-4">
              <div className="flex justify-between items-center mb-3">
                <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                  <Thermometer className="h-3.5 w-3.5 text-rose-400" />
                  CPU &amp; GPU Temperature Forecast
                </span>
                <span className="text-[10px] text-slate-500 font-mono">
                  Model: <span className="text-violet-400">{result.thermal.model}</span>
                </span>
              </div>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={thermalData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="cpuTempGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#f43f5e" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gpuTempGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#a78bfa" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#a78bfa" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis dataKey="t" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={v => `+${v}s`} />
                  <YAxis domain={[25, 105]} tick={{ fill: '#64748b', fontSize: 10 }} unit="°" />
                  <Tooltip content={<CustomTooltip unit="°C" />} />
                  <ReferenceLine y={75} stroke="#f59e0b" strokeDasharray="4 2" strokeOpacity={0.5} label={{ value: 'Warn', fill: '#f59e0b', fontSize: 9 }} />
                  <ReferenceLine y={90} stroke="#f43f5e" strokeDasharray="4 2" strokeOpacity={0.5} label={{ value: 'Crit', fill: '#f43f5e', fontSize: 9 }} />
                  <Area type="monotone" dataKey="cpu" name="CPU" stroke="#f43f5e" fill="url(#cpuTempGrad)" strokeWidth={2} dot={false} />
                  <Area type="monotone" dataKey="gpu" name="GPU" stroke="#a78bfa" fill="url(#gpuTempGrad)" strokeWidth={2} dot={false} />
                  <Legend wrapperStyle={{ fontSize: '10px', paddingTop: '8px', color: '#94a3b8' }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Battery chart */}
          {activeTab === 'battery' && (
            <div className="bg-white/5 border border-white/10 rounded-2xl p-4">
              <div className="flex justify-between items-center mb-3">
                <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                  <Battery className="h-3.5 w-3.5 text-emerald-400" />
                  Battery SoC &amp; Temperature Forecast
                </span>
                <span className="text-[10px] text-slate-500 font-mono">
                  Model: <span className="text-violet-400">{result.battery.model}</span>
                </span>
              </div>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={batteryData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="socGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#10b981" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="btempGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#f59e0b" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis dataKey="t" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={v => `+${v}s`} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                  <Tooltip content={<CustomTooltip unit="" />} />
                  <ReferenceLine y={20} stroke="#f43f5e" strokeDasharray="4 2" strokeOpacity={0.5} label={{ value: 'Low', fill: '#f43f5e', fontSize: 9 }} />
                  <Area type="monotone" dataKey="soc"  name="SoC (%)"  stroke="#10b981" fill="url(#socGrad)"   strokeWidth={2} dot={false} />
                  <Area type="monotone" dataKey="temp" name="Temp (°C)" stroke="#f59e0b" fill="url(#btempGrad)" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                  <Legend wrapperStyle={{ fontSize: '10px', paddingTop: '8px', color: '#94a3b8' }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Network chart */}
          {activeTab === 'network' && (
            <div className="bg-white/5 border border-white/10 rounded-2xl p-4">
              <div className="flex justify-between items-center mb-3">
                <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                  <Wifi className="h-3.5 w-3.5 text-sky-400" />
                  WiFi Signal &amp; Packet Loss Forecast
                </span>
                <span className="text-[10px] text-slate-500 font-mono">
                  Model: <span className="text-violet-400">{result.network.model}</span>
                </span>
              </div>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={networkData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="rssiGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#38bdf8" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#38bdf8" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="lossGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#fb923c" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#fb923c" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis dataKey="t" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={v => `+${v}s`} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                  <Tooltip content={<CustomTooltip unit="" />} />
                  <ReferenceLine y={-70} stroke="#f59e0b" strokeDasharray="4 2" strokeOpacity={0.5} label={{ value: 'Fair', fill: '#f59e0b', fontSize: 9 }} />
                  <ReferenceLine y={-80} stroke="#f43f5e" strokeDasharray="4 2" strokeOpacity={0.5} label={{ value: 'Poor', fill: '#f43f5e', fontSize: 9 }} />
                  <Area type="monotone" dataKey="rssi" name="RSSI (dBm)"     stroke="#38bdf8" fill="url(#rssiGrad)" strokeWidth={2}   dot={false} />
                  <Area type="monotone" dataKey="loss" name="Packet Loss (%)" stroke="#fb923c" fill="url(#lossGrad)" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                  <Legend wrapperStyle={{ fontSize: '10px', paddingTop: '8px', color: '#94a3b8' }} />
                </AreaChart>
              </ResponsiveContainer>

              {/* Quality timeline */}
              <div className="mt-3 flex gap-1 flex-wrap">
                {result.network.wifi_quality_forecast.filter((_, i) => i % 5 === 0).map((q, i) => (
                  <QualityBadge key={i} q={q} />
                ))}
              </div>
            </div>
          )}

          {/* Model attribution row */}
          <div className="flex gap-3 flex-wrap">
            {[
              { label: 'XGBoost', desc: 'CPU/GPU Thermal', color: 'text-rose-400' },
              { label: 'LSTM',    desc: 'Battery SoC',     color: 'text-emerald-400' },
              { label: 'Prophet', desc: 'WiFi Signal',     color: 'text-sky-400' },
            ].map(m => (
              <div key={m.label} className="flex items-center gap-1.5 text-[10px] text-slate-500 bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5">
                <Activity className={`h-3 w-3 ${m.color}`} />
                <span className={`font-bold ${m.color}`}>{m.label}</span>
                <span>→ {m.desc}</span>
              </div>
            ))}
            <div className="flex items-center gap-1.5 text-[10px] text-slate-500 bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 ml-auto">
              <Clock className="h-3 w-3 text-violet-400" />
              <span className="font-bold text-violet-400">{result.horizon_ticks}</span>
              <span>ticks · {result.horizon_minutes} min lookahead</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-12 border border-white/5 border-dashed rounded-2xl text-center text-slate-500 gap-3">
          <TrendingUp className="h-10 w-10 opacity-20" />
          <div>
            <p className="text-sm font-semibold">No forecast yet</p>
            <p className="text-xs mt-1">Configure inputs above and click <strong className="text-violet-400">Run Forecast</strong></p>
          </div>
        </div>
      )}
    </div>
  );
};

export default FutureStateDashboard;
