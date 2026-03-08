"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — Chain Heartbeat Monitor

   Live ECG-style visualization that pulses with block mining (~3.3s)
   and transaction activity. Shows the blockchain's "vital signs."
   ───────────────────────────────────────────────────────────────────────── */

import { useEffect, useRef, useMemo, useCallback, useState } from "react";
import { C, FONT, txTypeColor, formatNumber } from "./shared";
import type { Transaction } from "./types";

interface Props {
  transactions: Transaction[];
  height?: number;
  blockHeight?: number;
  blockTime?: number;
}

// Heartbeat event stored in the rolling buffer
interface Beat {
  time: number;      // Date.now() when the beat occurred
  amplitude: number; // 0-1 normalized
  color: string;
  type: "block" | "tx";
  label: string;
}

const MAX_BEATS = 80;
const BLOCK_INTERVAL = 3300; // 3.3 seconds

export function HeartbeatMonitor({
  transactions,
  height = 130,
  blockHeight = 0,
  blockTime = 3.3,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number>(0);
  const [width, setWidth] = useState(800);

  // Rolling beat buffer — persists across renders
  const beatsRef = useRef<Beat[]>([]);
  const lastBlockRef = useRef<number>(0);
  const lastTxCountRef = useRef<number>(0);
  const blockPulseRef = useRef<number>(0); // timestamp of last block pulse

  // Track container width
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) setWidth(entry.contentRect.width);
    });
    ro.observe(el);
    setWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  // Detect new blocks
  useEffect(() => {
    if (blockHeight > 0 && blockHeight !== lastBlockRef.current) {
      lastBlockRef.current = blockHeight;
      blockPulseRef.current = Date.now();
      beatsRef.current.push({
        time: Date.now(),
        amplitude: 1.0,
        color: C.success,
        type: "block",
        label: `#${blockHeight}`,
      });
      if (beatsRef.current.length > MAX_BEATS) {
        beatsRef.current = beatsRef.current.slice(-MAX_BEATS);
      }
    }
  }, [blockHeight]);

  // Detect new transactions
  useEffect(() => {
    if (transactions.length > lastTxCountRef.current && lastTxCountRef.current > 0) {
      const newTxs = transactions.slice(lastTxCountRef.current);
      for (const tx of newTxs.slice(-5)) { // max 5 new tx beats per update
        beatsRef.current.push({
          time: Date.now(),
          amplitude: Math.min(0.7, Math.log10(Math.max(tx.value, 0.01) + 1) * 0.2 + 0.15),
          color: txTypeColor(tx.type),
          type: "tx",
          label: tx.type === "coinbase" ? "COINBASE" : "TX",
        });
      }
      if (beatsRef.current.length > MAX_BEATS) {
        beatsRef.current = beatsRef.current.slice(-MAX_BEATS);
      }
    }
    lastTxCountRef.current = transactions.length;
  }, [transactions]);

  // Simulate block pulses at ~3.3s intervals if we haven't seen a real one
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      const timeSinceLastPulse = now - blockPulseRef.current;
      // Only auto-pulse if no real block arrived recently
      if (timeSinceLastPulse > BLOCK_INTERVAL * 1.5) {
        blockPulseRef.current = now;
        beatsRef.current.push({
          time: now,
          amplitude: 0.85,
          color: C.primary,
          type: "block",
          label: "SYNC",
        });
        if (beatsRef.current.length > MAX_BEATS) {
          beatsRef.current = beatsRef.current.slice(-MAX_BEATS);
        }
      }
    }, BLOCK_INTERVAL);
    return () => clearInterval(interval);
  }, []);

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
    ctx.clearRect(0, 0, width, height);

    const now = Date.now();
    const mid = height / 2;
    const windowMs = 20000; // Show last 20 seconds of beats

    // Background grid
    ctx.strokeStyle = `${C.border}30`;
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

    // Draw baseline
    ctx.strokeStyle = `${C.textMuted}20`;
    ctx.lineWidth = 0.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, mid);
    ctx.lineTo(width, mid);
    ctx.stroke();
    ctx.setLineDash([]);

    // Build continuous waveform from beats
    const beats = beatsRef.current;

    // Draw the continuous ECG line
    ctx.lineWidth = 1.5;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";

    // Sample the waveform at pixel resolution
    const samples = width;
    const waveform: { y: number; color: string }[] = [];

    for (let px = 0; px < samples; px++) {
      const t = now - windowMs + (px / samples) * windowMs;
      let y = mid;
      let beatColor: string = C.primary;

      // Find beats near this time and compute their waveform contribution
      for (const beat of beats) {
        const dt = t - beat.time;
        const beatDurationMs = beat.type === "block" ? 400 : 250;

        if (dt >= -50 && dt <= beatDurationMs) {
          const progress = Math.max(0, dt) / beatDurationMs;
          const amp = beat.amplitude * mid * 0.85;

          // ECG shape based on progress through the beat
          let deflection = 0;
          if (progress < 0.08) {
            // P wave — small bump
            const p = progress / 0.08;
            deflection = Math.sin(p * Math.PI) * amp * 0.12;
          } else if (progress < 0.15) {
            // PR segment — flat
            deflection = 0;
          } else if (progress < 0.2) {
            // Q dip
            const p = (progress - 0.15) / 0.05;
            deflection = -p * amp * 0.1;
          } else if (progress < 0.35) {
            // R peak — sharp spike up
            const p = (progress - 0.2) / 0.15;
            if (p < 0.5) {
              deflection = -amp * 0.1 + (amp * 1.1) * (p / 0.5);
            } else {
              deflection = amp * 1.0 * (1 - (p - 0.5) / 0.5);
            }
          } else if (progress < 0.45) {
            // S dip
            const p = (progress - 0.35) / 0.1;
            deflection = -Math.sin(p * Math.PI) * amp * 0.15;
          } else if (progress < 0.55) {
            // ST segment — flat
            deflection = 0;
          } else if (progress < 0.75) {
            // T wave — rounded bump
            const p = (progress - 0.55) / 0.2;
            deflection = Math.sin(p * Math.PI) * amp * 0.2;
          } else {
            // Return to baseline
            deflection = 0;
          }

          if (Math.abs(deflection) > Math.abs(y - mid)) {
            y = mid - deflection;
            beatColor = beat.color;
          }
        }
      }

      waveform.push({ y, color: beatColor });
    }

    // Draw waveform with color segments
    if (waveform.length > 1) {
      for (let i = 1; i < waveform.length; i++) {
        ctx.strokeStyle = waveform[i].color;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(i - 1, waveform[i - 1].y);
        ctx.lineTo(i, waveform[i].y);
        ctx.stroke();

        // Glow on peaks (far from baseline)
        const deflection = Math.abs(waveform[i].y - mid);
        if (deflection > mid * 0.4) {
          ctx.save();
          ctx.strokeStyle = `${waveform[i].color}30`;
          ctx.lineWidth = 6;
          ctx.beginPath();
          ctx.moveTo(i - 1, waveform[i - 1].y);
          ctx.lineTo(i, waveform[i].y);
          ctx.stroke();
          ctx.restore();
        }
      }
    }

    // Draw beat labels at beat positions
    ctx.font = `9px ${FONT.mono}`;
    ctx.textAlign = "center";
    for (const beat of beats) {
      const age = now - beat.time;
      if (age > windowMs || age < 0) continue;
      const px = ((beat.time - (now - windowMs)) / windowMs) * width;
      const opacity = Math.max(0.2, 1 - age / windowMs);

      if (beat.type === "block") {
        // Block marker — small label above peak
        ctx.fillStyle = `${beat.color}${Math.floor(opacity * 255).toString(16).padStart(2, "0")}`;
        ctx.fillText(beat.label, px + 20, 12);

        // Vertical marker line
        ctx.save();
        ctx.strokeStyle = `${beat.color}15`;
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 3]);
        ctx.beginPath();
        ctx.moveTo(px + 20, 16);
        ctx.lineTo(px + 20, height - 4);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.restore();
      }
    }

    // Pulse indicator (right edge — shows time since last beat)
    const timeSinceLastBeat = now - blockPulseRef.current;
    const pulsePhase = (timeSinceLastBeat % BLOCK_INTERVAL) / BLOCK_INTERVAL;
    const pulseSize = 4 + Math.sin(pulsePhase * Math.PI * 2) * 2;
    const pulseAlpha = 0.3 + (1 - pulsePhase) * 0.7;

    ctx.save();
    ctx.beginPath();
    ctx.arc(width - 12, 12, pulseSize, 0, Math.PI * 2);
    ctx.fillStyle = `${C.success}${Math.floor(pulseAlpha * 255).toString(16).padStart(2, "0")}`;
    ctx.fill();
    // Outer ring
    ctx.beginPath();
    ctx.arc(width - 12, 12, pulseSize + 3, 0, Math.PI * 2);
    ctx.strokeStyle = `${C.success}${Math.floor(pulseAlpha * 100).toString(16).padStart(2, "0")}`;
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.restore();

    // Scanline sweep — synced to block interval
    const scanProgress = pulsePhase;
    const scanX = scanProgress * width;
    const scanGrad = ctx.createLinearGradient(scanX - 40, 0, scanX, 0);
    scanGrad.addColorStop(0, "transparent");
    scanGrad.addColorStop(1, `${C.primary}18`);
    ctx.fillStyle = scanGrad;
    ctx.fillRect(scanX - 40, 0, 40, height);
  }, [width, height]);

  // Animation loop
  useEffect(() => {
    function loop() {
      drawFrame();
      rafRef.current = requestAnimationFrame(loop);
    }
    rafRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafRef.current);
  }, [drawFrame]);

  // Stats for header
  const txCount = transactions.length;
  const recentBlocks = beatsRef.current.filter((b) => b.type === "block" && Date.now() - b.time < 60000).length;

  return (
    <div ref={containerRef} className="relative overflow-hidden rounded-lg border" style={{ borderColor: C.border }}>
      {/* Header */}
      <div
        className="flex items-center justify-between border-b px-3 py-1.5"
        style={{ background: C.surface, borderColor: C.border }}
      >
        <div className="flex items-center gap-2">
          <span
            className="text-[10px] uppercase tracking-widest"
            style={{ color: C.textMuted, fontFamily: FONT.heading }}
          >
            Chain Heartbeat
          </span>
          {blockHeight > 0 && (
            <span className="text-[10px]" style={{ color: C.success, fontFamily: FONT.mono }}>
              #{formatNumber(blockHeight)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1 text-[9px]" style={{ fontFamily: FONT.mono }}>
            <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: C.success }} />
            <span style={{ color: C.textMuted }}>BLOCK</span>
          </span>
          <span className="flex items-center gap-1 text-[9px]" style={{ fontFamily: FONT.mono }}>
            <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: C.primary }} />
            <span style={{ color: C.textMuted }}>TX</span>
          </span>
          <span className="flex items-center gap-1 text-[9px]" style={{ fontFamily: FONT.mono }}>
            <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: C.secondary }} />
            <span style={{ color: C.textMuted }}>CONTRACT</span>
          </span>
          <span className="text-[9px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
            {blockTime.toFixed(1)}s
          </span>
        </div>
      </div>
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={`Chain heartbeat monitor — block ${blockHeight}, ${txCount} transactions`}
        style={{
          width: "100%",
          height,
          display: "block",
          background: C.bg,
        }}
      />
    </div>
  );
}
