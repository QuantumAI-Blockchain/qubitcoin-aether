// ─── QBC LAUNCHPAD — DNA Fingerprint Double-Helix SVG ─────────────────────────
"use client";

import React, { memo, useMemo } from "react";
import { L } from "./shared";

const BASE_COLORS = [L.dnaCyan, L.dnaGold, L.dnaViolet, L.dnaEmerald] as const;

interface DNAFingerprintProps {
  hash: string;
  size?: number;
  hasMint?: boolean;
  hasLockGap?: boolean;
  dilithiumVerified?: boolean;
}

const DNAFingerprint = memo(function DNAFingerprint({
  hash,
  size = 40,
  hasMint = false,
  hasLockGap = false,
  dilithiumVerified = false,
}: DNAFingerprintProps) {
  const basePairs = useMemo(() => {
    const pairs: Array<{ left: string; right: string; index: number }> = [];
    const normalized = hash.replace(/[^0-9a-fA-F]/g, "").padEnd(64, "0").slice(0, 64);
    for (let i = 0; i < 32; i++) {
      const byte = parseInt(normalized.slice(i * 2, i * 2 + 2), 16);
      const leftBits = (byte >> 6) & 0x03;
      const rightBits = (byte >> 4) & 0x03;
      pairs.push({
        left: BASE_COLORS[leftBits],
        right: BASE_COLORS[rightBits],
        index: i,
      });
    }
    return pairs;
  }, [hash]);

  const viewW = 40;
  const viewH = 80;
  const cx = viewW / 2;
  const ampX = 12;
  const yStart = 4;
  const yStep = (viewH - 8) / 31;
  const gapIndex = hasLockGap ? 16 : -1;
  const mintIndex = hasMint ? 24 : -1;

  return (
    <svg
      width={size}
      height={size * 2}
      viewBox={`0 0 ${viewW} ${viewH}`}
      style={{ overflow: "visible" }}
    >
      {/* Inject keyframes for rotation animation */}
      <defs>
        <style>{`
          @keyframes dnaRotate {
            0% { transform: rotateY(0deg); }
            100% { transform: rotateY(360deg); }
          }
          @keyframes dnaMintFlash {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
          }
        `}</style>
        {dilithiumVerified && (
          <filter id={`dna-glow-${hash.slice(0, 8)}`}>
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feFlood floodColor={L.glowCyan} floodOpacity="0.6" result="color" />
            <feComposite in="color" in2="blur" operator="in" result="shadow" />
            <feMerge>
              <feMergeNode in="shadow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        )}
      </defs>

      <g filter={dilithiumVerified ? `url(#dna-glow-${hash.slice(0, 8)})` : undefined}>
        {basePairs.map((bp, i) => {
          const y = yStart + i * yStep;
          const phase = (i / 32) * Math.PI * 4;
          const sinVal = Math.sin(phase);
          const cosVal = Math.cos(phase);
          const lx = cx + sinVal * ampX;
          const rx = cx - sinVal * ampX;
          const isGap = i === gapIndex || i === gapIndex + 1;
          const isMint = i === mintIndex;
          const depth = (cosVal + 1) / 2;
          const leftOpacity = 0.4 + depth * 0.6;
          const rightOpacity = 0.4 + (1 - depth) * 0.6;

          if (isGap) {
            return (
              <g key={i}>
                <circle cx={lx} cy={y} r={1.2} fill={bp.left} opacity={0.3} />
                <circle cx={rx} cy={y} r={1.2} fill={bp.right} opacity={0.3} />
              </g>
            );
          }

          return (
            <g key={i}>
              {/* Connecting rung */}
              <line
                x1={lx}
                y1={y}
                x2={rx}
                y2={y}
                stroke={bp.left}
                strokeOpacity={0.15}
                strokeWidth={0.5}
              />
              {/* Left strand node */}
              <circle
                cx={lx}
                cy={y}
                r={1.5}
                fill={bp.left}
                opacity={leftOpacity}
                style={
                  isMint
                    ? { animation: "dnaMintFlash 1s ease-in-out infinite" }
                    : undefined
                }
              />
              {/* Right strand node */}
              <circle
                cx={rx}
                cy={y}
                r={1.5}
                fill={bp.right}
                opacity={rightOpacity}
                style={
                  isMint
                    ? { animation: "dnaMintFlash 1s ease-in-out infinite" }
                    : undefined
                }
              />
            </g>
          );
        })}

        {/* Strand backbone lines (left) */}
        <polyline
          points={basePairs
            .map((_, i) => {
              const y = yStart + i * yStep;
              const phase = (i / 32) * Math.PI * 4;
              const x = cx + Math.sin(phase) * ampX;
              return `${x},${y}`;
            })
            .join(" ")}
          fill="none"
          stroke={L.glowCyan}
          strokeWidth={0.6}
          strokeOpacity={0.25}
        />

        {/* Strand backbone lines (right) */}
        <polyline
          points={basePairs
            .map((_, i) => {
              const y = yStart + i * yStep;
              const phase = (i / 32) * Math.PI * 4;
              const x = cx - Math.sin(phase) * ampX;
              return `${x},${y}`;
            })
            .join(" ")}
          fill="none"
          stroke={L.glowViolet}
          strokeWidth={0.6}
          strokeOpacity={0.25}
        />
      </g>
    </svg>
  );
});

export default DNAFingerprint;
