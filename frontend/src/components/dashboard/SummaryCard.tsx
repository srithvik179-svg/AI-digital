'use client';

import React, { useEffect, useState, useRef } from 'react';
import { NLSummary } from '@/types';
import {
  ShieldCheck, ShieldAlert, ShieldX, MessageSquare,
  Zap, ChevronDown, ChevronUp, Clock
} from 'lucide-react';

interface SummaryCardProps {
  summary: NLSummary | null | undefined;
  isConnected: boolean;
}

/* ─── Severity config ───────────────────────────────────────────── */
const SEV_CONFIG = {
  Healthy:  {
    border: 'border-emerald-500/30', bg: 'bg-emerald-500/5',
    headline: 'text-emerald-300', badge: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    dot: 'bg-emerald-400', glow: 'shadow-emerald-500/10', Icon: ShieldCheck,
  },
  Warning:  {
    border: 'border-amber-500/30',  bg: 'bg-amber-500/5',
    headline: 'text-amber-300',  badge: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    dot: 'bg-amber-400 animate-pulse', glow: 'shadow-amber-500/10', Icon: ShieldAlert,
  },
  Critical: {
    border: 'border-red-500/35',    bg: 'bg-red-500/5',
    headline: 'text-red-300',    badge: 'bg-red-500/15 text-red-400 border-red-500/30',
    dot: 'bg-red-400 animate-pulse', glow: 'shadow-red-500/15', Icon: ShieldX,
  },
};

function getCfg(sev: string) {
  return SEV_CONFIG[sev as keyof typeof SEV_CONFIG] ?? SEV_CONFIG.Healthy;
}

/* ─── Animated headline text ────────────────────────────────────── */
function AnimatedHeadline({ text, severity }: { text: string; severity: string }) {
  const [displayed, setDisplayed] = useState('');
  const [done, setDone] = useState(false);
  const prevText = useRef('');

  useEffect(() => {
    if (text === prevText.current) return;
    prevText.current = text;
    setDone(false);
    setDisplayed('');
    let i = 0;
    const id = setInterval(() => {
      i++;
      setDisplayed(text.slice(0, i));
      if (i >= text.length) { clearInterval(id); setDone(true); }
    }, 18); // ~18ms per char ≈ smooth typewriter
    return () => clearInterval(id);
  }, [text]);

  const cfg = getCfg(severity);
  return (
    <p className={`text-sm font-semibold leading-snug ${cfg.headline}`}>
      {displayed}
      {!done && <span className="inline-block w-0.5 h-4 ml-0.5 bg-current align-middle animate-pulse" />}
    </p>
  );
}

/* ══════════════════════════════════════════════════════
   MAIN COMPONENT
══════════════════════════════════════════════════════ */
export const SummaryCard: React.FC<SummaryCardProps> = ({ summary, isConnected }) => {
  const [expanded, setExpanded] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    if (summary) setLastUpdated(new Date());
  }, [summary?.headline]);

  if (!summary) {
    return (
      <div className="glass-panel rounded-2xl border border-white/5 px-5 py-4 flex items-center gap-3">
        <MessageSquare className="h-4 w-4 text-slate-600 shrink-0" />
        <p className="text-slate-600 text-sm">Awaiting telemetry to generate summary...</p>
      </div>
    );
  }

  const cfg = getCfg(summary.severity);
  const { Icon } = cfg;

  return (
    <div className={`glass-panel rounded-2xl border ${cfg.border} ${cfg.bg} shadow-lg ${cfg.glow} transition-all duration-500`}>
      {/* Header bar */}
      <div
        className="flex items-center gap-3 px-5 py-3.5 cursor-pointer select-none"
        onClick={() => setExpanded(e => !e)}
      >
        {/* Status icon */}
        <div className={`p-1.5 rounded-lg ${cfg.bg} border ${cfg.border} shrink-0`}>
          <Icon className={`h-4 w-4 ${cfg.headline}`} />
        </div>

        {/* Animated headline */}
        <div className="flex-1 min-w-0">
          <AnimatedHeadline text={summary.headline} severity={summary.severity} />
        </div>

        {/* Right side: badge + latency + expand */}
        <div className="flex items-center gap-2 shrink-0">
          <span className={`hidden sm:inline-flex items-center gap-1.5 text-[10px] font-bold px-2 py-0.5 rounded-full border ${cfg.badge}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
            {summary.severity}
          </span>
          <span className="hidden md:flex items-center gap-1 text-[10px] text-slate-600">
            <Zap className="h-3 w-3" />
            {summary.generated_in_ms.toFixed(2)}ms
          </span>
          {expanded
            ? <ChevronUp className="h-4 w-4 text-slate-500" />
            : <ChevronDown className="h-4 w-4 text-slate-500" />
          }
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="px-5 pb-5 pt-1 space-y-4 border-t border-white/5">

          {/* Full paragraph */}
          <p className="text-sm text-slate-300 leading-relaxed">{summary.paragraph}</p>

          {/* Observations bullets */}
          <div>
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">System Observations</p>
            <ul className="space-y-1.5">
              {summary.observations.map((obs, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${cfg.dot}`} />
                  <span className="text-xs text-slate-400 leading-relaxed">{obs}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Footer metadata */}
          <div className="flex items-center justify-between pt-2 border-t border-white/5">
            <div className="flex items-center gap-1.5 text-[10px] text-slate-600">
              <Clock className="h-3 w-3" />
              {lastUpdated
                ? `Updated ${lastUpdated.toLocaleTimeString()}`
                : 'Live'
              }
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-slate-600">
              <Zap className="h-3 w-3" />
              Generated in {summary.generated_in_ms.toFixed(3)} ms · Template engine · No LLM
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SummaryCard;
