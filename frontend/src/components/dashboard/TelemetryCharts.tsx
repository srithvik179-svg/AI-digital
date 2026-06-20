import React, { useState } from 'react';
import { TelemetryData } from '@/types';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend
} from 'recharts';
import { TrendingUp, Activity } from 'lucide-react';

interface TelemetryChartsProps {
  data: TelemetryData[];
}

export const TelemetryCharts: React.FC<TelemetryChartsProps> = ({ data }) => {
  const [activeTab, setActiveTab] = useState<'utilization' | 'thermals'>('utilization');

  // Format data for chart display (reversing to chronological order for line/area chart)
  const chartData = [...data].reverse().map(item => {
    const time = new Date(item.timestamp);
    return {
      ...item,
      timeStr: time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    };
  });

  if (chartData.length === 0) {
    return (
      <div className="glass-panel rounded-2xl p-8 border border-white/5 flex flex-col items-center justify-center h-[380px]">
        <Activity className="h-10 w-10 text-slate-600 animate-pulse mb-3" />
        <p className="text-slate-400 text-sm">No historical data available yet</p>
        <p className="text-slate-500 text-xs mt-1">Start the simulation or push telemetry records to view logs.</p>
      </div>
    );
  }

  // Custom tooltips matching the premium dark design
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-slate-950/90 border border-white/10 p-3 rounded-xl backdrop-blur-md shadow-2xl">
          <p className="text-slate-400 text-xs font-semibold mb-1.5">{label}</p>
          {payload.map((entry: any, index: number) => (
            <div key={index} className="flex items-center space-x-2 text-sm mt-0.5">
              <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
              <span className="text-slate-300">{entry.name}:</span>
              <span className="font-semibold text-white">
                {entry.value}{entry.name.includes('Temp') ? '°C' : entry.name.includes('Speed') ? ' RPM' : '%'}
              </span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="glass-panel rounded-2xl p-6 border border-white/5 flex flex-col h-[400px]">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-3">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 bg-indigo-500/10 rounded-lg">
            <TrendingUp className="h-5 w-5 text-indigo-400" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">Telemetry Trends</h2>
            <p className="text-slate-400 text-xs">Real-time performance diagnostic metrics</p>
          </div>
        </div>
        
        {/* Tab Buttons */}
        <div className="flex bg-slate-900/60 p-0.5 rounded-lg border border-white/5 self-stretch sm:self-auto">
          <button
            onClick={() => setActiveTab('utilization')}
            className={`flex-1 sm:flex-none px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all duration-200 ${
              activeTab === 'utilization'
                ? 'bg-indigo-600 text-white shadow-lg'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            System Load
          </button>
          <button
            onClick={() => setActiveTab('thermals')}
            className={`flex-1 sm:flex-none px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all duration-200 ${
              activeTab === 'thermals'
                ? 'bg-indigo-600 text-white shadow-lg'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Thermals & Fan
          </button>
        </div>
      </div>

      <div className="flex-1 w-full min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          {activeTab === 'utilization' ? (
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorCpu" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0.0}/>
                </linearGradient>
                <linearGradient id="colorRam" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#a855f7" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#a855f7" stopOpacity={0.0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
              <XAxis 
                dataKey="timeStr" 
                stroke="#64748b" 
                fontSize={10} 
                tickLine={false} 
                axisLine={false}
              />
              <YAxis 
                stroke="#64748b" 
                fontSize={10} 
                tickLine={false} 
                axisLine={false} 
                domain={[0, 100]}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend verticalAlign="top" height={36} iconType="circle" iconSize={8} />
              <Area 
                type="monotone" 
                dataKey="cpu_usage" 
                name="CPU Usage" 
                stroke="#6366f1" 
                strokeWidth={2}
                fillOpacity={1} 
                fill="url(#colorCpu)" 
              />
              <Area 
                type="monotone" 
                dataKey="memory_usage" 
                name="Memory Usage" 
                stroke="#a855f7" 
                strokeWidth={2}
                fillOpacity={1} 
                fill="url(#colorRam)" 
              />
            </AreaChart>
          ) : (
            <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
              <XAxis 
                dataKey="timeStr" 
                stroke="#64748b" 
                fontSize={10} 
                tickLine={false} 
                axisLine={false}
              />
              <YAxis 
                yAxisId="left"
                stroke="#22d3ee" 
                fontSize={10} 
                tickLine={false} 
                axisLine={false} 
                domain={[30, 100]}
              />
              <YAxis 
                yAxisId="right"
                orientation="right"
                stroke="#f43f5e" 
                fontSize={10} 
                tickLine={false} 
                axisLine={false}
                domain={[0, 6000]}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend verticalAlign="top" height={36} iconType="circle" iconSize={8} />
              <Line 
                yAxisId="left"
                type="monotone" 
                dataKey="cpu_temperature" 
                name="CPU Temp" 
                stroke="#22d3ee" 
                strokeWidth={2.5}
                dot={false}
              />
              <Line 
                yAxisId="right"
                type="monotone" 
                dataKey="fan_speed" 
                name="Fan Speed" 
                stroke="#f43f5e" 
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
};
export default TelemetryCharts;
