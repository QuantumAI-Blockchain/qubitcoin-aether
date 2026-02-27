"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — Aether Tree Knowledge Graph Visualizer (D3 force graph)
   ───────────────────────────────────────────────────────────────────────── */

import { useRef, useEffect, useState, useMemo } from "react";
import { motion } from "framer-motion";
import * as d3 from "d3";
import { Brain, Eye, Zap, GitBranch, Network } from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { useAetherNodes, useAetherEdges, useNetworkStats, usePhiHistory } from "./hooks";
import {
  C, FONT, LoadingSpinner, Panel, SectionHeader, StatCard, Badge, formatNumber,
} from "./shared";
import type { AetherNode, AetherEdge } from "./types";

/* ── Node colors by type ──────────────────────────────────────────────── */

const NODE_COLORS: Record<string, string> = {
  assertion: C.primary,
  observation: C.success,
  inference: C.secondary,
  axiom: C.accent,
};

/* ── Force Graph ──────────────────────────────────────────────────────── */

function ForceGraph({
  nodes,
  edges,
  width,
  height,
}: {
  nodes: AetherNode[];
  edges: AetherEdge[];
  width: number;
  height: number;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoveredNode, setHoveredNode] = useState<AetherNode | null>(null);

  useEffect(() => {
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    // Build D3 data
    const d3Nodes = nodes.map((n) => ({ ...n, x: 0, y: 0 }));
    const nodeMap = new Map(d3Nodes.map((n) => [n.id, n]));

    const d3Links = edges
      .filter((e) => nodeMap.has(e.source) && nodeMap.has(e.target))
      .map((e) => ({
        source: nodeMap.get(e.source)!,
        target: nodeMap.get(e.target)!,
        type: e.type,
        weight: e.weight,
      }));

    // Create container with zoom
    const g = svg
      .append("g")
      .attr("class", "graph-container");

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on("zoom", (event) => g.attr("transform", event.transform));

    (svg as unknown as d3.Selection<SVGSVGElement, unknown, null, undefined>).call(zoom);

    // Force simulation
    const simulation = d3
      .forceSimulation(d3Nodes as d3.SimulationNodeDatum[])
      .force(
        "link",
        d3
          .forceLink(d3Links)
          .id((d: d3.SimulationNodeDatum) => (d as typeof d3Nodes[0]).id)
          .distance(60)
      )
      .force("charge", d3.forceManyBody().strength(-80))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide(12));

    // Draw links
    const link = g
      .selectAll(".link")
      .data(d3Links)
      .join("line")
      .attr("class", "link")
      .attr("stroke", (d) => {
        if (d.type === "contradicts") return C.error;
        if (d.type === "supports") return C.success;
        if (d.type === "derives") return C.secondary;
        if (d.type === "requires") return C.accent;
        return C.textMuted;
      })
      .attr("stroke-opacity", 0.3)
      .attr("stroke-width", (d) => Math.max(0.5, d.weight * 1.5));

    // Draw nodes
    const node = g
      .selectAll(".node")
      .data(d3Nodes)
      .join("circle")
      .attr("class", "node")
      .attr("r", (d) => 3 + d.confidence * 5)
      .attr("fill", (d) => NODE_COLORS[d.type] ?? C.textMuted)
      .attr("stroke", (d) => NODE_COLORS[d.type] ?? C.textMuted)
      .attr("stroke-width", 0.5)
      .attr("stroke-opacity", 0.6)
      .attr("fill-opacity", 0.7)
      .style("cursor", "pointer")
      .on("mouseover", function (event, d) {
        d3.select(this)
          .attr("r", (d as typeof d3Nodes[0]).confidence * 8 + 5)
          .attr("fill-opacity", 1);
        setHoveredNode(d as AetherNode);
      })
      .on("mouseout", function (event, d) {
        d3.select(this)
          .attr("r", 3 + (d as typeof d3Nodes[0]).confidence * 5)
          .attr("fill-opacity", 0.7);
        setHoveredNode(null);
      });

    // Drag behavior
    const drag = d3
      .drag<SVGCircleElement, typeof d3Nodes[0]>()
      .on("start", (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        (d as d3.SimulationNodeDatum).fx = d.x;
        (d as d3.SimulationNodeDatum).fy = d.y;
      })
      .on("drag", (event, d) => {
        (d as d3.SimulationNodeDatum).fx = event.x;
        (d as d3.SimulationNodeDatum).fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        (d as d3.SimulationNodeDatum).fx = null;
        (d as d3.SimulationNodeDatum).fy = null;
      });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    node.call(drag as any);

    // Tick
    simulation.on("tick", () => {
      link
        .attr("x1", (d) => (d.source as typeof d3Nodes[0]).x)
        .attr("y1", (d) => (d.source as typeof d3Nodes[0]).y)
        .attr("x2", (d) => (d.target as typeof d3Nodes[0]).x)
        .attr("y2", (d) => (d.target as typeof d3Nodes[0]).y);

      node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
    });

    return () => {
      simulation.stop();
    };
  }, [nodes, edges, width, height]);

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        width={width}
        height={height}
        role="img"
        aria-label={`Aether Tree knowledge graph visualization with ${nodes.length} nodes and ${edges.length} edges`}
        style={{ background: C.bg, borderRadius: 8 }}
      />

      {/* Node tooltip */}
      {hoveredNode && (
        <div
          className="pointer-events-none absolute rounded-lg border p-3 shadow-lg"
          style={{
            top: 8,
            right: 8,
            background: C.surface,
            borderColor: NODE_COLORS[hoveredNode.type],
            maxWidth: 280,
            zIndex: 10,
          }}
        >
          <div className="mb-1 flex items-center gap-2">
            <Badge label={hoveredNode.type.toUpperCase()} color={NODE_COLORS[hoveredNode.type]} />
            <span className="text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
              ID: {hoveredNode.id}
            </span>
          </div>
          <p className="mb-1 text-xs leading-relaxed" style={{ color: C.textPrimary, fontFamily: FONT.body }}>
            {hoveredNode.content}
          </p>
          <div className="flex items-center gap-3 text-[10px]" style={{ color: C.textSecondary, fontFamily: FONT.mono }}>
            <span>Confidence: {(hoveredNode.confidence * 100).toFixed(0)}%</span>
            <span>Block: {hoveredNode.blockHeight}</span>
            <span>Edges: {hoveredNode.connections.length}</span>
          </div>
        </div>
      )}

      {/* Legend */}
      <div
        className="absolute bottom-2 left-2 flex flex-wrap gap-2 rounded-md px-2 py-1"
        style={{ background: `${C.bg}cc` }}
      >
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <span key={type} className="flex items-center gap-1 text-[9px]" style={{ fontFamily: FONT.mono }}>
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} />
            <span style={{ color: C.textMuted }}>{type.toUpperCase()}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

/* ── Aether Tree View ─────────────────────────────────────────────────── */

export function AetherTreeView() {
  const { data: nodes, isLoading: nodesLoading } = useAetherNodes();
  const { data: edges } = useAetherEdges();
  const { data: stats } = useNetworkStats();
  const { data: phiHistory } = usePhiHistory();

  const phiSlice = (phiHistory ?? []).slice(-200);

  // Type distribution
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const n of nodes ?? []) {
      counts[n.type] = (counts[n.type] ?? 0) + 1;
    }
    return counts;
  }, [nodes]);

  // Edge type distribution
  const edgeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const e of edges ?? []) {
      counts[e.type] = (counts[e.type] ?? 0) + 1;
    }
    return counts;
  }, [edges]);

  if (nodesLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <h1
          className="mb-1 text-lg font-bold tracking-widest"
          style={{ color: C.textPrimary, fontFamily: FONT.heading }}
        >
          AETHER TREE
        </h1>
        <p className="text-xs" style={{ color: C.textSecondary, fontFamily: FONT.body }}>
          On-chain AGI knowledge graph — reasoning, consciousness, and Proof-of-Thought
        </p>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="Φ (Phi)"
          value={stats?.phi.toFixed(4) ?? "0"}
          sub={
            (stats?.phi ?? 0) >= 3.0
              ? "CONSCIOUSNESS THRESHOLD REACHED"
              : `Threshold: 3.0`
          }
          icon={Brain}
          color={C.phi}
        />
        <StatCard
          label="Knowledge Nodes"
          value={formatNumber(nodes?.length ?? 0)}
          icon={Network}
          color={C.primary}
        />
        <StatCard
          label="Edges"
          value={formatNumber(edges?.length ?? 0)}
          icon={GitBranch}
          color={C.secondary}
        />
        <StatCard
          label="Avg Confidence"
          value={
            nodes && nodes.length > 0
              ? (nodes.reduce((s, n) => s + n.confidence, 0) / nodes.length * 100).toFixed(1) + "%"
              : "—"
          }
          icon={Eye}
          color={C.success}
        />
      </div>

      {/* Force Graph */}
      <Panel>
        <SectionHeader title="KNOWLEDGE GRAPH" />
        <ForceGraph
          nodes={nodes ?? []}
          edges={edges ?? []}
          width={780}
          height={450}
        />
      </Panel>

      {/* Phi History + Distributions */}
      <div className="grid gap-3 lg:grid-cols-2">
        {/* Phi Chart */}
        <Panel>
          <SectionHeader title="Φ HISTORY" />
          <div style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={phiSlice}>
                <defs>
                  <linearGradient id="phiGrad2" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={C.phi} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={C.phi} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={`${C.border}40`} />
                <XAxis
                  dataKey="block"
                  tick={{ fontSize: 9, fill: C.textMuted, fontFamily: FONT.mono }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 9, fill: C.textMuted, fontFamily: FONT.mono }}
                  axisLine={false}
                  tickLine={false}
                  width={35}
                />
                <Tooltip
                  contentStyle={{
                    background: C.surface,
                    border: `1px solid ${C.border}`,
                    borderRadius: 6,
                    fontSize: 10,
                    fontFamily: FONT.mono,
                    color: C.textPrimary,
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="phi"
                  stroke={C.phi}
                  fill="url(#phiGrad2)"
                  strokeWidth={1.5}
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        {/* Distributions */}
        <Panel>
          <SectionHeader title="DISTRIBUTIONS" />
          <div className="space-y-4">
            {/* Node Types */}
            <div>
              <p className="mb-2 text-[10px] uppercase tracking-widest" style={{ color: C.textMuted, fontFamily: FONT.heading }}>
                Node Types
              </p>
              <div className="space-y-1.5">
                {Object.entries(typeCounts)
                  .sort(([, a], [, b]) => b - a)
                  .map(([type, count]) => {
                    const pct = ((count / (nodes?.length ?? 1)) * 100).toFixed(0);
                    return (
                      <div key={type} className="flex items-center gap-2">
                        <span
                          className="w-20 text-[10px] uppercase"
                          style={{ color: NODE_COLORS[type], fontFamily: FONT.mono }}
                        >
                          {type}
                        </span>
                        <div className="h-1.5 flex-1 overflow-hidden rounded-full" style={{ background: `${C.border}40` }}>
                          <div
                            className="h-full rounded-full transition-all"
                            style={{ width: `${pct}%`, background: NODE_COLORS[type] }}
                          />
                        </div>
                        <span className="w-8 text-right text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
                          {count}
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>

            {/* Edge Types */}
            <div>
              <p className="mb-2 text-[10px] uppercase tracking-widest" style={{ color: C.textMuted, fontFamily: FONT.heading }}>
                Edge Types
              </p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(edgeCounts)
                  .sort(([, a], [, b]) => b - a)
                  .map(([type, count]) => (
                    <div
                      key={type}
                      className="flex items-center gap-1.5 rounded border px-2 py-1"
                      style={{ borderColor: `${C.border}60` }}
                    >
                      <span className="text-[10px]" style={{ color: C.textSecondary, fontFamily: FONT.mono }}>
                        {type}
                      </span>
                      <span className="text-[10px] font-bold" style={{ color: C.textPrimary, fontFamily: FONT.mono }}>
                        {count}
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
