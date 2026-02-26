// ─── QBC EXCHANGE — Liquidation Heatmap ─────────────────────────────────────
// D3-rendered horizontal bar heatmap showing liquidation density around current
// price. Longs below, shorts above. Amber-to-crimson gradient. Auto-resize.
"use client";

import React, { memo, useRef, useEffect, useMemo, useState, useCallback } from "react";
import { select, scaleLinear, scaleSqrt } from "d3";
import { useLiquidationLevels, useMarket } from "./hooks";
import { useExchangeStore } from "./store";
import {
  X,
  FONT,
  formatPrice,
  formatSize,
  panelStyle,
  panelHeaderStyle,
} from "./shared";
import type { LiquidationLevel } from "./types";

// ─── CONSTANTS ─────────────────────────────────────────────────────────────

const MARGIN = { top: 10, right: 20, bottom: 30, left: 70 };

// Gradient stops (amber -> crimson)
const GRADIENT_LOW = X.glowAmber;
const GRADIENT_HIGH = X.glowCrimson;
const CURRENT_PRICE_COLOR = X.glowCyan;
const BAR_HEIGHT_FRACTION = 0.7; // fraction of band height used by bar

// ─── RENDER FUNCTION ───────────────────────────────────────────────────────

function renderHeatmap(
  svg: SVGSVGElement,
  container: HTMLDivElement,
  tooltip: HTMLDivElement | null,
  levels: LiquidationLevel[],
  currentPrice: number,
): void {
  const rect = container.getBoundingClientRect();
  const width = rect.width;
  const height = rect.height;
  if (width <= 0 || height <= 0) return;

  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = height - MARGIN.top - MARGIN.bottom;
  if (innerW <= 0 || innerH <= 0) return;

  // Clear
  const root = select(svg);
  root.selectAll("*").remove();
  root.attr("width", width).attr("height", height).style("background", X.bgBase);

  // ── Defs for gradients ──────────────────────────────────────────────────
  const defs = root.append("defs");

  // Long liquidation gradient (below price)
  const longGrad = defs
    .append("linearGradient")
    .attr("id", "liq-grad-long")
    .attr("x1", "0%")
    .attr("y1", "0%")
    .attr("x2", "100%")
    .attr("y2", "0%");
  longGrad.append("stop").attr("offset", "0%").attr("stop-color", GRADIENT_LOW);
  longGrad.append("stop").attr("offset", "100%").attr("stop-color", GRADIENT_HIGH);

  // Short liquidation gradient (above price)
  const shortGrad = defs
    .append("linearGradient")
    .attr("id", "liq-grad-short")
    .attr("x1", "0%")
    .attr("y1", "0%")
    .attr("x2", "100%")
    .attr("y2", "0%");
  shortGrad.append("stop").attr("offset", "0%").attr("stop-color", GRADIENT_LOW);
  shortGrad.append("stop").attr("offset", "100%").attr("stop-color", GRADIENT_HIGH);

  const g = root
    .append("g")
    .attr("transform", `translate(${MARGIN.left},${MARGIN.top})`);

  // ── Separate long/short ─────────────────────────────────────────────────
  const longs = levels
    .filter((l) => l.side === "long")
    .sort((a, b) => b.price - a.price);
  const shorts = levels
    .filter((l) => l.side === "short")
    .sort((a, b) => a.price - b.price);

  // Combine all prices for Y domain
  const allPrices = levels.map((l) => l.price);
  if (allPrices.length === 0) return;

  const minPrice = Math.min(...allPrices, currentPrice);
  const maxPrice = Math.max(...allPrices, currentPrice);
  const pricePad = (maxPrice - minPrice) * 0.03;

  // Y-axis: price levels (inverted so higher prices are at the top)
  const yScale = scaleLinear()
    .domain([minPrice - pricePad, maxPrice + pricePad])
    .range([innerH, 0]);

  // X-axis: totalSize — use sqrt scale for perceptual linearity
  const maxSize = Math.max(...levels.map((l) => l.totalSize), 1);
  const xScale = scaleSqrt().domain([0, maxSize]).range([0, innerW]);

  // Band height based on price spacing
  const priceRange = maxPrice + pricePad - (minPrice - pricePad);
  const bandCount = levels.length > 0 ? levels.length : 1;
  const bandPx = Math.max(2, (innerH / bandCount) * BAR_HEIGHT_FRACTION);

  // ── Draw long liquidation bars (below current price) ────────────────────
  g.selectAll(".bar-long")
    .data(longs)
    .enter()
    .append("rect")
    .attr("class", "bar-long")
    .attr("x", 0)
    .attr("y", (d) => yScale(d.price) - bandPx / 2)
    .attr("width", (d) => xScale(d.totalSize))
    .attr("height", bandPx)
    .attr("fill", "url(#liq-grad-long)")
    .attr("opacity", 0.8)
    .attr("rx", 1);

  // ── Draw short liquidation bars (above current price) ───────────────────
  g.selectAll(".bar-short")
    .data(shorts)
    .enter()
    .append("rect")
    .attr("class", "bar-short")
    .attr("x", 0)
    .attr("y", (d) => yScale(d.price) - bandPx / 2)
    .attr("width", (d) => xScale(d.totalSize))
    .attr("height", bandPx)
    .attr("fill", "url(#liq-grad-short)")
    .attr("opacity", 0.8)
    .attr("rx", 1);

  // ── Current price marker ────────────────────────────────────────────────
  const priceY = yScale(currentPrice);
  g.append("line")
    .attr("x1", 0)
    .attr("x2", innerW)
    .attr("y1", priceY)
    .attr("y2", priceY)
    .attr("stroke", CURRENT_PRICE_COLOR)
    .attr("stroke-width", 1.5)
    .attr("stroke-dasharray", "6,4")
    .attr("opacity", 0.9);

  g.append("text")
    .attr("x", innerW + 4)
    .attr("y", priceY + 3)
    .attr("fill", CURRENT_PRICE_COLOR)
    .attr("font-family", FONT.mono)
    .attr("font-size", 9)
    .attr("text-anchor", "start")
    .text(formatPrice(currentPrice));

  // ── Y-Axis (price) ─────────────────────────────────────────────────────
  const yTickCount = Math.max(4, Math.floor(innerH / 35));
  const yTicks = yScale.ticks(yTickCount);

  // Grid lines
  g.selectAll(".grid-y")
    .data(yTicks)
    .enter()
    .append("line")
    .attr("class", "grid-y")
    .attr("x1", 0)
    .attr("x2", innerW)
    .attr("y1", (d) => yScale(d))
    .attr("y2", (d) => yScale(d))
    .attr("stroke", X.borderSubtle)
    .attr("stroke-dasharray", "2,2")
    .attr("opacity", 0.5);

  // Tick labels
  g.selectAll(".label-y")
    .data(yTicks)
    .enter()
    .append("text")
    .attr("class", "label-y")
    .attr("x", -8)
    .attr("y", (d) => yScale(d) + 3)
    .attr("text-anchor", "end")
    .attr("fill", X.textSecondary)
    .attr("font-family", FONT.mono)
    .attr("font-size", 10)
    .text((d) => formatPrice(d));

  // ── X-Axis (liquidation size) ──────────────────────────────────────────
  const xTickCount = Math.max(3, Math.floor(innerW / 80));
  const xTicks = xScale.ticks(xTickCount);

  g.selectAll(".label-x")
    .data(xTicks)
    .enter()
    .append("text")
    .attr("class", "label-x")
    .attr("x", (d) => xScale(d))
    .attr("y", innerH + 18)
    .attr("text-anchor", "middle")
    .attr("fill", X.textSecondary)
    .attr("font-family", FONT.mono)
    .attr("font-size", 9)
    .text((d) => formatSize(d));

  // X-axis label
  g.append("text")
    .attr("x", innerW / 2)
    .attr("y", innerH + 28)
    .attr("text-anchor", "middle")
    .attr("fill", X.textSecondary)
    .attr("font-family", FONT.display)
    .attr("font-size", 8)
    .attr("letter-spacing", "0.1em")
    .text("LIQUIDATION SIZE");

  // ── Side labels ─────────────────────────────────────────────────────────
  // "LONG LIQS" below price, "SHORT LIQS" above price
  if (longs.length > 0) {
    const longLabelY = yScale(longs[Math.floor(longs.length / 2)]?.price ?? currentPrice);
    g.append("text")
      .attr("x", innerW - 4)
      .attr("y", Math.min(longLabelY, innerH - 4))
      .attr("text-anchor", "end")
      .attr("fill", GRADIENT_HIGH)
      .attr("font-family", FONT.display)
      .attr("font-size", 8)
      .attr("letter-spacing", "0.1em")
      .attr("opacity", 0.6)
      .text("LONG LIQS");
  }

  if (shorts.length > 0) {
    const shortLabelY = yScale(shorts[Math.floor(shorts.length / 2)]?.price ?? currentPrice);
    g.append("text")
      .attr("x", innerW - 4)
      .attr("y", Math.max(shortLabelY, 12))
      .attr("text-anchor", "end")
      .attr("fill", GRADIENT_HIGH)
      .attr("font-family", FONT.display)
      .attr("font-size", 8)
      .attr("letter-spacing", "0.1em")
      .attr("opacity", 0.6)
      .text("SHORT LIQS");
  }

  // ── Hover interaction ───────────────────────────────────────────────────
  const overlay = g
    .append("rect")
    .attr("width", innerW)
    .attr("height", innerH)
    .attr("fill", "transparent")
    .style("cursor", "crosshair");

  // Highlight bar
  const highlightBar = g
    .append("rect")
    .attr("fill", X.textPrimary)
    .attr("opacity", 0)
    .attr("rx", 1)
    .attr("pointer-events", "none");

  overlay.on("mousemove", function (event) {
    if (!tooltip) return;
    const [, my] = [event.offsetX - MARGIN.left, event.offsetY - MARGIN.top];
    const hoverPrice = yScale.invert(my);

    // Find nearest level
    let nearest: LiquidationLevel | null = null;
    let nearestDist = Infinity;
    for (const l of levels) {
      const dist = Math.abs(l.price - hoverPrice);
      if (dist < nearestDist) {
        nearestDist = dist;
        nearest = l;
      }
    }

    if (!nearest) {
      tooltip.style.opacity = "0";
      highlightBar.attr("opacity", 0);
      return;
    }

    // Highlight bar
    highlightBar
      .attr("x", 0)
      .attr("y", yScale(nearest.price) - bandPx / 2 - 1)
      .attr("width", xScale(nearest.totalSize) + 2)
      .attr("height", bandPx + 2)
      .attr("opacity", 0.15);

    // Tooltip content
    const sideLabel = nearest.side === "long" ? "LONG" : "SHORT";
    const sideColor = nearest.side === "long" ? X.glowAmber : X.glowCrimson;

    tooltip.innerHTML =
      `<div style="font-family:${FONT.display};font-size:9px;letter-spacing:0.08em;color:${sideColor};margin-bottom:4px">${sideLabel} LIQUIDATIONS</div>` +
      `<div style="display:flex;justify-content:space-between;gap:16px">` +
      `<span style="color:${X.textSecondary}">Price</span>` +
      `<span style="color:${X.textPrimary}">${formatPrice(nearest.price)}</span></div>` +
      `<div style="display:flex;justify-content:space-between;gap:16px">` +
      `<span style="color:${X.textSecondary}">Size</span>` +
      `<span style="color:${X.textPrimary}">${formatSize(nearest.totalSize)}</span></div>` +
      `<div style="display:flex;justify-content:space-between;gap:16px">` +
      `<span style="color:${X.textSecondary}">Positions</span>` +
      `<span style="color:${X.textPrimary}">${nearest.positionCount}</span></div>`;

    tooltip.style.opacity = "1";

    // Position tooltip
    const tipW = 180;
    const tipH = 90;
    const containerRect = container.getBoundingClientRect();
    const svgRect = svg.getBoundingClientRect();

    let tipX = event.clientX - svgRect.left + 16;
    let tipY = event.clientY - svgRect.top - tipH / 2;

    if (tipX + tipW > containerRect.width - 4) {
      tipX = event.clientX - svgRect.left - tipW - 16;
    }
    if (tipY < 4) tipY = 4;
    if (tipY + tipH > containerRect.height - 4) {
      tipY = containerRect.height - tipH - 4;
    }

    tooltip.style.left = `${tipX}px`;
    tooltip.style.top = `${tipY}px`;
  });

  overlay.on("mouseleave", function () {
    if (tooltip) tooltip.style.opacity = "0";
    highlightBar.attr("opacity", 0);
  });
}

// ─── COMPONENT ──────────────────────────────────────────────────────────────

const LiquidationHeatmap = memo(function LiquidationHeatmap() {
  const activeMarket = useExchangeStore((s) => s.activeMarket);
  const { data: levels } = useLiquidationLevels(activeMarket);
  const { data: market } = useMarket(activeMarket);

  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const [dims, setDims] = useState({ w: 0, h: 0 });

  const currentPrice = market?.lastPrice ?? 0;

  // Summary stats
  const summary = useMemo(() => {
    if (!levels || levels.length === 0) {
      return { longTotal: 0, shortTotal: 0, longCount: 0, shortCount: 0 };
    }
    let longTotal = 0;
    let shortTotal = 0;
    let longCount = 0;
    let shortCount = 0;
    for (const l of levels) {
      if (l.side === "long") {
        longTotal += l.totalSize;
        longCount += l.positionCount;
      } else {
        shortTotal += l.totalSize;
        shortCount += l.positionCount;
      }
    }
    return { longTotal, shortTotal, longCount, shortCount };
  }, [levels]);

  // ── ResizeObserver ──────────────────────────────────────────────────────
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    let rafId: number;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width: w, height: h } = entry.contentRect;
        cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(() => {
          setDims((prev) => {
            const nw = Math.round(w);
            const nh = Math.round(h);
            if (prev.w === nw && prev.h === nh) return prev;
            return { w: nw, h: nh };
          });
        });
      }
    });

    ro.observe(el);
    return () => {
      ro.disconnect();
      cancelAnimationFrame(rafId);
    };
  }, []);

  // ── D3 render ───────────────────────────────────────────────────────────
  useEffect(() => {
    const svgEl = svgRef.current;
    const container = containerRef.current;
    if (!svgEl || !container || !levels || levels.length === 0 || currentPrice <= 0)
      return;

    renderHeatmap(svgEl, container, tooltipRef.current, levels, currentPrice);
  }, [levels, currentPrice, dims.w, dims.h]);

  const hasData = levels && levels.length > 0 && currentPrice > 0;

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
      <div style={panelHeaderStyle}>LIQUIDATION HEATMAP</div>

      {/* Summary stats bar */}
      <div
        style={{
          display: "flex",
          gap: 16,
          padding: "8px 14px",
          borderBottom: `1px solid ${X.borderSubtle}`,
          flexWrap: "wrap",
        }}
      >
        <div style={{ flex: "1 1 auto" }}>
          <div
            style={{
              fontFamily: FONT.display,
              fontSize: 8,
              letterSpacing: "0.1em",
              color: X.glowAmber,
              textTransform: "uppercase" as const,
            }}
          >
            Long Liqs
          </div>
          <div
            style={{
              fontFamily: FONT.mono,
              fontSize: 12,
              color: X.textPrimary,
            }}
          >
            {formatSize(summary.longTotal)}{" "}
            <span style={{ fontSize: 9, color: X.textSecondary }}>
              ({summary.longCount} pos)
            </span>
          </div>
        </div>
        <div style={{ flex: "1 1 auto" }}>
          <div
            style={{
              fontFamily: FONT.display,
              fontSize: 8,
              letterSpacing: "0.1em",
              color: X.glowCrimson,
              textTransform: "uppercase" as const,
            }}
          >
            Short Liqs
          </div>
          <div
            style={{
              fontFamily: FONT.mono,
              fontSize: 12,
              color: X.textPrimary,
            }}
          >
            {formatSize(summary.shortTotal)}{" "}
            <span style={{ fontSize: 9, color: X.textSecondary }}>
              ({summary.shortCount} pos)
            </span>
          </div>
        </div>
        <div style={{ flex: "1 1 auto" }}>
          <div
            style={{
              fontFamily: FONT.display,
              fontSize: 8,
              letterSpacing: "0.1em",
              color: X.glowCyan,
              textTransform: "uppercase" as const,
            }}
          >
            Current Price
          </div>
          <div
            style={{
              fontFamily: FONT.mono,
              fontSize: 12,
              color: X.glowCyan,
            }}
          >
            {currentPrice > 0 ? formatPrice(currentPrice) : "---"}
          </div>
        </div>
      </div>

      {/* Chart */}
      <div
        ref={containerRef}
        style={{
          position: "relative",
          flexGrow: 1,
          minHeight: 220,
          overflow: "hidden",
        }}
      >
        {!hasData ? (
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
            Waiting for liquidation data...
          </div>
        ) : (
          <svg
            ref={svgRef}
            style={{ display: "block", width: "100%", height: "100%" }}
          />
        )}

        {/* Tooltip */}
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
            minWidth: 160,
            whiteSpace: "nowrap",
            boxShadow: `0 4px 16px ${X.bgBase}cc`,
          }}
        />
      </div>

      {/* Legend */}
      <div
        style={{
          display: "flex",
          gap: 16,
          padding: "6px 14px",
          borderTop: `1px solid ${X.borderSubtle}`,
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div
            style={{
              width: 24,
              height: 6,
              borderRadius: 2,
              background: `linear-gradient(90deg, ${GRADIENT_LOW}, ${GRADIENT_HIGH})`,
            }}
          />
          <span
            style={{
              fontFamily: FONT.display,
              fontSize: 8,
              letterSpacing: "0.1em",
              color: X.textSecondary,
              textTransform: "uppercase" as const,
            }}
          >
            Liquidation Density
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div
            style={{
              width: 16,
              height: 0,
              borderTop: `2px dashed ${CURRENT_PRICE_COLOR}`,
            }}
          />
          <span
            style={{
              fontFamily: FONT.display,
              fontSize: 8,
              letterSpacing: "0.1em",
              color: X.textSecondary,
              textTransform: "uppercase" as const,
            }}
          >
            Current Price
          </span>
        </div>
      </div>
    </div>
  );
});

export default LiquidationHeatmap;
