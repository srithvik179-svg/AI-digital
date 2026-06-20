'use client';

import React, { useState, useCallback } from 'react';
import { ActiveAlert } from '@/types';
import {
  Thermometer, Battery, HardDrive, Wifi,
  AlertTriangle, ShieldX, Info,
  Bell, BellOff, CheckCheck, ChevronDown, ChevronUp,
  Flame, Zap
} from 'lucide-react';

interface AlertsPanelProps {
  alerts: ActiveAlert[];
  deviceId: string;
}

/* ─── Config maps ────────────────────────────────────────────────── */
const CATEGORY_CONFIG: Record<string, { icon: any; color: string; bg: string; border: string }> = {
  Overheating: { icon: Thermometer, color: 'text-orange-400', bg: 'bg-orange-500/10',  border: 'border-orange-500/25' },
  Battery:     { icon: Battery,     color: 'text-amber-400',  bg: 'bg-amber-500/10',   border: 'border-amber-500/25'  },
  Disk:        { icon: HardDrive,   color: 'text-rose-400',   bg: 'bg-rose-500/10',    border: 'border-rose-500/25'   },
  Network:     { icon: Wifi,        color: 'text-sky-400',    bg: 'bg-sky-500/10',     border: 'border-sky-500/25'    },
};

const SEVERITY_CONFIG: Record<string, { badge: string; dot: string; icon: any }> = {
  Critical: { badge: 'bg-red-500/20 text-red-400 border-red-500/30',    dot: 'bg-red-400',    icon: ShieldX       },
  Warning:  { badge: 'bg-amber-500/20 text-amber-400 border-amber-500/30', dot: 'bg-amber-400', icon: AlertTriangle },
  Info:     { badge: 'bg-blue-500/20 text-blue-400 border-blue-500/30',  dot: 'bg-blue-400',   icon: Info          },
};

function getCategoryConf(cat: string) {
  return CATEGORY_CONFIG[cat] ?? { icon: Bell, color: 'text-slate-400', bg: 'bg-slate-800', border: 'border-white/10' };
}

function getSeverityConf(sev: string) {
  return SEVERITY_CONFIG[sev] ?? SEVERITY_CONFIG.Info;
}

/* ─── Single alert row ───────────────────────────────────────────── */
function AlertRow({ alert, onAcknowledge, acknowledged }: {
  alert: ActiveAlert;
  onAcknowledge: (rule_id: string) => void;
  acknowledged: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const cat = getCategoryConf(alert.category);
  const sev = getSeverityConf(alert.severity);
  const CatIcon = cat.icon;
  const SevIcon = sev.icon;

  return (
    <div
      className={`rounded-xl border transition-all duration-300 overflow-hidden ${
        acknowledged ? 'opacity-40 border-white/5 bg-transparent' : `${cat.border} ${cat.bg}`
      }`}
    >
      <div
        className="flex items-start gap-3 p-3 cursor-pointer select-none"
        onClick={() => setExpanded(e => !e)}
      >
        {/* Category icon */}
        <div className={`p-1.5 rounded-lg shrink-0 mt-0.5 ${cat.bg}`}>
          <CatIcon className={`h-3.5 w-3.5 ${cat.color}`} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-0.5">
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${sev.badge}`}>
              {alert.severity}
            </span>
            <span className="text-[10px] text-slate-500 font-medium">{alert.category}</span>
            <span className="text-[10px] text-slate-600 font-mono ml-auto">{alert.rule_id}</span>
          </div>
          <p className="text-xs text-slate-300 leading-snug line-clamp-2">{alert.message}</p>
        </div>

        {/* Expand chevron */}
        <div className="shrink-0 mt-0.5">
          {expanded
            ? <ChevronUp className="h-3.5 w-3.5 text-slate-500" />
            : <ChevronDown className="h-3.5 w-3.5 text-slate-500" />
          }
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-3 pb-3 pt-0 space-y-2">
          <div className="flex items-center gap-4 text-[11px] text-slate-400 bg-black/20 rounded-lg px-3 py-2">
            <span>Metric: <span className="text-white font-mono">{alert.metric_name}</span></span>
            <span>Value: <span className="font-bold text-white">{alert.metric_value.toFixed(2)}</span></span>
          </div>
          {!acknowledged && (
            <button
              onClick={(e) => { e.stopPropagation(); onAcknowledge(alert.rule_id); }}
              className="flex items-center gap-1.5 text-[11px] text-emerald-400 hover:text-emerald-300 transition-colors font-medium"
            >
              <CheckCheck className="h-3.5 w-3.5" /> Mark as acknowledged
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Category group ─────────────────────────────────────────────── */
function CategoryGroup({ category, alerts, acknowledgedSet, onAcknowledge }: {
  category: string;
  alerts: ActiveAlert[];
  acknowledgedSet: Set<string>;
  onAcknowledge: (rule_id: string) => void;
}) {
  const [open, setOpen] = useState(true);
  const cfg = getCategoryConf(category);
  const CatIcon = cfg.icon;
  const critical = alerts.filter(a => a.severity === 'Critical').length;

  return (
    <div>
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 px-1 py-1.5 mb-2 group"
      >
        <CatIcon className={`h-4 w-4 ${cfg.color}`} />
        <span className={`text-xs font-bold ${cfg.color}`}>{category}</span>
        {critical > 0 && (
          <span className="text-[10px] font-bold bg-red-500/20 text-red-400 border border-red-500/30 px-1.5 py-0.5 rounded-full">
            {critical} critical
          </span>
        )}
        <span className="text-[10px] text-slate-600 ml-auto">{alerts.length} alert{alerts.length !== 1 ? 's' : ''}</span>
        {open ? <ChevronUp className="h-3 w-3 text-slate-600" /> : <ChevronDown className="h-3 w-3 text-slate-600" />}
      </button>
      {open && (
        <div className="space-y-2 ml-1">
          {alerts.map(a => (
            <AlertRow
              key={a.rule_id}
              alert={a}
              onAcknowledge={onAcknowledge}
              acknowledged={acknowledgedSet.has(a.rule_id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   MAIN COMPONENT
══════════════════════════════════════════════════════ */
export const AlertsPanel: React.FC<AlertsPanelProps> = ({ alerts, deviceId }) => {
  const [acknowledgedSet, setAcknowledgedSet] = useState<Set<string>>(new Set());
  const [showAcknowledged, setShowAcknowledged] = useState(false);

  const handleAcknowledge = useCallback((rule_id: string) => {
    setAcknowledgedSet(prev => new Set([...prev, rule_id]));
    // Also call the API in background
    fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/alerts/acknowledge/${rule_id}`, {
      method: 'POST'
    }).catch(() => {}); // fire-and-forget
  }, []);

  const handleAcknowledgeAll = useCallback(() => {
    const allIds = alerts.map(a => a.rule_id);
    setAcknowledgedSet(prev => new Set([...prev, ...allIds]));
    fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/alerts/acknowledge/device/${deviceId}/all`, {
      method: 'POST'
    }).catch(() => {});
  }, [alerts, deviceId]);

  const visibleAlerts = showAcknowledged
    ? alerts
    : alerts.filter(a => !acknowledgedSet.has(a.rule_id));

  const criticalCount = visibleAlerts.filter(a => a.severity === 'Critical').length;
  const warningCount  = visibleAlerts.filter(a => a.severity === 'Warning').length;

  // Group by category
  const grouped: Record<string, ActiveAlert[]> = {};
  for (const a of visibleAlerts) {
    if (!grouped[a.category]) grouped[a.category] = [];
    grouped[a.category].push(a);
  }
  // Sort: Critical-heavy categories first
  const sortedCategories = Object.keys(grouped).sort((a, b) => {
    const critA = grouped[a].filter(x => x.severity === 'Critical').length;
    const critB = grouped[b].filter(x => x.severity === 'Critical').length;
    return critB - critA;
  });

  return (
    <div className="glass-panel rounded-2xl border border-white/5 overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-4 border-b border-white/5 bg-slate-900/40">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className={`p-2 rounded-xl ${criticalCount > 0 ? 'bg-red-500/10' : warningCount > 0 ? 'bg-amber-500/10' : 'bg-emerald-500/10'}`}>
              {criticalCount > 0
                ? <Flame className="h-4.5 w-4.5 text-red-400 animate-pulse" />
                : warningCount > 0
                  ? <AlertTriangle className="h-4.5 w-4.5 text-amber-400" />
                  : <Bell className="h-4.5 w-4.5 text-emerald-400" />
              }
            </div>
            <div>
              <h2 className="text-sm font-bold text-white">Alert Detection</h2>
              <p className="text-[11px] text-slate-500">Rule-based anomaly monitoring</p>
            </div>
          </div>

          {/* Summary badges */}
          <div className="flex items-center gap-2">
            {criticalCount > 0 && (
              <span className="text-xs font-bold px-2 py-1 rounded-lg bg-red-500/20 text-red-400 border border-red-500/30 animate-pulse">
                {criticalCount} Critical
              </span>
            )}
            {warningCount > 0 && (
              <span className="text-xs font-bold px-2 py-1 rounded-lg bg-amber-500/20 text-amber-400 border border-amber-500/30">
                {warningCount} Warning
              </span>
            )}
            {visibleAlerts.length === 0 && (
              <span className="text-xs font-bold px-2 py-1 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                All Clear
              </span>
            )}
          </div>
        </div>

        {/* Action bar */}
        {alerts.length > 0 && (
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/5">
            <button
              onClick={() => setShowAcknowledged(s => !s)}
              className="flex items-center gap-1.5 text-[11px] text-slate-400 hover:text-slate-200 transition-colors"
            >
              {showAcknowledged ? <BellOff className="h-3.5 w-3.5" /> : <Bell className="h-3.5 w-3.5" />}
              {showAcknowledged ? 'Hide acknowledged' : 'Show acknowledged'}
            </button>
            {acknowledgedSet.size < alerts.length && (
              <button
                onClick={handleAcknowledgeAll}
                className="flex items-center gap-1.5 text-[11px] text-emerald-400 hover:text-emerald-300 transition-colors font-medium"
              >
                <CheckCheck className="h-3.5 w-3.5" /> Acknowledge all
              </button>
            )}
          </div>
        )}
      </div>

      {/* Alert list */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-white/10">
        {visibleAlerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 gap-3">
            <div className="p-3 rounded-2xl bg-emerald-500/10">
              <Zap className="h-6 w-6 text-emerald-400" />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-emerald-400">No Active Alerts</p>
              <p className="text-[11px] text-slate-600 mt-0.5">
                {acknowledgedSet.size > 0
                  ? `${acknowledgedSet.size} alert${acknowledgedSet.size !== 1 ? 's' : ''} acknowledged`
                  : 'All systems operating normally'}
              </p>
            </div>
          </div>
        ) : (
          sortedCategories.map(cat => (
            <CategoryGroup
              key={cat}
              category={cat}
              alerts={grouped[cat]}
              acknowledgedSet={acknowledgedSet}
              onAcknowledge={handleAcknowledge}
            />
          ))
        )}
      </div>

      {/* Footer: total count */}
      <div className="px-5 py-2.5 border-t border-white/5 bg-slate-900/20">
        <p className="text-[10px] text-slate-600 text-center">
          {alerts.length} rule{alerts.length !== 1 ? 's' : ''} evaluated · {acknowledgedSet.size} acknowledged · Live every 2s
        </p>
      </div>
    </div>
  );
};

export default AlertsPanel;
