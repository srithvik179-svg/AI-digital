import React, { useState, useEffect } from 'react';
import { ReasoningRule, RuleEvaluationResult, RuleCondition } from '@/types';
import { 
  ShieldCheck, 
  Plus, 
  Trash2, 
  Play, 
  Cpu, 
  AlertTriangle, 
  Edit, 
  Check, 
  X, 
  Activity, 
  BookOpen, 
  Settings2, 
  Info, 
  CheckCircle,
  ToggleLeft,
  ToggleRight
} from 'lucide-react';

interface ReasoningEngineProps {
  deviceId: string;
  latestSnapshotId?: string;
  tickCount?: number;
}

const METRIC_OPTIONS = [
  { value: 'cpu_usage', label: 'CPU Usage (%)' },
  { value: 'cpu_temperature', label: 'CPU Temp (°C)' },
  { value: 'memory_usage', label: 'Memory Usage (%)' },
  { value: 'disk_usage', label: 'Disk Usage (%)' },
  { value: 'battery_level', label: 'Battery Level (%)' },
  { value: 'battery_health', label: 'Battery Health (%)' },
  { value: 'battery_temperature', label: 'Battery Temp (°C)' },
  { value: 'cycle_count', label: 'Battery Cycle Count' },
  { value: 'fan_speed', label: 'Fan Speed (RPM)' },
  { value: 'active_process_count', label: 'Active Processes' },
  { value: 'gpu_usage', label: 'GPU Usage (%)' },
  { value: 'gpu_temperature', label: 'GPU Temp (°C)' },
  { value: 'signal_strength_dbm', label: 'WiFi Signal (dBm)' },
  { value: 'link_speed_mbps', label: 'WiFi Link Speed (Mbps)' },
  { value: 'power_source', label: 'Power Source (ac/battery)' },
  { value: 'power_draw_watts', label: 'Power Draw (Watts)' },
  { value: 'health_score', label: 'Health Score' },
];

const OPERATOR_OPTIONS = [
  { value: '>', label: '>' },
  { value: '<', label: '<' },
  { value: '>=', label: '>=' },
  { value: '<=', label: '<=' },
  { value: '==', label: '==' },
  { value: '!=', label: '!=' },
];

const SEVERITY_OPTIONS = [
  { value: 'info', label: 'Info (Green)' },
  { value: 'warning', label: 'Warning (Amber)' },
  { value: 'critical', label: 'Critical (Red)' },
];

export const ReasoningEngine: React.FC<ReasoningEngineProps> = ({ 
  deviceId, 
  latestSnapshotId,
  tickCount = 0
}) => {
  const [activeTab, setActiveTab] = useState<'reasoning' | 'rules'>('reasoning');
  const [rules, setRules] = useState<ReasoningRule[]>([]);
  const [evaluations, setEvaluations] = useState<RuleEvaluationResult[]>([]);
  const [loadingRules, setLoadingRules] = useState(false);
  const [loadingEval, setLoadingEval] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form States for Rule Creation/Editing
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null);
  const [ruleName, setRuleName] = useState('');
  const [ruleDescription, setRuleDescription] = useState('');
  const [logicalOperator, setLogicalOperator] = useState<'AND' | 'OR'>('AND');
  const [conclusion, setConclusion] = useState('');
  const [severity, setSeverity] = useState<'info' | 'warning' | 'critical'>('info');
  const [conditions, setConditions] = useState<RuleCondition[]>([
    { metric: 'cpu_usage', operator: '>', value: 80 }
  ]);
  const [isFormOpen, setIsFormOpen] = useState(false);

  // Fetch all rules
  const fetchRules = async () => {
    setLoadingRules(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/reasoning/rules`);
      if (!response.ok) throw new Error('Failed to fetch reasoning rules.');
      const data = await response.json();
      setRules(data);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to load rules.');
    } finally {
      setLoadingRules(false);
    }
  };

  // Evaluate rules on snapshot change
  const runEvaluation = async () => {
    if (!deviceId) return;
    setLoadingEval(true);
    try {
      const url = new URL(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/reasoning/evaluate/${deviceId}`);
      if (latestSnapshotId) {
        url.searchParams.append('snapshot_id', latestSnapshotId);
      }
      
      const response = await fetch(url.toString(), { method: 'POST' });
      if (!response.ok) throw new Error('Rule evaluation failed.');
      const data = await response.json();
      setEvaluations(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoadingEval(false);
    }
  };

  // Initial loading and live sync
  useEffect(() => {
    fetchRules();
  }, []);

  useEffect(() => {
    runEvaluation();
  }, [deviceId, latestSnapshotId, tickCount]);

  // Handle Condition mutations
  const handleAddCondition = () => {
    setConditions([...conditions, { metric: 'cpu_usage', operator: '>', value: 80 }]);
  };

  const handleRemoveCondition = (index: number) => {
    if (conditions.length === 1) return;
    setConditions(conditions.filter((_, i) => i !== index));
  };

  const handleConditionChange = (index: number, field: keyof RuleCondition, val: any) => {
    const updated = [...conditions];
    if (field === 'value') {
      // Parse to number if numeric, otherwise keep as string
      const parsedNum = parseFloat(val);
      updated[index][field] = isNaN(parsedNum) ? val : parsedNum;
    } else {
      updated[index][field] = val;
    }
    setConditions(updated);
  };

  // Create or Update Rule
  const handleSubmitRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ruleName.trim() || !conclusion.trim() || conditions.length === 0) return;

    const payload = {
      name: ruleName,
      description: ruleDescription,
      conditions,
      logical_operator: logicalOperator,
      conclusion,
      severity,
      is_active: true
    };

    try {
      let response;
      if (editingRuleId) {
        response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/reasoning/rules/${editingRuleId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      } else {
        response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/reasoning/rules`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      }

      if (!response.ok) throw new Error('Failed to save reasoning rule.');

      // Refresh
      resetForm();
      await fetchRules();
      await runEvaluation();
    } catch (err: any) {
      setError(err.message || 'Error occurred while saving rule.');
    }
  };

  // Toggle active status
  const handleToggleActive = async (rule: ReasoningRule) => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/reasoning/rules/${rule.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !rule.is_active })
      });
      if (!response.ok) throw new Error('Failed to toggle rule state.');
      
      // Update local state quickly
      setRules(prev => prev.map(r => r.id === rule.id ? { ...r, is_active: !r.is_active } : r));
      await runEvaluation();
    } catch (err: any) {
      setError(err.message || 'Error toggling rule.');
    }
  };

  // Delete Rule
  const handleDeleteRule = async (id: string) => {
    if (!confirm('Are you sure you want to delete this rule?')) return;
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/reasoning/rules/${id}`, {
        method: 'DELETE'
      });
      if (!response.ok) throw new Error('Failed to delete rule.');
      
      setRules(prev => prev.filter(r => r.id !== id));
      await runEvaluation();
    } catch (err: any) {
      setError(err.message || 'Error deleting rule.');
    }
  };

  const handleEditRuleClick = (rule: ReasoningRule) => {
    setEditingRuleId(rule.id);
    setRuleName(rule.name);
    setRuleDescription(rule.description || '');
    setLogicalOperator(rule.logical_operator === 'OR' ? 'OR' : 'AND');
    setConclusion(rule.conclusion);
    setSeverity(rule.severity as any);
    setConditions(rule.conditions);
    setIsFormOpen(true);
  };

  const resetForm = () => {
    setEditingRuleId(null);
    setRuleName('');
    setRuleDescription('');
    setLogicalOperator('AND');
    setConclusion('');
    setSeverity('info');
    setConditions([{ metric: 'cpu_usage', operator: '>', value: 80 }]);
    setIsFormOpen(false);
  };

  const getSeverityColor = (sev: string) => {
    switch (sev.toLowerCase()) {
      case 'critical':
        return 'text-rose-400 bg-rose-500/10 border-rose-500/20';
      case 'warning':
        return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
      default:
        return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
    }
  };

  return (
    <div className="glass-panel rounded-2xl border border-white/5 p-6 flex flex-col min-h-[580px] overflow-hidden">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-indigo-600/10 rounded-xl text-indigo-400 border border-indigo-500/20">
            <Settings2 className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-1.5 uppercase tracking-wider">
              Rule-Based Reasoning Engine
            </h2>
            <p className="text-slate-400 text-xs mt-0.5">Dynamic rule audits and reasoning triggers with evidence</p>
          </div>
        </div>

        {/* Tab Selection & Control */}
        <div className="flex items-center space-x-2 bg-slate-950/60 p-1.5 rounded-xl border border-white/5 self-stretch sm:self-auto justify-between">
          <button
            onClick={() => setActiveTab('reasoning')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition duration-200 ${
              activeTab === 'reasoning'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Activity className="h-3.5 w-3.5" />
            Live Audits
          </button>
          <button
            onClick={() => setActiveTab('rules')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition duration-200 ${
              activeTab === 'rules'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <BookOpen className="h-3.5 w-3.5" />
            Rules Registry ({rules.length})
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg text-xs bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="hover:opacity-80"><X className="h-4 w-4" /></button>
        </div>
      )}

      {/* Content tabs */}
      <div className="flex-1 flex flex-col min-h-0">
        
        {/* TAB 1: LIVE AUDITS / REASONING PANEL */}
        {activeTab === 'reasoning' && (
          <div className="flex-1 flex flex-col min-h-0 space-y-4">
            <div className="flex justify-between items-center bg-slate-900/30 px-4 py-2.5 rounded-xl border border-white/5">
              <span className="text-[11px] font-bold text-indigo-400 flex items-center gap-1.5">
                <Play className="h-3 w-3 text-emerald-400 fill-emerald-400" />
                Snapshot: {latestSnapshotId ? latestSnapshotId.substring(0, 8) : 'Live Stream'}
              </span>
              <span className="text-[10px] text-slate-500">
                Evaluating {evaluations.length} Active Rules
              </span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {evaluations.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs py-12">
                  <Activity className="h-8 w-8 mb-2 animate-pulse text-indigo-500" />
                  <span>Waiting for telemetry updates to run reasoning checks...</span>
                </div>
              ) : (
                evaluations.map((evalRes) => (
                  <div
                    key={evalRes.rule_id}
                    className={`border rounded-2xl p-4 transition-all duration-300 ${
                      evalRes.triggered
                        ? 'bg-slate-950/60 border-rose-500/20 hover:border-rose-500/40 shadow-[0_0_15px_-3px_rgba(244,63,94,0.05)]'
                        : 'bg-slate-950/20 border-white/5 hover:bg-slate-950/40'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4 mb-2">
                      <div className="flex items-center gap-2">
                        {evalRes.triggered ? (
                          <AlertTriangle className={`h-4.5 w-4.5 ${evalRes.severity === 'critical' ? 'text-rose-400 animate-bounce' : 'text-amber-400'}`} />
                        ) : (
                          <CheckCircle className="h-4.5 w-4.5 text-emerald-400" />
                        )}
                        <div>
                          <h4 className="text-xs font-bold text-white tracking-wide">
                            {evalRes.rule_name}
                          </h4>
                        </div>
                      </div>
                      <span className={`px-2 py-0.5 rounded-full text-[9px] uppercase font-bold border ${getSeverityColor(evalRes.severity)}`}>
                        {evalRes.severity}
                      </span>
                    </div>

                    <p className="text-slate-300 text-xs leading-relaxed mt-1 font-medium">
                      {evalRes.explanation}
                    </p>

                    {/* Evidence Badges */}
                    <div className="flex flex-wrap gap-2 mt-3 pt-2.5 border-t border-white/[0.03]">
                      <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider mr-1">Evidence:</span>
                      {Object.entries(evalRes.evidence).map(([metric, val]) => (
                        <div
                          key={metric}
                          className="bg-slate-900/80 px-2.5 py-1 rounded-lg border border-white/5 text-[10px] flex items-center gap-1.5"
                        >
                          <span className="text-slate-400 font-semibold">{metric.replace('_', ' ').toUpperCase()}:</span>
                          <span className="text-indigo-300 font-bold">
                            {val !== null ? (typeof val === 'number' ? val.toFixed(1) : String(val)) : 'N/A'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* TAB 2: RULES REGISTRY & EDITOR */}
        {activeTab === 'rules' && (
          <div className="flex-1 flex flex-col min-h-0 space-y-4">
            
            {/* Action Bar */}
            <div className="flex justify-between items-center">
              <span className="text-xs text-slate-400">Manage, edit, or configure custom logical conditions.</span>
              <button
                onClick={() => {
                  if (isFormOpen) resetForm();
                  else setIsFormOpen(true);
                }}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-500 text-white transition duration-200 shadow-md shadow-indigo-600/10"
              >
                {isFormOpen ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                {isFormOpen ? 'Close Form' : 'New Rule'}
              </button>
            </div>

            {/* Editor Form Modal Panel */}
            {isFormOpen && (
              <form onSubmit={handleSubmitRule} className="bg-slate-950/80 border border-indigo-500/20 rounded-2xl p-5 space-y-4 transition-all duration-300">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <Settings2 className="h-4 w-4 text-indigo-400" />
                  {editingRuleId ? 'Edit Reasoning Rule' : 'Create Custom Reasoning Rule'}
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-[10px] uppercase font-bold text-slate-400">Rule Name</label>
                    <input
                      type="text"
                      required
                      value={ruleName}
                      onChange={(e) => setRuleName(e.target.value)}
                      placeholder="e.g. Excessive Fan Throttling"
                      className="w-full bg-slate-900 border border-white/5 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500/50"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] uppercase font-bold text-slate-400">Conclusion Label</label>
                    <input
                      type="text"
                      required
                      value={conclusion}
                      onChange={(e) => setConclusion(e.target.value)}
                      placeholder="e.g. Thermal Stress Warning"
                      className="w-full bg-slate-900 border border-white/5 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500/50"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] uppercase font-bold text-slate-400">Description</label>
                  <input
                    type="text"
                    value={ruleDescription}
                    onChange={(e) => setRuleDescription(e.target.value)}
                    placeholder="e.g. Detects when the fan spins high while power consumption is low"
                    className="w-full bg-slate-900 border border-white/5 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500/50"
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-[10px] uppercase font-bold text-slate-400">Logical Joiner</label>
                    <select
                      value={logicalOperator}
                      onChange={(e) => setLogicalOperator(e.target.value as any)}
                      className="w-full bg-slate-900 border border-white/5 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500/50"
                    >
                      <option value="AND">AND (Requires ALL conditions)</option>
                      <option value="OR">OR (Requires AT LEAST ONE condition)</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] uppercase font-bold text-slate-400">Severity</label>
                    <select
                      value={severity}
                      onChange={(e) => setSeverity(e.target.value as any)}
                      className="w-full bg-slate-900 border border-white/5 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500/50"
                    >
                      {SEVERITY_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Conditions dynamic list */}
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] uppercase font-bold text-slate-400">Conditions Checklist</label>
                    <button
                      type="button"
                      onClick={handleAddCondition}
                      className="flex items-center gap-1 text-[10px] font-bold text-indigo-400 hover:text-indigo-300"
                    >
                      <Plus className="h-3 w-3" /> Add Condition
                    </button>
                  </div>

                  {conditions.map((cond, idx) => (
                    <div key={idx} className="flex items-center gap-2 bg-slate-900/50 p-2.5 rounded-xl border border-white/5">
                      <select
                        value={cond.metric}
                        onChange={(e) => handleConditionChange(idx, 'metric', e.target.value)}
                        className="flex-1 bg-slate-950 border border-white/5 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none"
                      >
                        {METRIC_OPTIONS.map(opt => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </select>

                      <select
                        value={cond.operator}
                        onChange={(e) => handleConditionChange(idx, 'operator', e.target.value)}
                        className="w-20 bg-slate-950 border border-white/5 rounded-lg px-2 py-1.5 text-xs text-white text-center focus:outline-none"
                      >
                        {OPERATOR_OPTIONS.map(opt => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </select>

                      <input
                        type="text"
                        required
                        value={cond.value}
                        onChange={(e) => handleConditionChange(idx, 'value', e.target.value)}
                        placeholder="Val"
                        className="w-24 bg-slate-950 border border-white/5 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500/50"
                      />

                      <button
                        type="button"
                        onClick={() => handleRemoveCondition(idx)}
                        disabled={conditions.length === 1}
                        className="p-1.5 text-slate-500 hover:text-rose-400 disabled:opacity-40 transition duration-150"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={resetForm}
                    className="px-4 py-2 bg-slate-900 border border-white/5 hover:bg-slate-800 text-slate-300 rounded-xl text-xs font-bold"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold shadow-md shadow-indigo-600/10"
                  >
                    {editingRuleId ? 'Update Rule' : 'Save Rule'}
                  </button>
                </div>
              </form>
            )}

            {/* Rules Listing */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {loadingRules ? (
                <div className="py-12 text-center text-slate-500 text-xs">Loading rules database...</div>
              ) : rules.length === 0 ? (
                <div className="py-12 text-center text-slate-500 text-xs">No rules found. Click "New Rule" to get started.</div>
              ) : (
                rules.map((rule) => (
                  <div key={rule.id} className="bg-slate-950/20 border border-white/5 p-4 rounded-xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4 hover:border-white/10 transition duration-200">
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded-full text-[8px] font-bold uppercase border ${getSeverityColor(rule.severity)}`}>
                          {rule.severity}
                        </span>
                        <h4 className="text-xs font-bold text-white">{rule.name}</h4>
                        <span className="text-[10px] text-slate-500">({rule.id})</span>
                      </div>
                      
                      {rule.description && (
                        <p className="text-[11px] text-slate-400 leading-normal">{rule.description}</p>
                      )}

                      {/* Logic breakdown summary string */}
                      <div className="text-[10px] text-indigo-400 font-mono">
                        IF {rule.conditions.map((c, i) => `${c.metric} ${c.operator} ${c.value}`).join(` ${rule.logical_operator} `)}
                        <br />
                        THEN &rarr; <span className="text-emerald-400 font-bold font-sans text-[11px]">{rule.conclusion}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0 self-end md:self-auto">
                      {/* Active Toggle Switch */}
                      <button
                        onClick={() => handleToggleActive(rule)}
                        className={`flex items-center transition duration-200 ${
                          rule.is_active ? 'text-indigo-400 hover:text-indigo-300' : 'text-slate-600 hover:text-slate-500'
                        }`}
                      >
                        {rule.is_active ? (
                          <div className="flex items-center gap-1.5 text-indigo-400 text-xs font-bold">
                            <ToggleRight className="h-6 w-6 shrink-0" />
                            <span>Active</span>
                          </div>
                        ) : (
                          <div className="flex items-center gap-1.5 text-slate-500 text-xs font-bold">
                            <ToggleLeft className="h-6 w-6 shrink-0" />
                            <span>Disabled</span>
                          </div>
                        )}
                      </button>

                      {/* Action buttons */}
                      <div className="flex items-center gap-1.5 border-l border-white/5 pl-3">
                        <button
                          onClick={() => handleEditRuleClick(rule)}
                          className="p-1.5 bg-slate-900 border border-white/5 rounded-lg text-slate-400 hover:text-white transition duration-150"
                          title="Edit rule"
                        >
                          <Edit className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteRule(rule.id)}
                          className="p-1.5 bg-slate-900 border border-white/5 rounded-lg text-slate-400 hover:text-rose-400 transition duration-150"
                          title="Delete rule"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

          </div>
        )}

      </div>
    </div>
  );
};
export default ReasoningEngine;
