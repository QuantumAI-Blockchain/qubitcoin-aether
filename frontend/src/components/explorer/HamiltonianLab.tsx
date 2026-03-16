"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — Hamiltonian Research Lab

   Live visualization of SUSY Hamiltonians mined on every block.
   Displays energy landscapes, Pauli decomposition heatmaps,
   eigenspectra, and IPFS archive links — all from live chain data.
   ───────────────────────────────────────────────────────────────────────── */

import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Atom, Zap, TrendingDown, Database, ExternalLink,
  ChevronDown, ChevronRight, Layers, Grid3x3, BarChart3,
  Activity, Cpu, Hash,
} from "lucide-react";
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  Cell, ReferenceLine, ScatterChart, Scatter, ZAxis,
} from "recharts";
import { useHamiltonianSolutions, useHamiltonianDetail } from "./hooks";
import { useExplorerStore } from "./store";
import {
  C, FONT, LoadingSpinner, Panel, SectionHeader, StatCard,
  formatNumber, truncHash,
} from "./shared";
import type { HamiltonianSolution } from "./types";

/* ── Pauli color map ─────────────────────────────────────────────────── */

const PAULI_COLORS: Record<string, string> = {
  I: "#1a2744",   // dim — identity
  X: "#00d4ff",   // cyan — bit flip
  Y: "#7c3aed",   // violet — phase+flip
  Z: "#f59e0b",   // amber — phase flip
};

const PAULI_LABELS: Record<string, string> = {
  I: "Identity",
  X: "Bit Flip (X)",
  Y: "Phase+Flip (Y)",
  Z: "Phase Flip (Z)",
};

/* ── Custom Tooltip ──────────────────────────────────────────────────── */

function LabTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: number; name: string; color: string }>;
  label?: string | number;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded border px-3 py-2"
      style={{
        background: C.surface,
        borderColor: C.border,
        fontFamily: FONT.mono,
        fontSize: 11,
      }}
    >
      <div style={{ color: C.textMuted, marginBottom: 4 }}>Block {label}</div>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2">
          <span style={{ color: p.color }}>{p.name}:</span>
          <span style={{ color: C.textPrimary }}>{typeof p.value === "number" ? p.value.toFixed(6) : p.value}</span>
        </div>
      ))}
    </div>
  );
}

/* ── Pauli Decomposition Visual ──────────────────────────────────────── */

function PauliDecomposition({ hamiltonian }: { hamiltonian: [string, number][] }) {
  if (!hamiltonian?.length) return null;

  const maxCoeff = Math.max(...hamiltonian.map(([, c]) => Math.abs(c)));

  return (
    <div className="space-y-2">
      <div
        className="text-[10px] uppercase tracking-widest"
        style={{ color: C.textMuted, fontFamily: FONT.heading }}
      >
        Pauli Decomposition
      </div>
      {hamiltonian.map(([pauliStr, coeff], idx) => (
        <div key={idx} className="flex items-center gap-2">
          {/* Pauli string with colored letters */}
          <div className="flex gap-0.5" style={{ fontFamily: FONT.mono, fontSize: 14 }}>
            {pauliStr.split("").map((ch, qi) => (
              <span
                key={qi}
                className="flex h-7 w-7 items-center justify-center rounded"
                style={{
                  background: `${PAULI_COLORS[ch] || C.border}30`,
                  color: PAULI_COLORS[ch] || C.textMuted,
                  border: `1px solid ${PAULI_COLORS[ch] || C.border}60`,
                  fontWeight: ch !== "I" ? "bold" : "normal",
                }}
                title={`Qubit ${qi}: ${PAULI_LABELS[ch] || ch}`}
              >
                {ch}
              </span>
            ))}
          </div>

          {/* Coefficient bar */}
          <div className="flex flex-1 items-center gap-2">
            <div
              className="h-3 overflow-hidden rounded-full"
              style={{ background: `${C.border}30`, flex: 1 }}
            >
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{
                  width: `${(Math.abs(coeff) / maxCoeff) * 100}%`,
                  background: coeff >= 0
                    ? `linear-gradient(90deg, ${C.primary}80, ${C.primary})`
                    : `linear-gradient(90deg, ${C.error}80, ${C.error})`,
                }}
              />
            </div>
            <span
              className="w-20 text-right text-[11px]"
              style={{
                fontFamily: FONT.mono,
                color: coeff >= 0 ? C.primary : C.error,
              }}
            >
              {coeff >= 0 ? "+" : ""}{coeff.toFixed(4)}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Matrix Heatmap (Canvas) ─────────────────────────────────────────── */

function MatrixHeatmap({ matrixReal, dim }: { matrixReal: number[]; dim: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !matrixReal?.length) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const size = 256;
    canvas.width = size;
    canvas.height = size;
    const cellSize = size / dim;

    const maxVal = Math.max(...matrixReal.map(Math.abs), 0.001);

    for (let i = 0; i < dim; i++) {
      for (let j = 0; j < dim; j++) {
        const val = matrixReal[i * dim + j];
        const norm = val / maxVal; // -1 to 1

        let r: number, g: number, b: number;
        if (norm >= 0) {
          // Positive: black → cyan
          r = 0;
          g = Math.floor(norm * 212);
          b = Math.floor(norm * 255);
        } else {
          // Negative: black → magenta
          r = Math.floor(-norm * 200);
          g = 0;
          b = Math.floor(-norm * 180);
        }

        ctx.fillStyle = `rgb(${r},${g},${b})`;
        ctx.fillRect(j * cellSize, i * cellSize, cellSize, cellSize);

        // Grid lines
        ctx.strokeStyle = `${C.border}40`;
        ctx.lineWidth = 0.5;
        ctx.strokeRect(j * cellSize, i * cellSize, cellSize, cellSize);
      }
    }

    // Diagonal highlight
    ctx.strokeStyle = `${C.accent}40`;
    ctx.lineWidth = 1;
    for (let i = 0; i < dim; i++) {
      ctx.strokeRect(i * cellSize, i * cellSize, cellSize, cellSize);
    }
  }, [matrixReal, dim]);

  return (
    <div className="space-y-2">
      <div
        className="text-[10px] uppercase tracking-widest"
        style={{ color: C.textMuted, fontFamily: FONT.heading }}
      >
        Hamiltonian Matrix ({dim}&times;{dim})
      </div>
      <div className="relative inline-block">
        <canvas
          ref={canvasRef}
          className="rounded border"
          style={{
            borderColor: C.border,
            width: 256,
            height: 256,
            imageRendering: "pixelated",
          }}
        />
        {/* Axis labels */}
        <div
          className="absolute -bottom-5 left-0 right-0 text-center text-[9px]"
          style={{ color: C.textMuted, fontFamily: FONT.mono }}
        >
          Basis States |0...0&rang; to |1...1&rang;
        </div>
      </div>
      {/* Color legend */}
      <div className="flex items-center gap-3 text-[9px]" style={{ fontFamily: FONT.mono }}>
        <span style={{ color: "#c800b4" }}>Negative</span>
        <div
          className="h-2 flex-1 rounded"
          style={{
            background: "linear-gradient(90deg, #c800b4, #000, #00d4ff)",
          }}
        />
        <span style={{ color: C.primary }}>Positive</span>
      </div>
    </div>
  );
}

/* ── Eigenspectrum ───────────────────────────────────────────────────── */

function Eigenspectrum({ eigenvalues, energy }: { eigenvalues: number[]; energy: number | null }) {
  if (!eigenvalues?.length) return null;

  const data = eigenvalues.map((e, i) => ({
    index: i,
    label: `|${i.toString(2).padStart(Math.ceil(Math.log2(eigenvalues.length)), "0")}\u27E9`,
    energy: e,
    isGround: i === 0,
  }));

  return (
    <div className="space-y-2">
      <div
        className="text-[10px] uppercase tracking-widest"
        style={{ color: C.textMuted, fontFamily: FONT.heading }}
      >
        Eigenspectrum ({eigenvalues.length} states)
      </div>
      <div style={{ height: 200 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
            <CartesianGrid stroke={`${C.border}30`} vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 8, fill: C.textMuted, fontFamily: FONT.mono }}
              interval={0}
              angle={-45}
              textAnchor="end"
              height={40}
            />
            <YAxis
              tick={{ fontSize: 9, fill: C.textMuted, fontFamily: FONT.mono }}
              width={50}
              label={{
                value: "Energy",
                angle: -90,
                position: "insideLeft",
                style: { fontSize: 9, fill: C.textMuted, fontFamily: FONT.mono },
              }}
            />
            <Tooltip content={<LabTooltip />} />
            {energy !== null && (
              <ReferenceLine
                y={energy}
                stroke={C.success}
                strokeDasharray="4 4"
                label={{
                  value: `VQE: ${energy.toFixed(4)}`,
                  position: "right",
                  style: { fontSize: 9, fill: C.success, fontFamily: FONT.mono },
                }}
              />
            )}
            <Bar dataKey="energy" name="Eigenvalue" radius={[2, 2, 0, 0]}>
              {data.map((d, i) => (
                <Cell
                  key={i}
                  fill={d.isGround ? C.success : `${C.secondary}${i === 0 ? "" : "80"}`}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="flex items-center gap-4 text-[9px]" style={{ fontFamily: FONT.mono }}>
        <span>
          <span className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: C.success }} />
          <span style={{ color: C.textMuted }}>Ground State: </span>
          <span style={{ color: C.success }}>{eigenvalues[0].toFixed(6)}</span>
        </span>
        <span>
          <span className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: C.secondary }} />
          <span style={{ color: C.textMuted }}>Energy Gap: </span>
          <span style={{ color: C.accent }}>
            {eigenvalues.length > 1
              ? (eigenvalues[1] - eigenvalues[0]).toFixed(6)
              : "N/A"}
          </span>
        </span>
      </div>
    </div>
  );
}

/* ── Energy Landscape Chart ──────────────────────────────────────────── */

function EnergyLandscape({ solutions, onSelect }: {
  solutions: HamiltonianSolution[];
  onSelect: (height: number) => void;
}) {
  const data = useMemo(() => {
    return [...solutions]
      .sort((a, b) => a.block_height - b.block_height)
      .map((s) => ({
        block: s.block_height,
        energy: s.energy,
        groundState: s.eigenvalues?.[0] ?? null,
        gap: s.eigenvalues && s.eigenvalues.length > 1
          ? s.eigenvalues[1] - s.eigenvalues[0]
          : null,
      }));
  }, [solutions]);

  return (
    <div style={{ height: 280 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          onClick={(e: Record<string, unknown>) => {
            const payload = e?.activePayload as Array<{ payload: { block: number } }> | undefined;
            if (payload?.[0]?.payload?.block) {
              onSelect(payload[0].payload.block);
            }
          }}
          style={{ cursor: "pointer" }}
        >
          <defs>
            <linearGradient id="energyGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={C.secondary} stopOpacity={0.4} />
              <stop offset="100%" stopColor={C.secondary} stopOpacity={0} />
            </linearGradient>
            <linearGradient id="groundGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={C.success} stopOpacity={0.3} />
              <stop offset="100%" stopColor={C.success} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={`${C.border}30`} />
          <XAxis
            dataKey="block"
            tick={{ fontSize: 9, fill: C.textMuted, fontFamily: FONT.mono }}
            tickFormatter={(v: number) => `#${v}`}
          />
          <YAxis
            tick={{ fontSize: 9, fill: C.textMuted, fontFamily: FONT.mono }}
            width={60}
            label={{
              value: "Energy",
              angle: -90,
              position: "insideLeft",
              style: { fontSize: 9, fill: C.textMuted, fontFamily: FONT.mono },
            }}
          />
          <Tooltip content={<LabTooltip />} />
          <Area
            type="monotone"
            dataKey="groundState"
            name="Ground State"
            stroke={C.success}
            fill="url(#groundGrad)"
            strokeWidth={1.5}
            dot={false}
            connectNulls
          />
          <Area
            type="monotone"
            dataKey="energy"
            name="VQE Energy"
            stroke={C.secondary}
            fill="url(#energyGrad)"
            strokeWidth={2}
            dot={false}
            connectNulls
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ── Solution Feed (live block list) ─────────────────────────────────── */

function SolutionFeed({ solutions, selectedHeight, onSelect }: {
  solutions: HamiltonianSolution[];
  selectedHeight: number | null;
  onSelect: (height: number) => void;
}) {
  return (
    <div className="space-y-1" style={{ maxHeight: 480, overflowY: "auto" }}>
      {solutions.map((s) => (
        <button
          key={s.block_height}
          onClick={() => onSelect(s.block_height)}
          className="flex w-full items-center gap-3 rounded px-3 py-2 text-left transition-colors"
          style={{
            background: selectedHeight === s.block_height
              ? `${C.secondary}20`
              : "transparent",
            borderLeft: selectedHeight === s.block_height
              ? `3px solid ${C.secondary}`
              : "3px solid transparent",
          }}
        >
          <div className="flex-shrink-0">
            <Atom size={14} style={{ color: C.secondary }} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span
                className="text-[11px] font-bold"
                style={{ color: C.primary, fontFamily: FONT.mono }}
              >
                #{s.block_height}
              </span>
              <span
                className="text-[10px]"
                style={{ color: C.textMuted, fontFamily: FONT.mono }}
              >
                {s.hamiltonian?.length || 0} terms
              </span>
            </div>
            <div className="flex items-center gap-3 text-[10px]" style={{ fontFamily: FONT.mono }}>
              <span style={{ color: C.textSecondary }}>
                E = <span style={{ color: s.energy !== null && s.energy < 0 ? C.success : C.accent }}>
                  {s.energy?.toFixed(6) ?? "N/A"}
                </span>
              </span>
              <span style={{ color: C.textMuted }}>
                {truncHash(s.miner_address, 6)}
              </span>
            </div>
          </div>
          {/* Mini eigenspectrum spark */}
          {s.eigenvalues && (
            <div className="flex h-6 items-end gap-px">
              {s.eigenvalues.slice(0, 8).map((e, i) => {
                const maxE = Math.max(...s.eigenvalues!.map(Math.abs));
                const h = Math.max(2, (Math.abs(e) / maxE) * 24);
                return (
                  <div
                    key={i}
                    className="w-1 rounded-t"
                    style={{
                      height: h,
                      background: i === 0 ? C.success : `${C.secondary}80`,
                    }}
                  />
                );
              })}
            </div>
          )}
        </button>
      ))}
    </div>
  );
}

/* ── Detail Panel ────────────────────────────────────────────────────── */

function DetailPanel({ height }: { height: number }) {
  const { data: detail, isLoading } = useHamiltonianDetail(height);

  if (isLoading) return <LoadingSpinner />;
  if (!detail || "error" in detail) {
    return (
      <div className="p-4 text-center text-[11px]" style={{ color: C.textMuted }}>
        No Hamiltonian data for block #{height}
      </div>
    );
  }

  const dim = 2 ** detail.qubit_count;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-5"
    >
      {/* Block header */}
      <div className="flex items-center justify-between">
        <div>
          <div
            className="text-lg font-bold"
            style={{ color: C.textPrimary, fontFamily: FONT.heading }}
          >
            Block #{detail.block_height}
          </div>
          <div className="text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
            Miner: {detail.miner_address}
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px]" style={{ color: C.textMuted }}>
            {detail.qubit_count}-qubit SUSY Hamiltonian
          </div>
          {detail.ipfs_cid && (
            <a
              href={`https://ipfs.io/ipfs/${detail.ipfs_cid}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-[10px]"
              style={{ color: C.primary }}
            >
              <ExternalLink size={10} />
              IPFS: {truncHash(detail.ipfs_cid, 8)}
            </a>
          )}
        </div>
      </div>

      {/* VQE Result */}
      <div
        className="flex items-center gap-4 rounded border px-4 py-3"
        style={{ borderColor: C.border, background: `${C.surface}80` }}
      >
        <div>
          <div className="text-[9px] uppercase tracking-widest" style={{ color: C.textMuted }}>
            VQE Achieved Energy
          </div>
          <div
            className="text-xl font-bold"
            style={{
              color: detail.energy !== null && detail.energy < 0 ? C.success : C.accent,
              fontFamily: FONT.mono,
            }}
          >
            {detail.energy?.toFixed(8) ?? "N/A"}
          </div>
        </div>
        {detail.eigenvalues && (
          <>
            <div className="h-8 border-l" style={{ borderColor: C.border }} />
            <div>
              <div className="text-[9px] uppercase tracking-widest" style={{ color: C.textMuted }}>
                Exact Ground State
              </div>
              <div
                className="text-xl font-bold"
                style={{ color: C.secondary, fontFamily: FONT.mono }}
              >
                {detail.eigenvalues[0].toFixed(8)}
              </div>
            </div>
            <div className="h-8 border-l" style={{ borderColor: C.border }} />
            <div>
              <div className="text-[9px] uppercase tracking-widest" style={{ color: C.textMuted }}>
                VQE Accuracy
              </div>
              <div
                className="text-xl font-bold"
                style={{ color: C.primary, fontFamily: FONT.mono }}
              >
                {detail.energy !== null && detail.eigenvalues[0] !== 0
                  ? (100 * (1 - Math.abs((detail.energy - detail.eigenvalues[0]) / detail.eigenvalues[0]))).toFixed(2) + "%"
                  : "N/A"
                }
              </div>
            </div>
          </>
        )}
      </div>

      {/* Two-column layout: Pauli + Matrix */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <PauliDecomposition hamiltonian={detail.hamiltonian} />
        </Panel>
        {detail.matrix_real && (
          <Panel>
            <MatrixHeatmap matrixReal={detail.matrix_real} dim={dim} />
          </Panel>
        )}
      </div>

      {/* Eigenspectrum */}
      {detail.eigenvalues && (
        <Panel>
          <Eigenspectrum eigenvalues={detail.eigenvalues} energy={detail.energy} />
        </Panel>
      )}

      {/* VQE Parameters */}
      {detail.params && detail.params.length > 0 && (
        <Panel>
          <div
            className="text-[10px] uppercase tracking-widest"
            style={{ color: C.textMuted, fontFamily: FONT.heading }}
          >
            VQE Circuit Parameters ({detail.params.length} angles)
          </div>
          <div className="mt-2 flex flex-wrap gap-1">
            {detail.params.map((p, i) => (
              <span
                key={i}
                className="rounded px-2 py-0.5 text-[10px]"
                style={{
                  background: `${C.border}40`,
                  color: C.textSecondary,
                  fontFamily: FONT.mono,
                }}
              >
                &theta;{i}: {typeof p === "number" ? p.toFixed(4) : p}
              </span>
            ))}
          </div>
        </Panel>
      )}
    </motion.div>
  );
}

/* ── Main Export: Hamiltonian Lab ─────────────────────────────────────── */

export function HamiltonianLab() {
  const navigate = useExplorerStore((s) => s.navigate);
  const { data, isLoading, error } = useHamiltonianSolutions(100);
  const [selectedHeight, setSelectedHeight] = useState<number | null>(null);

  const solutions = data?.solutions ?? [];
  const archiveStats = data?.archive_stats ?? {};

  // Auto-select first solution
  useEffect(() => {
    if (solutions.length > 0 && selectedHeight === null) {
      setSelectedHeight(solutions[0].block_height);
    }
  }, [solutions, selectedHeight]);

  // Computed stats
  const stats = useMemo(() => {
    if (!solutions.length) return { avgEnergy: 0, minEnergy: 0, maxEnergy: 0, avgGap: 0 };
    const energies = solutions.filter((s) => s.energy !== null).map((s) => s.energy as number);
    const gaps = solutions
      .filter((s) => s.eigenvalues && s.eigenvalues.length > 1)
      .map((s) => s.eigenvalues![1] - s.eigenvalues![0]);
    return {
      avgEnergy: energies.reduce((a, b) => a + b, 0) / (energies.length || 1),
      minEnergy: energies.length ? Math.min(...energies) : 0,
      maxEnergy: energies.length ? Math.max(...energies) : 0,
      avgGap: gaps.length ? gaps.reduce((a, b) => a + b, 0) / gaps.length : 0,
    };
  }, [solutions]);

  if (isLoading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center">
        <Atom size={48} style={{ color: C.textMuted, margin: "0 auto 16px" }} />
        <div style={{ color: C.textSecondary, fontFamily: FONT.body }}>
          Could not load Hamiltonian data from the node.
        </div>
        <div className="mt-1 text-[11px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
          Ensure the node is running and /quantum/hamiltonians endpoint is available.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1
            className="text-xl font-bold tracking-wide"
            style={{ color: C.textPrimary, fontFamily: FONT.heading }}
          >
            HAMILTONIAN RESEARCH LAB
          </h1>
          <p className="text-[11px]" style={{ color: C.textMuted, fontFamily: FONT.body }}>
            Live SUSY Hamiltonian solutions from Proof-of-SUSY-Alignment mining
            — every block generates a unique 4-qubit quantum problem
          </p>
        </div>
        <div className="text-right text-[10px]" style={{ fontFamily: FONT.mono }}>
          <div style={{ color: C.textMuted }}>Solutions loaded</div>
          <div style={{ color: C.primary, fontSize: 18, fontFamily: FONT.heading }}>
            {solutions.length}
          </div>
        </div>
      </div>

      {/* ── KPI Cards ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        <StatCard
          label="Avg VQE Energy"
          value={stats.avgEnergy.toFixed(4)}
          icon={Zap}
          color={C.secondary}
        />
        <StatCard
          label="Min Energy Found"
          value={stats.minEnergy.toFixed(4)}
          icon={TrendingDown}
          color={C.success}
        />
        <StatCard
          label="Avg Energy Gap"
          value={stats.avgGap.toFixed(4)}
          icon={Layers}
          color={C.accent}
        />
        <StatCard
          label="Total Solutions"
          value={formatNumber(archiveStats.total_solutions_archived ?? solutions.length)}
          icon={Database}
          color={C.primary}
        />
        <StatCard
          label="IPFS Archives"
          value={formatNumber(archiveStats.cids_stored ?? 0)}
          icon={Hash}
          color={C.quantum}
        />
        <StatCard
          label="Qubits / Block"
          value="4"
          icon={Cpu}
          color={C.susy}
        />
      </div>

      {/* ── Energy Landscape ───────────────────────────────────────────── */}
      <Panel>
        <SectionHeader title="ENERGY LANDSCAPE" />
        <div className="text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.body, marginBottom: 8 }}>
          VQE achieved energy vs exact ground state across recent blocks — click any point to inspect
        </div>
        <EnergyLandscape solutions={solutions} onSelect={setSelectedHeight} />
      </Panel>

      {/* ── Two-column: Feed + Detail ──────────────────────────────────── */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Solution feed */}
        <div className="lg:col-span-1">
          <Panel>
            <SectionHeader title="LIVE SOLUTIONS" />
            <SolutionFeed
              solutions={solutions}
              selectedHeight={selectedHeight}
              onSelect={setSelectedHeight}
            />
          </Panel>
        </div>

        {/* Detail panel */}
        <div className="lg:col-span-2">
          <Panel>
            <SectionHeader title="HAMILTONIAN DETAIL" />
            {selectedHeight !== null ? (
              <DetailPanel height={selectedHeight} />
            ) : (
              <div className="flex h-48 items-center justify-center text-[11px]" style={{ color: C.textMuted }}>
                Select a block from the feed to inspect its Hamiltonian
              </div>
            )}
          </Panel>
        </div>
      </div>

      {/* ── Pauli Legend ────────────────────────────────────────────────── */}
      <div
        className="flex items-center justify-center gap-6 py-2 text-[9px]"
        style={{ fontFamily: FONT.mono }}
      >
        {Object.entries(PAULI_COLORS).map(([gate, color]) => (
          <span key={gate} className="flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-3 rounded"
              style={{ background: `${color}60`, border: `1px solid ${color}` }}
            />
            <span style={{ color }}>{gate}</span>
            <span style={{ color: C.textMuted }}>{PAULI_LABELS[gate]}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
