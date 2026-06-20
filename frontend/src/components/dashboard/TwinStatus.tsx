import React from 'react';
import { TelemetryData } from '@/types';
import { Cpu, Thermometer, Battery, HardDrive, RefreshCw } from 'lucide-react';

interface TwinStatusProps {
  latestData: TelemetryData | null;
  isConnected: boolean;
}

export const TwinStatus: React.FC<TwinStatusProps> = ({ latestData, isConnected }) => {
  if (!latestData) {
    return (
      <div className="glass-panel rounded-2xl p-6 flex flex-col items-center justify-center h-48 border border-white/5">
        <RefreshCw className="animate-spin text-indigo-400 mb-2 h-8 w-8" />
        <p className="text-slate-400 text-sm">Awaiting laptop telemetry connection...</p>
      </div>
    );
  }

  const getBatteryColor = (level: number) => {
    if (level < 20) return 'text-red-500';
    if (level < 50) return 'text-amber-500';
    return 'text-emerald-500';
  };

  const getTempColor = (temp: number) => {
    if (temp > 75) return 'text-red-500';
    if (temp > 60) return 'text-amber-500';
    return 'text-cyan-400';
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 w-full">
      {/* CPU Usage Card */}
      <div className="glass-panel rounded-2xl p-5 border border-white/5 relative overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:border-indigo-500/30">
        <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-500/5 rounded-bl-full pointer-events-none" />
        <div className="flex items-center justify-between mb-4">
          <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">CPU Utilization</span>
          <Cpu className="text-indigo-400 h-5 w-5" />
        </div>
        <div className="flex items-baseline space-x-1">
          <span className="text-3xl font-bold tracking-tight">{latestData.cpu_usage}%</span>
          <span className="text-slate-500 text-xs">active</span>
        </div>
        <div className="mt-3 w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
          <div 
            className="bg-indigo-500 h-1.5 rounded-full transition-all duration-500" 
            style={{ width: `${latestData.cpu_usage}%` }}
          />
        </div>
        <p className="text-slate-400 text-xs mt-2 flex justify-between">
          <span>Processes: {latestData.active_process_count}</span>
          <span>Core Temp: {latestData.cpu_temperature}°C</span>
        </p>
      </div>

      {/* Memory Usage Card */}
      <div className="glass-panel rounded-2xl p-5 border border-white/5 relative overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:border-purple-500/30">
        <div className="absolute top-0 right-0 w-24 h-24 bg-purple-500/5 rounded-bl-full pointer-events-none" />
        <div className="flex items-center justify-between mb-4">
          <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Memory (RAM)</span>
          <Cpu className="text-purple-400 h-5 w-5" />
        </div>
        <div className="flex items-baseline space-x-1">
          <span className="text-3xl font-bold tracking-tight">{latestData.memory_usage}%</span>
          <span className="text-slate-500 text-xs">allocated</span>
        </div>
        <div className="mt-3 w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
          <div 
            className="bg-purple-500 h-1.5 rounded-full transition-all duration-500" 
            style={{ width: `${latestData.memory_usage}%` }}
          />
        </div>
        <p className="text-slate-400 text-xs mt-2 flex justify-between">
          <span>Buffer Cache: Active</span>
          <span>Disk: {latestData.disk_usage}%</span>
        </p>
      </div>

      {/* Thermals and Fan Speed Card */}
      <div className="glass-panel rounded-2xl p-5 border border-white/5 relative overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:border-cyan-500/30">
        <div className="absolute top-0 right-0 w-24 h-24 bg-cyan-500/5 rounded-bl-full pointer-events-none" />
        <div className="flex items-center justify-between mb-4">
          <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Thermals & Fan</span>
          <Thermometer className={`${getTempColor(latestData.cpu_temperature)} h-5 w-5`} />
        </div>
        <div className="flex items-baseline space-x-1">
          <span className="text-3xl font-bold tracking-tight">{latestData.cpu_temperature}°C</span>
          <span className="text-slate-500 text-xs">core</span>
        </div>
        <div className="mt-3 w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
          <div 
            className="bg-cyan-400 h-1.5 rounded-full transition-all duration-500" 
            style={{ width: `${Math.min(100, Math.max(0, (latestData.cpu_temperature - 30) * 1.5))}%` }}
          />
        </div>
        <p className="text-slate-400 text-xs mt-2 flex justify-between">
          <span>Fan speed: {latestData.fan_speed} RPM</span>
          <span className={latestData.cpu_temperature > 75 ? "text-red-400 font-medium" : "text-emerald-400"}>
            {latestData.cpu_temperature > 75 ? "Thermal warning" : "Cooling safe"}
          </span>
        </p>
      </div>

      {/* Battery State Card */}
      <div className="glass-panel rounded-2xl p-5 border border-white/5 relative overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:border-emerald-500/30">
        <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-bl-full pointer-events-none" />
        <div className="flex items-center justify-between mb-4">
          <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Battery Status</span>
          <Battery className={`${getBatteryColor(latestData.battery_level)} h-5 w-5`} />
        </div>
        <div className="flex items-baseline space-x-1">
          <span className="text-3xl font-bold tracking-tight">{latestData.battery_level}%</span>
          <span className="text-slate-500 text-xs uppercase">{latestData.power_source}</span>
        </div>
        <div className="mt-3 w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
          <div 
            className={`h-1.5 rounded-full transition-all duration-500 ${
              latestData.power_source === 'ac' ? 'bg-emerald-400 animate-pulse' : 'bg-emerald-500'
            }`}
            style={{ width: `${latestData.battery_level}%` }}
          />
        </div>
        <p className="text-slate-400 text-xs mt-2 flex justify-between">
          <span>Battery Health: {latestData.battery_health}%</span>
          <span>Source: {latestData.power_source.toUpperCase()}</span>
        </p>
      </div>
    </div>
  );
};
export default TwinStatus;
