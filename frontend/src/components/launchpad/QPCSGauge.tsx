// ─── QBC LAUNCHPAD — QPCS Radial Gauge ────────────────────────────────────────
"use client";

import React, { memo } from "react";
import type { QPCSComponents, QpcsGrade } from "./types";
import { gradeColor, gradeLabel, FONT, L } from "./shared";
import { QPCS_WEIGHTS } from "./config";

interface QPCSGaugeProps {
  score: number;
  grade: QpcsGrade;
  size?: number;
  showBreakdown?: boolean;
  components?: QPCSComponents;
}

const COMPONENT_KEYS: Array<keyof QPCSComponents> = [
  "liquidityLock",
  "teamVesting",
  "tokenomicsDistribution",
  "contractComplexity",
  "presaleStructure",
  "deployerHistory",
  "socialVerification",
  "susyAtDeploy",
];

const COMPONENT_COLORS: Record<keyof QPCSComponents, string> = {
  liquidityLock: L.glowCyan,
  teamVesting: L.glowGold,
  tokenomicsDistribution: L.glowEmerald,
  contractComplexity: L.glowViolet,
  presaleStructure: "#ec4899",
  deployerHistory: "#06b6d4",
  socialVerification: "#84cc16",
  susyAtDeploy: "#f97316",
};

const QPCSGauge = memo(function QPCSGauge({
  score,
  grade,
  size = 80,
  showBreakdown = false,
  components,
}: QPCSGaugeProps) {
  const color = gradeColor(grade);
  const label = gradeLabel(grade);
  const r = size * 0.38;
  const cx = size / 2;
  const cy = size / 2;
  const strokeW = size * 0.08;
  const circumference = 2 * Math.PI * r;
  const arcFraction = 0.75;
  const arcLength = circumference * arcFraction;
  const filledLength = arcLength * Math.min(1, score / 100);
  const startAngle = 135;
  const fontSize = size * 0.28;
  const labelSize = Math.max(7, size * 0.1);

  return (
    <div style={{ display: "inline-flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Background arc */}
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke={L.bgBase}
          strokeWidth={strokeW}
          strokeDasharray={`${arcLength} ${circumference - arcLength}`}
          strokeDashoffset={-circumference * ((1 - arcFraction) / 2) - circumference * 0.25}
          strokeLinecap="round"
          transform={`rotate(${startAngle} ${cx} ${cy})`}
          style={{ transform: `rotate(${startAngle}deg)`, transformOrigin: `${cx}px ${cy}px` }}
        />

        {/* Filled arc */}
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={strokeW}
          strokeDasharray={`${filledLength} ${circumference - filledLength}`}
          strokeDashoffset={-circumference * ((1 - arcFraction) / 2) - circumference * 0.25}
          strokeLinecap="round"
          style={{
            transform: `rotate(${startAngle}deg)`,
            transformOrigin: `${cx}px ${cy}px`,
            filter: `drop-shadow(0 0 4px ${color}60)`,
            transition: "stroke-dasharray 0.6s ease",
          }}
        />

        {/* Score text */}
        <text
          x={cx}
          y={cy - 2}
          textAnchor="middle"
          dominantBaseline="central"
          fill={color}
          fontFamily={FONT.display}
          fontSize={fontSize}
          fontWeight="bold"
        >
          {Math.round(score)}
        </text>

        {/* Grade label */}
        <text
          x={cx}
          y={cy + fontSize * 0.7}
          textAnchor="middle"
          dominantBaseline="central"
          fill={color}
          fontFamily={FONT.display}
          fontSize={labelSize}
          letterSpacing="0.05em"
          opacity={0.8}
        >
          {label}
        </text>
      </svg>

      {/* Breakdown bars */}
      {showBreakdown && components && (
        <div style={{ width: "100%", maxWidth: 220, display: "flex", flexDirection: "column", gap: 3 }}>
          {COMPONENT_KEYS.map((key) => {
            const value = components[key];
            const config = QPCS_WEIGHTS[key];
            const barColor = COMPONENT_COLORS[key];
            const pct = Math.min(100, (value / config.max) * 100);

            return (
              <div key={key} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span
                  style={{
                    fontFamily: FONT.mono,
                    fontSize: 9,
                    color: L.textSecondary,
                    width: 80,
                    flexShrink: 0,
                    textAlign: "right",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {config.label}
                </span>

                <div
                  style={{
                    flex: 1,
                    height: 4,
                    borderRadius: 2,
                    background: L.bgBase,
                    overflow: "hidden",
                    position: "relative",
                  }}
                >
                  <div
                    style={{
                      width: `${pct}%`,
                      height: "100%",
                      borderRadius: 2,
                      background: barColor,
                      boxShadow: `0 0 4px ${barColor}40`,
                      transition: "width 0.4s ease",
                    }}
                  />
                </div>

                <span
                  style={{
                    fontFamily: FONT.mono,
                    fontSize: 9,
                    color: L.textMuted,
                    width: 32,
                    flexShrink: 0,
                    textAlign: "right",
                  }}
                >
                  {value}/{config.max}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
});

export default QPCSGauge;
