'use client';

import React, { useState, useEffect } from 'react';
import { Database, Play, RefreshCw, Layers, Terminal, AlertCircle, CheckCircle, Network, Info } from 'lucide-react';

interface GraphNode {
  id: string;
  label: string;
  description: string;
  device_id?: string;
}

interface GraphEdge {
  source: string;
  target: string;
  relationship_type: string;
  correlation_strength: number;
  description: string;
}

interface CypherQueryResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  raw_rows: any[];
}

interface KnowledgeGraphExplorerProps {
  deviceId: string;
}

const TEMPLATE_QUERIES = [
  {
    name: "Show All Influences",
    query: "MATCH (n:TelemetryMetric {device_id: $device_id})-[r:INFLUENCES]->(m:TelemetryMetric {device_id: $device_id}) RETURN n, r, m"
  },
  {
    name: "Strong Relationships (|r| ≥ 0.8)",
    query: "MATCH (n:TelemetryMetric {device_id: $device_id})-[r:INFLUENCES]->(m:TelemetryMetric {device_id: $device_id}) WHERE abs(r.correlation_strength) >= 0.8 RETURN n, r, m"
  },
  {
    name: "Thermal Cooling Path Only",
    query: "MATCH (n:TelemetryMetric {device_id: $device_id})-[r:INFLUENCES {relationship_type: 'active_cooling'}]->(m:TelemetryMetric {device_id: $device_id}) RETURN n, r, m"
  }
];

export const KnowledgeGraphExplorer: React.FC<KnowledgeGraphExplorerProps> = ({ deviceId }) => {
  const [cypherQuery, setCypherQuery] = useState<string>(TEMPLATE_QUERIES[0].query);
  const [activeTab, setActiveTab] = useState<'visualizer' | 'json'>('visualizer');
  const [loading, setLoading] = useState<boolean>(false);
  const [syncing, setSyncing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
  const [graphData, setGraphData] = useState<CypherQueryResponse | null>(null);

  const executeCypher = async (customQuery?: string) => {
    const queryToRun = customQuery || cypherQuery;
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/knowledge-graph/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: queryToRun,
          device_id: deviceId
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to execute query');
      }

      const result = await response.json();
      setGraphData(result);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Error executing Cypher query.');
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    try {
      setSyncing(true);
      setSyncMessage(null);
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/knowledge-graph/sync?device_id=${deviceId}`, {
        method: 'POST'
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Sync failed');
      }

      const result = await response.json();
      setSyncMessage({
        type: 'success',
        text: `Successfully synchronized Knowledge Graph! Synced ${result.nodes_synced} nodes and ${result.edges_synced} edges.`
      });
      // Automatically refresh query to show synced nodes
      executeCypher();
    } catch (err: any) {
      setSyncMessage({
        type: 'error',
        text: err.message || 'Failed to sync with Neo4j.'
      });
    } finally {
      setSyncing(false);
    }
  };

  // Run initial query
  useEffect(() => {
    executeCypher();
  }, [deviceId]);

  // Dynamic circular layout positions for returned nodes
  const getNodePositions = (nodes: GraphNode[]) => {
    const positions: Record<string, { x: number; y: number }> = {};
    const count = nodes.length;
    const centerX = 240;
    const centerY = 130;
    const radius = 80;

    nodes.forEach((node, index) => {
      // Calculate circle coordinates evenly
      const angle = (2 * Math.PI * index) / count;
      positions[node.id] = {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle)
      };
    });
    return positions;
  };

  const nodePositions = graphData ? getNodePositions(graphData.nodes) : {};
  const NODE_RADIUS = 24;

  const getEdgeLinePoints = (edge: GraphEdge) => {
    const p1 = nodePositions[edge.source];
    const p2 = nodePositions[edge.target];
    if (!p1 || !p2) return null;

    const dx = p2.x - p1.x;
    const dy = p2.y - p1.y;
    const distance = Math.sqrt(dx * dx + dy * dy);

    if (distance === 0) return null;

    const ux = dx / distance;
    const uy = dy / distance;

    const startX = p1.x + ux * NODE_RADIUS;
    const startY = p1.y + uy * NODE_RADIUS;
    const endX = p2.x - ux * (NODE_RADIUS + 10);
    const endY = p2.y - uy * (NODE_RADIUS + 10);

    return { startX, startY, endX, endY, midX: (startX + endX) / 2, midY: (startY + endY) / 2 };
  };

  return (
    <div className="glass-panel rounded-2xl border border-white/5 overflow-hidden transition-all duration-300">
      {/* Header */}
      <div className="px-5 py-4 border-b border-white/5 bg-slate-900/40 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-2">
          <Database className="h-4.5 w-4.5 text-indigo-400" />
          <div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              Neo4j Graph Knowledge Base Explorer
            </h3>
            <p className="text-slate-500 text-[10px] mt-0.5">
              Live Cypher query terminal and hardware influence schema visualizer
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3 shrink-0 self-stretch sm:self-auto justify-end">
          {syncing ? (
            <span className="text-[10px] text-indigo-400 flex items-center gap-1">
              <RefreshCw className="h-3 w-3 animate-spin" /> Syncing Neo4j...
            </span>
          ) : (
            <button
              onClick={handleSync}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-400 border border-indigo-500/20 hover:border-indigo-500/30 transition duration-200"
            >
              <RefreshCw className="h-3 w-3" />
              Sync Postgres to Neo4j
            </button>
          )}
        </div>
      </div>

      {/* Main Grid */}
      <div className="p-5 grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Side: Query Editor & Templates */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <div>
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2">
              Query Templates
            </label>
            <div className="flex flex-wrap gap-2">
              {TEMPLATE_QUERIES.map((t, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setCypherQuery(t.query);
                    executeCypher(t.query);
                  }}
                  className={`px-2.5 py-1.5 rounded-lg text-[10px] font-semibold border transition duration-200 ${
                    cypherQuery === t.query
                      ? 'bg-slate-800 text-white border-white/20'
                      : 'bg-slate-900/40 text-slate-400 border-white/5 hover:text-slate-200 hover:bg-slate-800/40'
                  }`}
                >
                  {t.name}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 flex flex-col min-h-[160px]">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2 flex items-center gap-1.5">
              <Terminal className="h-3.5 w-3.5 text-indigo-400" />
              Cypher Terminal
            </label>
            <div className="flex-1 relative rounded-xl border border-white/5 bg-slate-950/60 overflow-hidden flex flex-col">
              <textarea
                value={cypherQuery}
                onChange={(e) => setCypherQuery(e.target.value)}
                className="w-full flex-1 p-3.5 font-mono text-xs bg-transparent text-slate-200 placeholder-slate-600 focus:outline-none resize-none leading-relaxed"
                placeholder="Write Cypher query here..."
              />
              
              <div className="px-3.5 py-2 border-t border-white/5 bg-slate-900/20 flex justify-between items-center shrink-0">
                <span className="text-[9px] text-slate-600 font-mono">Variables: $device_id</span>
                <button
                  onClick={() => executeCypher()}
                  disabled={loading}
                  className="flex items-center gap-1 px-3 py-1 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-850 disabled:opacity-50 text-white rounded-lg text-[10px] font-bold shadow-md transition duration-200"
                >
                  <Play className="h-3 w-3 fill-current" />
                  Run Cypher
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Right Side: Visual Output / Explorer */}
        <div className="lg:col-span-7 flex flex-col border-t lg:border-t-0 lg:border-l border-white/5 pt-5 lg:pt-0 lg:pl-6 min-h-[300px]">
          {/* Output Control Tabs */}
          <div className="flex items-center justify-between border-b border-white/5 pb-3 mb-4 shrink-0">
            <div className="bg-slate-950/60 p-0.5 rounded-lg border border-white/5 flex">
              <button
                onClick={() => setActiveTab('visualizer')}
                className={`px-3 py-1 text-[10px] font-bold rounded-md transition-all duration-200 ${
                  activeTab === 'visualizer'
                    ? 'bg-slate-800 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Graph Visualizer
              </button>
              <button
                onClick={() => setActiveTab('json')}
                className={`px-3 py-1 text-[10px] font-bold rounded-md transition-all duration-200 ${
                  activeTab === 'json'
                    ? 'bg-slate-800 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                JSON Response
              </button>
            </div>
            <span className="text-[10px] text-slate-500 font-medium">
              Returned: {graphData?.nodes.length ?? 0} nodes · {graphData?.edges.length ?? 0} edges
            </span>
          </div>

          {/* Tab Content Panels */}
          <div className="flex-1 flex flex-col justify-center min-h-0">
            {loading ? (
              <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs gap-2 py-10">
                <RefreshCw className="h-6 w-6 animate-spin text-indigo-400" />
                <span>Running Cypher transaction...</span>
              </div>
            ) : error ? (
              <div className="flex-1 flex flex-col items-center justify-center text-rose-400 text-xs p-4 text-center gap-2 py-10">
                <AlertCircle className="h-6 w-6 text-rose-500" />
                <span className="font-bold">Transaction Failed</span>
                <span className="text-slate-500 max-w-sm">{error}</span>
              </div>
            ) : activeTab === 'visualizer' ? (
              <div className="flex-1 bg-slate-950/10 rounded-xl border border-white/[0.02] flex items-center justify-center p-2 relative">
                {graphData && graphData.nodes.length > 0 ? (
                  <svg
                    viewBox="0 0 480 260"
                    className="w-full h-auto max-h-[240px] overflow-visible select-none"
                  >
                    <defs>
                      <marker
                        id="neo-arrow-emerald"
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
                        id="neo-arrow-rose"
                        viewBox="0 0 10 10"
                        refX="6"
                        refY="5"
                        markerWidth="6"
                        markerHeight="6"
                        orient="auto"
                      >
                        <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#f43f5e" />
                      </marker>
                    </defs>

                    {/* Edge Lines */}
                    {graphData.edges.map((edge, idx) => {
                      const pts = getEdgeLinePoints(edge);
                      if (!pts) return null;

                      const isPositive = edge.correlation_strength > 0;
                      return (
                        <g key={idx}>
                          <line
                            x1={pts.startX}
                            y1={pts.startY}
                            x2={pts.endX}
                            y2={pts.endY}
                            stroke={isPositive ? 'rgba(16, 185, 129, 0.4)' : 'rgba(244, 63, 94, 0.4)'}
                            strokeWidth={1.5}
                            markerEnd={isPositive ? 'url(#neo-arrow-emerald)' : 'url(#neo-arrow-rose)'}
                          />
                          <g transform={`translate(${pts.midX}, ${pts.midY})`}>
                            <rect
                              x="-14"
                              y="-6"
                              width="28"
                              height="12"
                              rx="3"
                              fill="#0b0f19"
                              className="stroke-white/5"
                              strokeWidth="0.5"
                            />
                            <text
                              textAnchor="middle"
                              dominantBaseline="central"
                              className={`text-[8px] font-mono font-bold ${isPositive ? 'fill-emerald-400' : 'fill-rose-400'}`}
                            >
                              {edge.correlation_strength.toFixed(2)}
                            </text>
                          </g>
                        </g>
                      );
                    })}

                    {/* Node Circles */}
                    {graphData.nodes.map((node) => {
                      const pos = nodePositions[node.id];
                      if (!pos) return null;

                      return (
                        <g key={node.id} transform={`translate(${pos.x}, ${pos.y})`}>
                          <circle
                            r={NODE_RADIUS}
                            className="fill-slate-900/90 stroke-indigo-500/40"
                            strokeWidth="1.5"
                          />
                          <text
                            textAnchor="middle"
                            dominantBaseline="central"
                            className="fill-slate-200 text-[8px] font-bold tracking-tight"
                          >
                            {node.label.split(' ')[0]}
                          </text>
                          <text
                            y={NODE_RADIUS + 9}
                            textAnchor="middle"
                            className="fill-slate-500 text-[8px] font-semibold"
                          >
                            {node.id}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                ) : (
                  <div className="text-center py-10 text-slate-600 text-xs flex flex-col items-center gap-1.5">
                    <Network className="h-6 w-6 text-slate-700" />
                    <span>No nodes matched your query layout context.</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex-1 rounded-xl border border-white/5 bg-slate-950/60 p-4 font-mono text-[10px] leading-relaxed max-h-[220px] overflow-y-auto text-indigo-300">
                {graphData ? (
                  <pre className="whitespace-pre-wrap">{JSON.stringify(graphData.raw_rows, null, 2)}</pre>
                ) : (
                  <span className="text-slate-600">No query response loaded yet.</span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Sync/Success Alerts Banner */}
      {syncMessage && (
        <div className={`px-5 py-3 border-t text-[10px] flex items-center justify-between ${
          syncMessage.type === 'success'
            ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
            : 'bg-red-500/10 border-red-500/20 text-red-400'
        }`}>
          <div className="flex items-center gap-2">
            {syncMessage.type === 'success' ? (
              <CheckCircle className="h-4 w-4 shrink-0" />
            ) : (
              <AlertCircle className="h-4 w-4 shrink-0" />
            )}
            <span>{syncMessage.text}</span>
          </div>
          <button 
            onClick={() => setSyncMessage(null)}
            className="text-[9px] uppercase font-bold hover:underline opacity-80"
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
};

export default KnowledgeGraphExplorer;
