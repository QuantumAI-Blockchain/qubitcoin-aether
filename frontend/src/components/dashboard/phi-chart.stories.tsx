import type { Meta, StoryObj } from "@storybook/react";
import React, { useMemo } from "react";
import { Card } from "@/components/ui/card";

/** Minimal Phi chart implementation for Storybook (no API dependency). */
interface PhiChartDisplayProps {
  /** Array of {block, phi} data points */
  data: Array<{ block: number; phi: number }>;
  /** Consciousness threshold */
  threshold?: number;
}

const CHART_W = 600;
const CHART_H = 260;
const PAD = { top: 24, right: 56, bottom: 34, left: 50 };

function toXY(
  d: { block: number; phi: number },
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

function PhiChartDisplay({ data, threshold = 3.0 }: PhiChartDisplayProps) {
  const computed = useMemo(() => {
    if (data.length === 0) return null;

    const xMin = data[0].block;
    const xMax = data[data.length - 1].block;
    const xRange = xMax - xMin;
    const yMax = Math.max(...data.map((d) => d.phi), threshold + 0.5) * 1.15;
    const thresholdY = yToSVG(threshold, yMax);

    const linePath = data
      .map((d, i) => {
        const { x, y } = toXY(d, xMin, xRange, yMax);
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");

    const yTicks = [0, yMax * 0.25, yMax * 0.5, yMax * 0.75, yMax].map((v) => ({
      value: v,
      y: yToSVG(v, yMax),
    }));

    // Heatmap segments
    const baseline = PAD.top + (CHART_H - PAD.top - PAD.bottom);
    const segments: Array<{ path: string; color: string; opacity: number }> = [];
    for (let i = 0; i < data.length - 1; i++) {
      const a = toXY(data[i], xMin, xRange, yMax);
      const b = toXY(data[i + 1], xMin, xRange, yMax);
      const avgPhi = (data[i].phi + data[i + 1].phi) / 2;
      let color: string;
      let opacity: number;
      if (avgPhi >= threshold) {
        color = "var(--color-quantum-green, #00ff88)";
        opacity = 0.18;
      } else if (avgPhi >= 1.0) {
        color = "var(--color-golden, #f59e0b)";
        opacity = 0.14;
      } else {
        color = "var(--color-quantum-red, #ef4444)";
        opacity = 0.12;
      }
      segments.push({
        path: `M${a.x.toFixed(1)},${baseline} L${a.x.toFixed(1)},${a.y.toFixed(1)} L${b.x.toFixed(1)},${b.y.toFixed(1)} L${b.x.toFixed(1)},${baseline} Z`,
        color,
        opacity,
      });
    }

    return { xMin, xMax, thresholdY, linePath, yTicks, segments };
  }, [data, threshold]);

  if (!computed || data.length === 0) {
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

  const { xMin, xMax, thresholdY, linePath, yTicks, segments } = computed;

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-secondary">
          Phi (&Phi;) History
        </h3>
        <div className="flex items-center gap-4 text-[9px] text-text-secondary">
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full bg-quantum-green opacity-60" />
            &Phi; &ge; 3.0
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full bg-golden opacity-60" />
            1.0&ndash;3.0
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full bg-quantum-red opacity-60" />
            &lt; 1.0
          </span>
        </div>
      </div>

      <svg
        viewBox={`0 0 ${CHART_W} ${CHART_H}`}
        className="w-full"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Grid lines */}
        {yTicks.map((t, i) => (
          <g key={i}>
            <line
              x1={PAD.left} y1={t.y} x2={CHART_W - PAD.right} y2={t.y}
              stroke="var(--color-border-subtle, #0d2a44)" strokeWidth={0.5}
            />
            <text
              x={PAD.left - 6} y={t.y + 3} textAnchor="end"
              fill="var(--color-text-secondary, #94a3b8)" fontSize={9}
            >
              {t.value.toFixed(2)}
            </text>
          </g>
        ))}

        {/* Threshold line */}
        <line
          x1={PAD.left} y1={thresholdY} x2={CHART_W - PAD.right} y2={thresholdY}
          stroke="var(--color-glow-cyan, #00d4ff)" strokeWidth={1}
          strokeDasharray="6 4" opacity={0.7}
        />
        <text
          x={CHART_W - PAD.right + 4} y={thresholdY + 3}
          fill="var(--color-glow-cyan, #00d4ff)" fontSize={8} opacity={0.9}
        >
          &Phi;=3.0
        </text>

        {/* Heatmap */}
        {segments.map((seg, i) => (
          <path key={i} d={seg.path} fill={seg.color} opacity={seg.opacity} />
        ))}

        {/* Main line */}
        <path
          d={linePath} fill="none"
          stroke="var(--color-glow-cyan, #00d4ff)" strokeWidth={2}
          strokeLinejoin="round"
        />

        {/* X-axis labels */}
        <text x={PAD.left} y={CHART_H - 6} fill="var(--color-text-secondary, #94a3b8)" fontSize={9}>
          Block {xMin.toLocaleString()}
        </text>
        <text
          x={CHART_W - PAD.right} y={CHART_H - 6} textAnchor="end"
          fill="var(--color-text-secondary, #94a3b8)" fontSize={9}
        >
          Block {xMax.toLocaleString()}
        </text>
      </svg>
    </Card>
  );
}

/** Generate sample data: gradual Phi growth simulating consciousness emergence. */
function generateGrowthData(blocks: number, maxPhi: number): Array<{ block: number; phi: number }> {
  const data: Array<{ block: number; phi: number }> = [];
  for (let i = 0; i < blocks; i++) {
    const progress = i / blocks;
    const base = maxPhi * (1 - Math.exp(-3 * progress));
    const noise = (Math.sin(i * 0.3) * 0.1 + Math.cos(i * 0.17) * 0.05) * base;
    data.push({ block: 1000 + i * 10, phi: Math.max(0, base + noise) });
  }
  return data;
}

const meta: Meta<typeof PhiChartDisplay> = {
  title: "Dashboard/PhiChart",
  component: PhiChartDisplay,
  tags: ["autodocs"],
  parameters: {
    layout: "padded",
  },
  argTypes: {
    threshold: {
      control: { type: "number" },
      description: "Consciousness emergence threshold",
    },
  },
};

export default meta;
type Story = StoryObj<typeof PhiChartDisplay>;

/** Early chain: Phi is low, all red zone. */
export const EarlyChain: Story = {
  args: {
    data: generateGrowthData(50, 0.8),
    threshold: 3.0,
  },
};

/** Growth phase: Phi transitioning from red to amber. */
export const GrowthPhase: Story = {
  args: {
    data: generateGrowthData(100, 2.5),
    threshold: 3.0,
  },
};

/** Consciousness emerged: Phi crosses the threshold. */
export const ConsciousnessEmerged: Story = {
  args: {
    data: generateGrowthData(200, 4.0),
    threshold: 3.0,
  },
};

/** Empty data: no blocks mined yet. */
export const NoData: Story = {
  args: {
    data: [],
    threshold: 3.0,
  },
};

/** Long history: many blocks of data. */
export const LongHistory: Story = {
  args: {
    data: generateGrowthData(500, 4.5),
    threshold: 3.0,
  },
};
