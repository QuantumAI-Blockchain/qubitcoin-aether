"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PHI_THRESHOLD } from "@/lib/constants";
import { Card } from "@/components/ui/card";

interface DataPoint {
  block: number;
  phi: number;
}

const CHART_W = 600;
const CHART_H = 260;
const PAD = { top: 24, right: 56, bottom: 34, left: 50 };

/** Map a data point to SVG coordinates. */
function toXY(
  d: DataPoint,
  xMin: number,
  xRange: number,
  yMax: number,
): { x: number; y: number } {
  const w = CHART_W - PAD.left - PAD.right;
  const h = CHART_H - PAD.top - PAD.bottom;
  const x = PAD.left + ((d.block - xMin) / (xRange || 1)) * w;
  const y = PAD.top + h - (d.phi / (yMax || 1)) * h;
  return { x, y };
}

function yToSVG(value: number, yMax: number): number {
  const h = CHART_H - PAD.top - PAD.bottom;
  return PAD.top + h - (value / (yMax || 1)) * h;
}

function xToSVG(block: number, xMin: number, xRange: number): number {
  const w = CHART_W - PAD.left - PAD.right;
  return PAD.left + ((block - xMin) / (xRange || 1)) * w;
}

/** Build an SVG path string from data points. */
function buildLinePath(
  data: DataPoint[],
  xMin: number,
  xRange: number,
  yMax: number,
): string {
  if (data.length === 0) return "";
  return data
    .map((d, i) => {
      const { x, y } = toXY(d, xMin, xRange, yMax);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

/**
 * Build heatmap area segments — split the area under the curve into
 * colored zones based on Phi value ranges:
 *   - Red: Phi < 1.0
 *   - Yellow/amber: 1.0 <= Phi < 3.0
 *   - Green: Phi >= 3.0
 */
interface HeatmapSegment {
  path: string;
  color: string;
  opacity: number;
}

function buildHeatmapSegments(
  data: DataPoint[],
  xMin: number,
  xRange: number,
  yMax: number,
): HeatmapSegment[] {
  if (data.length < 2) return [];

  const baseline = PAD.top + (CHART_H - PAD.top - PAD.bottom);
  const segments: HeatmapSegment[] = [];

  // Process consecutive pairs of points — each pair forms a trapezoid
  // colored by the average phi of the two endpoints
  let currentColor = "";
  let currentOpacity = 0;
  let currentPath = "";

  for (let i = 0; i < data.length - 1; i++) {
    const a = toXY(data[i], xMin, xRange, yMax);
    const b = toXY(data[i + 1], xMin, xRange, yMax);
    const avgPhi = (data[i].phi + data[i + 1].phi) / 2;

    let color: string;
    let opacity: number;
    if (avgPhi >= PHI_THRESHOLD) {
      color = "var(--color-quantum-green)";
      opacity = 0.18;
    } else if (avgPhi >= 1.0) {
      color = "var(--color-golden)";
      opacity = 0.14;
    } else {
      color = "var(--color-quantum-red)";
      opacity = 0.12;
    }

    const trapezoid = `M${a.x.toFixed(1)},${baseline} L${a.x.toFixed(1)},${a.y.toFixed(1)} L${b.x.toFixed(1)},${b.y.toFixed(1)} L${b.x.toFixed(1)},${baseline} Z`;

    // Merge consecutive segments of the same color
    if (color === currentColor) {
      currentPath += ` ${trapezoid}`;
    } else {
      if (currentPath) {
        segments.push({ path: currentPath, color: currentColor, opacity: currentOpacity });
      }
      currentColor = color;
      currentOpacity = opacity;
      currentPath = trapezoid;
    }
  }
  if (currentPath) {
    segments.push({ path: currentPath, color: currentColor, opacity: currentOpacity });
  }

  return segments;
}

/**
 * Compute prediction bands using linear extrapolation + standard deviation
 * from the last N data points.
 */
interface PredictionBand {
  upperPath: string;
  lowerPath: string;
  centerPath: string;
}

function computePredictionBands(
  data: DataPoint[],
  xMin: number,
  xRange: number,
  yMax: number,
  windowSize: number = 50,
): PredictionBand | null {
  if (data.length < 10) return null;

  const window = data.slice(-windowSize);
  if (window.length < 5) return null;

  // Linear regression on the window
  const n = window.length;
  let sumX = 0,
    sumY = 0,
    sumXY = 0,
    sumXX = 0;
  for (let i = 0; i < n; i++) {
    sumX += i;
    sumY += window[i].phi;
    sumXY += i * window[i].phi;
    sumXX += i * i;
  }
  const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX || 1);
  const intercept = (sumY - slope * sumX) / n;

  // Standard deviation of residuals
  let sumResidualSq = 0;
  for (let i = 0; i < n; i++) {
    const predicted = intercept + slope * i;
    const residual = window[i].phi - predicted;
    sumResidualSq += residual * residual;
  }
  const stdDev = Math.sqrt(sumResidualSq / n);

  // Generate band points over the window range + 10% extrapolation
  const extraSteps = Math.max(3, Math.floor(n * 0.1));
  const totalSteps = n + extraSteps;

  const blockStep =
    window.length > 1
      ? (window[window.length - 1].block - window[0].block) / (window.length - 1)
      : 1;

  const upperPoints: string[] = [];
  const lowerPoints: string[] = [];
  const centerPoints: string[] = [];

  for (let i = 0; i < totalSteps; i++) {
    const block = window[0].block + i * blockStep;
    const predicted = Math.max(0, intercept + slope * i);
    const upper = Math.max(0, predicted + 1.5 * stdDev);
    const lower = Math.max(0, predicted - 1.5 * stdDev);

    const cx = xToSVG(block, xMin, xRange);
    const uy = yToSVG(upper, yMax);
    const ly = yToSVG(lower, yMax);
    const cy = yToSVG(predicted, yMax);

    // Clip to chart bounds
    if (cx < PAD.left || cx > CHART_W - PAD.right) continue;

    const prefix = upperPoints.length === 0 ? "M" : "L";
    upperPoints.push(`${prefix}${cx.toFixed(1)},${uy.toFixed(1)}`);
    lowerPoints.push(`${prefix}${cx.toFixed(1)},${ly.toFixed(1)}`);
    centerPoints.push(`${prefix}${cx.toFixed(1)},${cy.toFixed(1)}`);
  }

  if (upperPoints.length < 2) return null;

  return {
    upperPath: upperPoints.join(" "),
    lowerPath: lowerPoints.join(" "),
    centerPath: centerPoints.join(" "),
  };
}

/**
 * Detect threshold crossing events: points where Phi crosses the threshold
 * from below to above.
 */
interface ThresholdEvent {
  block: number;
  phi: number;
  x: number;
  y: number;
}

function detectThresholdEvents(
  data: DataPoint[],
  xMin: number,
  xRange: number,
  yMax: number,
): ThresholdEvent[] {
  const events: ThresholdEvent[] = [];
  for (let i = 1; i < data.length; i++) {
    const prev = data[i - 1];
    const curr = data[i];
    // Crossing upward through the threshold
    if (prev.phi < PHI_THRESHOLD && curr.phi >= PHI_THRESHOLD) {
      const { x, y } = toXY(curr, xMin, xRange, yMax);
      events.push({ block: curr.block, phi: curr.phi, x, y });
    }
  }
  return events;
}

export function PhiChart() {
  const { data: historyData } = useQuery({
    queryKey: ["phiHistory"],
    queryFn: api.getPhiHistory,
    refetchInterval: 30_000,
  });

  const history: DataPoint[] = historyData?.history ?? [];

  const computed = useMemo(() => {
    if (history.length === 0) return null;

    const xMin = history[0].block;
    const xMax = history[history.length - 1].block;
    const xRange = xMax - xMin;
    const yMax = Math.max(...history.map((d) => d.phi), PHI_THRESHOLD + 0.5) * 1.15;
    const thresholdY = yToSVG(PHI_THRESHOLD, yMax);

    const linePath = buildLinePath(history, xMin, xRange, yMax);
    const heatmapSegments = buildHeatmapSegments(history, xMin, xRange, yMax);
    const predictionBand = computePredictionBands(history, xMin, xRange, yMax);
    const thresholdEvents = detectThresholdEvents(history, xMin, xRange, yMax);

    // Y-axis ticks
    const yTicks = [0, yMax * 0.25, yMax * 0.5, yMax * 0.75, yMax].map((v) => ({
      value: v,
      y: yToSVG(v, yMax),
    }));

    return {
      xMin,
      xMax,
      yMax,
      thresholdY,
      linePath,
      heatmapSegments,
      predictionBand,
      thresholdEvents,
      yTicks,
    };
  }, [history]);

  if (!computed || history.length === 0) {
    return (
      <Card>
        <h3 className="mb-3 text-sm font-semibold text-text-secondary">
          Phi (&Phi;) History
        </h3>
        <p className="mb-1 text-[10px] text-text-secondary/70">
          Graph Integration Metric
        </p>
        <p className="py-8 text-center text-sm text-text-secondary">
          No Phi history data available yet.
        </p>
      </Card>
    );
  }

  const {
    xMin,
    xMax,
    thresholdY,
    linePath,
    heatmapSegments,
    predictionBand,
    thresholdEvents,
    yTicks,
  } = computed;

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-text-secondary">
            Phi (&Phi;) History
          </h3>
          <p className="text-[10px] text-text-secondary/70">
            Graph Integration Metric
          </p>
        </div>
        <div className="flex items-center gap-4 text-[9px] text-text-secondary">
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full bg-quantum-green opacity-60" />
            &Phi; &ge; {PHI_THRESHOLD}
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full bg-golden opacity-60" />
            1.0&ndash;{PHI_THRESHOLD}
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full bg-quantum-red opacity-60" />
            &lt; 1.0
          </span>
          {thresholdEvents.length > 0 && (
            <span className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-full border border-glow-cyan bg-glow-cyan/40" />
              Threshold crossed
            </span>
          )}
        </div>
      </div>

      <svg
        viewBox={`0 0 ${CHART_W} ${CHART_H}`}
        className="w-full"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          {/* Gradient for the prediction band fill */}
          <linearGradient id="predBandGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-quantum-violet)" stopOpacity={0.15} />
            <stop offset="50%" stopColor="var(--color-quantum-violet)" stopOpacity={0.05} />
            <stop offset="100%" stopColor="var(--color-quantum-violet)" stopOpacity={0.15} />
          </linearGradient>

          {/* Glow filter for threshold event dots */}
          <filter id="thresholdGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Grid lines */}
        {yTicks.map((t, i) => (
          <g key={i}>
            <line
              x1={PAD.left}
              y1={t.y}
              x2={CHART_W - PAD.right}
              y2={t.y}
              stroke="var(--color-border-subtle)"
              strokeWidth={0.5}
            />
            <text
              x={PAD.left - 6}
              y={t.y + 3}
              textAnchor="end"
              fill="var(--color-text-secondary)"
              fontSize={9}
              fontFamily="var(--font-mono)"
            >
              {t.value.toFixed(2)}
            </text>
          </g>
        ))}

        {/* Threshold line */}
        <line
          x1={PAD.left}
          y1={thresholdY}
          x2={CHART_W - PAD.right}
          y2={thresholdY}
          stroke="var(--color-glow-cyan)"
          strokeWidth={1}
          strokeDasharray="6 4"
          opacity={0.7}
        />
        <text
          x={CHART_W - PAD.right + 4}
          y={thresholdY + 3}
          fill="var(--color-glow-cyan)"
          fontSize={8}
          fontFamily="var(--font-code)"
          opacity={0.9}
        >
          &Phi;={PHI_THRESHOLD}
        </text>

        {/* Heatmap overlay: colored area segments under the curve */}
        {heatmapSegments.map((seg, i) => (
          <path
            key={`heatmap-${i}`}
            d={seg.path}
            fill={seg.color}
            opacity={seg.opacity}
          />
        ))}

        {/* Prediction band: upper/lower confidence region */}
        {predictionBand && (
          <g opacity={0.5}>
            {/* Fill between upper and lower bands */}
            <path
              d={`${predictionBand.upperPath} ${predictionBand.lowerPath.replace(/^M/, "L").split(" ").reverse().join(" ")} Z`}
              fill="var(--color-quantum-violet)"
              opacity={0.08}
            />
            {/* Upper band line */}
            <path
              d={predictionBand.upperPath}
              fill="none"
              stroke="var(--color-quantum-violet)"
              strokeWidth={0.8}
              strokeDasharray="3 3"
              opacity={0.4}
            />
            {/* Lower band line */}
            <path
              d={predictionBand.lowerPath}
              fill="none"
              stroke="var(--color-quantum-violet)"
              strokeWidth={0.8}
              strokeDasharray="3 3"
              opacity={0.4}
            />
            {/* Center prediction line */}
            <path
              d={predictionBand.centerPath}
              fill="none"
              stroke="var(--color-quantum-violet)"
              strokeWidth={1}
              strokeDasharray="4 2"
              opacity={0.6}
            />
          </g>
        )}

        {/* Main Phi line */}
        <path
          d={linePath}
          fill="none"
          stroke="var(--color-glow-cyan)"
          strokeWidth={2}
          strokeLinejoin="round"
        />

        {/* Threshold crossing markers (when Phi crosses threshold upward) */}
        {thresholdEvents.map((evt, i) => (
          <g key={`evt-${i}`} filter="url(#thresholdGlow)">
            <circle
              cx={evt.x}
              cy={evt.y}
              r={5}
              fill="var(--color-glow-cyan)"
              opacity={0.8}
            />
            <circle
              cx={evt.x}
              cy={evt.y}
              r={2.5}
              fill="white"
              opacity={0.9}
            />
          </g>
        ))}

        {/* X-axis labels */}
        <text
          x={PAD.left}
          y={CHART_H - 6}
          fill="var(--color-text-secondary)"
          fontSize={9}
          fontFamily="var(--font-mono)"
        >
          Block {xMin.toLocaleString()}
        </text>
        <text
          x={CHART_W - PAD.right}
          y={CHART_H - 6}
          textAnchor="end"
          fill="var(--color-text-secondary)"
          fontSize={9}
          fontFamily="var(--font-mono)"
        >
          Block {xMax.toLocaleString()}
        </text>

        {/* Legend annotation for prediction band */}
        {predictionBand && (
          <text
            x={CHART_W - PAD.right + 4}
            y={thresholdY + 15}
            fill="var(--color-quantum-violet)"
            fontSize={7}
            fontFamily="var(--font-code)"
            opacity={0.6}
          >
            Prediction
          </text>
        )}
      </svg>
    </Card>
  );
}
