"use client";

// ─── QBC EXCHANGE — D3 Cumulative Depth Chart ────────────────────────────────
// Bid/ask area visualization with hover tooltip, mid-price marker, auto-resize.

import React, { useRef, useEffect, useMemo, memo, useState } from "react";
import {
  select,
  scaleLinear,
  area,
  axisBottom,
  axisLeft,
  bisector,
  pointer,
} from "d3";
import { useOrderBook } from "./hooks";
import { useExchangeStore } from "./store";
import {
  X,
  FONT,
  formatPrice,
  formatSize,
  panelStyle,
  panelHeaderStyle,
} from "./shared";
import { getMarketConfig } from "./config";

// ─── TYPES ───────────────────────────────────────────────────────────────────

interface CumulativePoint {
  price: number;
  cumSize: number;
  cumValue: number;
}

// ─── MARGINS ─────────────────────────────────────────────────────────────────

const MARGIN = { top: 10, right: 40, bottom: 30, left: 60 };

// ─── D3 RENDER FUNCTION (extracted for clarity) ─────────────────────────────

function renderChart(
  svg: SVGSVGElement,
  container: HTMLDivElement,
  tooltip: HTMLDivElement | null,
  bidPoints: CumulativePoint[],
  askPoints: CumulativePoint[],
  midPrice: number,
  baseAsset: string,
): void {
  const rect = container.getBoundingClientRect();
  const width = rect.width;
  const height = rect.height;
  if (width <= 0 || height <= 0) return;

  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = height - MARGIN.top - MARGIN.bottom;
  if (innerW <= 0 || innerH <= 0) return;

  // Clear previous render
  const root = select(svg);
  root.selectAll("*").remove();

  root
    .attr("width", width)
    .attr("height", height)
    .style("background", X.bgBase);

  const g = root
    .append("g")
    .attr("transform", `translate(${MARGIN.left},${MARGIN.top})`);

  // ── Price domain ──────────────────────────────────────────────────────
  const allPrices = [
    ...bidPoints.map((p) => p.price),
    ...askPoints.map((p) => p.price),
  ];
  const minPrice = Math.min(...allPrices);
  const maxPrice = Math.max(...allPrices);
  const pricePad = (maxPrice - minPrice) * 0.02;

  const xScale = scaleLinear()
    .domain([minPrice - pricePad, maxPrice + pricePad])
    .range([0, innerW]);

  // ── Size domain ───────────────────────────────────────────────────────
  const maxCumSize = Math.max(
    bidPoints.length > 0 ? bidPoints[bidPoints.length - 1].cumSize : 0,
    askPoints.length > 0 ? askPoints[askPoints.length - 1].cumSize : 0,
  );

  const yScale = scaleLinear()
    .domain([0, maxCumSize * 1.08])
    .range([innerH, 0]);

  // ── Step builders for staircase shape ─────────────────────────────────

  function buildStepBid(pts: CumulativePoint[]): [number, number][] {
    const steps: [number, number][] = [];
    if (pts.length === 0) return steps;
    // Start at mid-price with 0 cumulative
    steps.push([midPrice, 0]);
    for (let i = 0; i < pts.length; i++) {
      steps.push([pts[i].price, i === 0 ? 0 : pts[i - 1].cumSize]);
      steps.push([pts[i].price, pts[i].cumSize]);
    }
    return steps;
  }

  function buildStepAsk(pts: CumulativePoint[]): [number, number][] {
    const steps: [number, number][] = [];
    if (pts.length === 0) return steps;
    steps.push([midPrice, 0]);
    for (let i = 0; i < pts.length; i++) {
      steps.push([pts[i].price, i === 0 ? 0 : pts[i - 1].cumSize]);
      steps.push([pts[i].price, pts[i].cumSize]);
    }
    return steps;
  }

  const bidSteps = buildStepBid(bidPoints);
  const askSteps = buildStepAsk(askPoints);

  const areaGen = area<[number, number]>()
    .x((d) => xScale(d[0]))
    .y0(innerH)
    .y1((d) => yScale(d[1]));

  // ── Draw bid area ─────────────────────────────────────────────────────
  if (bidSteps.length > 0) {
    g.append("path")
      .datum(bidSteps)
      .attr("d", areaGen)
      .attr("fill", X.bid + "33")
      .attr("stroke", X.bid + "cc")
      .attr("stroke-width", 1.5);
  }

  // ── Draw ask area ─────────────────────────────────────────────────────
  if (askSteps.length > 0) {
    g.append("path")
      .datum(askSteps)
      .attr("d", areaGen)
      .attr("fill", X.ask + "33")
      .attr("stroke", X.ask + "cc")
      .attr("stroke-width", 1.5);
  }

  // ── Mid-price dashed line ─────────────────────────────────────────────
  if (midPrice > 0) {
    const mx = xScale(midPrice);
    g.append("line")
      .attr("x1", mx)
      .attr("x2", mx)
      .attr("y1", 0)
      .attr("y2", innerH)
      .attr("stroke", X.glowCyan)
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "4,3")
      .attr("opacity", 0.7);

    g.append("text")
      .attr("x", mx)
      .attr("y", -2)
      .attr("text-anchor", "middle")
      .attr("fill", X.glowCyan)
      .attr("font-family", FONT.mono)
      .attr("font-size", 9)
      .text(formatPrice(midPrice));
  }

  // ── X-Axis ────────────────────────────────────────────────────────────
  const xAxis = axisBottom(xScale)
    .ticks(Math.max(3, Math.floor(innerW / 80)))
    .tickSize(-innerH)
    .tickFormat((d) => formatPrice(d as number));

  const xAxisG = g
    .append("g")
    .attr("transform", `translate(0,${innerH})`)
    .call(xAxis);

  xAxisG
    .selectAll("line")
    .attr("stroke", X.borderSubtle)
    .attr("stroke-dasharray", "2,2");

  xAxisG.select(".domain").attr("stroke", X.borderSubtle);

  xAxisG
    .selectAll("text")
    .attr("fill", X.textSecondary)
    .attr("font-family", FONT.mono)
    .attr("font-size", 10);

  // ── Y-Axis ────────────────────────────────────────────────────────────
  const yAxis = axisLeft(yScale)
    .ticks(Math.max(3, Math.floor(innerH / 40)))
    .tickSize(-innerW)
    .tickFormat((d) => formatSize(d as number));

  const yAxisG = g.append("g").call(yAxis);

  yAxisG
    .selectAll("line")
    .attr("stroke", X.borderSubtle)
    .attr("stroke-dasharray", "2,2");

  yAxisG.select(".domain").attr("stroke", X.borderSubtle);

  yAxisG
    .selectAll("text")
    .attr("fill", X.textSecondary)
    .attr("font-family", FONT.mono)
    .attr("font-size", 10);

  // ── Hover interaction layer ───────────────────────────────────────────
  // Build sorted array of all points for bisector lookup
  const allPoints: (CumulativePoint & { side: "bid" | "ask" })[] = [
    ...[...bidPoints].reverse().map((p) => ({ ...p, side: "bid" as const })),
    ...askPoints.map((p) => ({ ...p, side: "ask" as const })),
  ];
  allPoints.sort((a, b) => a.price - b.price);

  const priceBisector = bisector<(typeof allPoints)[0], number>(
    (d) => d.price,
  ).left;

  // Invisible rect for mouse capture
  const overlay = g
    .append("rect")
    .attr("width", innerW)
    .attr("height", innerH)
    .attr("fill", "transparent")
    .style("cursor", "crosshair");

  // Crosshair lines
  const crosshairV = g
    .append("line")
    .attr("y1", 0)
    .attr("y2", innerH)
    .attr("stroke", X.textSecondary)
    .attr("stroke-width", 0.5)
    .attr("stroke-dasharray", "3,3")
    .attr("opacity", 0)
    .attr("pointer-events", "none");

  const crosshairH = g
    .append("line")
    .attr("x1", 0)
    .attr("x2", innerW)
    .attr("stroke", X.textSecondary)
    .attr("stroke-width", 0.5)
    .attr("stroke-dasharray", "3,3")
    .attr("opacity", 0)
    .attr("pointer-events", "none");

  const hoverDot = g
    .append("circle")
    .attr("r", 4)
    .attr("stroke", X.bgBase)
    .attr("stroke-width", 1.5)
    .attr("opacity", 0)
    .attr("pointer-events", "none");

  overlay.on("mousemove", function (event) {
    if (!tooltip || allPoints.length === 0) return;

    const [mx] = pointer(event, this);
    const hoverPrice = xScale.invert(mx);

    // Find nearest data point via bisection
    let idx = priceBisector(allPoints, hoverPrice);
    if (idx >= allPoints.length) idx = allPoints.length - 1;
    if (idx > 0) {
      const d0 = allPoints[idx - 1];
      const d1 = allPoints[idx];
      if (Math.abs(hoverPrice - d0.price) < Math.abs(hoverPrice - d1.price)) {
        idx = idx - 1;
      }
    }
    const pt = allPoints[idx];
    if (!pt) return;

    const px = xScale(pt.price);
    const py = yScale(pt.cumSize);

    // Update crosshair + dot
    crosshairV.attr("x1", px).attr("x2", px).attr("opacity", 0.5);
    crosshairH.attr("y1", py).attr("y2", py).attr("opacity", 0.5);
    hoverDot
      .attr("cx", px)
      .attr("cy", py)
      .attr("fill", pt.side === "bid" ? X.bid : X.ask)
      .attr("opacity", 1);

    // Populate tooltip
    const sideLabel = pt.side === "bid" ? "BID" : "ASK";
    const sideColor = pt.side === "bid" ? X.bid : X.ask;

    tooltip.innerHTML =
      `<div style="font-family:${FONT.display};font-size:9px;letter-spacing:0.08em;color:${sideColor};margin-bottom:4px">${sideLabel}</div>` +
      `<div style="display:flex;justify-content:space-between;gap:16px">` +
      `<span style="color:${X.textSecondary}">Price</span>` +
      `<span style="color:${X.textPrimary}">${formatPrice(pt.price)}</span></div>` +
      `<div style="display:flex;justify-content:space-between;gap:16px">` +
      `<span style="color:${X.textSecondary}">Depth</span>` +
      `<span style="color:${X.textPrimary}">${formatSize(pt.cumSize)} ${baseAsset}</span></div>` +
      `<div style="display:flex;justify-content:space-between;gap:16px">` +
      `<span style="color:${X.textSecondary}">Value</span>` +
      `<span style="color:${X.textPrimary}">${formatSize(pt.cumValue)} QUSD</span></div>`;

    tooltip.style.opacity = "1";

    // Position tooltip, flipping if near edges
    const containerWidth = container.getBoundingClientRect().width;
    const containerHeight = container.getBoundingClientRect().height;
    const tipW = 170;
    const tipH = 80;
    let tipX = px + MARGIN.left + 12;
    let tipY = py + MARGIN.top - tipH / 2;

    if (tipX + tipW > containerWidth - 4) {
      tipX = px + MARGIN.left - tipW - 12;
    }
    if (tipY < 4) tipY = 4;
    if (tipY + tipH > containerHeight - 4) tipY = containerHeight - tipH - 4;

    tooltip.style.left = `${tipX}px`;
    tooltip.style.top = `${tipY}px`;
  });

  overlay.on("mouseleave", function () {
    if (tooltip) tooltip.style.opacity = "0";
    crosshairV.attr("opacity", 0);
    crosshairH.attr("opacity", 0);
    hoverDot.attr("opacity", 0);
  });
}

// ─── COMPONENT ───────────────────────────────────────────────────────────────

const DepthChart = memo(function DepthChart() {
  const activeMarket = useExchangeStore((s) => s.activeMarket);
  const { data: book } = useOrderBook(activeMarket);

  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  // Track container dimensions to trigger re-render on resize
  const [dims, setDims] = useState({ w: 0, h: 0 });

  // Determine base asset label for tooltip context
  const baseAsset = useMemo(() => {
    const cfg = getMarketConfig(activeMarket);
    return cfg?.baseAsset ?? activeMarket.split("_")[0];
  }, [activeMarket]);

  // ── Build cumulative bid/ask arrays from order book data ──────────────
  const { bidPoints, askPoints, midPrice } = useMemo(() => {
    if (!book || book.bids.length === 0 || book.asks.length === 0) {
      return {
        bidPoints: [] as CumulativePoint[],
        askPoints: [] as CumulativePoint[],
        midPrice: 0,
      };
    }

    const mid = book.midPrice;

    // Bids: sorted descending by price (highest bid first).
    // Cumulative from highest bid outward to lowest bid.
    const sortedBids = [...book.bids].sort((a, b) => b.price - a.price);
    let cumBid = 0;
    const bids: CumulativePoint[] = [];
    for (const level of sortedBids) {
      cumBid += level.size;
      bids.push({
        price: level.price,
        cumSize: cumBid,
        cumValue: cumBid * level.price,
      });
    }

    // Asks: sorted ascending by price (lowest ask first).
    // Cumulative from lowest ask outward to highest ask.
    const sortedAsks = [...book.asks].sort((a, b) => a.price - b.price);
    let cumAsk = 0;
    const asks: CumulativePoint[] = [];
    for (const level of sortedAsks) {
      cumAsk += level.size;
      asks.push({
        price: level.price,
        cumSize: cumAsk,
        cumValue: cumAsk * level.price,
      });
    }

    return { bidPoints: bids, askPoints: asks, midPrice: mid };
  }, [book]);

  // ── ResizeObserver: track container dimensions ────────────────────────
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let rafId: number;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(() => {
          setDims((prev) => {
            const w = Math.round(width);
            const h = Math.round(height);
            if (prev.w === w && prev.h === h) return prev;
            return { w, h };
          });
        });
      }
    });

    ro.observe(container);
    return () => {
      ro.disconnect();
      cancelAnimationFrame(rafId);
    };
  }, []);

  // ── D3 render effect: re-runs on data change OR resize ────────────────
  useEffect(() => {
    const svg = svgRef.current;
    const container = containerRef.current;
    if (!svg || !container) return;
    if (bidPoints.length === 0 && askPoints.length === 0) return;

    renderChart(
      svg,
      container,
      tooltipRef.current,
      bidPoints,
      askPoints,
      midPrice,
      baseAsset,
    );
  }, [bidPoints, askPoints, midPrice, baseAsset, dims.w, dims.h]);

  // ── JSX ───────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        ...panelStyle,
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div style={panelHeaderStyle}>DEPTH</div>

      {/* Chart container */}
      <div
        ref={containerRef}
        style={{
          position: "relative",
          flexGrow: 1,
          minHeight: 200,
          overflow: "hidden",
        }}
      >
        {bidPoints.length === 0 && askPoints.length === 0 ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              fontFamily: FONT.mono,
              fontSize: 12,
              color: X.textSecondary,
            }}
          >
            Waiting for order book data...
          </div>
        ) : (
          <svg
            ref={svgRef}
            style={{ display: "block", width: "100%", height: "100%" }}
          />
        )}

        {/* Tooltip (positioned absolutely within container) */}
        <div
          ref={tooltipRef}
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            pointerEvents: "none",
            background: X.bgElevated,
            border: `1px solid ${X.borderSubtle}`,
            borderRadius: 6,
            padding: "8px 12px",
            fontFamily: FONT.mono,
            fontSize: 11,
            lineHeight: "18px",
            color: X.textPrimary,
            opacity: 0,
            transition: "opacity 0.1s",
            zIndex: 10,
            minWidth: 150,
            whiteSpace: "nowrap",
            boxShadow: `0 4px 16px ${X.bgBase}cc`,
          }}
        />
      </div>
    </div>
  );
});

export default DepthChart;
