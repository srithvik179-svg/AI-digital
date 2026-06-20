'use client';

import React, { useState } from 'react';
import { Play, Sparkles, AlertCircle, Loader, HelpCircle } from 'lucide-react';

interface TimeTravelPlaygroundProps {
  deviceId: string;
  selectedTimestamp: string | null;
  onProjectionLoaded: (projection: any[] | null) => void;
}

export const TimeTravelPlayground: React.FC<TimeTravelPlaygroundProps> = ({
  deviceId,
  selectedTimestamp,
  onProjectionLoaded,
}) => {
  const [cpuLoad, setCpuLoad] = useState<number>(80);
  const [gpuLoad, setGpuLoad] = useState<number>(30);
  const [duration, setDuration] = useState<number>(30);
  const [powerSource, setPowerSource] = useState<'battery' | 'ac' | 'inherit'>('inherit');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasRun, setHasRun] = useState(false);

  const handleRunSimulation = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const payload = {
        device_id: deviceId,
        start_timestamp: selectedTimestamp || null,
        cpu_load: cpuLoad,
        gpu_load: gpuLoad,
        duration_minutes: duration,
        power_source: powerSource === 'inherit' ? null : powerSource,
      };

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/twin-state/what-if`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        }
      );

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to project scenario');
      }

      const data = await response.json();
      onProjectionLoaded(data);
      setHasRun(true);
    } catch (err: any) {
      setError(err.message || 'Error running projection');
      onProjectionLoaded(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClear = () => {
    onProjectionLoaded(null);
    setHasRun(false);
  };

  return (
    <div className="glass-panel rounded-2xl border border-white/5 p-6 flex flex-col gap-5">
      <div>
        <h3 className="text-sm font-bold text-white flex items-center gap-2 leading-tight">
          Time Travel scenario Planner
          <Sparkles className="h-4 w-4 text-amber-400 fill-amber-400/20" />
        </h3>
        <p className="text-[11px] text-slate-500 mt-0.5">Project and overlay what-if telemetry paths on top of historical trends</p>
      </div>

      <div className="flex flex-col gap-4">
        {/* Seed Info Card */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-3.5 flex flex-col gap-1.5">
          <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Seed Point (Branch start)</span>
          {selectedTimestamp ? (
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-bold text-indigo-300">
                {new Date(selectedTimestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
              <span className="text-[9px] px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-400 font-bold border border-indigo-500/30">
                Custom Point
              </span>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400 italic">Latest snapshot state</span>
              <span className="text-[9px] px-2 py-0.5 rounded bg-slate-500/20 text-slate-400 font-bold border border-slate-500/30">
                Real-Time
              </span>
            </div>
          )}
          <p className="text-[10px] text-slate-500 mt-1 leading-normal">
            💡 <span className="text-slate-400">Tip:</span> drag the Replay console slider or click on any replay frame to lock in a seed timestamp!
          </p>
        </div>

        {/* Load configuration sliders */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="flex flex-col gap-2">
            <div className="flex justify-between text-xs">
              <span className="text-slate-300 font-semibold">Simulated CPU Load</span>
              <span className="text-indigo-400 font-mono font-bold">{cpuLoad}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              value={cpuLoad}
              onChange={(e) => setCpuLoad(parseInt(e.target.value))}
              className="accent-indigo-500 h-1 bg-white/10 rounded-lg appearance-none cursor-pointer"
            />
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex justify-between text-xs">
              <span className="text-slate-300 font-semibold">Simulated GPU Load</span>
              <span className="text-violet-400 font-mono font-bold">{gpuLoad}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              value={gpuLoad}
              onChange={(e) => setGpuLoad(parseInt(e.target.value))}
              className="accent-violet-500 h-1 bg-white/10 rounded-lg appearance-none cursor-pointer"
            />
          </div>
        </div>

        {/* Duration & Power source selection */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-slate-400">Duration</label>
            <select
              value={duration}
              onChange={(e) => setDuration(parseInt(e.target.value))}
              className="bg-white/5 border border-white/10 rounded-xl text-xs p-3 text-slate-200 outline-none focus:border-indigo-500 cursor-pointer"
            >
              <option value={5} className="bg-[#0e1626]">5 Minutes</option>
              <option value={10} className="bg-[#0e1626]">10 Minutes</option>
              <option value={15} className="bg-[#0e1626]">15 Minutes</option>
              <option value={30} className="bg-[#0e1626]">30 Minutes</option>
              <option value={60} className="bg-[#0e1626]">60 Minutes (1 hour)</option>
              <option value={120} className="bg-[#0e1626]">120 Minutes (2 hours)</option>
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-slate-400">Power Source</label>
            <select
              value={powerSource}
              onChange={(e) => setPowerSource(e.target.value as any)}
              className="bg-white/5 border border-white/10 rounded-xl text-xs p-3 text-slate-200 outline-none focus:border-indigo-500 cursor-pointer"
            >
              <option value="inherit" className="bg-[#0e1626]">Inherit from seed</option>
              <option value="battery" className="bg-[#0e1626]">🔌 Battery Only</option>
              <option value="ac" className="bg-[#0e1626]">⚡ AC Charger connected</option>
            </select>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl p-3">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Buttons */}
        <div className="flex items-center gap-3 mt-1">
          <button
            onClick={handleRunSimulation}
            disabled={isLoading}
            className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 text-xs font-bold text-white transition shadow-lg shadow-indigo-500/20"
          >
            {isLoading ? (
              <>
                <Loader className="h-4 w-4 animate-spin" />
                Projecting scenario...
              </>
            ) : (
              <>
                <Play className="h-4 w-4 fill-white" />
                Project Branch Path
              </>
            )}
          </button>
          
          {hasRun && (
            <button
              onClick={handleClear}
              className="py-3 px-4 rounded-xl border border-white/10 hover:bg-white/5 text-xs text-slate-400 hover:text-white transition"
            >
              Clear
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default TimeTravelPlayground;
