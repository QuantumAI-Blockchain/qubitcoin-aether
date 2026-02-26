"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";

interface ReserveData {
  total_minted: string;
  total_backed: string;
  backing_percentage: number;
}

const CHART_W = 320;
const CHART_H = 320;
const CENTER = CHART_W / 2;
const RADIUS = 120;
const STROKE = 18;

/** Animated donut gauge showing QUSD backing ratio in real time. */
export function QUSDReserveGauge() {
  const { data, isLoading, error } = useQuery<ReserveData>({
    queryKey: ["qusdReserves"],
    queryFn: () => api.getQUSDReserves(),
    refetchInterval: 15_000,
  });

  const pct = data?.backing_percentage ?? 0;
  const minted = data ? parseFloat(data.total_minted) : 0;
  const backed = data ? parseFloat(data.total_backed) : 0;
  const circumference = 2 * Math.PI * RADIUS;
  const filledLength = (Math.min(pct, 100) / 100) * circumference;

  const statusColor =
    pct >= 100
      ? "text-quantum-green"
      : pct >= 50
        ? "text-golden-amber"
        : "text-quantum-red";

  const strokeColor =
    pct >= 100
      ? "var(--color-glow-cyan)"
      : pct >= 50
        ? "var(--color-golden-amber)"
        : "var(--color-quantum-red)";

  if (isLoading) {
    return (
      <Card>
        <h3 className="mb-3 text-sm font-semibold text-text-secondary">
          QUSD Reserve Backing
        </h3>
        <p className="py-12 text-center text-sm text-text-secondary">Loading...</p>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <h3 className="mb-3 text-sm font-semibold text-text-secondary">
          QUSD Reserve Backing
        </h3>
        <p className="py-12 text-center text-sm text-text-secondary">
          Unable to fetch reserve data.
        </p>
      </Card>
    );
  }

  return (
    <Card glow={pct >= 100 ? "green" : "none"}>
      <h3 className="mb-1 text-sm font-semibold text-text-secondary">
        QUSD Reserve Backing
      </h3>
      <p className="mb-4 text-xs text-text-secondary">
        Real-time collateral coverage of QUSD supply
      </p>

      {/* Donut gauge */}
      <div className="flex justify-center">
        <svg
          viewBox={`0 0 ${CHART_W} ${CHART_H}`}
          className="w-full max-w-[280px]"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Background circle */}
          <circle
            cx={CENTER}
            cy={CENTER}
            r={RADIUS}
            fill="none"
            stroke="var(--color-border-subtle)"
            strokeWidth={STROKE}
          />

          {/* Filled arc */}
          <motion.circle
            cx={CENTER}
            cy={CENTER}
            r={RADIUS}
            fill="none"
            stroke={strokeColor}
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference - filledLength }}
            transition={{ duration: 1.5, ease: "easeOut" }}
            transform={`rotate(-90 ${CENTER} ${CENTER})`}
          />

          {/* Center text */}
          <text
            x={CENTER}
            y={CENTER - 12}
            textAnchor="middle"
            fill="currentColor"
            className={statusColor}
            fontSize={36}
            fontWeight="bold"
            fontFamily="var(--font-mono)"
          >
            {pct.toFixed(1)}%
          </text>
          <text
            x={CENTER}
            y={CENTER + 14}
            textAnchor="middle"
            fill="var(--color-text-secondary)"
            fontSize={12}
          >
            Backing Ratio
          </text>
        </svg>
      </div>

      {/* Stats grid */}
      <div className="mt-4 grid grid-cols-2 gap-4 border-t border-border-subtle pt-4">
        <div>
          <p className="text-xs text-text-secondary">Total Minted</p>
          <p className="mt-0.5 font-[family-name:var(--font-code)] text-sm font-semibold">
            {formatLargeNumber(minted)} QUSD
          </p>
        </div>
        <div>
          <p className="text-xs text-text-secondary">Total Backed</p>
          <p className="mt-0.5 font-[family-name:var(--font-code)] text-sm font-semibold text-quantum-green">
            {formatLargeNumber(backed)} QBC
          </p>
        </div>
        <div>
          <p className="text-xs text-text-secondary">Deficit</p>
          <p className="mt-0.5 font-[family-name:var(--font-code)] text-sm font-semibold">
            {minted > backed
              ? `${formatLargeNumber(minted - backed)} QUSD`
              : "None"}
          </p>
        </div>
        <div>
          <p className="text-xs text-text-secondary">Status</p>
          <p className={`mt-0.5 text-sm font-semibold ${statusColor}`}>
            {pct >= 100 ? "Fully Backed" : pct >= 50 ? "Partial" : "Under-collateralized"}
          </p>
        </div>
      </div>
    </Card>
  );
}

/** Milestone timeline showing the 10-year path to 100% backing. */
export function QUSDMilestoneTimeline() {
  const { data } = useQuery<ReserveData>({
    queryKey: ["qusdReserves"],
    queryFn: () => api.getQUSDReserves(),
    refetchInterval: 30_000,
  });

  const pct = data?.backing_percentage ?? 0;

  const milestones = [
    { year: "Y1-2", target: 5, label: "5% · Launch" },
    { year: "Y3-4", target: 15, label: "15% · Growth" },
    { year: "Y5-6", target: 30, label: "30% · Adoption" },
    { year: "Y7-9", target: 50, label: "50% · Maturity" },
    { year: "Y10+", target: 100, label: "100% · Full Backing" },
  ];

  return (
    <Card>
      <h3 className="mb-1 text-sm font-semibold text-text-secondary">
        Reserve Milestone Roadmap
      </h3>
      <p className="mb-4 text-xs text-text-secondary">
        10-year path to 100% QUSD backing
      </p>

      <div className="space-y-3">
        {milestones.map((m) => {
          const reached = pct >= m.target;
          const active = !reached && pct < m.target;
          const progress = active ? Math.min((pct / m.target) * 100, 100) : reached ? 100 : 0;

          return (
            <div key={m.year} className="flex items-center gap-3">
              {/* Indicator dot */}
              <div
                className={`h-3 w-3 flex-shrink-0 rounded-full border-2 ${
                  reached
                    ? "border-quantum-green bg-quantum-green"
                    : active
                      ? "border-golden-amber"
                      : "border-border-subtle"
                }`}
              />

              {/* Year label */}
              <span className="w-12 flex-shrink-0 font-[family-name:var(--font-code)] text-xs text-text-secondary">
                {m.year}
              </span>

              {/* Progress bar */}
              <div className="flex-1">
                <div className="h-2 w-full overflow-hidden rounded-full bg-bg-deep">
                  <motion.div
                    className={`h-full rounded-full ${
                      reached
                        ? "bg-quantum-green"
                        : "bg-gradient-to-r from-golden-amber to-quantum-green"
                    }`}
                    initial={{ width: 0 }}
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 1, delay: 0.1 }}
                  />
                </div>
              </div>

              {/* Label */}
              <span
                className={`w-36 flex-shrink-0 text-right text-xs ${
                  reached ? "text-quantum-green" : "text-text-secondary"
                }`}
              >
                {m.label}
              </span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function formatLargeNumber(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(2)}K`;
  return n.toFixed(2);
}
