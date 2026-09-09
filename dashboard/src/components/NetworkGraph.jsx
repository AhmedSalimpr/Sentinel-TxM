import React, { useMemo, useState, useCallback } from 'react';
import * as d3Force from 'd3-force';
import {
  ZoomIn, ZoomOut, Maximize2,
  ShieldAlert, Activity,
  Info, TrendingUp, DollarSign, Network
} from 'lucide-react';

// ─── Light Mode Colour palette ──────────────────────────────────────────────────
const COLOR = {
  hub:    '#e11d48',
  sink:   '#059669',
  cycle:  '#d97706',
  mule:   '#4f46e5',
  normal: '#64748b',
  sel:    '#2563eb',
};

function nodeRole(node) {
  if (node.label === 'hub')  return 'hub';
  if (node.label === 'sink') return 'sink';
  if (node.label?.startsWith('cycle_node') || node.label === 'cycle') return 'cycle';
  if (node.label === 'spoke') return 'mule';
  return 'normal';
}

function roleColor(role) {
  return COLOR[role] ?? COLOR.normal;
}

function fmt(amount) {
  if (!amount && amount !== 0) return '—';
  return amount >= 1000
    ? `$${(amount / 1000).toFixed(1)}k`
    : `$${Number(amount).toFixed(0)}`;
}

export default function NetworkGraph({ subgraph, onSelectUser, selectedUserId }) {
  const [hoveredNode, setHoveredNode] = useState(null);
  const [hoveredEdge, setHoveredEdge] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);

  const [zoom, setZoom]         = useState(1);
  const [pan, setPan]           = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const W = 760, H = 520;

  const simNodes = useMemo(() => {
    if (!subgraph?.nodes?.length) return [];
    const nodes = subgraph.nodes.map(n => ({ ...n }));
    const edges = (subgraph.edges || []).map(e => ({ ...e }));
    const cx = W / 2, cy = H / 2;
    const isHub = nodes.some(n => n.label === 'hub');
    if (isHub) {
      nodes.forEach(n => {
        if (n.label === 'hub')  { n.fx = cx - 60; n.fy = cy; }
        if (n.label === 'sink') { n.fx = cx + 230; n.fy = cy; }
      });
    }
    d3Force.forceSimulation(nodes)
      .force('link',      d3Force.forceLink(edges).id(d => d.id).distance(isHub ? 145 : 115))
      .force('charge',    d3Force.forceManyBody().strength(isHub ? -500 : -380))
      .force('center',    d3Force.forceCenter(cx, cy))
      .force('collision', d3Force.forceCollide().radius(38))
      .stop()
      .tick(320);
    return nodes;
  }, [subgraph]);

  const nodeMap  = useMemo(() => new Map(simNodes.map(n => [n.id, n])), [simNodes]);

  const edgeData = useMemo(() => {
    if (!subgraph?.edges) return [];
    return subgraph.edges.map((edge, idx) => {
      const src = nodeMap.get(edge.source);
      const tgt = nodeMap.get(edge.target);
      const srcRole = nodeRole(src || {});
      const tgtRole = nodeRole(tgt || {});
      let flowColor = COLOR.normal;
      if (srcRole === 'hub')   flowColor = COLOR.hub;
      else if (tgtRole === 'hub' || tgtRole === 'sink') flowColor = COLOR.sink;
      else if (srcRole === 'cycle' || tgtRole === 'cycle') flowColor = COLOR.cycle;
      else if (srcRole === 'mule') flowColor = COLOR.mule;
      return {
        ...edge, idx,
        sx: src?.x ?? 0, sy: src?.y ?? 0,
        tx: tgt?.x ?? 0, ty: tgt?.y ?? 0,
        flowColor,
        markerId: flowColor === COLOR.hub ? 'arr-red' : flowColor === COLOR.sink ? 'arr-green' : flowColor === COLOR.mule ? 'arr-indigo' : 'arr-amber',
      };
    });
  }, [subgraph, nodeMap]);

  const nodeStats = useMemo(() => {
    const s = {};
    simNodes.forEach(n => { s[n.id] = { inDeg: 0, outDeg: 0, inVol: 0, outVol: 0 }; });
    edgeData.forEach(e => {
      if (s[e.source]) { s[e.source].outDeg++; s[e.source].outVol += e.amount || 0; }
      if (s[e.target]) { s[e.target].inDeg++;  s[e.target].inVol  += e.amount || 0; }
    });
    return s;
  }, [simNodes, edgeData]);

  const graphStats = useMemo(() => {
    const totalVol = edgeData.reduce((acc, e) => acc + (e.amount || 0), 0);
    const maxRisk  = Math.max(0, ...simNodes.map(n => n.risk || 0));
    return { totalVol, maxRisk, edgeCount: edgeData.length, nodeCount: simNodes.length };
  }, [simNodes, edgeData]);

  const clickNode = useCallback(id => {
    setSelectedNode(id);
    onSelectUser?.(id);
  }, [onSelectUser]);

  const onWheel = e => {
    e.preventDefault();
    setZoom(z => Math.min(Math.max(z * (e.deltaY < 0 ? 1.12 : 0.9), 0.4), 4));
  };
  const onMouseDown = e => {
    if (e.target.tagName === 'svg' || e.target.tagName === 'rect') {
      setDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };
  const onMouseMove = e => {
    if (dragging) setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  };
  const onMouseUp = () => setDragging(false);
  const resetView = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  if (!subgraph?.nodes?.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted text-xs gap-2 bg-surface border border-border rounded-xl">
        <Activity className="w-8 h-8 opacity-40 text-muted" />
        No graph structure for this alert type.
      </div>
    );
  }

  const panelNodeId = selectedNode || hoveredNode;
  const panelNode   = simNodes.find(n => n.id === panelNodeId);
  const panelStats  = panelNode ? nodeStats[panelNode.id] : null;
  const panelRole   = panelNode ? nodeRole(panelNode)  : null;
  const panelColor  = panelNode ? roleColor(panelRole) : '#0f172a';

  return (
    <div className="relative w-full h-full flex bg-surface rounded-xl border border-border overflow-hidden select-none shadow-sm">

      {/* ── SVG Canvas ─────────────────────────────────────────────────────────── */}
      <div
        className="flex-1 flex flex-col relative bg-surface"
        onWheel={onWheel}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
      >
        {/* Top bar */}
        <div className="absolute top-3 left-3 right-3 z-20 flex items-center justify-between pointer-events-none">
          <div className="flex items-center gap-2 bg-surface/90 border border-border shadow-xs px-3 py-1.5 rounded-lg backdrop-blur-sm text-[11px]">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="font-mono text-gray-300 font-medium">
              {graphStats.nodeCount} nodes · {graphStats.edgeCount} edges · <span className="text-danger font-bold">{fmt(graphStats.totalVol)}</span> total flow
            </span>
          </div>
          <div className="flex gap-1 bg-surface/90 border border-border shadow-xs p-1 rounded-lg backdrop-blur-sm pointer-events-auto">
            <button onClick={() => setZoom(z => Math.min(z * 1.2, 4))} className="p-1.5 text-muted hover:text-white hover:bg-surface-hover rounded-md transition-colors" title="Zoom In">
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => setZoom(z => Math.max(z / 1.2, 0.4))} className="p-1.5 text-muted hover:text-white hover:bg-surface-hover rounded-md transition-colors" title="Zoom Out">
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button onClick={resetView} className="p-1.5 text-muted hover:text-white hover:bg-surface-hover rounded-md transition-colors" title="Reset View">
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Dot grid background */}
        <div className="absolute inset-0 pointer-events-none opacity-[0.25]"
          style={{ backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.06) 1.2px, transparent 1.2px)', backgroundSize: '20px 20px' }}
        />

        <svg
          width="100%" height="100%"
          viewBox={`0 0 ${W} ${H}`}
          className="w-full h-full relative z-10 cursor-grab active:cursor-grabbing"
        >
          <defs>
            <radialGradient id="hub-glow" cx="50%" cy="50%" r="50%">
              <stop offset="0%"   stopColor={COLOR.hub} stopOpacity="0.5" />
              <stop offset="100%" stopColor={COLOR.hub} stopOpacity="0" />
            </radialGradient>
            <radialGradient id="sel-glow" cx="50%" cy="50%" r="50%">
              <stop offset="0%"   stopColor={COLOR.sel} stopOpacity="0.35" />
              <stop offset="100%" stopColor={COLOR.sel} stopOpacity="0" />
            </radialGradient>
            {[
              { id: 'arr-red',    fill: COLOR.hub   },
              { id: 'arr-green',  fill: COLOR.sink  },
              { id: 'arr-amber',  fill: COLOR.cycle },
              { id: 'arr-indigo', fill: COLOR.mule  },
            ].map(({ id, fill }) => (
              <marker key={id} id={id} viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill={fill} />
              </marker>
            ))}
          </defs>

          <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>
            {/* Edges */}
            <g>
              {edgeData.map(edge => {
                const isHov = hoveredEdge === edge.idx;
                return (
                  <g key={`e-${edge.idx}`}
                    onMouseEnter={() => setHoveredEdge(edge.idx)}
                    onMouseLeave={() => setHoveredEdge(null)}
                  >
                    <line x1={edge.sx} y1={edge.sy} x2={edge.tx} y2={edge.ty} stroke="transparent" strokeWidth="14" style={{ cursor: 'pointer' }} />
                    {isHov && (
                      <line x1={edge.sx} y1={edge.sy} x2={edge.tx} y2={edge.ty}
                        stroke={edge.flowColor} strokeWidth="6" strokeOpacity="0.25" />
                    )}
                    <line
                      x1={edge.sx} y1={edge.sy} x2={edge.tx} y2={edge.ty}
                      stroke={edge.flowColor}
                      strokeWidth={isHov ? 2.5 : 1.5}
                      strokeOpacity={isHov ? 1 : 0.75}
                      strokeDasharray="7 5"
                      className="animate-flow-dash"
                      markerEnd={`url(#${edge.markerId})`}
                    />
                    {isHov && edge.amount > 0 && (
                      <g transform={`translate(${(edge.sx + edge.tx) / 2},${(edge.sy + edge.ty) / 2})`}>
                        <rect x="-28" y="-10" width="56" height="20" rx="5" fill="#0d0e12" stroke={edge.flowColor} strokeWidth="1.5" className="shadow-md" />
                        <text textAnchor="middle" dominantBaseline="middle" fontSize="9.5" fontWeight="700"
                          fill={edge.flowColor} fontFamily="JetBrains Mono, monospace">{fmt(edge.amount)}</text>
                      </g>
                    )}
                  </g>
                );
              })}
            </g>

            {/* Nodes */}
            <g>
              {simNodes.map(node => {
                const role = nodeRole(node);
                const col  = roleColor(role);
                const isSelected = selectedNode === node.id || selectedUserId === node.id;
                const isHovered  = hoveredNode === node.id;
                const isHub  = role === 'hub';
                const isSink = role === 'sink';
                let r = isHub ? 22 : isSink ? 17 : role === 'cycle' ? 14 : 12;
                if (isSelected || isHovered) r += 2;
                const ringColor = isSelected ? COLOR.sel : col;

                return (
                  <g key={node.id}
                    transform={`translate(${node.x},${node.y})`}
                    style={{ cursor: 'pointer' }}
                    onClick={() => clickNode(node.id)}
                    onMouseEnter={() => setHoveredNode(node.id)}
                    onMouseLeave={() => setHoveredNode(null)}
                  >
                    {isHub && (
                      <circle r="44" fill="url(#hub-glow)" opacity="0.6">
                        <animate attributeName="r"       values="36;52;36" dur="2.2s" repeatCount="indefinite" />
                        <animate attributeName="opacity" values="0.6;0.2;0.6" dur="2.2s" repeatCount="indefinite" />
                      </circle>
                    )}
                    {isSelected && !isHub && (
                      <circle r={r + 14} fill="url(#sel-glow)" />
                    )}
                    <circle r={r + 3} fill="none" stroke={ringColor} strokeWidth="1" strokeOpacity="0.3" />
                    <circle r={r} fill="#0d0e12" stroke={ringColor} strokeWidth={isSelected || isHovered ? 3 : 2} className="shadow-sm" />
                    <circle r={r - 4} fill={col} fillOpacity={isHub || isSink ? 0.35 : 0.2} />

                    {/* Glyph text */}
                    <text textAnchor="middle" dominantBaseline="middle"
                      fontSize={isHub ? 12 : isSink ? 11 : 9}
                      fill={col}
                      fontWeight="800"
                      style={{ pointerEvents: 'none' }}>
                      {isHub ? '⚡' : isSink ? '▼' : role === 'cycle' ? '◆' : '●'}
                    </text>

                    {/* Short ID label */}
                    <text y={r + 13} textAnchor="middle" fontSize="8.5"
                      fontFamily="JetBrains Mono, monospace"
                      fontWeight={isSelected ? '700' : '600'}
                      fill={isSelected ? '#f1f5f9' : '#86868b'}
                      style={{ pointerEvents: 'none' }}>
                      {node.id.substring(0, 7)}…
                    </text>

                    {/* Role chip */}
                    {(isHub || isSink) && (
                      <text y={-r - 7} textAnchor="middle" fontSize="7.5"
                        fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="800"
                        fill={col} letterSpacing="1" style={{ pointerEvents: 'none' }}>
                        {isHub ? 'MULE HUB' : 'SINK'}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          </g>
        </svg>

        {/* Bottom legend */}
        <div className="absolute bottom-3 left-3 z-20 flex items-center gap-3 bg-surface/90 border border-border shadow-xs px-3 py-1.5 rounded-lg backdrop-blur-sm text-[10px]">
          {[
            { col: COLOR.hub,   label: 'Hub Outflow' },
            { col: COLOR.sink,  label: 'Sink Inflow' },
            { col: COLOR.cycle, label: 'Cycle Edge'  },
            { col: COLOR.mule,  label: 'Spoke Edge'  },
          ].map(({ col, label }) => (
            <div key={label} className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: col }} />
              <span className="text-gray-300 font-semibold">{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Right sidebar ───────────────────────────────────────────────────────── */}
      <div className="w-52 border-l border-border bg-background flex flex-col overflow-y-auto shrink-0">
        <div className="px-3 py-3 border-b border-border flex items-center gap-2 bg-surface/50">
          <Network className="w-3.5 h-3.5 text-primary" />
          <span className="text-[10px] font-bold text-gray-300 uppercase tracking-wide">Graph Intelligence</span>
        </div>

        {/* Network stats */}
        <div className="px-3 py-3 border-b border-border space-y-2.5">
          <StatRow icon={<DollarSign className="w-3 h-3 text-danger" />}    label="Total Flow"  value={fmt(graphStats.totalVol)} valueColor="text-danger" />
          <StatRow icon={<TrendingUp className="w-3 h-3 text-muted" />}   label="Nodes"       value={graphStats.nodeCount} />
          <StatRow icon={<Activity   className="w-3 h-3 text-muted" />}   label="Edges"       value={graphStats.edgeCount} />
          <StatRow icon={<ShieldAlert className="w-3 h-3 text-warning" />} label="Max Risk"    value={graphStats.maxRisk.toFixed(3)} valueColor={graphStats.maxRisk > 0.75 ? 'text-danger' : 'text-warning'} />
        </div>

        {/* Node detail */}
        {panelNode ? (
          <div className="px-3 py-3 flex-1">
            <div className="flex items-center justify-between mb-2.5">
              <span className="text-[10px] font-bold text-gray-300 uppercase tracking-wide">Node Detail</span>
              <span className="text-[9.5px] px-1.5 py-0.5 rounded font-bold uppercase"
                style={{ background: `${panelColor}15`, color: panelColor, border: `1px solid ${panelColor}40` }}>
                {panelRole}
              </span>
            </div>
            <div className="mb-2">
              <span className="text-[9px] text-muted uppercase font-semibold block mb-0.5">Account ID</span>
              <span className="text-[9.5px] font-mono text-gray-100 font-semibold break-all leading-tight">{panelNode.id.substring(0, 18)}…</span>
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              <MiniCard label="KYC"     value={panelNode.kyc || '—'}           color={panelNode.kyc === 'verified' ? 'text-success' : 'text-warning'} />
              <MiniCard label="Risk"    value={panelNode.risk?.toFixed(3) ?? '—'} color={panelNode.risk > 0.75 ? 'text-danger' : 'text-warning'} />
              <MiniCard label="In Deg"  value={panelStats?.inDeg ?? 0} />
              <MiniCard label="Out Deg" value={panelStats?.outDeg ?? 0} />
              <MiniCard label="In Vol"  value={fmt(panelStats?.inVol)}  color="text-success" />
              <MiniCard label="Out Vol" value={fmt(panelStats?.outVol)} color="text-danger" />
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center flex-1 gap-2 text-muted px-4 text-center">
            <Info className="w-5 h-5 text-muted/50" />
            <span className="text-[10.5px] font-medium leading-snug">Click or hover a node to inspect details</span>
          </div>
        )}
      </div>
    </div>
  );
}

function StatRow({ icon, label, value, valueColor = 'text-gray-100' }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-1.5 text-muted">
        {icon}
        <span className="text-[10.5px] font-medium">{label}</span>
      </div>
      <span className={`text-[10.5px] font-bold font-mono ${valueColor}`}>{value}</span>
    </div>
  );
}

function MiniCard({ label, value, color = 'text-gray-100' }) {
  return (
    <div className="bg-surface border border-border rounded-lg p-2 text-center">
      <div className="text-[8.5px] text-muted uppercase font-bold mb-0.5">{label}</div>
      <div className={`text-[10.5px] font-bold font-mono ${color}`}>{value}</div>
    </div>
  );
}
