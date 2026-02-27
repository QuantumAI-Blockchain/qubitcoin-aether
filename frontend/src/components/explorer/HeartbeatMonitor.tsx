"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — Transaction Heartbeat Monitor (ECG-style SVG waveform)
   ───────────────────────────────────────────────────────────────────────── */

import { useEffect, useRef, useMemo, useCallback } from "react";
import { C, FONT, txTypeColor } from "./shared";
import type { Transaction } from "./types";

interface Props {
  transactions: Transaction[];
  width?: number;
  height?: number;
}

export function HeartbeatMonitor({
  transactions,
  width = 800,
  height = 120,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);

  // Take the last 60 transactions for the waveform
  const txSlice = useMemo(
    () => transactions.slice(-60),
    [transactions]
  );

  const drawFrame = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const cw = width * dpr;
    const ch = height * dpr;
    if (canvas.width !== cw || canvas.height !== ch) {
      canvas.width = cw;
      canvas.height = ch;
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Clear
    ctx.clearRect(0, 0, width, height);

    // Background grid
    ctx.strokeStyle = `${C.border}40`;
    ctx.lineWidth = 0.5;
    for (let y = 0; y < height; y += 20) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
    for (let x = 0; x < width; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }

    if (txSlice.length === 0) return;

    const mid = height / 2;
    const segWidth = width / txSlice.length;

    // Draw the ECG-style waveform
    ctx.lineWidth = 1.5;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";

    // Main waveform path
    ctx.beginPath();
    ctx.strokeStyle = C.primary;

    for (let i = 0; i < txSlice.length; i++) {
      const tx = txSlice[i];
      const x = i * segWidth;

      // Amplitude based on log of value
      const amp = Math.min(
        Math.log10(Math.max(tx.value, 0.01) + 1) * 15,
        mid * 0.85
      );

      // ECG waveform shape per transaction
      const color = txTypeColor(tx.type);

      // Draw individual beat segment
      ctx.save();
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();

      // P wave (small bump)
      const pw = segWidth * 0.15;
      ctx.moveTo(x, mid);
      ctx.quadraticCurveTo(x + pw * 0.5, mid - amp * 0.15, x + pw, mid);

      // PR segment (flat)
      ctx.lineTo(x + segWidth * 0.2, mid);

      // QRS complex (sharp spike)
      const qx = x + segWidth * 0.2;
      ctx.lineTo(qx + segWidth * 0.05, mid + amp * 0.1); // Q dip
      ctx.lineTo(qx + segWidth * 0.15, mid - amp); // R peak
      ctx.lineTo(qx + segWidth * 0.25, mid + amp * 0.2); // S dip
      ctx.lineTo(qx + segWidth * 0.3, mid); // return to baseline

      // ST segment + T wave
      const tw = x + segWidth * 0.65;
      ctx.lineTo(tw, mid);
      ctx.quadraticCurveTo(
        tw + segWidth * 0.15,
        mid - amp * 0.25,
        tw + segWidth * 0.3,
        mid
      );

      // Flat to end
      ctx.lineTo(x + segWidth, mid);

      ctx.stroke();
      ctx.restore();

      // Glow effect on high-value transactions
      if (tx.value > 100) {
        ctx.save();
        ctx.strokeStyle = `${color}40`;
        ctx.lineWidth = 4;
        ctx.beginPath();
        const peakX = qx + segWidth * 0.15;
        ctx.moveTo(peakX - 2, mid - amp + 2);
        ctx.lineTo(peakX, mid - amp);
        ctx.lineTo(peakX + 2, mid - amp + 2);
        ctx.stroke();
        ctx.restore();
      }
    }

    // Draw baseline
    ctx.strokeStyle = `${C.textMuted}30`;
    ctx.lineWidth = 0.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, mid);
    ctx.lineTo(width, mid);
    ctx.stroke();
    ctx.setLineDash([]);

    // Scanline effect (animated glow) — continuous sweep
    const time = Date.now() % 4000;
    const scanX = (time / 4000) * width;
    const gradient = ctx.createLinearGradient(scanX - 60, 0, scanX, 0);
    gradient.addColorStop(0, "transparent");
    gradient.addColorStop(1, `${C.primary}30`);
    ctx.fillStyle = gradient;
    ctx.fillRect(scanX - 60, 0, 60, height);
  }, [txSlice, width, height]);

  // Continuous animation loop using requestAnimationFrame
  useEffect(() => {
    function loop() {
      drawFrame();
      rafRef.current = requestAnimationFrame(loop);
    }
    rafRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafRef.current);
  }, [drawFrame]);

  return (
    <div className="relative overflow-hidden rounded-lg border" style={{ borderColor: C.border }}>
      {/* Header */}
      <div
        className="flex items-center justify-between border-b px-3 py-1.5"
        style={{ background: C.surface, borderColor: C.border }}
      >
        <span
          className="text-[10px] uppercase tracking-widest"
          style={{ color: C.textMuted, fontFamily: FONT.heading }}
        >
          Transaction Heartbeat
        </span>
        <div className="flex items-center gap-3">
          {["transfer", "coinbase", "contract_call", "susy_swap"].map((t) => (
            <span key={t} className="flex items-center gap-1 text-[9px]" style={{ fontFamily: FONT.mono }}>
              <span
                className="inline-block h-1.5 w-1.5 rounded-full"
                style={{ background: txTypeColor(t) }}
              />
              <span style={{ color: C.textMuted }}>
                {t === "contract_call" ? "CALL" : t === "susy_swap" ? "SUSY" : t.toUpperCase()}
              </span>
            </span>
          ))}
        </div>
      </div>
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={`Transaction heartbeat monitor showing ECG-style waveform for the last ${txSlice.length} transactions`}
        style={{
          width,
          height,
          display: "block",
          background: `${C.bg}`,
        }}
      />
    </div>
  );
}
