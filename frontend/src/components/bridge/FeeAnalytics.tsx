"use client";
/* ---------------------------------------------------------------------------
   QBC Bridge — Fee Analytics & Calculator
   --------------------------------------------------------------------------- */

import { useState, useMemo, useCallback, memo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Calculator,
  TrendingDown,
  Zap,
  DollarSign,
  ArrowRight,
  BarChart3,
  Fuel,
  Info,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  LineChart,
  Line,
} from "recharts";
import { CHAINS, EXTERNAL_CHAINS } from "./chain-config";
import { useBridgeStore } from "./store";
import { useFeeEstimate, useGasPrices, useBridgeTransactions } from "./hooks";
import {
  B,
  FONT,
  Panel,
  SectionHeader,
  WTokenLabel,
  TokenBadge,
  ChainBadge,
  AnimatedNumber,
  GlowButton,
  Skeleton,
  formatAmount,
  formatUsd,
  formatPct,
  formatDuration,
  panelStyle,
  chainColor,
  tokenColor,
} from "./shared";
import type {
  ExternalChainId,
  OperationType,
  TokenType,
  BridgeTx,
  FeeEstimate,
  GasPrice,
} from "./types";

/* ── Recharts Custom Tooltip ─────────────────────────────────────────────── */

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div
      className="rounded-lg border px-3 py-2"
      style={{
        background: B.bgElevated,
        borderColor: B.borderActive,
        boxShadow: `0 0 12px ${B.glowCyan}20`,
      }}
    >
      {label && (
        <div
          className="mb-1 text-[10px]"
          style={{ color: B.textSecondary, fontFamily: FONT.mono }}
        >
          {label}
        </div>
      )}
      {payload.map((entry, i) => (
        <div
          key={i}
          className="flex items-center gap-2 text-[10px]"
          style={{ fontFamily: FONT.mono }}
        >
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: entry.color }}
          />
          <span style={{ color: B.textSecondary }}>{entry.name}:</span>
          <span style={{ color: B.textPrimary }}>
            {typeof entry.value === "number" ? formatAmount(entry.value, 4) : entry.value}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ── Fee Calculator Panel ────────────────────────────────────────────────── */

function FeeCalculator() {
  const [operation, setOperation] = useState<OperationType>("wrap");
  const [token, setToken] = useState<TokenType>("QBC");
  const [chain, setChain] = useState<ExternalChainId>("ethereum");
  const [amount, setAmount] = useState("1000");

  const { data: fee, isLoading } = useFeeEstimate(operation, token, chain, amount);

  const selectStyle: React.CSSProperties = {
    background: B.bgBase,
    borderColor: B.borderActive,
    color: B.textPrimary,
    fontFamily: FONT.mono,
    fontSize: "0.75rem",
  };

  const isWrap = operation === "wrap";
  const wrapped: "wQBC" | "wQUSD" = token === "QBC" ? "wQBC" : "wQUSD";

  return (
    <Panel
      accent={B.glowCyan}
      style={{
        borderWidth: 2,
        borderColor: `${B.glowCyan}40`,
        boxShadow: `0 0 20px ${B.glowCyan}08`,
      }}
    >
      <div className="mb-4 flex items-center gap-2">
        <Calculator size={16} style={{ color: B.glowCyan }} />
        <span
          className="text-xs font-bold uppercase tracking-[0.2em]"
          style={{ color: B.glowCyan, fontFamily: FONT.display }}
        >
          Fee Calculator
        </span>
      </div>

      {/* Inputs */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {/* Operation */}
        <div className="space-y-1">
          <label
            className="text-[9px] font-bold uppercase tracking-[0.15em]"
            style={{ color: B.textSecondary, fontFamily: FONT.display }}
          >
            Operation
          </label>
          <select
            value={operation}
            onChange={(e) => setOperation(e.target.value as OperationType)}
            className="w-full rounded-lg border px-3 py-2"
            style={selectStyle}
          >
            <option value="wrap">WRAP</option>
            <option value="unwrap">UNWRAP</option>
          </select>
        </div>

        {/* Token */}
        <div className="space-y-1">
          <label
            className="text-[9px] font-bold uppercase tracking-[0.15em]"
            style={{ color: B.textSecondary, fontFamily: FONT.display }}
          >
            Token
          </label>
          <select
            value={token}
            onChange={(e) => setToken(e.target.value as TokenType)}
            className="w-full rounded-lg border px-3 py-2"
            style={selectStyle}
          >
            <option value="QBC">QBC</option>
            <option value="QUSD">QUSD</option>
          </select>
        </div>

        {/* Chain */}
        <div className="space-y-1">
          <label
            className="text-[9px] font-bold uppercase tracking-[0.15em]"
            style={{ color: B.textSecondary, fontFamily: FONT.display }}
          >
            Chain
          </label>
          <select
            value={chain}
            onChange={(e) => setChain(e.target.value as ExternalChainId)}
            className="w-full rounded-lg border px-3 py-2"
            style={selectStyle}
          >
            {EXTERNAL_CHAINS.map((c) => (
              <option key={c} value={c}>
                {CHAINS[c].shortName}
              </option>
            ))}
          </select>
        </div>

        {/* Amount */}
        <div className="space-y-1">
          <label
            className="text-[9px] font-bold uppercase tracking-[0.15em]"
            style={{ color: B.textSecondary, fontFamily: FONT.display }}
          >
            Amount
          </label>
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            className="w-full rounded-lg border px-3 py-2"
            style={{
              ...selectStyle,
              outline: "none",
            }}
            min="0"
            step="0.01"
          />
        </div>
      </div>

      {/* Results */}
      <AnimatePresence mode="wait">
        {fee && (
          <motion.div
            key={`${operation}-${token}-${chain}-${amount}`}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="mt-4"
          >
            <div
              className="rounded-xl border p-4"
              style={{
                borderColor: `${B.borderSubtle}`,
                background: B.bgBase,
              }}
            >
              {/* Fee breakdown rows */}
              <div className="space-y-2 text-xs" style={{ fontFamily: FONT.mono }}>
                <FeeRow
                  label={`Protocol Fee (${formatPct(fee.protocolFeePercent)})`}
                  value={formatAmount(fee.protocolFee, 6)}
                  suffix={isWrap ? token : wrapped}
                  color={B.textPrimary}
                />
                <FeeRow
                  label={`Relayer Fee (${formatPct(fee.relayerFeePercent)})`}
                  value={formatAmount(fee.relayerFee, 6)}
                  suffix={isWrap ? token : wrapped}
                  color={B.textPrimary}
                />
                <FeeRow
                  label="Dest Gas (relayer-paid)"
                  value={`${formatAmount(fee.destGasQbcEquiv, 6)} (~${formatUsd(fee.destGasUsd)})`}
                  suffix=""
                  color={B.textPrimary}
                />
                <FeeRow
                  label={`Dest Gas Native (${CHAINS[chain].nativeSymbol})`}
                  value={formatAmount(fee.destGasNative, 6)}
                  suffix={CHAINS[chain].nativeSymbol}
                  color={B.textSecondary}
                />

                {/* Divider */}
                <div
                  className="border-t pt-2"
                  style={{ borderColor: `${B.borderSubtle}60` }}
                />

                <FeeRow
                  label="Total Fee"
                  value={formatAmount(fee.totalFeeToken, 6)}
                  suffix={`${isWrap ? token : wrapped} (${formatPct(fee.totalFeePercent)})`}
                  color={B.glowAmber}
                  bold
                />

                <div
                  className="border-t pt-2"
                  style={{ borderColor: `${B.borderSubtle}60` }}
                />

                <FeeRow
                  label="You Receive"
                  value={formatAmount(fee.amountReceived, 6)}
                  suffix={isWrap ? wrapped : token}
                  color={isWrap ? B.glowGold : B.glowCyan}
                  bold
                  large
                />

                {/* Estimated time */}
                <div className="flex items-center justify-between pt-1 text-[10px]">
                  <span style={{ color: B.textSecondary }}>Est. Bridge Time</span>
                  <span style={{ color: B.textPrimary }}>
                    {formatDuration(fee.estTimeSeconds.min)} {"-"}{" "}
                    {formatDuration(fee.estTimeSeconds.max)}
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {isLoading && (
        <div className="mt-4 space-y-2">
          <Skeleton width="100%" height={120} />
        </div>
      )}
    </Panel>
  );
}

function FeeRow({
  label,
  value,
  suffix,
  color,
  bold,
  large,
}: {
  label: string;
  value: string;
  suffix: string;
  color: string;
  bold?: boolean;
  large?: boolean;
}) {
  return (
    <div
      className={`flex items-center justify-between ${large ? "text-sm" : "text-[11px]"}`}
    >
      <span style={{ color: B.textSecondary }}>{label}</span>
      <span
        style={{
          color,
          fontWeight: bold ? 700 : 400,
          fontFamily: FONT.mono,
        }}
      >
        {value}
        {suffix ? ` ${suffix}` : ""}
      </span>
    </div>
  );
}

/* ── Gas Prices Panel ────────────────────────────────────────────────────── */

function GasPricesPanel() {
  const { data: gasPrices, isLoading } = useGasPrices();

  if (isLoading || !gasPrices) {
    return (
      <Panel>
        <SectionHeader title="LIVE GAS PRICES" />
        <Skeleton width="100%" height={120} />
      </Panel>
    );
  }

  return (
    <Panel>
      <div className="mb-3 flex items-center gap-2">
        <Fuel size={14} style={{ color: B.glowAmber }} />
        <span
          className="text-[10px] font-bold uppercase tracking-[0.15em]"
          style={{ color: B.textSecondary, fontFamily: FONT.display }}
        >
          Live Gas Prices
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {gasPrices.map((gp) => {
          const info = CHAINS[gp.chain];
          const color = info?.color ?? B.textSecondary;

          return (
            <div
              key={gp.chain}
              className="rounded-lg border p-3"
              style={{
                borderColor: `${color}25`,
                background: `${color}05`,
              }}
            >
              <div className="mb-2 flex items-center gap-1.5">
                <ChainBadge chain={gp.chain} />
              </div>
              <div className="space-y-1 text-[10px]" style={{ fontFamily: FONT.mono }}>
                {gp.gwei !== null && (
                  <div className="flex justify-between">
                    <span style={{ color: B.textSecondary }}>Gas:</span>
                    <span style={{ color }}>{gp.gwei.toFixed(1)} gwei</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span style={{ color: B.textSecondary }}>Tx Cost:</span>
                  <span style={{ color: B.textPrimary }}>
                    {gp.nativeAmount.toFixed(6)} {info?.nativeSymbol}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span style={{ color: B.textSecondary }}>USD:</span>
                  <span style={{ color: B.glowAmber }}>
                    {formatUsd(gp.usdEquiv)}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

/* ── Fee Comparison Chart ────────────────────────────────────────────────── */

function FeeComparisonChart() {
  const compareAmounts = [100, 1000, 10000, 50000];

  const data = useMemo(() => {
    return compareAmounts.map((amt) => {
      const ethProtocol = amt * 0.001;
      const ethRelayer = amt * 0.0005;
      const ethGas = 5.2;
      const bnbProtocol = amt * 0.001;
      const bnbRelayer = amt * 0.0005;
      const bnbGas = 0.24;
      const solProtocol = amt * 0.001;
      const solRelayer = amt * 0.0005;
      const solGas = 0.004;

      return {
        amount: `${(amt / 1000).toFixed(0)}k QBC`,
        ETH: ethProtocol + ethRelayer + ethGas,
        BNB: bnbProtocol + bnbRelayer + bnbGas,
        SOL: solProtocol + solRelayer + solGas,
      };
    });
  }, []);

  return (
    <Panel>
      <SectionHeader title="FEE COMPARISON BY CHAIN & AMOUNT" />
      <div style={{ width: "100%", height: 260 }}>
        <ResponsiveContainer>
          <BarChart
            data={data}
            margin={{ top: 5, right: 10, left: 10, bottom: 5 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={`${B.borderSubtle}60`}
            />
            <XAxis
              dataKey="amount"
              tick={{
                fontSize: 9,
                fill: B.textSecondary,
                fontFamily: FONT.mono,
              }}
              stroke={B.borderSubtle}
            />
            <YAxis
              tick={{
                fontSize: 9,
                fill: B.textSecondary,
                fontFamily: FONT.mono,
              }}
              stroke={B.borderSubtle}
              tickFormatter={(v: number) => formatAmount(v, 1)}
              label={{
                value: "Total Fee (QBC)",
                angle: -90,
                position: "insideLeft",
                style: {
                  fontSize: 9,
                  fill: B.textSecondary,
                  fontFamily: FONT.mono,
                },
              }}
            />
            <RTooltip content={<ChartTooltip />} />
            <Legend
              wrapperStyle={{
                fontSize: 10,
                fontFamily: FONT.mono,
              }}
            />
            <Bar dataKey="ETH" fill="#627eea" radius={[2, 2, 0, 0]} />
            <Bar dataKey="BNB" fill="#f3ba2f" radius={[2, 2, 0, 0]} />
            <Bar dataKey="SOL" fill="#9945ff" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}

/* ── Fee Breakdown Donut ─────────────────────────────────────────────────── */

function FeeBreakdownDonut() {
  const { data: txs } = useBridgeTransactions();

  const breakdown = useMemo(() => {
    if (!txs || txs.length === 0) {
      return [
        { name: "Protocol", value: 0.1, color: B.glowCyan },
        { name: "Relayer", value: 0.05, color: B.glowViolet },
        { name: "Dest Gas", value: 0.03, color: B.glowAmber },
      ];
    }

    const totalProtocol = txs.reduce((s, tx) => s + tx.protocolFee, 0);
    const totalRelayer = txs.reduce((s, tx) => s + tx.relayerFee, 0);
    const totalGas = txs.reduce((s, tx) => s + tx.destinationGasFee, 0);

    return [
      { name: "Protocol (0.10%)", value: totalProtocol, color: B.glowCyan },
      { name: "Relayer (0.05%)", value: totalRelayer, color: B.glowViolet },
      { name: "Dest Gas", value: totalGas, color: B.glowAmber },
    ];
  }, [txs]);

  return (
    <Panel>
      <SectionHeader title="FEE COMPOSITION" />
      <div style={{ width: "100%", height: 240 }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={breakdown}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={80}
              paddingAngle={3}
              dataKey="value"
            >
              {breakdown.map((entry, i) => (
                <Cell key={i} fill={entry.color} opacity={0.8} />
              ))}
            </Pie>
            <RTooltip content={<ChartTooltip />} />
            <Legend
              wrapperStyle={{
                fontSize: 10,
                fontFamily: FONT.mono,
                color: B.textSecondary,
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}

/* ── Historical Fee Trend ────────────────────────────────────────────────── */

function FeeTrendChart() {
  const { data: txs } = useBridgeTransactions();

  const chartData = useMemo(() => {
    if (!txs || txs.length === 0) return [];

    // Group by day, calculate average fee %
    const byDay = new Map<string, { fees: number[]; count: number }>();

    for (const tx of txs) {
      const date = new Date(tx.initiatedAt * 1000)
        .toISOString()
        .slice(0, 10);
      const entry = byDay.get(date) ?? { fees: [], count: 0 };
      entry.fees.push(tx.totalFeePercent);
      entry.count += 1;
      byDay.set(date, entry);
    }

    return Array.from(byDay.entries())
      .map(([date, entry]) => ({
        date,
        avgFeePct:
          entry.fees.reduce((s, f) => s + f, 0) / entry.fees.length,
        txCount: entry.count,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
      .slice(-30);
  }, [txs]);

  if (chartData.length === 0) {
    return (
      <Panel>
        <SectionHeader title="AVERAGE FEE % (30 DAYS)" />
        <div
          className="flex items-center justify-center py-12 text-xs"
          style={{ color: B.textSecondary, fontFamily: FONT.body }}
        >
          No fee data available
        </div>
      </Panel>
    );
  }

  return (
    <Panel>
      <SectionHeader title="AVERAGE FEE % (30 DAYS)" />
      <div style={{ width: "100%", height: 220 }}>
        <ResponsiveContainer>
          <LineChart
            data={chartData}
            margin={{ top: 5, right: 10, left: 10, bottom: 5 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={`${B.borderSubtle}60`}
            />
            <XAxis
              dataKey="date"
              tick={{
                fontSize: 9,
                fill: B.textSecondary,
                fontFamily: FONT.mono,
              }}
              stroke={B.borderSubtle}
              tickFormatter={(v: string) => v.slice(5)}
            />
            <YAxis
              tick={{
                fontSize: 9,
                fill: B.textSecondary,
                fontFamily: FONT.mono,
              }}
              stroke={B.borderSubtle}
              tickFormatter={(v: number) => `${v.toFixed(2)}%`}
              domain={["auto", "auto"]}
            />
            <RTooltip content={<ChartTooltip />} />
            <Line
              type="monotone"
              dataKey="avgFeePct"
              name="Avg Fee %"
              stroke={B.glowAmber}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}

/* ── Aggregate Stats ─────────────────────────────────────────────────────── */

function AggregateStats() {
  const { data: txs } = useBridgeTransactions();

  const stats = useMemo(() => {
    if (!txs || txs.length === 0) {
      return {
        totalFees: 0,
        avgFee: 0,
        avgFeePct: 0,
        cheapestChain: "solana" as ExternalChainId,
        cheapestAvg: 0,
        totalVolume: 0,
        feeToVolumeRatio: 0,
      };
    }

    const totalFees = txs.reduce((s, tx) => s + tx.totalFee, 0);
    const avgFee = totalFees / txs.length;
    const avgFeePct =
      txs.reduce((s, tx) => s + tx.totalFeePercent, 0) / txs.length;
    const totalVolume = txs.reduce((s, tx) => s + tx.amountSent, 0);

    // Find cheapest chain by avg fee %
    const chainFees = new Map<ExternalChainId, number[]>();
    for (const tx of txs) {
      const ext =
        tx.operation === "wrap" ? tx.destinationChain : tx.sourceChain;
      if (ext === "qbc_mainnet") continue;
      const c = ext as ExternalChainId;
      const arr = chainFees.get(c) ?? [];
      arr.push(tx.totalFeePercent);
      chainFees.set(c, arr);
    }

    let cheapestChain: ExternalChainId = "solana";
    let cheapestAvg = Infinity;
    for (const [chain, fees] of chainFees.entries()) {
      const avg = fees.reduce((s, f) => s + f, 0) / fees.length;
      if (avg < cheapestAvg) {
        cheapestAvg = avg;
        cheapestChain = chain;
      }
    }

    return {
      totalFees,
      avgFee,
      avgFeePct,
      cheapestChain,
      cheapestAvg: cheapestAvg === Infinity ? 0 : cheapestAvg,
      totalVolume,
      feeToVolumeRatio: totalVolume > 0 ? (totalFees / totalVolume) * 100 : 0,
    };
  }, [txs]);

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <StatBox
        icon={<DollarSign size={14} />}
        label="Total Fees Collected"
        value={formatAmount(stats.totalFees, 2)}
        suffix="QBC"
        color={B.glowAmber}
      />
      <StatBox
        icon={<BarChart3 size={14} />}
        label="Avg Fee per Tx"
        value={formatAmount(stats.avgFee, 4)}
        suffix={`QBC (${formatPct(stats.avgFeePct)})`}
        color={B.glowCyan}
      />
      <StatBox
        icon={<TrendingDown size={14} />}
        label="Cheapest Chain"
        value={CHAINS[stats.cheapestChain].shortName}
        suffix={`avg ${formatPct(stats.cheapestAvg)}`}
        color={CHAINS[stats.cheapestChain].color}
      />
      <StatBox
        icon={<Zap size={14} />}
        label="Fee/Volume Ratio"
        value={formatPct(stats.feeToVolumeRatio)}
        suffix=""
        color={B.glowViolet}
      />
    </div>
  );
}

function StatBox({
  icon,
  label,
  value,
  suffix,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  suffix: string;
  color: string;
}) {
  return (
    <Panel style={{ borderColor: `${color}25` }}>
      <div className="flex items-center gap-1.5 mb-2" style={{ color }}>
        {icon}
        <span
          className="text-[9px] font-bold uppercase tracking-[0.15em]"
          style={{ color: B.textSecondary, fontFamily: FONT.display }}
        >
          {label}
        </span>
      </div>
      <div
        className="text-lg font-bold"
        style={{ color, fontFamily: FONT.mono }}
      >
        {value}
      </div>
      {suffix && (
        <div
          className="text-[10px]"
          style={{ color: B.textSecondary, fontFamily: FONT.mono }}
        >
          {suffix}
        </div>
      )}
    </Panel>
  );
}

/* ── Fee Schedule Table ──────────────────────────────────────────────────── */

function FeeSchedule() {
  const rows = [
    {
      component: "Protocol Fee",
      rate: "0.10%",
      description: "Core bridge protocol fee, applied to all operations",
      recipient: "QBC Bridge Treasury",
      color: B.glowCyan,
    },
    {
      component: "Relayer Fee",
      rate: "0.05%",
      description: "Compensates the Aether relay node for cross-chain message delivery",
      recipient: "Relay Node Operator",
      color: B.glowViolet,
    },
    {
      component: "Dest Gas (ETH)",
      rate: "~$14.00",
      description: "Gas to mint/burn on Ethereum (relayer-fronted, deducted from bridged amount)",
      recipient: "Ethereum Network",
      color: "#627eea",
    },
    {
      component: "Dest Gas (BNB)",
      rate: "~$0.65",
      description: "Gas to mint/burn on BNB Smart Chain",
      recipient: "BNB Network",
      color: "#f3ba2f",
    },
    {
      component: "Dest Gas (SOL)",
      rate: "~$0.01",
      description: "Gas to mint/burn on Solana",
      recipient: "Solana Network",
      color: "#9945ff",
    },
  ];

  return (
    <Panel>
      <div className="mb-3 flex items-center gap-2">
        <Info size={14} style={{ color: B.textSecondary }} />
        <span
          className="text-[10px] font-bold uppercase tracking-[0.15em]"
          style={{ color: B.textSecondary, fontFamily: FONT.display }}
        >
          Fee Schedule
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full" style={{ borderCollapse: "collapse" }}>
          <thead>
            <tr
              style={{
                borderBottom: `1px solid ${B.borderSubtle}`,
                background: B.bgBase,
              }}
            >
              {["COMPONENT", "RATE", "DESCRIPTION", "RECIPIENT"].map((col) => (
                <th
                  key={col}
                  className="px-3 py-2 text-left text-[9px] font-bold uppercase tracking-[0.15em]"
                  style={{ color: B.textSecondary, fontFamily: FONT.display }}
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.component}
                style={{ borderBottom: `1px solid ${B.borderSubtle}40` }}
              >
                <td className="px-3 py-2.5">
                  <span
                    className="text-[10px] font-bold"
                    style={{ color: row.color, fontFamily: FONT.mono }}
                  >
                    {row.component}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <span
                    className="text-[10px] font-bold"
                    style={{ color: B.textPrimary, fontFamily: FONT.mono }}
                  >
                    {row.rate}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <span
                    className="text-[10px]"
                    style={{ color: B.textSecondary, fontFamily: FONT.body }}
                  >
                    {row.description}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <span
                    className="text-[10px]"
                    style={{ color: B.textSecondary, fontFamily: FONT.mono }}
                  >
                    {row.recipient}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div
        className="mt-3 rounded-lg border px-3 py-2 text-[9px]"
        style={{
          borderColor: `${B.glowAmber}30`,
          background: `${B.glowAmber}05`,
          color: B.textSecondary,
          fontFamily: FONT.body,
        }}
      >
        All fees are deducted from the bridged amount. No additional charges.
        Protocol fees are collected by the QBC Bridge Treasury DAO and can be
        adjusted through governance. The relayer fronts destination gas costs and
        recoups them from the bridged amount in QBC-equivalent.
      </div>
    </Panel>
  );
}

/* ── Fee Analytics (Main Export) ──────────────────────────────────────────── */

export function FeeAnalytics() {
  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4">
      <SectionHeader
        title="FEE ANALYTICS"
        action={
          <div className="flex items-center gap-1.5">
            <Calculator size={12} style={{ color: B.glowAmber }} />
            <span
              className="text-[10px]"
              style={{ color: B.glowAmber, fontFamily: FONT.mono }}
            >
              Transparent Pricing
            </span>
          </div>
        }
      />

      {/* Fee Calculator */}
      <FeeCalculator />

      {/* Aggregate Stats */}
      <AggregateStats />

      {/* Gas Prices */}
      <GasPricesPanel />

      {/* Charts */}
      <div className="grid gap-4 lg:grid-cols-2">
        <FeeComparisonChart />
        <FeeBreakdownDonut />
      </div>

      {/* Fee Trend */}
      <FeeTrendChart />

      {/* Fee Schedule */}
      <FeeSchedule />
    </div>
  );
}

export default FeeAnalytics;
