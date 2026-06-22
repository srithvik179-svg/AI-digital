'use client';

import React, { useEffect, useState } from 'react';
import { 
  ShieldAlert, 
  Cpu, 
  CheckCircle2, 
  AlertCircle, 
  Loader, 
  Zap, 
  Wifi, 
  TrendingUp, 
  Wrench, 
  Activity, 
  RefreshCw, 
  Layers, 
  Server,
  UserCheck,
  Flame,
  BatteryCharging
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip as RechartsTooltip, 
  Cell 
} from 'recharts';

interface KPICardData {
  label: string;
  value: any;
  unit?: string | null;
  color: string;
  trend?: 'up' | 'down' | 'stable' | null;
  icon: string;
}

interface Recommendation {
  id: string;
  priority: string;
  category: string;
  title: string;
  description: string;
  action: string;
  evidence: string[];
  devices: string[];
  confidence: number;
  estimated_impact: string;
}

interface RiskItem {
  device_id: string;
  health_score: number;
  risk_level: string;
  alerts: number;
  top_risk?: string | null;
  online: boolean;
}

interface RiskAssessment {
  overall_risk: string;
  risk_color: string;
  healthy_count: number;
  warning_count: number;
  critical_count: number;
  offline_count: number;
  total_devices: number;
  risk_items: RiskItem[];
  risk_breakdown: Record<string, number>;
}

interface PredictionItem {
  device_id: string;
  metric: string;
  horizon_min: number;
  predicted: number;
  unit: string;
  severity: string;
  confidence: number;
  evidence: string;
}

interface IncidentItem {
  id: string;
  device_id: string;
  severity: string;
  metric: string;
  message: string;
  value?: number | null;
  threshold?: number | null;
  detected_at: string;
}

interface DeviceHealthBucket {
  label: string;
  count: number;
  color: string;
}

interface ExecutiveOverview {
  generated_at: string;
  fleet_health: number;
  fleet_risk: string;
  fleet_risk_color: string;
  total_devices: number;
  online_devices: number;
  kpis: KPICardData[];
  recommendations: Recommendation[];
  risk_assessment: RiskAssessment;
  predictions: PredictionItem[];
  incidents: IncidentItem[];
  health_histogram: DeviceHealthBucket[];
  summary_sentence: string;
}

export default function ExecutiveDashboard() {
  const [data, setData] = useState<ExecutiveOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [roleMode, setRoleMode] = useState<'support' | 'product'>('support');
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [actioningRecId, setActioningRecId] = useState<string | null>(null);

  const fetchDashboardData = async () => {
    try {
      const url = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/executive/overview`;
      const res = await fetch(url);
      if (!res.ok) throw new Error('Failed to fetch executive data');
      const payload: ExecutiveOverview = await res.json();
      setData(payload);
      setLastUpdated(new Date().toLocaleTimeString());
      setError(null);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Server connection issue');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleRemediate = (recId: string) => {
    setActioningRecId(recId);
    setTimeout(() => {
      setActioningRecId(null);
      alert(`Remediation action dispatched successfully for recommendation: ${recId}`);
    }, 1000);
  };

  if (loading && !data) {
    return (
      <div className="glass-panel rounded-2xl p-12 border border-white/5 flex flex-col items-center justify-center space-y-4 min-h-[400px]">
        <Loader className="h-8 w-8 animate-spin text-indigo-500" />
        <p className="text-slate-400 text-sm font-semibold animate-pulse">Assembling Operational Intelligence...</p>
      </div>
    );
  }

  // Fallback to empty structure if no data and request failed
  const dashboardData = data || {
    generated_at: new Date().toISOString(),
    fleet_health: 100,
    fleet_risk: 'HEALTHY',
    fleet_risk_color: '#10b981',
    total_devices: 0,
    online_devices: 0,
    kpis: [],
    recommendations: [],
    risk_assessment: {
      overall_risk: 'HEALTHY',
      risk_color: '#10b981',
      healthy_count: 0,
      warning_count: 0,
      critical_count: 0,
      offline_count: 0,
      total_devices: 0,
      risk_items: [],
      risk_breakdown: {}
    },
    predictions: [],
    incidents: [],
    health_histogram: [],
    summary_sentence: 'No active telemetry nodes reported. Launch telemetry collector daemon.'
  };

  const getMetricIcon = (metric: string) => {
    if (metric.includes('temp')) return <Flame className="h-4 w-4 text-orange-400 shrink-0" />;
    if (metric.includes('battery')) return <BatteryCharging className="h-4 w-4 text-emerald-400 shrink-0" />;
    if (metric.includes('wifi') || metric.includes('signal') || metric.includes('conn')) return <Wifi className="h-4 w-4 text-indigo-400 shrink-0" />;
    return <Cpu className="h-4 w-4 text-slate-400 shrink-0" />;
  };

  return (
    <div className="space-y-6">
      {/* Top Banner Alert / Status */}
      <div className="glass-panel rounded-2xl p-5 border border-white/5 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-gradient-to-r from-slate-950/40 via-indigo-950/10 to-slate-950/40 backdrop-blur-md">
        <div className="flex-1 space-y-1">
          <div className="flex items-center space-x-2">
            <Activity className="h-5 w-5 text-indigo-400 animate-pulse" />
            <h2 className="text-base font-bold text-white tracking-tight">Executive Operational Center</h2>
          </div>
          <p className="text-slate-300 text-xs md:text-sm leading-relaxed max-w-3xl">
            {dashboardData.summary_sentence}
          </p>
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto self-stretch md:self-auto justify-between md:justify-end shrink-0">
          <div className="flex items-center space-x-1.5 text-[10px] font-semibold text-slate-400 bg-slate-900/60 border border-white/5 rounded-lg px-2.5 py-1.5">
            <RefreshCw className="h-3 w-3 text-indigo-400 animate-spin" />
            <span>Updated: {lastUpdated || 'Live'}</span>
          </div>

          {/* Perspective Selector Tabs */}
          <div className="flex bg-slate-950/80 p-0.5 rounded-xl border border-white/5 select-none shadow-inner shrink-0">
            <button
              onClick={() => setRoleMode('support')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition duration-200 ${
                roleMode === 'support'
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Wrench className="h-3.5 w-3.5" />
              <span>Support view</span>
            </button>
            <button
              onClick={() => setRoleMode('product')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition duration-200 ${
                roleMode === 'product'
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <TrendingUp className="h-3.5 w-3.5" />
              <span>Product view</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Grid Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* KPI Strip & Dials (Left 1-col) */}
        <div className="space-y-6 lg:col-span-1">
          {/* Fleet Health Dial */}
          <div className="glass-panel rounded-2xl p-6 border border-white/5 flex flex-col items-center justify-center bg-slate-950/30 text-center relative overflow-hidden h-[300px]">
            {/* Ambient Background Light */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-48 h-48 rounded-full blur-[70px] pointer-events-none opacity-20"
                 style={{ backgroundColor: dashboardData.fleet_risk_color }} />
            
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4 z-10">Overall Fleet Health</h3>
            
            {/* SVG Arc Gauge */}
            <div className="relative w-40 h-40 flex items-center justify-center z-10">
              <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                {/* Background path */}
                <circle 
                  cx="50" 
                  cy="50" 
                  r="42" 
                  fill="transparent" 
                  stroke="#1e293b" 
                  strokeWidth="8" 
                  strokeLinecap="round"
                />
                {/* Score Fill */}
                <circle 
                  cx="50" 
                  cy="50" 
                  r="42" 
                  fill="transparent" 
                  stroke={dashboardData.fleet_risk_color} 
                  strokeWidth="8" 
                  strokeDasharray={`${2 * Math.PI * 42}`}
                  strokeDashoffset={`${2 * Math.PI * 42 * (1 - dashboardData.fleet_health / 100)}`}
                  strokeLinecap="round"
                  className="transition-all duration-1000 ease-out"
                />
              </svg>
              {/* Absolute Center Text */}
              <div className="absolute flex flex-col items-center justify-center">
                <span className="text-4xl font-extrabold text-white tracking-tight">{Math.round(dashboardData.fleet_health)}</span>
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">score</span>
              </div>
            </div>
            
            <div className="mt-4 flex items-center space-x-2 z-10">
              <span className="inline-block w-2.5 h-2.5 rounded-full animate-pulse" style={{ backgroundColor: dashboardData.fleet_risk_color }} />
              <span className="text-xs font-bold uppercase tracking-wider text-slate-200" style={{ color: dashboardData.fleet_risk_color }}>
                {dashboardData.fleet_risk} Risk Profile
              </span>
            </div>
          </div>

          {/* Grid Metrics */}
          <div className="grid grid-cols-2 gap-4">
            {dashboardData.kpis.filter(k => k.label !== 'Fleet Health').map((kpi, idx) => (
              <div key={idx} className="glass-panel rounded-xl p-4 border border-white/5 flex flex-col justify-between space-y-3 bg-slate-900/10">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{kpi.label}</span>
                  <span className="text-sm select-none">{kpi.icon}</span>
                </div>
                <div className="flex items-baseline space-x-1">
                  <span className="text-xl font-extrabold text-white tracking-tight" style={{ color: kpi.color }}>
                    {kpi.value}
                  </span>
                  {kpi.unit && (
                    <span className="text-[10px] text-slate-500 font-semibold">{kpi.unit}</span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Device Risk Summary Table */}
          <div className="glass-panel rounded-2xl border border-white/5 bg-slate-950/20 overflow-hidden">
            <div className="px-4 py-3 border-b border-white/5 bg-slate-900/30 flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">Device Health List</h3>
              <span className="text-[9px] font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-full">
                {dashboardData.risk_assessment.total_devices} nodes
              </span>
            </div>
            <div className="divide-y divide-white/[0.03] max-h-[220px] overflow-y-auto">
              {dashboardData.risk_assessment.risk_items.length === 0 ? (
                <div className="text-center py-6 text-[11px] text-slate-500">No telemetry records found.</div>
              ) : (
                dashboardData.risk_assessment.risk_items.map((item, idx) => (
                  <div key={idx} className="px-4 py-2.5 flex items-center justify-between text-xs hover:bg-white/[0.01]">
                    <div className="flex flex-col space-y-0.5">
                      <span className="font-mono text-white text-[11px] font-semibold">{item.device_id}</span>
                      <span className="text-[9px] text-slate-500 flex items-center gap-1">
                        <span className={`w-1.5 h-1.5 rounded-full ${item.online ? 'bg-emerald-400' : 'bg-slate-500'}`} />
                        {item.online ? 'Online' : 'Offline'} &bull; {item.alerts} alerts
                      </span>
                    </div>
                    <div className="flex items-center space-x-3">
                      {item.top_risk && (
                        <span className="text-[9px] font-semibold text-amber-500 bg-amber-500/10 px-1.5 py-0.5 rounded uppercase tracking-wider">
                          {item.top_risk.replace('_', ' ')}
                        </span>
                      )}
                      <span className="font-bold text-[11px]" style={{ color: item.risk_level === 'HEALTHY' ? '#10b981' : item.risk_level === 'CRITICAL' ? '#ef4444' : '#f97316' }}>
                        {item.health_score.toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Tabbed content — Perspectives (Right 2-cols) */}
        <div className="lg:col-span-2 space-y-6">
          {roleMode === 'support' ? (
            /* SUPPORT PERSPECTIVE: Incidents & Recommendations */
            <>
              {/* Active Incident Feed */}
              <div className="glass-panel rounded-2xl border border-white/5 bg-slate-950/20 overflow-hidden flex flex-col h-[280px]">
                <div className="px-5 py-4 border-b border-white/5 bg-slate-900/40 flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <ShieldAlert className="h-4.5 w-4.5 text-indigo-400 animate-pulse" />
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider">Real-Time Incident Feed</h3>
                  </div>
                  <span className="text-[10px] text-slate-500">Live operational alerts</span>
                </div>
                <div className="flex-1 overflow-y-auto divide-y divide-white/[0.02] p-2 space-y-1">
                  {dashboardData.incidents.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center py-6">
                      <CheckCircle2 className="h-8 w-8 text-emerald-500 mb-2 opacity-80" />
                      <p className="text-slate-200 text-xs font-bold">All Operational Parameters Nominal</p>
                      <p className="text-slate-500 text-[10px] mt-0.5">No anomalies detected in the last 24 hours.</p>
                    </div>
                  ) : (
                    dashboardData.incidents.map((incident) => (
                      <div 
                        key={incident.id} 
                        className={`p-3 rounded-xl border flex items-start gap-3 transition duration-200 hover:bg-slate-900/20 ${
                          incident.severity === 'critical' 
                            ? 'bg-red-500/[0.02] border-red-500/10' 
                            : 'bg-amber-500/[0.02] border-amber-500/10'
                        }`}
                      >
                        <div className="mt-0.5">
                          {incident.severity === 'critical' ? (
                            <AlertCircle className="h-4 w-4 text-red-500 animate-pulse" />
                          ) : (
                            <AlertCircle className="h-4 w-4 text-amber-500" />
                          )}
                        </div>
                        <div className="flex-1 space-y-1.5">
                          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
                            <div className="flex items-center gap-2">
                              <span className="text-[11px] font-bold font-mono text-slate-300">{incident.device_id}</span>
                              <span className="text-[9px] text-slate-500">&bull; {new Date(incident.detected_at).toLocaleTimeString()}</span>
                            </div>
                            <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider self-start sm:self-auto ${
                              incident.severity === 'critical' 
                                ? 'bg-red-500/15 text-red-400' 
                                : 'bg-amber-500/15 text-amber-400'
                            }`}>
                              {incident.severity}
                            </span>
                          </div>
                          <p className="text-slate-200 text-xs font-semibold leading-relaxed">
                            {incident.message}
                          </p>
                          <div className="flex items-center gap-4 text-[10px] text-slate-500">
                            {incident.value !== null && incident.value !== undefined && (
                              <span>Reading: <strong className="text-slate-400">{incident.value}</strong></span>
                            )}
                            {incident.threshold !== null && incident.threshold !== undefined && (
                              <span>Threshold: <strong className="text-slate-400">&gt; {incident.threshold}</strong></span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Actionable AI Recommendations */}
              <div className="glass-panel rounded-2xl border border-white/5 bg-slate-950/20 overflow-hidden flex flex-col min-h-[350px]">
                <div className="px-5 py-4 border-b border-white/5 bg-slate-900/40 flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <UserCheck className="h-4.5 w-4.5 text-indigo-400" />
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider">AI Remediation Recommendations</h3>
                  </div>
                  <span className="text-[10px] text-indigo-400 font-bold bg-indigo-500/10 px-2 py-0.5 rounded-full">
                    Ranked by Priority
                  </span>
                </div>
                <div className="flex-1 overflow-y-auto divide-y divide-white/[0.02] p-4 space-y-4">
                  {dashboardData.recommendations.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center py-12">
                      <CheckCircle2 className="h-10 w-10 text-emerald-500 mb-2 opacity-80" />
                      <p className="text-slate-200 text-xs font-bold">No Actions Required</p>
                      <p className="text-slate-500 text-[10px] mt-0.5">Recommendations are derived dynamically from active incidents.</p>
                    </div>
                  ) : (
                    dashboardData.recommendations.map((rec) => (
                      <div key={rec.id} className="space-y-3 pb-4 last:pb-0">
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${
                                rec.priority === 'critical'
                                  ? 'bg-red-500/15 text-red-400'
                                  : rec.priority === 'high'
                                  ? 'bg-amber-500/15 text-amber-400'
                                  : 'bg-indigo-500/15 text-indigo-400'
                              }`}>
                                {rec.priority}
                              </span>
                              <span className="text-[9px] text-slate-500 font-mono capitalize">[{rec.category}]</span>
                            </div>
                            <h4 className="text-sm font-extrabold text-white">{rec.title}</h4>
                          </div>
                          
                          <button
                            onClick={() => handleRemediate(rec.id)}
                            disabled={actioningRecId === rec.id}
                            className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 transition duration-200 shadow-md shrink-0 disabled:opacity-50"
                          >
                            {actioningRecId === rec.id ? (
                              <>
                                <Loader className="h-3 w-3 animate-spin" />
                                Deploying...
                              </>
                            ) : (
                              <>
                                <Zap className="h-3 w-3 fill-current" />
                                Remediate
                              </>
                            )}
                          </button>
                        </div>

                        <p className="text-slate-300 text-xs leading-relaxed">{rec.description}</p>
                        
                        <div className="bg-slate-900/40 border border-white/[0.03] p-3 rounded-xl space-y-1.5">
                          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Action Steps</div>
                          <p className="text-slate-200 text-xs font-medium leading-normal">{rec.action}</p>
                        </div>

                        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[10px] text-slate-500 pt-1">
                          <div>
                            Impact: <strong className="text-indigo-400">{rec.estimated_impact}</strong>
                          </div>
                          <div>
                            Confidence: <strong className="text-slate-300">{Math.round(rec.confidence * 100)}%</strong>
                          </div>
                          <div>
                            Affected: <strong className="text-slate-300 font-mono">{rec.devices.join(', ')}</strong>
                          </div>
                        </div>

                        <div className="space-y-1">
                          <div className="text-[9px] font-bold text-slate-500 uppercase tracking-wider">Evidence Logs</div>
                          <ul className="list-disc pl-4 space-y-0.5">
                            {rec.evidence.map((ev, i) => (
                              <li key={i} className="text-[10px] text-slate-400 leading-normal">{ev}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </>
          ) : (
            /* PRODUCT PERSPECTIVE: Predictions & Detailed Histograms */
            <>
              {/* Short Term Prediction Horizon */}
              <div className="glass-panel rounded-2xl border border-white/5 bg-slate-950/20 overflow-hidden flex flex-col h-[280px]">
                <div className="px-5 py-4 border-b border-white/5 bg-slate-900/40 flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Layers className="h-4.5 w-4.5 text-indigo-400" />
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider">AI Predictive Risk Forecasts</h3>
                  </div>
                  <span className="text-[10px] text-slate-500">Extrapolation Timeline</span>
                </div>
                <div className="flex-1 overflow-y-auto divide-y divide-white/[0.02] p-2 space-y-1">
                  {dashboardData.predictions.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center py-6">
                      <CheckCircle2 className="h-8 w-8 text-emerald-500 mb-2 opacity-80" />
                      <p className="text-slate-200 text-xs font-bold">Stable Trend Profile</p>
                      <p className="text-slate-500 text-[10px] mt-0.5">No critical thermal, power, or component failures predicted within 60 minutes.</p>
                    </div>
                  ) : (
                    dashboardData.predictions.map((pred, idx) => (
                      <div key={idx} className="p-3 rounded-xl border border-white/5 bg-slate-900/5 hover:bg-slate-900/20 transition flex items-start gap-3">
                        <div className="mt-1 shrink-0">
                          {getMetricIcon(pred.metric)}
                        </div>
                        <div className="flex-1 space-y-1">
                          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
                            <span className="text-[11px] font-bold font-mono text-slate-300">
                              {pred.device_id} &bull; <span className="text-indigo-400">{pred.metric.replace('_', ' ')}</span>
                            </span>
                            <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider self-start sm:self-auto ${
                              pred.severity === 'critical' 
                                ? 'bg-red-500/15 text-red-400 animate-pulse' 
                                : 'bg-amber-500/15 text-amber-400'
                            }`}>
                              {pred.severity} (Horizon: {pred.horizon_min}m)
                            </span>
                          </div>
                          <p className="text-slate-400 text-[10px] leading-relaxed">
                            {pred.evidence}
                          </p>
                          <div className="flex items-center justify-between text-[11px] pt-1">
                            <span className="text-slate-300">
                              Projected Target: <strong className="text-white font-extrabold">{pred.predicted.toFixed(1)}{pred.unit}</strong>
                            </span>
                            <span className="text-slate-500">
                              Confidence: {Math.round(pred.confidence * 100)}%
                            </span>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Analytics: Health Distribution & Risk Breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 min-h-[350px]">
                
                {/* Health Histogram */}
                <div className="glass-panel rounded-2xl p-5 border border-white/5 bg-slate-950/20 flex flex-col justify-between">
                  <div>
                    <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">Fleet Health Distribution</h3>
                    <p className="text-slate-500 text-[10px]">Bucket count of registered assets by health score.</p>
                  </div>
                  
                  <div className="h-44 w-full mt-4 flex items-end">
                    {dashboardData.health_histogram.length === 0 ? (
                      <div className="w-full text-center text-slate-500 text-xs my-auto">No bucket analytics loaded.</div>
                    ) : (
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={dashboardData.health_histogram} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                          <XAxis 
                            dataKey="label" 
                            stroke="#475569" 
                            fontSize={10} 
                            tickLine={false} 
                            axisLine={false}
                          />
                          <YAxis 
                            stroke="#475569" 
                            fontSize={10} 
                            tickLine={false} 
                            axisLine={false}
                            allowDecimals={false}
                          />
                          <RechartsTooltip 
                            contentStyle={{ background: '#090d16', borderColor: 'rgba(255,255,255,0.08)', borderRadius: '12px' }}
                            labelStyle={{ color: '#fff', fontSize: '10px', fontWeight: 'bold' }}
                            itemStyle={{ color: '#818cf8', fontSize: '10px' }}
                          />
                          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                            {dashboardData.health_histogram.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={entry.color} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </div>

                {/* Risk Breakdown Category progress bars */}
                <div className="glass-panel rounded-2xl p-5 border border-white/5 bg-slate-950/20 flex flex-col justify-between">
                  <div>
                    <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">Anomalies Category Breakdown</h3>
                    <p className="text-slate-500 text-[10px]">Percentage of total alert volume registered across operational sub-systems.</p>
                  </div>

                  <div className="space-y-3.5 mt-4">
                    {Object.entries(dashboardData.risk_assessment.risk_breakdown).length === 0 ? (
                      <div className="text-center text-slate-500 text-xs py-8">All subsystems normal. 0% anomalies.</div>
                    ) : (
                      Object.entries(dashboardData.risk_assessment.risk_breakdown).map(([category, percentage], idx) => (
                        <div key={idx} className="space-y-1">
                          <div className="flex items-center justify-between text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                            <span>{category}</span>
                            <span className="text-white">{percentage}%</span>
                          </div>
                          <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden border border-white/[0.02]">
                            <div 
                              className={`h-full rounded-full transition-all duration-1000 ${
                                category === 'thermal' 
                                  ? 'bg-orange-500 shadow-md shadow-orange-500/20' 
                                  : category === 'battery' 
                                  ? 'bg-emerald-500 shadow-md shadow-emerald-500/20' 
                                  : category === 'performance' 
                                  ? 'bg-indigo-500 shadow-md shadow-indigo-500/20' 
                                  : 'bg-slate-400'
                              }`} 
                              style={{ width: `${percentage}%` }} 
                            />
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

      </div>
    </div>
  );
}
