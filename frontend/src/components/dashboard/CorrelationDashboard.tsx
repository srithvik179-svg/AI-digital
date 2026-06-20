'use client';

import React, { useEffect, useState } from 'react';
import { SlidersHorizontal, RefreshCw, Info, TrendingUp, TrendingDown, HelpCircle } from 'lucide-react';

interface Metric {
  id: string;
  label: string;
}

interface CorrelationData {
  device_id: string;
  metrics: Metric[];
  pearson: number[][];
  spearman: number[][];
  total_records_analyzed: number;
}

interface CorrelationDashboardProps {
  deviceId: string;
  // Trigger update when historical logs are refreshed or simulated
  tickCount?: number;
}

export const CorrelationDashboard: React.FC<CorrelationDashboardProps> = ({ deviceId, tickCount = 0 }) => {
  const [data, setData] = useState<CorrelationData | null>(null);
  const [method, setMethod] = useState<'pearson' | 'spearman'>('pearson');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredCell, setHoveredCell] = useState<{ row: number; col: number; val: number } | null>(null);

  const fetchCorrelationMatrix = async () => {
    try {
      setLoading(true);
      const url = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/relationships/matrix?device_id=${deviceId}`;
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Failed to load matrix data (HTTP ${response.status})`);
      }
      const json = await response.json();
      setData(json);
      setError(null);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to connect to relationship server.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCorrelationMatrix();
  }, [deviceId]);

  // Optionally refresh when tickCount changes (e.g. when simulation runs)
  useEffect(() => {
    // Only refresh occasionally to not overload the database on every single tick
    if (tickCount > 0 && tickCount % 5 === 0) {
      fetchCorrelationMatrix();
    }
  }, [tickCount]);

  const getCellColor = (val: number) => {
    if (val === 1.0) return 'bg-indigo-600 text-white font-semibold';
    if (val === -1.0) return 'bg-rose-950/80 border border-rose-500/40 text-rose-300 font-semibold';

    if (val > 0) {
      // Scale Emerald color based on strength
      // 0.0 -> 0.3: emerald-500/10
      // 0.3 -> 0.6: emerald-500/40
      // 0.6 -> 0.8: emerald-500/70
      // 0.8 -> 1.0: emerald-500/90
      if (val >= 0.8) return 'bg-emerald-500/90 text-white';
      if (val >= 0.6) return 'bg-emerald-500/70 text-slate-100';
      if (val >= 0.3) return 'bg-emerald-500/40 text-emerald-200';
      return 'bg-emerald-500/10 text-emerald-300/80';
    } else if (val < 0) {
      const abs = Math.abs(val);
      // Scale Rose color based on strength
      if (abs >= 0.8) return 'bg-rose-500/90 text-white';
      if (abs >= 0.6) return 'bg-rose-500/70 text-slate-100';
      if (abs >= 0.3) return 'bg-rose-500/40 text-rose-200';
      return 'bg-rose-500/10 text-rose-300/80';
    }

    return 'bg-slate-800/30 text-slate-400';
  };

  const getCorrelationStrengthLabel = (val: number) => {
    const abs = Math.abs(val);
    let strength = '';
    if (abs >= 0.8) strength = 'Strong';
    else if (abs >= 0.5) strength = 'Moderate';
    else if (abs >= 0.2) strength = 'Weak';
    else strength = 'Negligible';

    const direction = val > 0 ? 'Positive' : val < 0 ? 'Negative' : 'No';
    return `${strength} ${direction} Correlation`;
  };

  const matrix = data ? data[method] : [];
  const metrics = data ? data.metrics : [];

  // Short labels for column headers to save space
  const getShortLabel = (label: string) => {
    switch (label) {
      case 'CPU Usage': return 'CPU';
      case 'Memory Usage': return 'RAM';
      case 'Disk Usage': return 'Disk';
      case 'CPU Temp': return 'Temp';
      case 'Fan Speed': return 'Fan';
      case 'Battery Level': return 'Bat';
      case 'Battery Temp': return 'B-Tmp';
      case 'GPU Usage': return 'GPU';
      default: return label.slice(0, 4);
    }
  };

  return (
    <div className="glass-panel rounded-2xl border border-white/5 overflow-hidden transition-all duration-300">
      {/* Header */}
      <div className="px-5 py-4 border-b border-white/5 bg-slate-900/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center space-x-2">
          <SlidersHorizontal className="h-4.5 w-4.5 text-indigo-400" />
          <div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              Statistical Correlation Matrix
            </h3>
            <p className="text-slate-500 text-[10px] mt-0.5">
              Analyzes continuous covariance patterns across 8 hardware channels
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3 shrink-0">
          {/* Method Selector */}
          <div className="bg-slate-950/60 p-0.5 rounded-lg border border-white/5 flex">
            <button
              onClick={() => setMethod('pearson')}
              className={`px-2.5 py-1 text-[10px] font-bold rounded-md transition-all duration-200 ${
                method === 'pearson'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Pearson
            </button>
            <button
              onClick={() => setMethod('spearman')}
              className={`px-2.5 py-1 text-[10px] font-bold rounded-md transition-all duration-200 ${
                method === 'spearman'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Spearman (Ranks)
            </button>
          </div>

          {/* Refresh Button */}
          <button
            onClick={fetchCorrelationMatrix}
            disabled={loading}
            className="p-1.5 bg-slate-900 border border-white/5 hover:border-white/10 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition duration-200 disabled:opacity-50"
            title="Recalculate statistical metrics"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Main Container */}
      <div className="p-5 flex flex-col lg:flex-row gap-6">
        {/* Heatmap Grid Section */}
        <div className="flex-1 overflow-x-auto min-w-full lg:min-w-0">
          {loading && !data ? (
            <div className="h-[360px] flex flex-col items-center justify-center text-slate-500 text-xs gap-2">
              <RefreshCw className="h-6 w-6 animate-spin text-indigo-400" />
              <span>Analyzing telemetry distribution...</span>
            </div>
          ) : error ? (
            <div className="h-[360px] flex flex-col items-center justify-center text-rose-400 text-xs p-4 text-center gap-2">
              <Info className="h-6 w-6 text-rose-500" />
              <span>{error}</span>
              <button
                onClick={fetchCorrelationMatrix}
                className="mt-2 px-3 py-1 bg-slate-900 hover:bg-slate-800 border border-white/5 text-[10px] font-bold text-slate-300 rounded"
              >
                Retry Request
              </button>
            </div>
          ) : (
            <div className="min-w-[500px] select-none">
              {/* Heatmap Table */}
              <table className="w-full border-collapse">
                <thead>
                  <tr>
                    {/* Corner Cell */}
                    <th className="w-[120px] text-left text-[10px] font-bold text-slate-500 uppercase pb-2 pr-2">
                      Channels
                    </th>
                    {metrics.map((m) => (
                      <th
                        key={m.id}
                        className="text-center text-[10px] font-bold text-slate-500 uppercase pb-2"
                      >
                        {getShortLabel(m.label)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {metrics.map((rowMetric, rowIdx) => (
                    <tr key={rowMetric.id} className="border-b border-white/[0.02] last:border-0">
                      {/* Row Header */}
                      <td className="text-left text-xs font-medium text-slate-300 py-2.5 pr-2 truncate max-w-[120px]">
                        {rowMetric.label}
                      </td>
                      {/* Grid Cells */}
                      {metrics.map((colMetric, colIdx) => {
                        const val = matrix[rowIdx]?.[colIdx] ?? 0.0;
                        const isHovered = hoveredCell && hoveredCell.row === rowIdx && hoveredCell.col === colIdx;
                        const isDiagonal = rowIdx === colIdx;

                        return (
                          <td
                            key={colMetric.id}
                            onMouseEnter={() => setHoveredCell({ row: rowIdx, col: colIdx, val })}
                            onMouseLeave={() => setHoveredCell(null)}
                            className="p-1 text-center"
                          >
                            <div
                              className={`h-9 w-full flex items-center justify-center rounded-lg text-xs transition-all duration-150 cursor-crosshair border ${
                                isDiagonal
                                  ? 'border-indigo-500/20 bg-indigo-950/20 text-indigo-400 font-semibold'
                                  : isHovered
                                  ? 'ring-2 ring-white scale-105 z-10 shadow-lg border-white/20'
                                  : 'border-transparent'
                              } ${getCellColor(val)}`}
                            >
                              {val.toFixed(2)}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Info panel / Detail Sidebar */}
        <div className="w-full lg:w-[280px] shrink-0 flex flex-col justify-between border-t lg:border-t-0 lg:border-l border-white/5 pt-5 lg:pt-0 lg:pl-5">
          {/* Active Detail Display */}
          <div className="space-y-4">
            <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1.5">
              <Info className="h-3.5 w-3.5 text-indigo-400" />
              Dynamic Analysis
            </h4>

            {hoveredCell && metrics[hoveredCell.row] && metrics[hoveredCell.col] ? (
              <div className="bg-slate-950/40 p-4 rounded-xl border border-white/5 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-slate-500 font-bold uppercase">Relationship</span>
                  <span className="text-[10px] font-semibold bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded-full border border-indigo-500/20">
                    {method === 'pearson' ? 'Pearson' : 'Spearman'}
                  </span>
                </div>

                <div className="text-xs font-semibold text-slate-200">
                  {metrics[hoveredCell.row].label} 
                  <span className="text-slate-500 mx-1.5">↔</span> 
                  {metrics[hoveredCell.col].label}
                </div>

                <div className="flex items-center gap-2">
                  <div className={`h-8 w-14 rounded-lg flex items-center justify-center text-xs font-bold ${getCellColor(hoveredCell.val)}`}>
                    {hoveredCell.val.toFixed(3)}
                  </div>
                  <div className="text-[11px] leading-tight">
                    <div className="font-bold text-slate-300">
                      {getCorrelationStrengthLabel(hoveredCell.val)}
                    </div>
                    <div className="text-slate-500 mt-0.5">
                      {hoveredCell.val > 0 ? 'Co-varying directly' : hoveredCell.val < 0 ? 'Co-varying inversely' : 'No linear trend'}
                    </div>
                  </div>
                </div>

                <p className="text-[11px] text-slate-400 leading-relaxed pt-1.5 border-t border-white/5">
                  {hoveredCell.row === hoveredCell.col ? (
                    'Self-correlation is always exactly 1.0.'
                  ) : hoveredCell.val >= 0.7 ? (
                    'Indicates a very strong direct relationship. Changes in one channel are closely mirrored in the other.'
                  ) : hoveredCell.val >= 0.4 ? (
                    'Indicates a moderate direct trend. Workload cycles or thermal flow are partially linked.'
                  ) : hoveredCell.val <= -0.7 ? (
                    'Indicates a very strong inverse relationship. As one increases, the other decreases rapidly.'
                  ) : hoveredCell.val <= -0.4 ? (
                    'Indicates a moderate inverse relationship (e.g. charging speeds dropping as battery level fills).'
                  ) : (
                    'Weak or negligible correlation. These channels operate mostly independently of each other.'
                  )}
                </p>
              </div>
            ) : (
              <div className="bg-slate-950/15 p-4 rounded-xl border border-dashed border-white/5 text-center text-slate-500 py-10">
                <HelpCircle className="h-6 w-6 text-slate-600 mx-auto mb-2" />
                <p className="text-xs">Hover over any grid block to view granular covariance analyses.</p>
              </div>
            )}
          </div>

          {/* Quick Statistics Summary Card */}
          <div className="mt-6 bg-slate-900/20 p-4 rounded-xl border border-white/5 text-xs space-y-2">
            <div className="flex justify-between items-center text-slate-400">
              <span>Records analyzed</span>
              <span className="font-mono text-slate-200">{data?.total_records_analyzed ?? 0}</span>
            </div>
            <div className="flex justify-between items-center text-slate-400">
              <span>Variables tracked</span>
              <span className="font-mono text-slate-200">8 channels</span>
            </div>
            <div className="flex justify-between items-center text-slate-400">
              <span>Analysis delay</span>
              <span className="font-mono text-slate-200">&lt; 50 ms</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CorrelationDashboard;
