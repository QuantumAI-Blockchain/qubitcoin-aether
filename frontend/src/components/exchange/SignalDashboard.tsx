// ─── QBC EXCHANGE — AetherTree Validator Consensus Panel ─────────────────────
// Split from QuantumIntelligence.tsx for lazy loading
"use client";

import React, { memo, useMemo } from "react";
import { useValidators, useAetherReasoning } from "./hooks";
import {
  X,
  FONT,
  panelStyle,
  panelHeaderStyle,
} from "./shared";

function consensusLabel(onlineCount: number, total: number): { label: string; color: string } {
  const ratio = onlineCount / total;
  if (ratio >= 0.9) return { label: "STRONG", color: X.glowEmerald };
  if (ratio >= 0.7) return { label: "MODERATE", color: X.glowAmber };
  return { label: "WEAK", color: X.glowCrimson };
}

function exchangeImpact(onlineCount: number, total: number): { label: string; color: string } {
  const ratio = onlineCount / total;
  if (ratio >= 0.9) return { label: "LOW RISK", color: X.glowEmerald };
  if (ratio >= 0.7) return { label: "MEDIUM RISK", color: X.glowAmber };
  return { label: "HIGH RISK", color: X.glowCrimson };
}

const validatorStatusColor: Record<string, string> = {
  online: X.glowEmerald,
  offline: X.glowCrimson,
  degraded: X.glowAmber,
};

const SignalDashboard = memo(function SignalDashboard() {
  const { data: validators } = useValidators();
  const { data: reasoningStats } = useAetherReasoning();

  const validatorList = validators ?? [];
  const total = validatorList.length || 11;
  const onlineCount = validatorList.filter((v) => v.status === "online").length;
  const degradedCount = validatorList.filter((v) => v.status === "degraded").length;
  const offlineCount = validatorList.filter((v) => v.status === "offline").length;

  // Enrich validator names with live reasoning stats if available
  const _reasoningInfo = reasoningStats
    ? `${reasoningStats.total_operations.toLocaleString()} reasoning ops across ${reasoningStats.blocks_processed.toLocaleString()} blocks`
    : null;

  const consensus = consensusLabel(onlineCount, total);
  const impact = exchangeImpact(onlineCount, total);

  const finalityStatus = useMemo(() => {
    if (onlineCount >= Math.ceil(total * 2 / 3)) return { label: "FINALIZED", color: X.glowEmerald };
    if (onlineCount >= Math.ceil(total / 2)) return { label: "PENDING", color: X.glowAmber };
    return { label: "AT RISK", color: X.glowCrimson };
  }, [onlineCount, total]);

  // Arrange 11 validators in a visually interesting grid: 4-3-4 pattern
  const rows = useMemo(() => {
    const items = validatorList.length > 0 ? validatorList : Array.from({ length: 11 }, (_, i) => ({
      name: `Node ${i}`,
      status: "online" as const,
      lastSeen: Date.now(),
    }));
    return [items.slice(0, 4), items.slice(4, 7), items.slice(7, 11)];
  }, [validatorList]);

  return (
    <div style={panelStyle}>
      <div style={panelHeaderStyle}>AetherTree Validator Consensus</div>
      <div style={{ padding: "12px 14px" }}>
        {/* Stats row */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 8,
            marginBottom: 12,
          }}
        >
          <div>
            <div style={{ fontFamily: FONT.body, fontSize: 10, color: X.textSecondary, marginBottom: 2 }}>
              Active Validators
            </div>
            <span style={{ fontFamily: FONT.mono, fontSize: 18, color: X.textPrimary }}>
              {onlineCount}
              <span style={{ fontSize: 13, color: X.textSecondary }}>/{total}</span>
            </span>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: FONT.body, fontSize: 10, color: X.textSecondary, marginBottom: 2 }}>
              Consensus Health
            </div>
            <span
              style={{
                fontFamily: FONT.display,
                fontSize: 13,
                letterSpacing: "0.06em",
                color: consensus.color,
              }}
            >
              {consensus.label}
            </span>
          </div>
          <div>
            <div style={{ fontFamily: FONT.body, fontSize: 10, color: X.textSecondary, marginBottom: 2 }}>
              Block Finality
            </div>
            <span
              style={{
                fontFamily: FONT.display,
                fontSize: 11,
                letterSpacing: "0.06em",
                padding: "2px 6px",
                borderRadius: 3,
                background: finalityStatus.color + "18",
                color: finalityStatus.color,
                border: `1px solid ${finalityStatus.color}30`,
              }}
            >
              {finalityStatus.label}
            </span>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: FONT.body, fontSize: 10, color: X.textSecondary, marginBottom: 2 }}>
              Exchange Impact
            </div>
            <span
              style={{
                fontFamily: FONT.display,
                fontSize: 11,
                letterSpacing: "0.06em",
                padding: "2px 6px",
                borderRadius: 3,
                background: impact.color + "18",
                color: impact.color,
                border: `1px solid ${impact.color}30`,
              }}
            >
              {impact.label}
            </span>
          </div>
        </div>

        {/* Validator grid: 4-3-4 */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 6,
            marginBottom: 10,
          }}
        >
          {rows.map((row, ri) => (
            <div key={ri} style={{ display: "flex", gap: 6, justifyContent: "center" }}>
              {row.map((v) => {
                const c = validatorStatusColor[v.status] ?? X.textSecondary;
                return (
                  <div
                    key={v.name}
                    title={`${v.name}: ${v.status}`}
                    style={{
                      width: 30,
                      height: 30,
                      borderRadius: 4,
                      background: c + "20",
                      border: `1px solid ${c}50`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      cursor: "default",
                      position: "relative",
                    }}
                  >
                    <div
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        background: c,
                        boxShadow: v.status === "online" ? `0 0 6px ${c}80` : "none",
                      }}
                    />
                    <span
                      style={{
                        position: "absolute",
                        bottom: -12,
                        fontFamily: FONT.mono,
                        fontSize: 7,
                        color: X.textSecondary,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {v.name.slice(0, 3).toUpperCase()}
                    </span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        {/* Legend */}
        <div
          style={{
            display: "flex",
            gap: 14,
            justifyContent: "center",
            marginTop: 16,
            paddingTop: 8,
            borderTop: `1px solid ${X.borderSubtle}`,
          }}
        >
          {[
            { label: `Online (${onlineCount})`, color: X.glowEmerald },
            { label: `Degraded (${degradedCount})`, color: X.glowAmber },
            { label: `Offline (${offlineCount})`, color: X.glowCrimson },
          ].map((item) => (
            <div key={item.label} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: item.color }} />
              <span style={{ fontFamily: FONT.mono, fontSize: 9, color: X.textSecondary }}>
                {item.label}
              </span>
            </div>
          ))}
        </div>

        {/* Live reasoning stats from Aether Mind */}
        {_reasoningInfo && (
          <div
            style={{
              marginTop: 8,
              textAlign: "center",
              fontFamily: FONT.mono,
              fontSize: 9,
              color: X.glowCyan,
              opacity: 0.7,
            }}
          >
            {_reasoningInfo}
          </div>
        )}
      </div>
    </div>
  );
});

export default SignalDashboard;
