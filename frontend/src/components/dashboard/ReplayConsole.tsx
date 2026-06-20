'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Play, Pause, Square, ChevronRight, RefreshCw, AlertCircle, Loader } from 'lucide-react';
import { TelemetryData } from '@/types';

interface ReplayConsoleProps {
  deviceId: string;
  onFrameChange: (frame: TelemetryData | null) => void;
  onReplayActiveChange: (isActive: boolean) => void;
}

export const ReplayConsole: React.FC<ReplayConsoleProps> = ({
  deviceId,
  onFrameChange,
  onReplayActiveChange,
}) => {
  const [replayHistory, setReplayHistory] = useState<TelemetryData[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<1 | 2 | 5 | 10>(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [limit, setLimit] = useState<60 | 120>(60);
  
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const fetchReplayData = async () => {
    setIsLoading(true);
    setError(null);
    setIsPlaying(false);
    onReplayActiveChange(false);
    onFrameChange(null);
    
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/twin-state/replay?device_id=${deviceId}&limit=${limit}`
      );
      if (!response.ok) {
        throw new Error('Failed to load replay history');
      }
      const data = await response.json();
      setReplayHistory(data);
      setCurrentIndex(0);
    } catch (err: any) {
      setError(err.message || 'Error loading replay');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchReplayData();
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [deviceId, limit]);

  // Handle Playback Loop
  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);

    if (isPlaying && replayHistory.length > 0) {
      // Calculate interval: base interval is 1000ms divided by playbackSpeed
      const intervalMs = 1000 / playbackSpeed;
      
      timerRef.current = setInterval(() => {
        setCurrentIndex(prev => {
          const next = prev + 1;
          if (next >= replayHistory.length) {
            setIsPlaying(false);
            onReplayActiveChange(false);
            onFrameChange(null);
            if (timerRef.current) clearInterval(timerRef.current);
            return prev;
          }
          onFrameChange(replayHistory[next]);
          return next;
        });
      }, intervalMs);
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying, replayHistory, playbackSpeed]);

  const handlePlayPause = () => {
    if (replayHistory.length === 0) return;
    
    const newIsPlaying = !isPlaying;
    setIsPlaying(newIsPlaying);
    onReplayActiveChange(newIsPlaying);
    
    if (newIsPlaying) {
      // Start or resume frame update
      onFrameChange(replayHistory[currentIndex]);
    }
  };

  const handleStop = () => {
    setIsPlaying(false);
    onReplayActiveChange(false);
    setCurrentIndex(0);
    onFrameChange(null);
    if (timerRef.current) clearInterval(timerRef.current);
  };

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const idx = parseInt(e.target.value, 10);
    setCurrentIndex(idx);
    
    // If stopped, entering slider should activate replay mode at that index
    onReplayActiveChange(true);
    onFrameChange(replayHistory[idx]);
  };

  const currentFrame = replayHistory[currentIndex];
  const timeStr = currentFrame
    ? new Date(currentFrame.timestamp).toLocaleString()
    : '—';

  return (
    <div className="glass-panel rounded-2xl border border-white/5 p-6 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-white leading-tight">Historical State Replay</h3>
          <p className="text-[11px] text-slate-500 mt-0.5">Scrub and playback historical laptop telemetry updates</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={limit}
            onChange={(e) => setLimit(parseInt(e.target.value) as 60 | 120)}
            disabled={isLoading || isPlaying}
            className="bg-white/5 border border-white/10 rounded-lg text-xs px-2.5 py-1 text-slate-300 outline-none focus:border-indigo-500"
          >
            <option value={60} className="bg-[#0e1626]">Last 60 ticks (~2m)</option>
            <option value={120} className="bg-[#0e1626]">Last 120 ticks (~4m)</option>
          </select>
          <button
            onClick={fetchReplayData}
            disabled={isLoading || isPlaying}
            className="p-1.5 rounded-lg border border-white/10 hover:bg-white/5 text-slate-400 hover:text-white transition"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl p-3">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-6 gap-2">
          <Loader className="h-6 w-6 text-indigo-400 animate-spin" />
          <span className="text-xs text-slate-500">Querying historical database timeline...</span>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {/* Progress Slider */}
          <div className="flex items-center gap-3">
            <span className="text-[10px] text-slate-500 font-mono">00:00</span>
            <input
              type="range"
              min={0}
              max={Math.max(0, replayHistory.length - 1)}
              value={currentIndex}
              onChange={handleSliderChange}
              disabled={replayHistory.length === 0}
              className="flex-1 accent-indigo-500 h-1 bg-white/10 rounded-lg appearance-none cursor-pointer"
            />
            <span className="text-[10px] text-slate-500 font-mono">
              {replayHistory.length > 0 ? `${replayHistory.length - 1}` : '00'}
            </span>
          </div>

          {/* Controls HUD */}
          <div className="flex flex-wrap items-center justify-between gap-4 mt-1 bg-white/5 border border-white/10 rounded-xl p-3.5">
            {/* Playback Controls */}
            <div className="flex items-center gap-2">
              <button
                onClick={handlePlayPause}
                disabled={replayHistory.length === 0}
                className="flex items-center justify-center p-2.5 rounded-lg bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 text-white transition shadow-lg shadow-indigo-500/20"
              >
                {isPlaying ? <Pause className="h-4 w-4 fill-white" /> : <Play className="h-4 w-4 fill-white" />}
              </button>
              <button
                onClick={handleStop}
                disabled={replayHistory.length === 0}
                className="flex items-center justify-center p-2.5 rounded-lg border border-white/10 hover:bg-white/5 disabled:opacity-50 text-slate-400 hover:text-white transition"
              >
                <Square className="h-4 w-4 fill-slate-400 hover:fill-white" />
              </button>
            </div>

            {/* Playback info */}
            <div className="text-center md:text-left">
              <p className="text-xs font-semibold text-slate-300">
                {replayHistory.length > 0 ? `Frame ${currentIndex + 1} of ${replayHistory.length}` : 'No frames loaded'}
              </p>
              <p className="text-[10px] text-slate-500 mt-0.5 font-mono">{timeStr}</p>
            </div>

            {/* Speed rates */}
            <div className="flex items-center bg-white/5 border border-white/10 rounded-lg p-0.5">
              {([1, 2, 5, 10] as const).map((rate) => (
                <button
                  key={rate}
                  onClick={() => setPlaybackSpeed(rate)}
                  className={`text-[10px] font-bold px-2 py-1 rounded-md transition ${
                    playbackSpeed === rate
                      ? 'bg-indigo-500 text-white shadow-md'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {rate}x
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReplayConsole;
