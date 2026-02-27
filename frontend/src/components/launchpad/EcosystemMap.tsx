// ─── QBC LAUNCHPAD — Ecosystem Map (D3 Force-Directed Graph) ─────────────────
"use client";

import React, { memo, useRef, useEffect, useState, useCallback } from "react";
import * as d3 from "d3";
import { useProjects, useEcosystemEdges } from "./hooks";
import { useLaunchpadStore } from "./store";
import { L, FONT, formatNumber, formatUsd, tierColor, tierLabel, panelStyle } from "./shared";
import type { ProjectTier, Project } from "./types";

/* ── Types ──────────────────────────────────────────────────────────────────── */

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  project: Project;
  radius: number;
}

interface GraphEdge extends d3.SimulationLinkDatum<GraphNode> {
  type: "vouch" | "shared_deployer" | "governance";
  weight: number;
}

/* ── Constants ──────────────────────────────────────────────────────────────── */

const TIERS: ProjectTier[] = ["protocol", "established", "growth", "early", "seed"];

const TIER_LABELS: Record<ProjectTier, string> = {
  protocol: "Protocol",
  established: "Established",
  growth: "Growth",
  early: "Early",
  seed: "Seed",
};

const EDGE_COLORS: Record<string, string> = {
  vouch: L.glowEmerald,
  shared_deployer: L.textMuted,
  governance: L.glowViolet,
};

const SVG_HEIGHT = 600;
const MIN_RADIUS = 8;
const MAX_RADIUS = 40;

/* ── CSS Injection ──────────────────────────────────────────────────────────── */

if (typeof document !== "undefined") {
  const id = "ecosystem-map-css";
  if (!document.getElementById(id)) {
    const style = document.createElement("style");
    style.id = id;
    style.textContent = `
      @keyframes ecoGlowPulse {
        0%, 100% { opacity: 0.25; r: attr(r); }
        50% { opacity: 0.6; }
      }
      .eco-glow-ring {
        animation: ecoGlowPulse 2.5s ease-in-out infinite;
      }
    `;
    document.head.appendChild(style);
  }
}

/* ── Helpers ─────────────────────────────────────────────────────────────────── */

function computeRadius(marketCap: number): number {
  if (marketCap <= 0) return MIN_RADIUS;
  const logVal = Math.log10(Math.max(1, marketCap));
  const minLog = 3;
  const maxLog = 10;
  const t = Math.max(0, Math.min(1, (logVal - minLog) / (maxLog - minLog)));
  return MIN_RADIUS + t * (MAX_RADIUS - MIN_RADIUS);
}

/* ── Component ──────────────────────────────────────────────────────────────── */

export const EcosystemMap = memo(function EcosystemMap() {
  const { data: projects } = useProjects();
  const { data: edges } = useEcosystemEdges();
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const simulationRef = useRef<d3.Simulation<GraphNode, GraphEdge> | null>(null);
  const [activeTier, setActiveTier] = useState<ProjectTier | "all">("all");
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    project: Project;
  } | null>(null);
  const [svgWidth, setSvgWidth] = useState(900);

  const handleNodeClick = useCallback((address: string) => {
    useLaunchpadStore.getState().setSelectedProject(address);
  }, []);

  /* ── Resize observer ──────────────────────────────────────────────────────── */
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setSvgWidth(entry.contentRect.width);
      }
    });
    observer.observe(el);
    setSvgWidth(el.clientWidth);
    return () => observer.disconnect();
  }, []);

  /* ── D3 simulation ────────────────────────────────────────────────────────── */
  useEffect(() => {
    if (!projects || !edges || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const width = svgWidth;
    const height = SVG_HEIGHT;

    // Build node map
    const nodeMap = new Map<string, GraphNode>();
    for (const p of projects) {
      nodeMap.set(p.address, {
        id: p.address,
        project: p,
        radius: computeRadius(p.marketCap),
      });
    }

    // Build edges (only between existing nodes)
    const graphEdges: GraphEdge[] = [];
    for (const e of edges) {
      if (nodeMap.has(e.source) && nodeMap.has(e.target)) {
        graphEdges.push({
          source: e.source,
          target: e.target,
          type: e.type as GraphEdge["type"],
          weight: e.weight,
        });
      }
    }

    const graphNodes = Array.from(nodeMap.values());

    // Force simulation
    const simulation = d3
      .forceSimulation<GraphNode>(graphNodes)
      .force(
        "link",
        d3
          .forceLink<GraphNode, GraphEdge>(graphEdges)
          .id((d) => d.id)
          .distance(100)
      )
      .force("charge", d3.forceManyBody().strength(-200))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force(
        "collide",
        d3.forceCollide<GraphNode>().radius((d) => d.radius + 5)
      );

    simulationRef.current = simulation;

    // Edge group
    const linkGroup = svg.append("g").attr("class", "edges");
    const links = linkGroup
      .selectAll<SVGLineElement, GraphEdge>("line")
      .data(graphEdges)
      .join("line")
      .attr("stroke", (d) => EDGE_COLORS[d.type] ?? L.textMuted)
      .attr("stroke-width", (d) => (d.type === "vouch" ? 2.5 : 1))
      .attr("stroke-dasharray", (d) =>
        d.type === "shared_deployer" ? "4 3" : "none"
      )
      .attr("stroke-opacity", (d) => {
        if (d.type === "vouch") {
          const maxWeight = 10000;
          return 0.3 + 0.7 * Math.min(1, d.weight / maxWeight);
        }
        return 0.3;
      });

    // Node group
    const nodeGroup = svg.append("g").attr("class", "nodes");

    const nodeContainers = nodeGroup
      .selectAll<SVGGElement, GraphNode>("g")
      .data(graphNodes)
      .join("g")
      .attr("cursor", "pointer")
      .call(
        d3
          .drag<SVGGElement, GraphNode>()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    // Protocol glow ring
    nodeContainers
      .filter((d) => d.project.tier === "protocol")
      .append("circle")
      .attr("r", (d) => d.radius + 6)
      .attr("fill", "none")
      .attr("stroke", L.tierProtocol)
      .attr("stroke-width", 2)
      .attr("class", "eco-glow-ring")
      .attr("opacity", 0.4);

    // Main circle
    nodeContainers
      .append("circle")
      .attr("r", (d) => d.radius)
      .attr("fill", (d) => tierColor(d.project.tier))
      .attr("fill-opacity", 0.85)
      .attr("stroke", (d) => tierColor(d.project.tier))
      .attr("stroke-width", 1.5)
      .attr("stroke-opacity", 0.5);

    // Labels (only for nodes with radius > 20)
    nodeContainers
      .filter((d) => d.radius > 20)
      .append("text")
      .text((d) => d.project.symbol)
      .attr("text-anchor", "middle")
      .attr("dy", (d) => d.radius + 14)
      .attr("fill", L.textSecondary)
      .attr("font-family", FONT.display)
      .attr("font-size", 9)
      .attr("letter-spacing", "0.05em")
      .attr("pointer-events", "none");

    // Hover and click
    nodeContainers.on("mouseenter", (event, d) => {
      const svgRect = svgRef.current?.getBoundingClientRect();
      if (!svgRect) return;
      setTooltip({
        x: event.clientX - svgRect.left,
        y: event.clientY - svgRect.top - 10,
        project: d.project,
      });
    });

    nodeContainers.on("mouseleave", () => {
      setTooltip(null);
    });

    nodeContainers.on("click", (_event, d) => {
      handleNodeClick(d.project.address);
    });

    // Tick
    simulation.on("tick", () => {
      links
        .attr("x1", (d) => ((d.source as GraphNode).x ?? 0))
        .attr("y1", (d) => ((d.source as GraphNode).y ?? 0))
        .attr("x2", (d) => ((d.target as GraphNode).x ?? 0))
        .attr("y2", (d) => ((d.target as GraphNode).y ?? 0));

      nodeContainers.attr("transform", (d) => {
        const x = Math.max(d.radius, Math.min(width - d.radius, d.x ?? 0));
        const y = Math.max(d.radius, Math.min(height - d.radius, d.y ?? 0));
        d.x = x;
        d.y = y;
        return `translate(${x},${y})`;
      });
    });

    return () => {
      simulation.stop();
      simulationRef.current = null;
    };
  }, [projects, edges, svgWidth, handleNodeClick]);

  /* ── Tier filter opacity update ───────────────────────────────────────────── */
  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);

    svg.selectAll<SVGGElement, GraphNode>("g.nodes > g").attr("opacity", (d) => {
      if (activeTier === "all") return 1;
      return d.project.tier === activeTier ? 1 : 0.15;
    });

    svg.selectAll<SVGLineElement, GraphEdge>("g.edges > line").attr("opacity", (d) => {
      if (activeTier === "all") return null as unknown as number;
      const src = (d.source as GraphNode).project?.tier;
      const tgt = (d.target as GraphNode).project?.tier;
      return src === activeTier || tgt === activeTier ? 0.6 : 0.05;
    });
  }, [activeTier]);

  /* ── Render ───────────────────────────────────────────────────────────────── */
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Tier filter bar */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <button
          onClick={() => setActiveTier("all")}
          style={{
            ...filterBtnStyle,
            background: activeTier === "all" ? L.bgHover : "transparent",
            color: activeTier === "all" ? L.textPrimary : L.textSecondary,
            borderColor: activeTier === "all" ? L.borderMedium : L.borderSubtle,
          }}
        >
          ALL
        </button>
        {TIERS.map((tier) => (
          <button
            key={tier}
            onClick={() => setActiveTier(activeTier === tier ? "all" : tier)}
            style={{
              ...filterBtnStyle,
              background: activeTier === tier ? tierColor(tier) + "18" : "transparent",
              color: activeTier === tier ? tierColor(tier) : L.textSecondary,
              borderColor: activeTier === tier ? tierColor(tier) + "60" : L.borderSubtle,
            }}
          >
            {TIER_LABELS[tier]}
          </button>
        ))}
      </div>

      {/* SVG container */}
      <div
        ref={containerRef}
        style={{
          position: "relative",
          width: "100%",
          height: SVG_HEIGHT,
          ...panelStyle,
          overflow: "hidden",
          background: L.bgBase,
        }}
      >
        <svg
          ref={svgRef}
          width={svgWidth}
          height={SVG_HEIGHT}
          style={{ display: "block" }}
        />

        {/* Tooltip */}
        {tooltip && (
          <div
            style={{
              position: "absolute",
              left: tooltip.x,
              top: tooltip.y,
              transform: "translate(-50%, -100%)",
              background: L.bgPanel,
              border: `1px solid ${L.borderMedium}`,
              borderRadius: 6,
              padding: "10px 14px",
              pointerEvents: "none",
              zIndex: 20,
              minWidth: 180,
              boxShadow: `0 4px 20px rgba(0,0,0,0.6)`,
            }}
          >
            <div
              style={{
                fontFamily: FONT.display,
                fontSize: 12,
                color: tierColor(tooltip.project.tier),
                marginBottom: 4,
                letterSpacing: "0.04em",
              }}
            >
              {tooltip.project.name}
            </div>
            <div style={{ display: "flex", gap: 8, marginBottom: 4 }}>
              <span
                style={{
                  fontFamily: FONT.display,
                  fontSize: 9,
                  color: tierColor(tooltip.project.tier),
                  border: `1px solid ${tierColor(tooltip.project.tier)}40`,
                  borderRadius: 3,
                  padding: "1px 5px",
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                }}
              >
                {tierLabel(tooltip.project.tier)}
              </span>
            </div>
            <div style={tooltipRowStyle}>
              <span style={{ color: L.textSecondary }}>QPCS</span>
              <span style={{ color: L.glowCyan, fontFamily: FONT.mono }}>
                {tooltip.project.qpcs.toFixed(1)}
              </span>
            </div>
            <div style={tooltipRowStyle}>
              <span style={{ color: L.textSecondary }}>Market Cap</span>
              <span style={{ color: L.textPrimary, fontFamily: FONT.mono }}>
                {formatUsd(tooltip.project.marketCap)}
              </span>
            </div>
            <div style={tooltipRowStyle}>
              <span style={{ color: L.textSecondary }}>Holders</span>
              <span style={{ color: L.textPrimary, fontFamily: FONT.mono }}>
                {formatNumber(tooltip.project.holderCount)}
              </span>
            </div>
          </div>
        )}

        {/* Legend */}
        <div
          style={{
            position: "absolute",
            bottom: 12,
            left: 12,
            display: "flex",
            flexDirection: "column",
            gap: 6,
            background: L.bgPanel + "e0",
            border: `1px solid ${L.borderSubtle}`,
            borderRadius: 6,
            padding: "10px 12px",
            zIndex: 10,
          }}
        >
          <div
            style={{
              fontFamily: FONT.display,
              fontSize: 9,
              color: L.textSecondary,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              marginBottom: 2,
            }}
          >
            TIERS
          </div>
          {TIERS.map((tier) => (
            <div
              key={tier}
              style={{ display: "flex", alignItems: "center", gap: 6 }}
            >
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: tierColor(tier),
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontFamily: FONT.body,
                  fontSize: 10,
                  color: L.textSecondary,
                }}
              >
                {TIER_LABELS[tier]}
              </span>
            </div>
          ))}
          <div
            style={{
              fontFamily: FONT.display,
              fontSize: 9,
              color: L.textSecondary,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              marginTop: 6,
              marginBottom: 2,
            }}
          >
            EDGES
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div
              style={{
                width: 18,
                height: 0,
                borderTop: `2.5px solid ${L.glowEmerald}`,
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontFamily: FONT.body,
                fontSize: 10,
                color: L.textSecondary,
              }}
            >
              Vouch
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div
              style={{
                width: 18,
                height: 0,
                borderTop: `1px dashed ${L.textMuted}`,
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontFamily: FONT.body,
                fontSize: 10,
                color: L.textSecondary,
              }}
            >
              Shared Deployer
            </span>
          </div>
        </div>
      </div>
    </div>
  );
});

/* ── Inline Style Helpers ─────────────────────────────────────────────────── */

const filterBtnStyle: React.CSSProperties = {
  fontFamily: FONT.display,
  fontSize: 10,
  letterSpacing: "0.06em",
  padding: "5px 14px",
  borderRadius: 4,
  border: `1px solid ${L.borderSubtle}`,
  cursor: "pointer",
  textTransform: "uppercase",
  transition: "all 0.15s ease",
};

const tooltipRowStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: 16,
  fontFamily: FONT.body,
  fontSize: 11,
  lineHeight: "18px",
};
