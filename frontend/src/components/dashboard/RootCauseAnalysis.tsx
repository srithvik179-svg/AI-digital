import React, { useEffect, useState } from 'react';
import { RuleEvaluationResult } from '@/types';
import { 
  ShieldAlert, 
  HelpCircle, 
  ArrowRight, 
  CheckCircle, 
  Wrench, 
  Info, 
  Activity, 
  ChevronDown, 
  ChevronUp, 
  Compass, 
  Cpu 
} from 'lucide-react';

interface RCADiagnosis {
  cause: string;
  confidence: number;
  evidence: string[];
  remedy: string;
  path: string[];
}

interface RCAResponse {
  device_id: string;
  snapshot_id: string;
  timestamp: string;
  active_alerts: string[];
  diagnoses: RCADiagnosis[];
}

interface RootCauseAnalysisProps {
  deviceId: string;
  latestSnapshotId?: string;
  tickCount?: number;
}

export const RootCauseAnalysis: React.FC<RootCauseAnalysisProps> = ({
  deviceId,
  latestSnapshotId,
  tickCount = 0
}) => {
  const [data, setData] = useState<RCAResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const fetchRCA = async () => {
    if (!deviceId) return;
    setLoading(true);
    setError(null);
    try {
      const url = new URL(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/rca/analyze/${deviceId}`);
      if (latestSnapshotId) {
        url.searchParams.append('snapshot_id', latestSnapshotId);
      }

      const response = await fetch(url.toString(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!response.ok) {
        throw new Error('Root cause analysis computation failed.');
      }

      const resData = await response.json();
      setData(resData);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to query RCA Engine.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRCA();
  }, [deviceId, latestSnapshotId, tickCount]);

  const getConfidenceColor = (conf: number) => {
    if (conf >= 0.8) return 'text-rose-400 stroke-rose-500';
    if (conf >= 0.6) return 'text-amber-400 stroke-amber-500';
    return 'text-emerald-400 stroke-emerald-500';
  };

  const getConfidenceBg = (conf: number) => {
    if (conf >= 0.8) return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
    if (conf >= 0.6) return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
  };

  return (
    <div className="glass-panel rounded-2xl border border-white/5 p-6 flex flex-col h-[520px] overflow-hidden">
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center space-x-2.5">
          <div className="p-1.5 bg-indigo-500/10 rounded-lg text-indigo-400">
            <Compass className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-1.5 uppercase tracking-wider">
              Root Cause Analysis
            </h2>
            <p className="text-slate-400 text-xs">Real-time alert diagnostic engine</p>
          </div>
        </div>
        {data && data.active_alerts.length > 0 && (
          <span className="px-2.5 py-1 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-lg text-[10px] font-bold uppercase tracking-wider animate-pulse">
            {data.active_alerts.length} Triggered Alert{data.active_alerts.length > 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Diagnostics List Scroll container */}
      <div className="flex-1 overflow-y-auto space-y-3 bg-slate-950/20 rounded-xl p-2.5 border border-white/5">
        {loading && !data && (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs py-8">
            <div className="h-5 w-5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin mb-2" />
            <span>Computing root causes...</span>
          </div>
        )}

        {error && (
          <div className="p-4 text-xs text-rose-400 bg-rose-500/5 border border-rose-500/10 rounded-lg">
            Error: {error}
          </div>
        )}

        {!loading && data && data.diagnoses.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs py-8">
            <CheckCircle className="h-8 w-8 mb-2 text-emerald-400" />
            <span>System healthy. No active root causes.</span>
          </div>
        )}

        {data && data.diagnoses.map((diag, index) => {
          const isExpanded = expandedIndex === index;
          const confPercent = Math.round(diag.confidence * 100);
          
          return (
            <div
              key={index}
              className={`border rounded-xl transition duration-300 overflow-hidden ${
                isExpanded 
                  ? 'bg-slate-900/60 border-white/10' 
                  : diag.cause === 'Normal Operation' 
                  ? 'bg-emerald-500/5 border-emerald-500/10 text-slate-300' 
                  : 'bg-slate-900/40 hover:bg-slate-900/50 border-white/5'
              }`}
            >
              {/* Diagnosis Main Row */}
              <div
                onClick={() => setExpandedIndex(isExpanded ? null : index)}
                className="px-4 py-3 flex items-center justify-between cursor-pointer text-xs"
              >
                <div className="flex items-center space-x-3.5 min-w-0">
                  {/* Circular Confidence Meter */}
                  <div className="relative h-9 w-9 shrink-0 flex items-center justify-center">
                    <svg className="absolute transform -rotate-90 w-full h-full">
                      <circle
                        cx="18"
                        cy="18"
                        r="14"
                        className="stroke-slate-800"
                        strokeWidth="2.5"
                        fill="transparent"
                      />
                      <circle
                        cx="18"
                        cy="18"
                        r="14"
                        className={`transition-all duration-500 ${getConfidenceColor(diag.confidence)}`}
                        strokeWidth="2.5"
                        fill="transparent"
                        strokeDasharray={2 * Math.PI * 14}
                        strokeDashoffset={2 * Math.PI * 14 * (1 - diag.confidence)}
                      />
                    </svg>
                    <span className="text-[10px] font-bold text-white z-10">{confPercent}%</span>
                  </div>

                  <div className="min-w-0">
                    <h3 className="font-bold text-slate-200 truncate">{diag.cause}</h3>
                    <p className="text-[10px] text-slate-400 mt-0.5 capitalize truncate">
                      Confidence Level &bull; {diag.confidence >= 0.8 ? 'High' : diag.confidence >= 0.6 ? 'Medium' : 'Low'}
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-3 shrink-0">
                  <span className={`px-2 py-0.5 rounded text-[9px] uppercase font-bold border ${getConfidenceBg(diag.confidence)}`}>
                    {diag.confidence >= 0.8 ? 'Causal Root' : 'Symptom'}
                  </span>
                  {isExpanded ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
                </div>
              </div>

              {/* Expandable Trace Details */}
              {isExpanded && (
                <div className="px-4 pb-4 pt-1 border-t border-white/5 bg-slate-950/40 text-xs space-y-3.5">
                  
                  {/* Evidence parameters */}
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-bold tracking-wider block mb-1">Causal Evidence</span>
                    <ul className="space-y-1 pl-1">
                      {diag.evidence.map((ev, i) => (
                        <li key={i} className="flex items-start gap-1.5 text-slate-300">
                          <span className="text-indigo-400 mt-1 shrink-0">&bull;</span>
                          <span>{ev}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Recommendation / Remedy */}
                  <div className="p-3 bg-indigo-950/20 border border-indigo-500/10 rounded-xl flex items-start gap-2.5">
                    <Wrench className="h-4.5 w-4.5 text-indigo-400 shrink-0 mt-0.5" />
                    <div>
                      <span className="text-[10px] text-indigo-400 font-bold uppercase tracking-wider block">Recommended Remedy</span>
                      <p className="text-slate-300 mt-0.5 leading-relaxed font-medium">{diag.remedy}</p>
                    </div>
                  </div>

                  {/* Decision Tree path trace */}
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-bold tracking-wider block mb-1.5">Diagnostic Trace Path</span>
                    <div className="flex flex-wrap items-center gap-1.5 font-mono text-[9px]">
                      {diag.path.map((node, i) => (
                        <React.Fragment key={i}>
                          {i > 0 && <ArrowRight className="h-3 w-3 text-slate-600 shrink-0" />}
                          <span className="px-2.5 py-1 rounded bg-slate-900 border border-white/5 text-slate-400 truncate max-w-[180px]">
                            {node}
                          </span>
                        </React.Fragment>
                      ))}
                    </div>
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
export default RootCauseAnalysis;
