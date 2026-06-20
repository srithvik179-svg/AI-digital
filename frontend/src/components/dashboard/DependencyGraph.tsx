'use client';

import React, { useEffect, useState } from 'react';
import { 
  Network, RefreshCw, Info, Cpu, Thermometer, Wind, Zap, 
  BatteryCharging, ChevronRight, HelpCircle 
} from 'lucide-react';
import { RelationshipNode, RelationshipEdge, RelationshipGraph } from '@/types';

interface DependencyGraphProps {
  deviceId: string;
  tickCount?: number;
}

const NODE_POSITIONS: Record<string, { x: number; y: number }> = {
  cpu_usage: { x: 100, y: 90 },
  cpu_temperature: { x: 300, y: 90 },
  fan_speed_rpm: { x: 500, y: 90 },
  power_source: { x: 200, y: 230 },
  battery_level_delta: { x: 400, y: 230 },
};

// Radius of node circles
const NODE_RADIUS = 28;

export const DependencyGraph: React.FC<DependencyGraphProps> = ({ deviceId, tickCount = 0 }) => {
  const [graphData, setGraphData] = useState<RelationshipGraph | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Interaction State
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<RelationshipEdge | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<RelationshipEdge | null>(null);

  const fetchRelationships = async () => {
    try {
      setLoading(true);
      const url = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/relationships?device_id=${deviceId}`;
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Failed to load dependency graph (HTTP ${response.status})`);
      }
      const json = await response.json();
      setGraphData(json);
      setError(null);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to fetch hardware dependencies.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRelationships();
  }, [deviceId]);

  // Refresh topology occasionally when metrics tick
  useEffect(() => {
    if (tickCount > 0 && tickCount % 5 === 0) {
      fetchRelationships();
    }
  }, [tickCount]);

  const getNodeIcon = (nodeId: string) => {
    const iconClass = "h-6 w-6 text-indigo-400";
    switch (nodeId) {
      case 'cpu_usage':
        return <Cpu className={iconClass} />;
      case 'cpu_temperature':
        return <Thermometer className="h-6 w-6 text-rose-400" />;
      case 'fan_speed_rpm':
        return <Wind className="h-6 w-6 text-sky-400 animate-spin" style={{ animationDuration: '4s' }} />;
      case 'power_source':
        return <Zap className="h-6 w-6 text-amber-400" />;
      case 'battery_level_delta':
        return <BatteryCharging className="h-6 w-6 text-emerald-400" />;
      default:
        return <Network className={iconClass} />;
    }
  };

  const getEdgeStrengthColor = (strength: number, isHoveredOrSelected: boolean) => {
    if (isHoveredOrSelected) {
      return strength > 0 ? 'stroke-emerald-400' : 'stroke-rose-400';
    }
    return strength > 0 ? 'stroke-emerald-500/40' : 'stroke-rose-500/40';
  };

  const getEdgeFlowColor = (strength: number) => {
    return strength > 0 ? 'text-emerald-400' : 'text-rose-400';
  };

  // Helper to check if a node is connected to the selected node
  const isNodeConnectedToSelected = (nodeId: string) => {
    if (!selectedNodeId) return true;
    if (nodeId === selectedNodeId) return true;

    // Check if there's any edge between selectedNodeId and nodeId
    return graphData?.edges.some(
      e => (e.source === selectedNodeId && e.target === nodeId) || 
           (e.target === selectedNodeId && e.source === nodeId)
    ) ?? false;
  };

  const getEdgeLinePoints = (edge: RelationshipEdge) => {
    const p1 = NODE_POSITIONS[edge.source];
    const p2 = NODE_POSITIONS[edge.target];
    if (!p1 || !p2) return null;

    // Truncate vectors so lines start/end at circle edges
    const dx = p2.x - p1.x;
    const dy = p2.y - p1.y;
    const distance = Math.sqrt(dx * dx + dy * dy);

    if (distance === 0) return null;

    const ux = dx / distance;
    const uy = dy / distance;

    const startX = p1.x + ux * NODE_RADIUS;
    const startY = p1.y + uy * NODE_RADIUS;

    // Extra offset for arrow head marker to not overlap circle
    const targetOffset = NODE_RADIUS + 12;
    const endX = p2.x - ux * targetOffset;
    const endY = p2.y - uy * targetOffset;

    return { startX, startY, endX, endY, midX: (startX + endX) / 2, midY: (startY + endY) / 2 };
  };

  const getEdgeLabelPosition = (edge: RelationshipEdge) => {
    const points = getEdgeLinePoints(edge);
    if (!points) return { x: 0, y: 0 };
    // Place label slightly above midpoint
    return { x: points.midX, y: points.midY - 10 };
  };

  // Active details to show in inspector
  const activeInspectEntity = selectedEdge 
    ? { type: 'edge', data: selectedEdge } 
    : selectedNodeId && graphData?.nodes.find(n => n.id === selectedNodeId)
    ? { type: 'node', data: graphData.nodes.find(n => n.id === selectedNodeId)! }
    : null;

  return (
    <div className="glass-panel rounded-2xl border border-white/5 overflow-hidden transition-all duration-300 flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-4 border-b border-white/5 bg-slate-900/40 flex items-center justify-between gap-3 shrink-0">
        <div className="flex items-center space-x-2">
          <Network className="h-4.5 w-4.5 text-indigo-400" />
          <div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              Hardware Dependency Topology
            </h3>
            <p className="text-slate-500 text-[10px] mt-0.5">
              Interactive structural map mapping telemetry influences and state paths
            </p>
          </div>
        </div>

        <button
          onClick={fetchRelationships}
          disabled={loading}
          className="p-1.5 bg-slate-900 border border-white/5 hover:border-white/10 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition duration-200 disabled:opacity-50"
          title="Refresh dependency graph"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
        </button>
      </div>

      {/* Main Container */}
      <div className="p-5 flex flex-col lg:flex-row gap-6 flex-1 min-h-0">
        {/* Graph Canvas */}
        <div className="flex-1 min-w-0 bg-slate-950/20 rounded-2xl border border-white/[0.03] p-2 relative flex items-center justify-center">
          {loading && !graphData ? (
            <div className="h-[280px] flex flex-col items-center justify-center text-slate-500 text-xs gap-2">
              <RefreshCw className="h-6 w-6 animate-spin text-indigo-400" />
              <span>Mapping telemetry causal graph...</span>
            </div>
          ) : error ? (
            <div className="h-[280px] flex flex-col items-center justify-center text-rose-400 text-xs p-4 text-center gap-2">
              <Info className="h-6 w-6 text-rose-500" />
              <span>{error}</span>
              <button
                onClick={fetchRelationships}
                className="mt-2 px-3 py-1 bg-slate-900 hover:bg-slate-800 border border-white/5 text-[10px] font-bold text-slate-300 rounded"
              >
                Retry Request
              </button>
            </div>
          ) : (
            <svg
              viewBox="0 0 600 320"
              className="w-full h-auto max-h-[290px] select-none"
              style={{ overflow: 'visible' }}
            >
              {/* Arrow Head Defs */}
              <defs>
                <marker
                  id="arrow-emerald"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto"
                >
                  <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#10b981" />
                </marker>
                <marker
                  id="arrow-rose"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto"
                >
                  <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#f43f5e" />
                </marker>
                <marker
                  id="arrow-dim"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto"
                >
                  <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="rgba(255, 255, 255, 0.15)" />
                </marker>
              </defs>

              {/* Draw Edges */}
              {graphData?.edges.map((edge, index) => {
                const points = getEdgeLinePoints(edge);
                if (!points) return null;

                const isSelected = selectedEdge === edge;
                const isHovered = hoveredEdge === edge;
                const isDimmed = 
                  (selectedNodeId && edge.source !== selectedNodeId && edge.target !== selectedNodeId) ||
                  (selectedEdge && !isSelected);

                const colorClass = getEdgeStrengthColor(edge.correlation_strength, isHovered || isSelected);
                const absCorr = Math.abs(edge.correlation_strength);
                
                // Animation flow duration inversely proportional to correlation strength
                const flowSpeed = absCorr > 0.05 ? `${(2.5 / absCorr).toFixed(2)}s` : '0s';
                
                // Arrow marker based on state and correlation direction
                const markerId = isDimmed 
                  ? 'url(#arrow-dim)' 
                  : edge.correlation_strength > 0 
                  ? 'url(#arrow-emerald)' 
                  : 'url(#arrow-rose)';

                return (
                  <g 
                    key={index}
                    className="cursor-pointer transition-all duration-300"
                    onMouseEnter={() => setHoveredEdge(edge)}
                    onMouseLeave={() => setHoveredEdge(null)}
                    onClick={() => {
                      setSelectedEdge(edge);
                      setSelectedNodeId(null);
                    }}
                  >
                    {/* Invisible thick background line for easier hover selection */}
                    <line
                      x1={points.startX}
                      y1={points.startY}
                      x2={points.endX}
                      y2={points.endY}
                      stroke="transparent"
                      strokeWidth={16}
                    />

                    {/* Edge Base Line */}
                    <line
                      x1={points.startX}
                      y1={points.startY}
                      x2={points.endX}
                      y2={points.endY}
                      className={`transition-all duration-300 ${colorClass}`}
                      strokeWidth={isSelected || isHovered ? 2.5 : 1.5}
                      markerEnd={markerId}
                    />

                    {/* Animated Flow Layer (dashed indicator) */}
                    {!isDimmed && absCorr > 0.05 && (
                      <line
                        x1={points.startX}
                        y1={points.startY}
                        x2={points.endX}
                        y2={points.endY}
                        stroke={edge.correlation_strength > 0 ? '#10b981' : '#f43f5e'}
                        strokeWidth={isSelected || isHovered ? 3.0 : 2.0}
                        strokeDasharray="5 8"
                        className="flowing-path-anim"
                        style={{
                          animation: `flow-anim ${flowSpeed} linear infinite`,
                          opacity: isSelected || isHovered ? 0.9 : 0.4
                        }}
                      />
                    )}

                    {/* Edge Label (Correlation Value) */}
                    <g transform={`translate(${points.midX}, ${points.midY})`}>
                      <rect
                        x="-18"
                        y="-8"
                        width="36"
                        height="16"
                        rx="4"
                        className={`stroke-white/5 transition-all duration-300 ${
                          isDimmed 
                            ? 'fill-slate-950/80' 
                            : isSelected || isHovered 
                            ? 'fill-slate-900 border border-white/20' 
                            : 'fill-slate-950/90'
                        }`}
                        strokeWidth="0.5"
                      />
                      <text
                        textAnchor="middle"
                        dominantBaseline="central"
                        className={`text-[9px] font-mono font-bold transition-all duration-300 ${
                          isDimmed 
                            ? 'fill-slate-600' 
                            : edge.correlation_strength > 0 
                            ? 'fill-emerald-400' 
                            : 'fill-rose-400'
                        }`}
                      >
                        {edge.correlation_strength > 0 ? '+' : ''}
                        {edge.correlation_strength.toFixed(2)}
                      </text>
                    </g>
                  </g>
                );
              })}

              {/* Draw Nodes */}
              {graphData?.nodes.map((node) => {
                const pos = NODE_POSITIONS[node.id];
                if (!pos) return null;

                const isSelected = selectedNodeId === node.id;
                const isHovered = hoveredNodeId === node.id;
                const isDimmed = !isNodeConnectedToSelected(node.id) || (selectedEdge && selectedEdge.source !== node.id && selectedEdge.target !== node.id);

                return (
                  <g
                    key={node.id}
                    transform={`translate(${pos.x}, ${pos.y})`}
                    className="cursor-pointer transition-all duration-300"
                    onMouseEnter={() => setHoveredNodeId(node.id)}
                    onMouseLeave={() => setHoveredNodeId(null)}
                    onClick={() => {
                      setSelectedNodeId(node.id);
                      setSelectedEdge(null);
                    }}
                  >
                    {/* Glow effect for selected/hovered nodes */}
                    {(isSelected || isHovered) && (
                      <circle
                        r={NODE_RADIUS + 6}
                        className="fill-indigo-500/10 stroke-indigo-500/20 animate-pulse"
                        strokeWidth={1}
                      />
                    )}

                    {/* Node Circle */}
                    <circle
                      r={NODE_RADIUS}
                      className={`transition-all duration-300 ${
                        isDimmed 
                          ? 'fill-slate-950/40 stroke-white/5 opacity-40' 
                          : isSelected
                          ? 'fill-indigo-950/80 stroke-indigo-500'
                          : isHovered
                          ? 'fill-slate-900 stroke-indigo-400'
                          : 'fill-slate-900/90 stroke-white/10'
                      }`}
                      strokeWidth={isSelected ? 2 : 1.5}
                      style={{
                        boxShadow: '0 4px 12px 0 rgba(0,0,0,0.5)',
                        backdropFilter: 'blur(4px)'
                      }}
                    />

                    {/* HTML icon container via foreignObject */}
                    <foreignObject
                      x={-NODE_RADIUS / 2}
                      y={-NODE_RADIUS / 2}
                      width={NODE_RADIUS}
                      height={NODE_RADIUS}
                      style={{ pointerEvents: 'none' }}
                      className={`transition-opacity duration-300 ${isDimmed ? 'opacity-30' : 'opacity-100'}`}
                    >
                      <div className="h-full w-full flex items-center justify-center">
                        {getNodeIcon(node.id)}
                      </div>
                    </foreignObject>

                    {/* Node label */}
                    <text
                      y={NODE_RADIUS + 14}
                      textAnchor="middle"
                      className={`text-[10px] font-semibold tracking-wide transition-all duration-300 ${
                        isDimmed 
                          ? 'fill-slate-600' 
                          : isSelected || isHovered 
                          ? 'fill-white font-bold' 
                          : 'fill-slate-300'
                      }`}
                    >
                      {node.label}
                    </text>
                  </g>
                );
              })}
            </svg>
          )}

          {/* SVG dashed flow animation style */}
          <style jsx global>{`
            @keyframes flow-anim {
              to {
                stroke-dashoffset: -26;
              }
            }
            .flowing-path-anim {
              pointer-events: none;
            }
          `}</style>
        </div>

        {/* Node/Edge Inspection Sidebar */}
        <div className="w-full lg:w-[240px] shrink-0 flex flex-col justify-between border-t lg:border-t-0 lg:border-l border-white/5 pt-5 lg:pt-0 lg:pl-5 h-full">
          <div className="space-y-4">
            <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1.5">
              <Info className="h-3.5 w-3.5 text-indigo-400" />
              Causal Inspector
            </h4>

            {activeInspectEntity ? (
              <div className="bg-slate-950/40 p-4 rounded-xl border border-white/5 space-y-3">
                {activeInspectEntity.type === 'node' ? (
                  <>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-slate-500 font-bold uppercase">Component Node</span>
                      <span className="text-[10px] font-semibold bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded-full border border-indigo-500/20">
                        Node
                      </span>
                    </div>

                    <div className="text-xs font-bold text-slate-200">
                      {(activeInspectEntity.data as RelationshipNode).label}
                    </div>

                    <p className="text-[11px] text-slate-400 leading-relaxed">
                      {(activeInspectEntity.data as RelationshipNode).description}
                    </p>

                    <div className="pt-2 border-t border-white/5 text-[10px] text-slate-500">
                      Click connecting paths to examine structural influence strength.
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-slate-500 font-bold uppercase">Influence Path</span>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                        (activeInspectEntity.data as RelationshipEdge).correlation_strength > 0
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                      }`}>
                        {(activeInspectEntity.data as RelationshipEdge).relationship_type}
                      </span>
                    </div>

                    <div className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                      <span>{(activeInspectEntity.data as RelationshipEdge).source}</span>
                      <ChevronRight className="h-3 w-3 text-slate-500" />
                      <span>{(activeInspectEntity.data as RelationshipEdge).target}</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <div className={`h-6 px-2 rounded-md flex items-center justify-center text-[10px] font-bold ${
                        (activeInspectEntity.data as RelationshipEdge).correlation_strength > 0
                          ? 'bg-emerald-500/20 text-emerald-300'
                          : 'bg-rose-500/20 text-rose-300'
                      }`}>
                        r = {(activeInspectEntity.data as RelationshipEdge).correlation_strength.toFixed(3)}
                      </div>
                      <span className="text-[10px] text-slate-400 font-medium">
                        {(activeInspectEntity.data as RelationshipEdge).correlation_strength > 0 
                          ? 'Direct correlation' 
                          : 'Inverse correlation'}
                      </span>
                    </div>

                    <p className="text-[11px] text-slate-400 leading-relaxed pt-1.5 border-t border-white/5">
                      {(activeInspectEntity.data as RelationshipEdge).description}
                    </p>
                  </>
                )}

                <button
                  onClick={() => {
                    setSelectedNodeId(null);
                    setSelectedEdge(null);
                  }}
                  className="w-full text-center py-1.5 bg-slate-900/60 hover:bg-slate-900 border border-white/5 text-[9px] font-bold text-slate-400 hover:text-slate-200 rounded transition duration-200"
                >
                  Clear Selection
                </button>
              </div>
            ) : (
              <div className="bg-slate-950/15 p-4 rounded-xl border border-dashed border-white/5 text-center text-slate-500 py-10">
                <HelpCircle className="h-6 w-6 text-slate-600 mx-auto mb-2" />
                <p className="text-xs">Click nodes or paths in the viewport to inspect structural properties.</p>
              </div>
            )}
          </div>

          {/* Quick Statistics Summary Card */}
          <div className="mt-4 bg-slate-900/20 p-4 rounded-xl border border-white/5 text-xs space-y-1.5 shrink-0">
            <div className="flex justify-between items-center text-slate-400">
              <span>Nodes mapped</span>
              <span className="font-mono text-slate-200">{graphData?.nodes.length ?? 0}</span>
            </div>
            <div className="flex justify-between items-center text-slate-400">
              <span>Edges mapped</span>
              <span className="font-mono text-slate-200">{graphData?.edges.length ?? 0}</span>
            </div>
            <div className="flex justify-between items-center text-slate-400 text-[10px] border-t border-white/5 pt-1.5 mt-1.5">
              <span className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                Direct Influence (+r)
              </span>
            </div>
            <div className="flex justify-between items-center text-slate-400 text-[10px]">
              <span className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                Inverse Influence (-r)
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DependencyGraph;
