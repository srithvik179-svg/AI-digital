'use client';

import React, { useEffect, useState, useRef } from 'react';
import { TelemetryData } from '@/types';
import TwinStatus from '@/components/dashboard/TwinStatus';
import TelemetryCharts from '@/components/dashboard/TelemetryCharts';
import ChatInterface from '@/components/dashboard/ChatInterface';
import { Terminal, Settings, Play, ShieldAlert, Cpu, CheckCircle2, Upload, AlertCircle, Loader } from 'lucide-react';

const DEVICE_ID = "laptop-mac-001";

export default function Dashboard() {
  const [telemetryHistory, setTelemetryHistory] = useState<TelemetryData[]>([]);
  const [latestData, setLatestData] = useState<TelemetryData | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
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
    
    const connectWs = () => {
      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setIsConnected(true);
          console.log("WebSocket connected.");
        };

        ws.onmessage = (event) => {
          const payload = JSON.parse(event.data);
          if (payload.type === 'telemetry_update') {
            const data = payload.data as TelemetryData;
            setLatestData(data);
            setTelemetryHistory(prev => [data, ...prev].slice(0, 30));
          }
        };

        ws.onclose = () => {
          setIsConnected(false);
          setIsSimulating(false);
          console.log("WebSocket disconnected. Reconnecting in 5 seconds...");
          setTimeout(connectWs, 5000);
        };

        ws.onerror = (err) => {
          console.error("WebSocket error:", err);
          ws.close();
        };
      } catch (e) {
        console.error("Failed to connect websocket:", e);
      }
    };

    connectWs();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
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

  return (
    <main className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col">
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

        <div className="flex items-center space-x-4">
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
        
        {/* Intro/Simulation Bar */}
        <div className="glass-panel rounded-2xl p-5 border border-white/5 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <h2 className="text-sm font-bold text-white">Active Device: {DEVICE_ID}</h2>
            <p className="text-slate-400 text-xs mt-0.5">
              Analyzing battery metrics, core CPU cycles, and thermal envelopes dynamically.
            </p>
          </div>
          
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full md:w-auto self-stretch md:self-auto">
            {/* Hidden File Input */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".csv"
              className="hidden"
            />
            
            {/* CSV Import Button */}
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadStatus.status === 'uploading'}
              className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold bg-slate-900 border border-white/5 text-slate-200 hover:text-white hover:bg-slate-800 transition duration-200 shadow-md disabled:opacity-50"
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

            {/* Simulation Button */}
            <button
              onClick={handleStartSimulation}
              disabled={!isConnected || isSimulating}
              className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition duration-200 shadow-md ${
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

        {/* Upload Status Notification Banner */}
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

        {/* Dashboard HUD Cards */}
        <TwinStatus latestData={latestData} isConnected={isConnected} />

        {/* Charts & AI Agent Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Charts Panel */}
          <div className="lg:col-span-2">
            <TelemetryCharts data={telemetryHistory} />
          </div>

          {/* AI Twin chat interface */}
          <div className="lg:col-span-1">
            <ChatInterface deviceId={DEVICE_ID} />
          </div>
        </div>

        {/* Historical Logs Console */}
        <div className="glass-panel rounded-2xl border border-white/5 overflow-hidden">
          <div className="px-5 py-4 border-b border-white/5 bg-slate-900/40 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Terminal className="h-4.5 w-4.5 text-indigo-400" />
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">Raw Telemetry Stream</h3>
            </div>
            <span className="text-[10px] text-slate-500">Showing last 10 frames</span>
          </div>
          <div className="p-4 font-mono text-[11px] leading-relaxed max-h-[220px] overflow-y-auto bg-slate-950/40 text-slate-400 space-y-1">
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

      {/* Footer */}
      <footer className="py-6 border-t border-white/5 text-center text-xs text-slate-600 bg-slate-950/20">
        AI Digital Twin Telemetry Engine &bull; Developed by Antigravity
      </footer>
    </main>
  );
}
