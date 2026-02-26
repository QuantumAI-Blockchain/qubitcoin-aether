"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";

interface DataPoint {
  block: number;
  phi: number;
}

const CHART_W = 600;
const CHART_H = 200;
const PAD = { top: 20, right: 16, bottom: 30, left: 50 };

function buildPath(data: DataPoint[], xMin: number, xMax: number, yMax: number): string {
  if (data.length === 0) return "";
  const w = CHART_W - PAD.left - PAD.right;
  const h = CHART_H - PAD.top - PAD.bottom;
  const xRange = xMax - xMin || 1;
  const yRange = yMax || 1;

  return data
    .map((d, i) => {
      const x = PAD.left + ((d.block - xMin) / xRange) * w;
      const y = PAD.top + h - (d.phi / yRange) * h;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function buildAreaPath(data: DataPoint[], xMin: number, xMax: number, yMax: number): string {
  if (data.length === 0) return "";
  const w = CHART_W - PAD.left - PAD.right;
  const h = CHART_H - PAD.top - PAD.bottom;
  const xRange = xMax - xMin || 1;
  const yRange = yMax || 1;
  const baseline = PAD.top + h;

  const points = data.map((d) => {
    const x = PAD.left + ((d.block - xMin) / xRange) * w;
    const y = PAD.top + h - (d.phi / yRange) * h;
    return { x, y };
  });

  const first = points[0];
  const last = points[points.length - 1];

  let path = `M${first.x.toFixed(1)},${baseline}`;
  for (const p of points) {
    path += ` L${p.x.toFixed(1)},${p.y.toFixed(1)}`;
  }
  path += ` L${last.x.toFixed(1)},${baseline} Z`;
  return path;
}

export function PhiChart() {
  const { data: historyData } = useQuery({
    queryKey: ["phiHistory"],
    queryFn: api.getPhiHistory,
    refetchInterval: 30_000,
  });

  const history: DataPoint[] = historyData?.history ?? [];

  if (history.length === 0) {
    return (
      <Card>
        <h3 className="mb-3 text-sm font-semibold text-text-secondary">
          Phi (&Phi;) History
        </h3>
        <p className="py-8 text-center text-sm text-text-secondary">
          No Phi history data available yet.
        </p>
      </Card>
    );
  }

  const xMin = history[0].block;
  const xMax = history[history.length - 1].block;
  const yMax = Math.max(...history.map((d) => d.phi), 3.0) * 1.15;
  const thresholdY =
    PAD.top + (CHART_H - PAD.top - PAD.bottom) - (3.0 / yMax) * (CHART_H - PAD.top - PAD.bottom);

  const linePath = buildPath(history, xMin, xMax, yMax);
  const areaPath = buildAreaPath(history, xMin, xMax, yMax);

  // Y-axis ticks
  const yTicks = [0, yMax * 0.25, yMax * 0.5, yMax * 0.75, yMax].map((v) => ({
    value: v,
    y: PAD.top + (CHART_H - PAD.top - PAD.bottom) - (v / yMax) * (CHART_H - PAD.top - PAD.bottom),
  }));

  return (
    <Card>
      <h3 className="mb-3 text-sm font-semibold text-text-secondary">
        Phi (&Phi;) History
      </h3>
      <svg
        viewBox={`0 0 ${CHART_W} ${CHART_H}`}
        className="w-full"
        preserveAspectRatio="xMidYMid meet"
      >
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
          stroke="var(--color-quantum-red)"
          strokeWidth={1}
          strokeDasharray="4 3"
          opacity={0.6}
        />
        <text
          x={CHART_W - PAD.right + 2}
          y={thresholdY + 3}
          fill="var(--color-quantum-red)"
          fontSize={8}
          opacity={0.8}
        >
          &Phi;=3.0
        </text>

        {/* Area fill */}
        <path
          d={areaPath}
          fill="url(#phiGradient)"
          opacity={0.25}
        />

        {/* Line */}
        <path
          d={linePath}
          fill="none"
          stroke="var(--color-glow-cyan)"
          strokeWidth={2}
          strokeLinejoin="round"
        />

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

        {/* Gradient definition */}
        <defs>
          <linearGradient id="phiGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-glow-cyan)" stopOpacity={0.6} />
            <stop offset="100%" stopColor="var(--color-glow-cyan)" stopOpacity={0} />
          </linearGradient>
        </defs>
      </svg>
    </Card>
  );
}
