import React, { useEffect, useState } from 'react';
import { 
  Brain, 
  TrendingUp, 
  AlertTriangle, 
  Wrench, 
  Sparkles, 
  Clock, 
  Activity, 
  CheckCircle2, 
  ShieldAlert,
  Gauge,
  Battery,
  HardDrive
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';

interface ActiveMetrics {
  cpu_usage: number;
  cpu_temperature: number;
  gpu_usage: number;
  gpu_temperature: number;
  battery_level: number;
  battery_health: number;
  battery_cycle_count: number;
  write_bytes_sec: number;
  power_source: string;
  fan_rpm: number;
  memory_usage: number;
  wifi_signal: number;
}

interface Diagnosis {
  condition: string;
  severity: string;
  evidence: string;
  confidence: number;
}

interface Recommendation {
  action: string;
  trigger: string;
  estimated_cooling_c: number;
  estimated_battery_extension_mins: number;
  description: string;
  priority: string;
}

interface DecisionSplit {
  feature: string;
  value: number;
  threshold: number;
  comparison: string;
  split_rule: string;
}

interface Classification {
  predicted_tier: string;
  confidence: number;
  decision_path: DecisionSplit[];
}

interface ForecastTick {
  tick: number;
  value: number;
  upper_bound: number;
  lower_bound: number;
  margin_of_error: number;
}

interface Forecast {
  cpu_temperature: ForecastTick[];
  cpu_forecast_confidence: number;
  battery_level: ForecastTick[];
  battery_forecast_confidence: number;
}

interface AnomalyState {
  is_anomaly: boolean;
  anomaly_score: number;
  anomaly_rating: number;
}

interface FailureTimepoint {
  day: number;
  failure_probability: number;
  survival_probability: number;
}

interface FailurePrediction {
  battery_rul_days: number;
  battery_rul_confidence: number;
  battery_health_status: string;
  battery_failure_probability_trajectory: FailureTimepoint[];
  ssd_rul_days: number;
  ssd_rul_confidence: number;
  ssd_health_status: string;
  ssd_failure_probability_trajectory: FailureTimepoint[];
}

interface AIReasoningState {
  device_id: string;
  timestamp: string;
  active_metrics: ActiveMetrics;
  system_stress_index: number;
  diagnoses: Diagnosis[];
  recommendations: Recommendation[];
  classification: Classification;
  forecast: Forecast;
  anomaly: AnomalyState;
  failure_prediction: FailurePrediction;
}

interface AIReasoningDashboardProps {
  deviceId: string;
  tickCount?: number;
}

export const AIReasoningDashboard: React.FC<AIReasoningDashboardProps> = ({
  deviceId,
  tickCount = 0
}) => {
  const [data, setData] = useState<AIReasoningState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeChartTab, setActiveChartTab] = useState<'cpu' | 'battery'>('cpu');

  const fetchAIReasoningState = async () => {
    if (!deviceId) return;
    setLoading(true);
    setError(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
      const response = await fetch(`${apiUrl}/ai-reasoning/state/${deviceId}`);
      
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error(`Device telemetry not found. Ingest some CSV data first.`);
        }
        throw new Error('Failed to retrieve AI reasoning state.');
      }
      
      const resData = await response.json();
      setData(resData);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Error fetching AI analysis.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAIReasoningState();
  }, [deviceId, tickCount]);

  const getTierColor = (tier: string) => {
    switch (tier) {
      case 'Nominal': return 'text-emerald-400 border-emerald-500/20 bg-emerald-500/5';
      case 'High Load': return 'text-sky-400 border-sky-500/20 bg-sky-500/5';
      case 'Thermal Throttling': return 'text-amber-400 border-amber-500/20 bg-amber-500/5';
      case 'Critical Warning': return 'text-rose-400 border-rose-500/20 bg-rose-500/5';
      default: return 'text-slate-400 border-slate-500/20 bg-slate-500/5';
    }
  };

  const getPriorityColor = (priority: string) => {
    if (priority === 'HIGH') return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
    if (priority === 'MEDIUM') return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
  };

  if (loading && !data) {
    return (
      <div className="glass-panel rounded-2xl border border-white/5 p-8 flex flex-col items-center justify-center h-[600px]">
        <div className="h-8 w-8 border-4 border-indigo-400 border-t-transparent rounded-full animate-spin mb-4" />
        <span className="text-slate-400 text-sm">Initializing models and executing forward inference...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-panel rounded-2xl border border-white/5 p-8 flex flex-col items-center justify-center h-[600px] text-center">
        <AlertTriangle className="h-12 w-12 text-rose-500 mb-4" />
        <h3 className="text-white text-base font-bold mb-2">AI Analysis Offline</h3>
        <p className="text-slate-400 text-xs max-w-md leading-relaxed mb-6">{error}</p>
        <button 
          onClick={fetchAIReasoningState}
          className="px-4 py-2 bg-indigo-500 hover:bg-indigo-600 active:scale-95 transition rounded-xl text-xs font-bold text-white shadow-lg shadow-indigo-500/20"
        >
          Retry Execution
        </button>
      </div>
    );
  }

  if (!data) return null;

  // Prepare forecasting chart dataset
  const chartData = activeChartTab === 'cpu' 
    ? data.forecast.cpu_temperature 
    : data.forecast.battery_level;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
      
      {/* ────────────────── COL 1: SYSTEM HEALTH CLASSIFICATION & STRESS INDEX ────────────────── */}
      <div className="space-y-6">
        
        {/* Core AI Summary & Health Gauge */}
        <div className="glass-panel rounded-2xl border border-white/5 p-6 flex flex-col justify-between h-[300px] relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 rounded-full blur-2xl pointer-events-none" />
          
          <div className="flex justify-between items-start">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-indigo-500/10 rounded-xl text-indigo-400">
                <Brain className="h-5 w-5 animate-pulse" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white uppercase tracking-wider">AI Reasoning Layer</h2>
                <p className="text-slate-400 text-[10px]">Consolidated multi-model evaluation</p>
              </div>
            </div>
            <span className={`px-2.5 py-1 text-[10px] font-bold uppercase rounded-lg border tracking-wider ${getTierColor(data.classification.predicted_tier)}`}>
              {data.classification.predicted_tier}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4 my-auto">
            {/* System Stress Index */}
            <div className="bg-slate-950/30 border border-white/5 rounded-xl p-4 text-center">
              <span className="text-[10px] text-slate-500 font-bold uppercase block mb-1">System Stress</span>
              <div className="text-2xl font-black text-slate-100 flex items-center justify-center gap-1">
                {data.system_stress_index}
                <span className="text-xs font-normal text-slate-400">%</span>
              </div>
              <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
                <div 
                  className={`h-full rounded-full transition-all duration-1000 ${
                    data.system_stress_index > 70 ? 'bg-rose-500' : data.system_stress_index > 45 ? 'bg-amber-500' : 'bg-emerald-500'
                  }`}
                  style={{ width: `${data.system_stress_index}%` }}
                />
              </div>
            </div>

            {/* Classification Confidence */}
            <div className="bg-slate-950/30 border border-white/5 rounded-xl p-4 text-center">
              <span className="text-[10px] text-slate-500 font-bold uppercase block mb-1">Classification Conf.</span>
              <div className="text-2xl font-black text-indigo-400">
                {data.classification.confidence}%
              </div>
              <span className="text-[9px] text-slate-400 block mt-2 leading-none">Decision tree fit bounds</span>
            </div>
          </div>

          {/* Model info footer */}
          <div className="flex justify-between items-center text-[10px] border-t border-white/5 pt-3">
            <span className="text-slate-500 font-mono">Last update: {new Date(data.timestamp).toLocaleTimeString()}</span>
            <span className="text-indigo-400 font-bold flex items-center gap-1">
              <Sparkles className="h-3 w-3" /> Scikit-Learn Active
            </span>
          </div>
        </div>

        {/* Isolation Forest Anomaly Detection Card */}
        <div className={`glass-panel rounded-2xl border p-6 h-[220px] transition duration-500 relative overflow-hidden ${
          data.anomaly.is_anomaly 
            ? 'border-rose-500/20 bg-rose-950/5 shadow-lg shadow-rose-950/5' 
            : 'border-white/5 hover:border-white/10'
        }`}>
          {data.anomaly.is_anomaly && (
            <div className="absolute -top-12 -right-12 w-24 h-24 bg-rose-500/10 rounded-full blur-xl pointer-events-none animate-pulse" />
          )}

          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center space-x-2">
              <Gauge className="h-4.5 w-4.5 text-slate-400" />
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">Outlier & Anomaly Profile</span>
            </div>
            {data.anomaly.is_anomaly ? (
              <span className="px-2 py-0.5 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-[9px] font-bold rounded uppercase tracking-wider animate-pulse flex items-center gap-1">
                <ShieldAlert className="h-3 w-3" /> Anomaly Flagged
              </span>
            ) : (
              <span className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[9px] font-bold rounded uppercase tracking-wider">
                Normal Distribution
              </span>
            )}
          </div>

          <div className="flex items-center space-x-6 my-4">
            <div className="text-center shrink-0">
              <div className={`text-3xl font-black ${data.anomaly.is_anomaly ? 'text-rose-400' : 'text-slate-100'}`}>
                {data.anomaly.anomaly_rating.toFixed(1)}%
              </div>
              <span className="text-[10px] text-slate-400 block mt-1">Anomaly Rating</span>
            </div>
            
            <div className="text-xs text-slate-400 space-y-1.5 border-l border-white/5 pl-4">
              <p>Model: <strong className="text-slate-200">Isolation Forest</strong></p>
              <p>Multi-D Score: <strong className="font-mono text-slate-300">{data.anomaly.anomaly_score.toFixed(4)}</strong></p>
              <p className="text-[10px] leading-relaxed">
                Out-of-distribution detection across CPU, GPU, memory, and fans.
              </p>
            </div>
          </div>
        </div>

      </div>

      {/* ────────────────── COL 2: 10-TICK FUTURE TIME-SERIES FORECAST ────────────────── */}
      <div className="space-y-6">
        
        {/* XGBoost / Gradient Boosting Forecast chart */}
        <div className="glass-panel rounded-2xl border border-white/5 p-6 flex flex-col justify-between h-[300px]">
          <div className="flex justify-between items-center mb-2">
            <div className="flex items-center space-x-2">
              <TrendingUp className="h-4.5 w-4.5 text-indigo-400" />
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">10-Tick Time Series Forecast</h3>
            </div>
            <div className="flex bg-slate-950/60 rounded-lg p-0.5 border border-white/5">
              <button
                onClick={() => setActiveChartTab('cpu')}
                className={`px-2.5 py-1 text-[10px] font-bold rounded-md transition ${
                  activeChartTab === 'cpu' ? 'bg-indigo-500 text-white' : 'text-slate-400 hover:text-white'
                }`}
              >
                CPU Temp
              </button>
              <button
                onClick={() => setActiveChartTab('battery')}
                className={`px-2.5 py-1 text-[10px] font-bold rounded-md transition ${
                  activeChartTab === 'battery' ? 'bg-indigo-500 text-white' : 'text-slate-400 hover:text-white'
                }`}
              >
                Battery
              </button>
            </div>
          </div>

          <div className="flex-1 w-full h-[180px] mt-2">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                <XAxis 
                  dataKey="tick" 
                  stroke="rgba(255,255,255,0.2)" 
                  fontSize={9}
                  tickFormatter={(t) => `+${t}m`}
                />
                <YAxis 
                  stroke="rgba(255,255,255,0.2)" 
                  fontSize={9}
                  domain={activeChartTab === 'cpu' ? [40, 105] : [0, 100]}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const item = payload[0].payload as ForecastTick;
                      return (
                        <div className="bg-slate-900/90 backdrop-blur border border-white/10 p-2.5 rounded-lg shadow-xl text-[10px] space-y-1">
                          <p className="text-white font-bold">Tick +{item.tick} (Projected)</p>
                          <p className="text-indigo-400 font-bold">Value: {item.value.toFixed(1)}{activeChartTab === 'cpu' ? '°C' : '%'}</p>
                          <p className="text-slate-400">Bounds: [{item.lower_bound.toFixed(1)}, {item.upper_bound.toFixed(1)}]</p>
                          <p className="text-slate-500 font-mono">Error margin: &plusmn;{item.margin_of_error.toFixed(2)}</p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                
                {/* Lower Error Bound */}
                <Line 
                  type="monotone" 
                  dataKey="lower_bound" 
                  stroke="rgba(99, 102, 241, 0.25)" 
                  strokeDasharray="5 5"
                  dot={false}
                  activeDot={false}
                />
                {/* Projected Value */}
                <Line 
                  type="monotone" 
                  dataKey="value" 
                  stroke={activeChartTab === 'cpu' ? '#f43f5e' : '#10b981'} 
                  strokeWidth={2.5}
                  dot={{ r: 3, fill: '#fff', stroke: activeChartTab === 'cpu' ? '#f43f5e' : '#10b981', strokeWidth: 1 }}
                  activeDot={{ r: 5 }}
                />
                {/* Upper Error Bound */}
                <Line 
                  type="monotone" 
                  dataKey="upper_bound" 
                  stroke="rgba(99, 102, 241, 0.25)" 
                  strokeDasharray="5 5"
                  dot={false}
                  activeDot={false}
                />
                
                {activeChartTab === 'cpu' && (
                  <ReferenceLine y={85} stroke="rgba(239, 68, 68, 0.4)" strokeDasharray="3 3" label={{ value: 'Thermal Throttling', fill: 'rgba(239, 68, 68, 0.6)', fontSize: 7, position: 'top' }} />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="flex justify-between items-center text-[10px] text-slate-400 border-t border-white/5 pt-3 mt-1">
            <span>Model: Autoregressive Gradient Boosting</span>
            <span className="text-indigo-400 font-medium">
              Forecast confidence: {activeChartTab === 'cpu' ? data.forecast.cpu_forecast_confidence : data.forecast.battery_forecast_confidence}%
            </span>
          </div>
        </div>

        {/* Fine-Grained Decision Splits Trace */}
        <div className="glass-panel rounded-2xl border border-white/5 p-6 flex flex-col justify-between h-[220px]">
          <div className="flex items-center space-x-2 mb-2">
            <Activity className="h-4.5 w-4.5 text-slate-400" />
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">Decision Tree Trace Path</h3>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2 pr-1 my-2 bg-slate-950/20 border border-white/5 rounded-xl p-2.5">
            {data.classification.decision_path.length === 0 ? (
              <div className="text-[10px] text-slate-500 text-center py-8">No splits traversed (Root decision node matched).</div>
            ) : (
              data.classification.decision_path.map((split, i) => (
                <div key={i} className="flex items-center justify-between text-[10px] p-2 rounded-lg bg-slate-900/50 border border-white/5">
                  <span className="font-mono text-slate-400">{split.feature}</span>
                  <span className="font-mono text-slate-500 font-semibold">{split.value} {split.comparison} {split.threshold}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold ${
                    split.comparison === '<=' ? 'bg-indigo-500/10 text-indigo-400' : 'bg-amber-500/10 text-amber-400'
                  }`}>
                    {split.comparison === '<=' ? 'True' : 'False'}
                  </span>
                </div>
              ))
            )}
          </div>

          <div className="text-[9px] text-slate-500">
            Split conditions traversed to resolve Fine-Grained Health classification model.
          </div>
        </div>

      </div>

      {/* ────────────────── COL 3: FAILURE PREDICTION & ACTIONS ────────────────── */}
      <div className="xl:col-span-1 space-y-6">
        
        {/* RUL & Weibull Degradation Trajectory */}
        <div className="glass-panel rounded-2xl border border-white/5 p-6 flex flex-col justify-between h-[300px]">
          <div className="flex items-center space-x-2 mb-2.5">
            <Clock className="h-4.5 w-4.5 text-indigo-400" />
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">Remaining Useful Life (RUL)</h3>
          </div>

          <div className="space-y-4 my-auto">
            {/* Battery RUL */}
            <div className="flex items-center justify-between p-3 bg-slate-950/20 border border-white/5 rounded-xl">
              <div className="flex items-center space-x-3">
                <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-400">
                  <Battery className="h-4.5 w-4.5" />
                </div>
                <div>
                  <h4 className="text-[10px] font-bold text-slate-300 uppercase leading-none">Battery Wearout</h4>
                  <span className="text-[9px] text-slate-500">Cycle rate: {data.failure_prediction.battery_health_status}</span>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-black text-slate-100">{data.failure_prediction.battery_rul_days} Days</div>
                <span className="text-[8px] text-emerald-400">Conf. {data.failure_prediction.battery_rul_confidence}%</span>
              </div>
            </div>

            {/* SSD RUL */}
            <div className="flex items-center justify-between p-3 bg-slate-950/20 border border-white/5 rounded-xl">
              <div className="flex items-center space-x-3">
                <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400">
                  <HardDrive className="h-4.5 w-4.5" />
                </div>
                <div>
                  <h4 className="text-[10px] font-bold text-slate-300 uppercase leading-none">SSD Storage Wear</h4>
                  <span className="text-[9px] text-slate-500">Bytes written rate: {data.failure_prediction.ssd_health_status}</span>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-black text-slate-100">{data.failure_prediction.ssd_rul_days} Days</div>
                <span className="text-[8px] text-indigo-400">Conf. {data.failure_prediction.ssd_rul_confidence}%</span>
              </div>
            </div>
          </div>

          <div className="text-[10px] text-slate-400 leading-relaxed border-t border-white/5 pt-3 flex justify-between items-center">
            <span>Model: Weibull hazard distribution</span>
            <span className="text-[9px] text-slate-500">365-day wear-out horizons</span>
          </div>
        </div>

        {/* Actionable Tuning Recommendations */}
        <div className="glass-panel rounded-2xl border border-white/5 p-6 flex flex-col justify-between h-[220px]">
          <div className="flex justify-between items-center mb-2">
            <div className="flex items-center space-x-2">
              <Wrench className="h-4.5 w-4.5 text-amber-400" />
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">Optimization Actions</h3>
            </div>
            <span className="text-[9px] text-indigo-400 font-bold">{data.recommendations.length} Recommended</span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2.5 pr-1 my-2 bg-slate-950/20 border border-white/5 rounded-xl p-2.5">
            {data.recommendations.length === 0 ? (
              <div className="flex flex-col items-center justify-center text-slate-500 text-xs py-8">
                <CheckCircle2 className="h-6 w-6 text-emerald-400 mb-1.5" />
                <span>Thermodynamic configuration optimized.</span>
              </div>
            ) : (
              data.recommendations.map((rec, i) => (
                <div key={i} className="p-2.5 bg-slate-900 border border-white/5 rounded-xl flex items-start gap-2.5 text-[10px]">
                  <div className="mt-0.5 shrink-0">
                    <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold ${getPriorityColor(rec.priority)}`}>
                      {rec.priority}
                    </span>
                  </div>
                  <div className="space-y-1">
                    <h4 className="font-bold text-slate-200">{rec.action}</h4>
                    <p className="text-slate-400 leading-relaxed">{rec.description}</p>
                    <div className="flex gap-2.5 pt-1.5 text-[9px] font-mono text-slate-500">
                      {rec.estimated_cooling_c !== 0 && (
                        <span className="text-rose-400 font-medium">
                          Cooling: -{rec.estimated_cooling_c}°C
                        </span>
                      )}
                      {rec.estimated_battery_extension_mins !== 0 && (
                        <span className={rec.estimated_battery_extension_mins > 0 ? 'text-emerald-400 font-medium' : 'text-rose-400 font-medium'}>
                          Battery: {rec.estimated_battery_extension_mins > 0 ? '+' : ''}{rec.estimated_battery_extension_mins} min
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

      </div>

    </div>
  );
};

export default AIReasoningDashboard;
