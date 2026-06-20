import React, { useState } from 'react';
import { TelemetryData } from '@/types';
import { Search, Sparkles, AlertTriangle, CheckCircle, ChevronDown, ChevronUp, Clock, Cpu, Battery, HardDrive, Thermometer } from 'lucide-react';

interface TelemetrySearchProps {
  deviceId: string;
}

const SEARCH_SUGGESTIONS = [
  "Show high temperature events",
  "Show battery drain events",
  "Show high CPU load",
  "Show weak WiFi signals",
  "Show critical health snapshots"
];

export const TelemetrySearch: React.FC<TelemetrySearchProps> = ({ deviceId }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<TelemetryData[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const handleSearch = async (searchQuery: string) => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    setError(null);
    setExpandedRow(null);

    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/search?device_id=${deviceId}&query=${encodeURIComponent(searchQuery)}`
      );

      if (!response.ok) {
        throw new Error('Failed to query search engine');
      }

      const data = await response.json();
      setResults(data);
    } catch (err: any) {
      setError(err.message || 'An error occurred while searching.');
    } finally {
      setLoading(false);
    }
  };

  const getHealthBadgeClass = (category?: string) => {
    switch (category) {
      case 'Healthy':
        return 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
      case 'Warning':
        return 'bg-amber-500/10 text-amber-400 border border-amber-500/20';
      case 'Critical':
        return 'bg-rose-500/10 text-rose-400 border border-rose-500/20';
      default:
        return 'bg-slate-500/10 text-slate-400 border border-slate-500/20';
    }
  };

  const formatTimestamp = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleString();
    } catch {
      return isoString;
    }
  };

  return (
    <div className="glass-panel rounded-2xl border border-white/5 p-6 flex flex-col h-[520px] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2.5">
          <div className="p-1.5 bg-indigo-500/10 rounded-lg text-indigo-400">
            <Search className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-1.5">
              Telemetry Event Search
              <Sparkles className="h-3.5 w-3.5 text-amber-400 fill-amber-400/20" />
            </h2>
            <p className="text-slate-400 text-xs">Search logs using natural language</p>
          </div>
        </div>
      </div>

      {/* Search Input */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSearch(query);
        }}
        className="relative flex items-center mb-3"
      >
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask e.g. 'Show battery drain events' or 'Show high temperature'..."
          className="w-full bg-slate-950/80 border border-white/5 rounded-xl pl-4 pr-12 py-3 text-sm text-slate-200 focus:outline-none focus:border-indigo-500/50 transition duration-200"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="absolute right-2 p-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition duration-200 disabled:opacity-40"
        >
          {loading ? (
            <div className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <Search className="h-4 w-4" />
          )}
        </button>
      </form>

      {/* Suggestions */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {SEARCH_SUGGESTIONS.map((suggestion, i) => (
          <button
            key={i}
            type="button"
            onClick={() => {
              setQuery(suggestion);
              handleSearch(suggestion);
            }}
            className="text-[10px] px-2.5 py-1.5 rounded-lg bg-slate-900/60 border border-white/5 text-slate-400 hover:text-white hover:bg-slate-800/80 transition duration-200"
          >
            {suggestion}
          </button>
        ))}
      </div>

      {/* Results Box */}
      <div className="flex-1 overflow-y-auto space-y-2 bg-slate-950/20 rounded-xl p-2 border border-white/5">
        {error && (
          <div className="p-4 text-xs text-rose-400 bg-rose-500/5 border border-rose-500/10 rounded-lg">
            Error: {error}
          </div>
        )}

        {!loading && !error && results.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs py-8">
            <Clock className="h-8 w-8 mb-2 text-slate-600" />
            <span>No query executed or no matching records found.</span>
          </div>
        )}

        {results.map((item) => {
          const isExpanded = expandedRow === item.id;
          return (
            <div
              key={item.id}
              className="bg-slate-900/40 hover:bg-slate-900/60 border border-white/5 rounded-xl transition duration-200 overflow-hidden"
            >
              {/* Row Header */}
              <div
                onClick={() => setExpandedRow(isExpanded ? null : item.id)}
                className="px-4 py-3 flex items-center justify-between cursor-pointer text-xs"
              >
                <div className="flex items-center space-x-3 min-w-0">
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${getHealthBadgeClass(item.health_category)}`}>
                    {item.health_score ?? 100} / 100
                  </span>
                  <span className="text-slate-400 truncate max-w-[150px]">
                    {formatTimestamp(item.timestamp)}
                  </span>
                </div>
                <div className="flex items-center space-x-4">
                  <div className="hidden sm:flex items-center space-x-3 text-slate-400">
                    <span className="flex items-center gap-1"><Cpu className="h-3 w-3" /> {item.cpu_usage.toFixed(0)}%</span>
                    <span className="flex items-center gap-1"><Thermometer className="h-3 w-3" /> {item.cpu_temperature.toFixed(0)}°C</span>
                    <span className="flex items-center gap-1"><Battery className="h-3 w-3" /> {item.battery_level.toFixed(0)}%</span>
                  </div>
                  {isExpanded ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
                </div>
              </div>

              {/* Expandable Details */}
              {isExpanded && (
                <div className="px-4 pb-4 pt-1 border-t border-white/5 bg-slate-950/40 text-xs space-y-3">
                  {/* Quick summary grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-slate-300">
                    <div className="p-2 bg-slate-900/50 rounded-lg border border-white/5">
                      <div className="text-[10px] text-slate-500 uppercase font-semibold">CPU Usage</div>
                      <div className="font-bold mt-0.5 text-white">{item.cpu_usage.toFixed(1)}%</div>
                      <div className="text-[10px] text-slate-400">{item.active_process_count} active processes</div>
                    </div>
                    <div className="p-2 bg-slate-900/50 rounded-lg border border-white/5">
                      <div className="text-[10px] text-slate-500 uppercase font-semibold">Thermals</div>
                      <div className="font-bold mt-0.5 text-white">{item.cpu_temperature.toFixed(1)}°C</div>
                      <div className="text-[10px] text-slate-400">{item.fan_speed} RPM</div>
                    </div>
                    <div className="p-2 bg-slate-900/50 rounded-lg border border-white/5">
                      <div className="text-[10px] text-slate-500 uppercase font-semibold">Battery State</div>
                      <div className="font-bold mt-0.5 text-white">{item.battery_level.toFixed(1)}%</div>
                      <div className="text-[10px] text-slate-400 capitalize">{item.power_source} power (Health: {item.battery_health}%)</div>
                    </div>
                    <div className="p-2 bg-slate-900/50 rounded-lg border border-white/5">
                      <div className="text-[10px] text-slate-500 uppercase font-semibold">Disk Storage</div>
                      <div className="font-bold mt-0.5 text-white">{item.disk_usage.toFixed(1)}%</div>
                      <div className="text-[10px] text-slate-400">Used space</div>
                    </div>
                  </div>

                  {/* Secondary stats row */}
                  <div className="flex flex-wrap gap-x-6 gap-y-1.5 text-slate-400 text-[11px] border-t border-white/5 pt-2.5">
                    {item.gpu_usage !== undefined && (
                      <span>GPU: <strong className="text-slate-200">{item.gpu_usage.toFixed(1)}%</strong> (temp: {item.gpu_temperature}°C)</span>
                    )}
                    {item.signal_strength_dbm !== undefined && (
                      <span>WiFi: <strong className="text-slate-200">{item.ssid || 'connected'}</strong> ({item.signal_strength_dbm} dBm)</span>
                    )}
                    {item.thermal_state && (
                      <span>Thermal State: <strong className="text-slate-200 capitalize">{item.thermal_state}</strong></span>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
export default TelemetrySearch;
