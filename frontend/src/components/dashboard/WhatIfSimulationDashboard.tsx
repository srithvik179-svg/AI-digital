'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Sparkles, Thermometer, Zap, Battery, AlertTriangle, Fan, Cpu } from 'lucide-react';

export const WhatIfSimulationDashboard: React.FC = () => {
  const [cpuUsage, setCpuUsage] = useState<number>(50);
  const [gpuUsage, setGpuUsage] = useState<number>(20);
  const [memoryUsage, setMemoryUsage] = useState<number>(50);
  const [batteryLevel, setBatteryLevel] = useState<number>(80);
  const [batteryHealth, setBatteryHealth] = useState<number>(90);
  const [powerSource, setPowerSource] = useState<'battery' | 'ac'>('battery');
  const [ambientTemp, setAmbientTemp] = useState<number>(25);

  const [predictions, setPredictions] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const runSimulation = useCallback(async () => {
    setIsLoading(true);
    try {
      const payload = {
        cpu_usage: cpuUsage,
        gpu_usage: gpuUsage,
        memory_usage: memoryUsage,
        battery_level: batteryLevel,
        battery_health: batteryHealth,
        power_source: powerSource,
        ambient_temperature: ambientTemp
      };

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/what-if-simulation/simulate`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        }
      );

      if (!response.ok) {
        throw new Error('Simulation calculation failed');
      }

      const data = await response.json();
      setPredictions(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Error executing simulation');
    } finally {
      setIsLoading(false);
    }
  }, [cpuUsage, gpuUsage, memoryUsage, batteryLevel, batteryHealth, powerSource, ambientTemp]);

  useEffect(() => {
    runSimulation();
  }, [runSimulation]);

  const getTempColorClass = (state: string) => {
    switch (state) {
      case 'nominal': return 'text-emerald-400';
      case 'moderate': return 'text-amber-400';
      case 'serious': return 'text-rose-400';
      case 'critical': return 'text-red-500 animate-pulse';
      default: return 'text-slate-400';
    }
  };

  const getTempBgClass = (state: string) => {
    switch (state) {
      case 'nominal': return 'bg-emerald-500/10 border-emerald-500/20';
      case 'moderate': return 'bg-amber-500/10 border-amber-500/20';
      case 'serious': return 'bg-rose-500/10 border-rose-500/20';
      case 'critical': return 'bg-red-500/20 border-red-500/30';
      default: return 'bg-white/5 border-white/10';
    }
  };

  const formatRuntime = (mins: number) => {
    if (mins <= 0) return '0m';
    const hrs = Math.floor(mins / 60);
    const remainingMins = Math.round(mins % 60);
    if (hrs > 0) return `${hrs}h ${remainingMins}m`;
    return `${remainingMins}m`;
  };

  return (
    <div className="glass-panel rounded-2xl border border-white/5 p-6 flex flex-col gap-6">
      {/* Title */}
      <div className="flex justify-between items-start">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2 leading-tight">
            What-If Simulator Engine
            <Sparkles className="h-4 w-4 text-indigo-400 fill-indigo-400/20" />
          </h3>
          <p className="text-[11px] text-slate-500 mt-0.5">Simulate steady-state diagnostics under arbitrary workloads in real time</p>
        </div>
        {isLoading && (
          <span className="text-[10px] bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded border border-indigo-500/30 font-bold font-mono animate-pulse">
            COMPUTING
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sliders Control Panel */}
        <div className="flex flex-col gap-4 bg-white/5 border border-white/10 rounded-2xl p-5">
          <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">Hypothetical Workload</h4>
          
          <div className="flex flex-col gap-2">
            <div className="flex justify-between text-xs">
              <span className="text-slate-400">CPU Usage</span>
              <span className="text-white font-bold font-mono">{cpuUsage}%</span>
            </div>
            <input
              type="range" min={0} max={100} value={cpuUsage}
              onChange={(e) => setCpuUsage(parseInt(e.target.value))}
              className="accent-indigo-500 h-1 bg-white/10 rounded-lg appearance-none cursor-pointer"
            />
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex justify-between text-xs">
              <span className="text-slate-400">GPU Usage</span>
              <span className="text-white font-bold font-mono">{gpuUsage}%</span>
            </div>
            <input
              type="range" min={0} max={100} value={gpuUsage}
              onChange={(e) => setGpuUsage(parseInt(e.target.value))}
              className="accent-indigo-500 h-1 bg-white/10 rounded-lg appearance-none cursor-pointer"
            />
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex justify-between text-xs">
              <span className="text-slate-400">Memory Usage</span>
              <span className="text-white font-bold font-mono">{memoryUsage}%</span>
            </div>
            <input
              type="range" min={0} max={100} value={memoryUsage}
              onChange={(e) => setMemoryUsage(parseInt(e.target.value))}
              className="accent-indigo-500 h-1 bg-white/10 rounded-lg appearance-none cursor-pointer"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Battery Level</span>
                <span className="text-white font-bold font-mono">{batteryLevel}%</span>
              </div>
              <input
                type="range" min={0} max={100} value={batteryLevel}
                onChange={(e) => setBatteryLevel(parseInt(e.target.value))}
                className="accent-indigo-500 h-1 bg-white/10 rounded-lg appearance-none cursor-pointer"
              />
            </div>

            <div className="flex flex-col gap-2">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Battery Health</span>
                <span className="text-white font-bold font-mono">{batteryHealth}%</span>
              </div>
              <input
                type="range" min={10} max={100} value={batteryHealth}
                onChange={(e) => setBatteryHealth(parseInt(e.target.value))}
                className="accent-indigo-500 h-1 bg-white/10 rounded-lg appearance-none cursor-pointer"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 mt-1">
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">Power Source</label>
              <select
                value={powerSource}
                onChange={(e) => setPowerSource(e.target.value as any)}
                className="bg-white/5 border border-white/10 rounded-xl text-xs p-2.5 text-slate-200 outline-none focus:border-indigo-500 cursor-pointer"
              >
                <option value="battery" className="bg-[#0e1626]">🔌 Battery Power</option>
                <option value="ac" className="bg-[#0e1626]">⚡ AC Charger</option>
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">Ambient Temp</label>
              <select
                value={ambientTemp}
                onChange={(e) => setAmbientTemp(parseInt(e.target.value))}
                className="bg-white/5 border border-white/10 rounded-xl text-xs p-2.5 text-slate-200 outline-none focus:border-indigo-500 cursor-pointer"
              >
                <option value={18} className="bg-[#0e1626]">❄️ Cool (18°C)</option>
                <option value={25} className="bg-[#0e1626]">🌡️ Normal (25°C)</option>
                <option value={35} className="bg-[#0e1626]">🔥 Warm (35°C)</option>
                <option value={40} className="bg-[#0e1626]">🥵 Hot (40°C)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Prediction Results HUD */}
        <div className="flex flex-col gap-4">
          {error && (
            <div className="flex items-center gap-2 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl p-3">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {predictions ? (
            <div className="flex flex-col gap-4">
              {/* Thermal Dashboard */}
              <div className={`border rounded-2xl p-4 flex items-center justify-between transition ${getTempBgClass(predictions.temperature.thermal_state)}`}>
                <div className="flex items-center gap-3">
                  <div className={`p-2.5 rounded-xl bg-white/5 ${getTempColorClass(predictions.temperature.thermal_state)}`}>
                    <Thermometer className="h-5 w-5" />
                  </div>
                  <div>
                    <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 block leading-tight">Predicted Temperature</span>
                    <span className="text-lg font-bold text-white font-mono">{predictions.temperature.cpu_temperature}°C</span>
                  </div>
                </div>
                
                <div className="text-right">
                  <div className="flex items-center gap-1.5 justify-end">
                    <Fan className={`h-4 w-4 text-slate-400 ${predictions.temperature.fan_speed_rpm > 1200 ? 'animate-spin' : ''}`} />
                    <span className="text-xs font-mono font-bold text-slate-300">{predictions.temperature.fan_speed_rpm} RPM</span>
                  </div>
                  <span className={`text-[10px] font-bold uppercase ${getTempColorClass(predictions.temperature.thermal_state)}`}>
                    {predictions.temperature.thermal_state}
                  </span>
                </div>

                {predictions.temperature.is_throttling && (
                  <div className="ml-2 bg-red-500/25 border border-red-500/40 px-2 py-0.5 rounded text-[9px] font-bold text-red-300 animate-pulse uppercase tracking-wide">
                    Throttled ({Math.round(predictions.temperature.throttle_ratio * 100)}%)
                  </div>
                )}
              </div>

              {/* Power Consumption Dashboard */}
              <div className="bg-white/5 border border-white/10 rounded-2xl p-4 flex flex-col gap-3">
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <Zap className="h-4 w-4 text-yellow-400 fill-yellow-400/10" />
                    <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">Power Consumption</span>
                  </div>
                  <span className="text-sm font-bold text-yellow-400 font-mono">{predictions.power.total_power_draw_watts}W</span>
                </div>
                
                <div className="flex flex-col gap-2">
                  <div className="flex flex-col gap-0.5">
                    <div className="flex justify-between text-[10px] text-slate-400">
                      <span>CPU Core Draw</span>
                      <span className="font-mono text-slate-300">{predictions.power.cpu_power_draw_watts} W</span>
                    </div>
                    <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                      <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${Math.min(100, (predictions.power.cpu_power_draw_watts / 35.0) * 100)}%` }} />
                    </div>
                  </div>

                  <div className="flex flex-col gap-0.5">
                    <div className="flex justify-between text-[10px] text-slate-400">
                      <span>GPU Core Draw</span>
                      <span className="font-mono text-slate-300">{predictions.power.gpu_power_draw_watts} W</span>
                    </div>
                    <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                      <div className="h-full bg-violet-400 rounded-full" style={{ width: `${Math.min(100, (predictions.power.gpu_power_draw_watts / 20.0) * 100)}%` }} />
                    </div>
                  </div>

                  {predictions.power.charging_power_draw_watts > 0 && (
                    <div className="flex justify-between text-[10px] text-slate-400">
                      <span>Battery Charger Power</span>
                      <span className="font-mono text-emerald-400">+{predictions.power.charging_power_draw_watts} W</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Battery Impact Dashboard */}
              <div className="bg-white/5 border border-white/10 rounded-2xl p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-white/5 text-emerald-400">
                    <Battery className="h-5 w-5" />
                  </div>
                  <div>
                    <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 block leading-tight">
                      {predictions.battery.battery_status === 'charging' ? 'Estimated Charge Time' : 'Estimated Runtime'}
                    </span>
                    <span className="text-base font-bold text-white font-mono">
                      {predictions.battery.battery_status === 'full' ? 'Battery Full' : formatRuntime(predictions.battery.battery_remaining_minutes)}
                    </span>
                  </div>
                </div>

                <div className="text-right flex flex-col gap-0.5">
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 block leading-tight">Rate of Impact</span>
                  {predictions.battery.battery_status === 'charging' ? (
                    <span className="text-xs font-mono font-bold text-emerald-400">+{predictions.battery.battery_charge_rate_percent_per_hour}% / hr</span>
                  ) : predictions.battery.battery_status === 'full' ? (
                    <span className="text-xs font-mono font-bold text-slate-400 font-semibold">Stable</span>
                  ) : (
                    <span className="text-xs font-mono font-bold text-rose-400">-{predictions.battery.battery_drain_rate_percent_per_hour}% / hr</span>
                  )}
                  <span className="text-[9px] text-slate-500 font-mono">Temp: {predictions.battery.battery_temperature}°C</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center border border-white/5 border-dashed rounded-2xl p-8 text-center text-slate-500">
              <Cpu className="h-8 w-8 mb-2 opacity-30" />
              <p className="text-xs">Adjust sliders to calculate live diagnostics predictions</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default WhatIfSimulationDashboard;
