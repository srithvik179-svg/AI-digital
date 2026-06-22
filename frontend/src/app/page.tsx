'use client';

import React, { useEffect, useState, useRef } from 'react';
import { TelemetryData, ActiveAlert, NLSummary } from '@/types';
import TwinStatus from '@/components/dashboard/TwinStatus';
import TelemetryCharts from '@/components/dashboard/TelemetryCharts';
import ChatInterface from '@/components/dashboard/ChatInterface';
import AlertsPanel from '@/components/dashboard/AlertsPanel';
import SummaryCard from '@/components/dashboard/SummaryCard';
import TelemetrySearch from '@/components/dashboard/TelemetrySearch';
import CorrelationDashboard from '@/components/dashboard/CorrelationDashboard';
import DependencyGraph from '@/components/dashboard/DependencyGraph';
import KnowledgeGraphExplorer from '@/components/dashboard/KnowledgeGraphExplorer';
import ReplayConsole from '@/components/dashboard/ReplayConsole';
import TimeTravelPlayground from '@/components/dashboard/TimeTravelPlayground';
import ReasoningEngine from '@/components/dashboard/ReasoningEngine';
import RootCauseAnalysis from '@/components/dashboard/RootCauseAnalysis';
import AIReasoningDashboard from '@/components/dashboard/AIReasoningDashboard';
import WhatIfSimulationDashboard from '@/components/dashboard/WhatIfSimulationDashboard';
import FutureStateDashboard from '@/components/dashboard/FutureStateDashboard';
import LiveIngestionStatus from '@/components/dashboard/LiveIngestionStatus';
import FleetDashboard from '@/components/dashboard/FleetDashboard';
import DigitalTwin3D from '@/components/dashboard/DigitalTwin3D';
import ExecutiveDashboard from '@/components/dashboard/ExecutiveDashboard';
import { Terminal, Settings, Play, ShieldAlert, Cpu, CheckCircle2, Upload, AlertCircle, Loader, ArrowLeft, History } from 'lucide-react';

const DEVICE_ID = "laptop-mac-001";

export default function Dashboard() {
  const [appModule, setAppModule] = useState<'landing' | 'historical' | 'live'>('landing');
  const [liveTab, setLiveTab] = useState<'state' | 'prediction' | 'simulation'>('state');
  const [dashboardMode, setDashboardMode] = useState<'executive' | 'detailed'>('detailed');
  const [telemetryHistory, setTelemetryHistory] = useState<TelemetryData[]>([]);
  const [latestData, setLatestData] = useState<TelemetryData | null>(null);
  const [activeAlerts, setActiveAlerts] = useState<ActiveAlert[]>([]);
  const [nlSummary, setNlSummary] = useState<NLSummary | null>(null);
  const [tickCount, setTickCount] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);

  // Phase 18 & 19: Replay & Time Travel States
  const [isReplayActive, setIsReplayActive] = useState(false);
  const isReplayActiveRef = useRef(false);
  const [projections, setProjections] = useState<any[] | null>(null);

  const handleReplayActiveChange = (isActive: boolean) => {
    setIsReplayActive(isActive);
    isReplayActiveRef.current = isActive;
  };

  const handleReplayFrameChange = (frame: TelemetryData | null) => {
    if (frame) {
      setLatestData(frame);
      if (frame.active_alerts) {
        setActiveAlerts(frame.active_alerts);
      }
      if (frame.nl_summary) {
        setNlSummary(frame.nl_summary);
      }
    } else {
      // Replay stopped, reset to live latest tick
      if (telemetryHistory.length > 0) {
        const liveLatest = telemetryHistory[0];
        setLatestData(liveLatest);
        if (liveLatest.active_alerts) {
          setActiveAlerts(liveLatest.active_alerts);
        }
        if (liveLatest.nl_summary) {
          setNlSummary(liveLatest.nl_summary);
        }
      }
    }
  };
  const [uploadStatus, setUploadStatus] = useState<{
    status: 'idle' | 'uploading' | 'success' | 'error';
    importedCount?: number;
    skippedCount?: number;
    message?: string;
  }>({ status: 'idle' });
  
  const wsRef = useRef<WebSocket | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploadStatus({ status: 'uploading' });

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/telemetry/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const result = await response.json();
      setUploadStatus({
        status: 'success',
        importedCount: result.imported_count,
        skippedCount: result.skipped_count,
        message: `Successfully imported ${result.imported_count} records! Skipped ${result.skipped_count} rows.`
      });

      if (fileInputRef.current) fileInputRef.current.value = '';

      // Immediately fetch latest logs to populate chart
      const fetchResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/telemetry/?device_id=${DEVICE_ID}&limit=30`);
      if (fetchResponse.ok) {
        const data = await fetchResponse.json();
        if (data.length > 0) {
          setLatestData(data[0]);
          setTelemetryHistory(data);
        }
      }
    } catch (e: any) {
      setUploadStatus({
        status: 'error',
        message: e.message || 'CSV Import failed. Check headers and column types.'
      });
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Setup WebSocket connection
  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/api/v1/telemetry/ws';
    console.log(`Connecting to WebSocket: ${wsUrl}`);
    
    let reconnectTimeout: NodeJS.Timeout | null = null;
    let isUnmounted = false;

    const connectWs = () => {
      if (isUnmounted) return;

      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          if (isUnmounted) {
            ws.close();
            return;
          }
          setIsConnected(true);
          console.log("WebSocket connected.");
        };

        ws.onmessage = (event) => {
          if (isUnmounted) return;
          try {
            const payload = JSON.parse(event.data);
              if (payload.type === 'telemetry_update') {
                const data = payload.data as TelemetryData;
                setTelemetryHistory(prev => [data, ...prev].slice(0, 60));
                setTickCount(c => c + 1);
                
                // Only update dials and summary if replay is not active!
                if (!isReplayActiveRef.current) {
                  setLatestData(data);
                  if (data.active_alerts) {
                    setActiveAlerts(data.active_alerts);
                  }
                  if (data.nl_summary) {
                    setNlSummary(data.nl_summary);
                  }
                }
              }
          } catch (err) {
            console.error("Failed to parse WebSocket message:", err);
          }
        };

        ws.onclose = () => {
          setIsConnected(false);
          setIsSimulating(false);
          wsRef.current = null;
          
          if (!isUnmounted) {
            console.log("WebSocket disconnected. Reconnecting in 5 seconds...");
            reconnectTimeout = setTimeout(connectWs, 5000);
          } else {
            console.log("WebSocket connection closed cleanly during cleanup.");
          }
        };

        ws.onerror = (err) => {
          console.error("WebSocket error:", err);
          ws.close();
        };
      } catch (e) {
        console.error("Failed to connect websocket:", e);
        if (!isUnmounted) {
          reconnectTimeout = setTimeout(connectWs, 5000);
        }
      }
    };

    connectWs();

    return () => {
      isUnmounted = true;
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
      if (wsRef.current) {
        // Prevent onclose handler from running when we close it explicitly
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  // Request mock data stream from server
  const handleStartSimulation = () => {
    if (wsRef.current && isConnected && !isSimulating) {
      wsRef.current.send(JSON.stringify({
        type: 'start_mock_stream',
        device_id: DEVICE_ID
      }));
      setIsSimulating(true);
    }
  };

  // Render Landing Page
  if (appModule === 'landing') {
    return (
      <main className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col relative overflow-hidden">
        {/* Dynamic Background Glow */}
        <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-indigo-500/10 rounded-full blur-[120px] pointer-events-none" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-purple-500/10 rounded-full blur-[120px] pointer-events-none" />

        {/* Navigation Header */}
        <header className="border-b border-white/5 py-4 px-6 md:px-8 bg-slate-950/20 backdrop-blur-md sticky top-0 z-50 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-indigo-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-indigo-600/20">
              <Cpu className="h-6 w-6 animate-pulse" />
            </div>
            <div>
              <h1 className="text-lg font-bold bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
                TwinIntel
              </h1>
              <p className="text-slate-500 text-xs font-medium">Laptop Telemetry AI Digital Twin</p>
            </div>
          </div>
          <div className={`flex items-center space-x-2 px-3 py-1.5 rounded-full text-xs font-semibold border transition-all duration-300 ${
            isConnected 
              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
              : 'bg-red-500/10 border-red-500/20 text-red-400'
          }`}>
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400 pulse-dot-green' : 'bg-red-500 pulse-dot-red'}`} />
            <span>{isConnected ? 'Daemon Connected' : 'Disconnected'}</span>
          </div>
        </header>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col justify-center items-center max-w-6xl w-full mx-auto p-6 md:p-8 z-10 space-y-12">
          {/* Welcome Text */}
          <div className="text-center space-y-4 max-w-3xl">
            <h2 className="text-4xl md:text-5xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-200 to-indigo-400 bg-clip-text text-transparent">
              Hardware Intelligence Portal
            </h2>
            <p className="text-slate-400 text-base md:text-lg">
              Welcome to TwinIntel. Choose your analytical workspace to get started. Focus on past metrics, or explore real-time simulations and predictions.
            </p>
          </div>

          {/* Module Selector Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 w-full">
            {/* Historical Telemetry Intelligence */}
            <div 
              onClick={() => setAppModule('historical')}
              className="group relative cursor-pointer glass-panel rounded-3xl border border-white/5 p-8 bg-slate-950/20 hover:bg-slate-900/40 hover:border-indigo-500/30 transition-all duration-300 flex flex-col justify-between h-[360px] overflow-hidden"
            >
              {/* Card Background Glow */}
              <div className="absolute top-0 right-0 w-32 h-32 bg-amber-500/5 rounded-full blur-3xl group-hover:bg-amber-500/10 transition-colors duration-300" />
              
              <div className="space-y-4">
                <div className="p-3.5 bg-amber-500/10 rounded-2xl text-amber-400 w-fit group-hover:scale-110 transition-transform duration-300">
                  <History className="h-8 w-8" />
                </div>
                <div className="space-y-1">
                  <span className="text-amber-400 text-xs font-bold uppercase tracking-wider">Module 1</span>
                  <h3 className="text-2xl font-bold text-white group-hover:text-amber-400 transition-colors duration-300">
                    Historical Telemetry Intelligence
                  </h3>
                  <p className="text-slate-400 text-sm leading-relaxed">
                    Examine uploaded CSV telemetry datasets and database logs. Drill down into historical trends, alerts, component correlations, and diagnostic root causes.
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-between mt-6">
                <div className="flex flex-wrap gap-2 max-w-[70%]">
                  <span className="px-2 py-0.5 bg-slate-900 text-[10px] text-slate-400 rounded-md border border-white/5">Dataset Upload</span>
                  <span className="px-2 py-0.5 bg-slate-900 text-[10px] text-slate-400 rounded-md border border-white/5">RCA Engine</span>
                  <span className="px-2 py-0.5 bg-slate-900 text-[10px] text-slate-400 rounded-md border border-white/5">Heatmaps</span>
                </div>
                <span className="text-xs font-bold text-amber-400 group-hover:underline flex items-center gap-1.5">
                  Launch Workspace &rarr;
                </span>
              </div>
            </div>

            {/* Live AI Digital Twin */}
            <div 
              onClick={() => setAppModule('live')}
              className="group relative cursor-pointer glass-panel rounded-3xl border border-white/5 p-8 bg-slate-950/20 hover:bg-slate-900/40 hover:border-indigo-500/30 transition-all duration-300 flex flex-col justify-between h-[360px] overflow-hidden"
            >
              {/* Card Background Glow */}
              <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/5 rounded-full blur-3xl group-hover:bg-indigo-500/10 transition-colors duration-300" />

              <div className="space-y-4">
                <div className="p-3.5 bg-indigo-500/10 rounded-2xl text-indigo-400 w-fit group-hover:scale-110 transition-transform duration-300">
                  <Cpu className="h-8 w-8" />
                </div>
                <div className="space-y-1">
                  <span className="text-indigo-400 text-xs font-bold uppercase tracking-wider">Module 2</span>
                  <h3 className="text-2xl font-bold text-white group-hover:text-indigo-400 transition-colors duration-300">
                    Live AI Digital Twin
                  </h3>
                  <p className="text-slate-400 text-sm leading-relaxed">
                    Monitor live host telemetries via WMI/psutil agents. Interact with a 3D twin, forecast future state degradation bounds, and simulate what-if steady states.
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-between mt-6">
                <div className="flex flex-wrap gap-2 max-w-[70%]">
                  <span className="px-2 py-0.5 bg-slate-900 text-[10px] text-slate-400 rounded-md border border-white/5">3D Model</span>
                  <span className="px-2 py-0.5 bg-slate-900 text-[10px] text-slate-400 rounded-md border border-white/5">ML Forecasting</span>
                  <span className="px-2 py-0.5 bg-slate-900 text-[10px] text-slate-400 rounded-md border border-white/5">Steady-State Sim</span>
                </div>
                <span className="text-xs font-bold text-indigo-400 group-hover:underline flex items-center gap-1.5">
                  Launch Twin &rarr;
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="py-6 border-t border-white/5 text-center text-xs text-slate-600 bg-slate-950/20 z-10">
          AI Digital Twin Telemetry Engine &bull; Developed by Antigravity
        </footer>
      </main>
    );
  }

  // Render Workspaces
  return (
    <main className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col">
      {/* Dynamic Background Glow */}
      <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-indigo-500/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-purple-500/10 rounded-full blur-[120px] pointer-events-none" />

      {/* Navigation Header */}
      <header className="border-b border-white/5 py-4 px-6 md:px-8 bg-slate-950/20 backdrop-blur-md sticky top-0 z-50 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <button 
            onClick={() => setAppModule('landing')}
            className="flex items-center gap-1.5 p-2 bg-slate-900 border border-white/5 text-slate-400 rounded-xl hover:text-white hover:bg-slate-800 transition duration-200 text-xs font-bold"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Modules</span>
          </button>
          
          <div className="h-6 w-[1px] bg-white/10" />

          <div>
            <h1 className="text-sm md:text-base font-bold bg-gradient-to-r from-white via-slate-200 to-indigo-400 bg-clip-text text-transparent flex items-center gap-2">
              <span>TwinIntel</span>
              <span className="text-xs px-2 py-0.5 rounded bg-slate-900 border border-white/5 text-slate-400 font-normal">
                {appModule === 'historical' ? 'Historical Analysis' : 'Live Twin'}
              </span>
            </h1>
            <p className="text-slate-500 text-[10px] md:text-xs font-medium">
              {appModule === 'historical' ? 'Analyze uploaded datasets & database logs' : 'Monitor live device telemetry & simulation'}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          {/* Dashboard Mode Selector */}
          <div className="flex bg-slate-900 border border-white/5 p-0.5 rounded-xl text-xs select-none">
            <button
              onClick={() => setDashboardMode('executive')}
              className={`px-3 py-1.5 rounded-lg font-bold transition duration-200 ${
                dashboardMode === 'executive'
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Executive View
            </button>
            <button
              onClick={() => setDashboardMode('detailed')}
              className={`px-3 py-1.5 rounded-lg font-bold transition duration-200 ${
                dashboardMode === 'detailed'
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Engineering Twin
            </button>
          </div>

          {/* Status Badge */}
          <div className={`flex items-center space-x-2 px-3 py-1.5 rounded-full text-xs font-semibold border transition-all duration-300 ${
            isConnected 
              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
              : 'bg-red-500/10 border-red-500/20 text-red-400'
          }`}>
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400 pulse-dot-green' : 'bg-red-500 pulse-dot-red'}`} />
            <span>{isConnected ? 'Daemon Connected' : 'Disconnected'}</span>
          </div>

          <button className="p-2 bg-slate-900 border border-white/5 text-slate-400 rounded-xl hover:text-white transition duration-200">
            <Settings className="h-4.5 w-4.5" />
          </button>
        </div>
      </header>

      {/* Main Grid Content */}
      <div className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-8 space-y-6">
        
        {dashboardMode === 'executive' ? (
          <ExecutiveDashboard />
        ) : appModule === 'historical' ? (
          /* =========================================================================
             MODULE 1: HISTORICAL TELEMETRY INTELLIGENCE
             ========================================================================= */
          <>
            {/* Historical controls bar */}
            <div className="glass-panel rounded-2xl p-5 border border-white/5 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
              <div>
                <h2 className="text-sm font-bold text-white">Historical Data: {DEVICE_ID}</h2>
                <p className="text-slate-400 text-xs mt-0.5">
                  Analyzing uploaded CSV datasets, historical alerts database, and system logs.
                </p>
              </div>
              
              <div className="flex items-center gap-3 w-full md:w-auto">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileUpload}
                  accept=".csv"
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadStatus.status === 'uploading'}
                  className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold bg-slate-900 border border-white/5 text-slate-200 hover:text-white hover:bg-slate-800 transition duration-200 shadow-md disabled:opacity-50 w-full md:w-auto"
                >
                  {uploadStatus.status === 'uploading' ? (
                    <>
                      <Loader className="h-4.5 w-4.5 animate-spin text-indigo-400" />
                      Uploading CSV...
                    </>
                  ) : (
                    <>
                      <Upload className="h-4.5 w-4.5 text-indigo-400" />
                      Upload Telemetry CSV
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Upload status banner */}
            {uploadStatus.status !== 'idle' && (
              <div className={`p-4 rounded-xl text-xs flex items-center justify-between border ${
                uploadStatus.status === 'success'
                  ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                  : uploadStatus.status === 'error'
                  ? 'bg-red-500/10 border-red-500/20 text-red-400'
                  : 'bg-indigo-500/10 border-indigo-500/20 text-indigo-400'
              }`}>
                <div className="flex items-center gap-2">
                  {uploadStatus.status === 'success' ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                  ) : uploadStatus.status === 'error' ? (
                    <ShieldAlert className="h-4 w-4 shrink-0" />
                  ) : (
                    <Loader className="h-4 w-4 animate-spin shrink-0" />
                  )}
                  <span>
                    {uploadStatus.status === 'uploading' 
                      ? 'Importing CSV file to database...' 
                      : uploadStatus.message}
                  </span>
                </div>
                {uploadStatus.status !== 'uploading' && (
                  <button 
                    onClick={() => setUploadStatus({ status: 'idle' })} 
                    className="text-[10px] uppercase font-bold hover:underline opacity-80"
                  >
                    Dismiss
                  </button>
                )}
              </div>
            )}

            {/* Collapsible summary card */}
            <SummaryCard summary={nlSummary} isConnected={isConnected} />

            {/* Twin Status (HUD Cards & Score breakdown) */}
            <TwinStatus latestData={latestData} isConnected={isConnected} />

            {/* Telemetry Search */}
            <div className="grid grid-cols-1 gap-6">
              <TelemetrySearch deviceId={DEVICE_ID} />
            </div>

            {/* Historical Replay Console & Time Travel Scenario Planner */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <ReplayConsole
                deviceId={DEVICE_ID}
                onFrameChange={handleReplayFrameChange}
                onReplayActiveChange={handleReplayActiveChange}
              />
              <TimeTravelPlayground
                deviceId={DEVICE_ID}
                selectedTimestamp={latestData?.timestamp || null}
                onProjectionLoaded={setProjections}
              />
            </div>

            {/* Historical Telemetry Charts */}
            <TelemetryCharts data={telemetryHistory} projections={projections} />

            {/* Correlation Matrix and Influence topology graph */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <CorrelationDashboard deviceId={DEVICE_ID} tickCount={tickCount} />
              <DependencyGraph deviceId={DEVICE_ID} tickCount={tickCount} />
            </div>

            {/* Alerts database and Root Cause diagnostics */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <AlertsPanel alerts={activeAlerts} deviceId={DEVICE_ID} />
              <RootCauseAnalysis 
                deviceId={DEVICE_ID} 
                latestSnapshotId={latestData?.id} 
                tickCount={tickCount} 
              />
            </div>

            {/* Neo4j Knowledge Graph Explorer */}
            <KnowledgeGraphExplorer deviceId={DEVICE_ID} />

            {/* Rule-Based Reasoning Engine */}
            <ReasoningEngine 
              deviceId={DEVICE_ID} 
              latestSnapshotId={latestData?.id} 
              tickCount={tickCount} 
            />

            {/* Historical AI Chat & Raw Log Stream */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <ChatInterface deviceId={DEVICE_ID} mode="historical" />
              </div>
              
              <div className="glass-panel rounded-2xl border border-white/5 overflow-hidden">
                <div className="px-5 py-4 border-b border-white/5 bg-slate-900/40 flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Terminal className="h-4.5 w-4.5 text-indigo-400" />
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider">Historical Logs</h3>
                  </div>
                  <span className="text-[10px] text-slate-500">Last 10 loaded ticks</span>
                </div>
                <div className="p-4 font-mono text-[11px] leading-relaxed max-h-[440px] h-[440px] overflow-y-auto bg-slate-950/40 text-slate-400 space-y-1">
                  {telemetryHistory.length === 0 ? (
                    <div className="text-center py-6 text-slate-600">Awaiting CSV upload or data logs...</div>
                  ) : (
                    telemetryHistory.slice(0, 10).map((log, idx) => (
                      <div key={idx} className="flex items-start border-b border-white/[0.02] pb-1 hover:bg-white/[0.01] px-2 rounded">
                        <span className="text-slate-500 mr-3 shrink-0">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                        <span className="text-amber-400 mr-2 shrink-0">history:</span>
                        <span className="break-all">
                          cpu={log.cpu_usage}% | memory={log.memory_usage}% | temp={log.cpu_temperature}°C | fan={log.fan_speed}RPM | battery={log.battery_level}% | health={log.battery_health}%
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </>
        ) : (
          /* =========================================================================
             MODULE 2: LIVE AI DIGITAL TWIN
             ========================================================================= */
          <>
            {/* Live stream status bar */}
            <div className="glass-panel rounded-2xl p-5 border border-white/5 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
              <div>
                <h2 className="text-sm font-bold text-white">Live Monitor: {DEVICE_ID}</h2>
                <p className="text-slate-400 text-xs mt-0.5">
                  Streaming hardware sensor metrics and forecasting dynamic operational health bounds.
                </p>
              </div>
              
              <div className="w-full md:w-auto">
                <button
                  onClick={handleStartSimulation}
                  disabled={!isConnected || isSimulating}
                  className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition duration-200 shadow-md w-full md:w-auto ${
                    isSimulating
                      ? 'bg-indigo-950 text-indigo-400 border border-indigo-500/20 cursor-default'
                      : 'bg-indigo-600 hover:bg-indigo-500 text-white cursor-pointer disabled:opacity-50'
                  }`}
                >
                  {isSimulating ? (
                    <>
                      <CheckCircle2 className="h-4 w-4" />
                      Telemetry Streaming Live
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 fill-current" />
                      Start Live Simulation Stream
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Tab controls */}
            <div className="flex space-x-1 bg-slate-900/60 border border-white/5 p-1 rounded-xl w-fit">
              <button
                onClick={() => setLiveTab('state')}
                className={`px-4 py-2 rounded-lg font-bold text-xs transition duration-200 ${
                  liveTab === 'state'
                    ? 'bg-indigo-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Current State
              </button>
              <button
                onClick={() => setLiveTab('prediction')}
                className={`px-4 py-2 rounded-lg font-bold text-xs transition duration-200 ${
                  liveTab === 'prediction'
                    ? 'bg-indigo-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Prediction
              </button>
              <button
                onClick={() => setLiveTab('simulation')}
                className={`px-4 py-2 rounded-lg font-bold text-xs transition duration-200 ${
                  liveTab === 'simulation'
                    ? 'bg-indigo-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                What-If Simulation
              </button>
            </div>

            {/* Tab content rendering */}
            {liveTab === 'state' && (
              <>
                {/* Live Ingestion Pipeline Status */}
                <LiveIngestionStatus />

                {/* Multi-Device Fleet Management */}
                <FleetDashboard />

                {/* 3D Digital Twin Visualization */}
                <DigitalTwin3D />

                {/* Dashboard HUD Cards & Live score breakdown */}
                <TwinStatus latestData={latestData} isConnected={isConnected} />

                {/* Live Telemetry rolling charts */}
                <TelemetryCharts data={telemetryHistory} projections={projections} />

                {/* Live Chat Interface and Raw telemetry logs console */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  <div className="lg:col-span-2">
                    <ChatInterface deviceId={DEVICE_ID} mode="live" />
                  </div>
                  
                  <div className="glass-panel rounded-2xl border border-white/5 overflow-hidden">
                    <div className="px-5 py-4 border-b border-white/5 bg-slate-900/40 flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Terminal className="h-4.5 w-4.5 text-indigo-400" />
                        <h3 className="text-xs font-bold text-white uppercase tracking-wider">Raw Telemetry Stream</h3>
                      </div>
                      <span className="text-[10px] text-slate-500">Showing last 10 frames</span>
                    </div>
                    <div className="p-4 font-mono text-[11px] leading-relaxed max-h-[440px] h-[440px] overflow-y-auto bg-slate-950/40 text-slate-400 space-y-1">
                      {telemetryHistory.length === 0 ? (
                        <div className="text-center py-6 text-slate-600">Awaiting stream packets...</div>
                      ) : (
                        telemetryHistory.slice(0, 10).map((log, idx) => (
                          <div key={idx} className="flex items-start border-b border-white/[0.02] pb-1 hover:bg-white/[0.01] px-2 rounded">
                            <span className="text-slate-500 mr-3 shrink-0">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                            <span className="text-indigo-400 mr-2 shrink-0">info:</span>
                            <span className="break-all">
                              cpu={log.cpu_usage}% | memory={log.memory_usage}% | temp={log.cpu_temperature}°C | fan={log.fan_speed}RPM | battery={log.battery_level}% ({log.power_source}) | processes={log.active_process_count}
                            </span>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </>
            )}

            {liveTab === 'prediction' && (
              <>
                {/* XGBoost · LSTM · Prophet Predictions */}
                <FutureStateDashboard />

                {/* AI Reasoning Dashboard (Anomaly detection, confidence scores, recommendations) */}
                <AIReasoningDashboard deviceId={DEVICE_ID} tickCount={tickCount} />

                {/* Live AI chat */}
                <div className="grid grid-cols-1 gap-6">
                  <ChatInterface deviceId={DEVICE_ID} mode="live" />
                </div>
              </>
            )}

            {liveTab === 'simulation' && (
              <>
                {/* What-If Steady State Simulation Engine */}
                <WhatIfSimulationDashboard />

                {/* Time Travel scenario planner overlays */}
                <div className="grid grid-cols-1 gap-6">
                  <TimeTravelPlayground
                    deviceId={DEVICE_ID}
                    selectedTimestamp={latestData?.timestamp || null}
                    onProjectionLoaded={setProjections}
                  />
                </div>

                {/* Live AI chat */}
                <div className="grid grid-cols-1 gap-6">
                  <ChatInterface deviceId={DEVICE_ID} mode="live" />
                </div>
              </>
            )}
          </>
        )}

      </div>

      {/* Footer */}
      <footer className="py-6 border-t border-white/5 text-center text-xs text-slate-600 bg-slate-950/20">
        AI Digital Twin Telemetry Engine &bull; Developed by Antigravity
      </footer>
    </main>
  );
}
