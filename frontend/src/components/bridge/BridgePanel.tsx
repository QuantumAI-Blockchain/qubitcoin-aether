"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Bridge — Bridge Panel (Wrap / Unwrap primary UI)
   ───────────────────────────────────────────────────────────────────────── */

import { useState, useMemo, useCallback, memo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Lock, Unlock, ArrowDown, ChevronDown, ChevronUp, Flame, Plus, Wallet } from "lucide-react";
import { CHAINS, EXTERNAL_CHAINS } from "./chain-config";
import { useBridgeStore } from "./store";
import { useFeeEstimate } from "./hooks";
import {
  B, FONT, Panel, SectionHeader, WTokenLabel, TokenBadge, ChainBadge,
  CopyButton, HashDisplay, GlowButton, VaultBackingBadge, AnimatedNumber,
  truncAddr, formatAmount, formatUsd, formatPct, tokenColor, panelStyle,
} from "./shared";
import type { ExternalChainId, TokenType, OperationType } from "./types";

/* ── Direction Selector ───────────────────────────────────────────────── */

function DirectionSelector() {
  const { direction, setDirection } = useBridgeStore();

  return (
    <div className="grid grid-cols-2 gap-3">
      {(["wrap", "unwrap"] as const).map((dir) => {
        const active = direction === dir;
        const isWrap = dir === "wrap";
        const color = isWrap ? B.glowCyan : B.glowGold;

        return (
          <motion.button
            key={dir}
            layout
            onClick={() => setDirection(dir)}
            className="relative overflow-hidden rounded-xl p-4 text-left transition-all"
            style={{
              ...panelStyle,
              borderColor: active ? `${color}60` : B.borderSubtle,
              borderLeftWidth: active ? 3 : 1,
              borderLeftColor: active ? color : B.borderSubtle,
              background: active ? `${B.bgElevated}` : B.bgPanel,
            }}
          >
            <div className="mb-2 flex items-center gap-2">
              {isWrap ? <Lock size={16} style={{ color }} /> : <Unlock size={16} style={{ color }} />}
              <span
                className="text-sm font-bold tracking-widest"
                style={{ color: active ? color : B.textSecondary, fontFamily: FONT.display }}
              >
                {dir.toUpperCase()}
              </span>
            </div>
            <div className="space-y-0.5 text-[10px]" style={{ color: B.textSecondary, fontFamily: FONT.mono }}>
              <div>
                {isWrap ? "QBC → " : ""}
                {isWrap ? <WTokenLabel token="wQBC" /> : <span style={{ color: B.glowCyan }}>QBC</span>}
                {!isWrap ? " → QBC" : ""}
              </div>
              <div>
                {isWrap ? "QUSD → " : ""}
                {isWrap ? <WTokenLabel token="wQUSD" /> : <span style={{ color: B.glowViolet }}>QUSD</span>}
                {!isWrap ? " → QUSD" : ""}
              </div>
            </div>
            <p className="mt-2 text-[9px]" style={{ color: B.textSecondary }}>
              {isWrap ? "Lock native · Mint wrapped" : "Burn wrapped · Unlock native"}
            </p>
          </motion.button>
        );
      })}
    </div>
  );
}

/* ── Context Banner ───────────────────────────────────────────────────── */

function ContextBanner() {
  const { direction, token, selectedChain } = useBridgeStore();
  const isWrap = direction === "wrap";
  const chainName = selectedChain ? CHAINS[selectedChain].name : "[destination chain]";
  const wrapped = token === "QBC" ? "wQBC" : "wQUSD";

  return (
    <div
      className="rounded-lg border px-3 py-2 text-[10px] leading-relaxed"
      style={{
        borderColor: `${isWrap ? B.glowCyan : B.glowGold}20`,
        background: `${isWrap ? B.glowCyan : B.glowGold}05`,
        color: B.textSecondary,
        fontFamily: FONT.body,
      }}
    >
      {isWrap
        ? `Your ${token} will be locked in the Qubitcoin Bridge Vault. An equal amount of ${wrapped} will be minted to your ${chainName} wallet. Redeemable 1:1 at any time.`
        : `Your ${wrapped} will be permanently burned on ${chainName}. An equal amount of ${token} will be unlocked from the Qubitcoin Bridge Vault and sent to your Qubitcoin wallet.`}
    </div>
  );
}

/* ── Token Toggle ─────────────────────────────────────────────────────── */

function TokenToggle() {
  const { token, setToken } = useBridgeStore();

  return (
    <div className="flex gap-1 rounded-lg border p-1" style={{ borderColor: B.borderSubtle, background: B.bgBase }}>
      {(["QBC", "QUSD"] as const).map((t) => {
        const active = token === t;
        const color = tokenColor(t);
        return (
          <button
            key={t}
            onClick={() => setToken(t)}
            className="flex-1 rounded-md py-1.5 text-xs font-bold tracking-wider transition-all"
            style={{
              color: active ? color : B.textSecondary,
              background: active ? `${color}15` : "transparent",
              fontFamily: FONT.display,
            }}
          >
            {t}
          </button>
        );
      })}
    </div>
  );
}

/* ── Amount Input ─────────────────────────────────────────────────────── */

function AmountInput() {
  const { amount, setAmount, direction, token } = useBridgeStore();
  const isWrap = direction === "wrap";
  const color = isWrap ? tokenColor(token) : tokenColor(token === "QBC" ? "wQBC" : "wQUSD");

  // Mock balances
  const balance = token === "QBC" ? 4281.44 : 847.21;
  const gasBalance = 0.8421;
  const parsedAmount = parseFloat(amount) || 0;
  const overBalance = parsedAmount > balance;
  const underMin = parsedAmount > 0 && parsedAmount < 1;
  const overLimit = parsedAmount > 100000;
  const valid = parsedAmount >= 1 && parsedAmount <= balance && parsedAmount <= 100000;

  const borderColor = overBalance || underMin
    ? B.glowCrimson
    : overLimit
      ? B.glowAmber
      : valid
        ? color
        : B.borderSubtle;

  return (
    <div className="space-y-2">
      <div
        className="rounded-lg border p-3 transition-colors"
        style={{ borderColor, background: B.bgBase }}
      >
        <input
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="0.000000"
          className="w-full bg-transparent text-2xl font-bold outline-none"
          style={{ color: B.textPrimary, fontFamily: FONT.display }}
          min="0"
          step="0.000001"
        />
        <div className="mt-1 flex items-center justify-between">
          <span className="text-[10px]" style={{ color: B.textSecondary, fontFamily: FONT.mono }}>
            ≈ {formatUsd(parsedAmount * (token === "QBC" ? 0.2847 : 1.0012))}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-[10px]" style={{ color: B.glowGold, fontFamily: FONT.mono }}>
              Balance: {formatAmount(balance)}
              {isWrap ? ` ${token}` : ` w${token}`}
            </span>
            <button
              onClick={() => setAmount(String(Math.max(0, balance - (isWrap ? gasBalance : 0))))}
              className="rounded border px-1.5 py-0.5 text-[8px] font-bold tracking-wider"
              style={{ borderColor: B.borderActive, color: B.glowCyan, fontFamily: FONT.display }}
            >
              MAX
            </button>
            <button
              onClick={() => setAmount(String(balance / 2))}
              className="rounded border px-1.5 py-0.5 text-[8px] font-bold tracking-wider"
              style={{ borderColor: B.borderActive, color: B.glowCyan, fontFamily: FONT.display }}
            >
              HALF
            </button>
          </div>
        </div>
      </div>

      {/* Validation messages */}
      {overBalance && (
        <p className="text-[10px]" style={{ color: B.glowCrimson, fontFamily: FONT.mono }}>
          Insufficient {isWrap ? token : `w${token}`} balance (available: {formatAmount(balance)})
        </p>
      )}
      {underMin && (
        <p className="text-[10px]" style={{ color: B.glowCrimson, fontFamily: FONT.mono }}>
          Minimum {isWrap ? "wrap" : "unwrap"} amount: 1.000000 {isWrap ? token : `w${token}`}
        </p>
      )}
      {overLimit && (
        <p className="text-[10px]" style={{ color: B.glowAmber, fontFamily: FONT.mono }}>
          Exceeds daily vault limit — resets in 14h 32m
        </p>
      )}
    </div>
  );
}

/* ── Chain Selector ───────────────────────────────────────────────────── */

function ChainSelector() {
  const { selectedChain, setSelectedChain } = useBridgeStore();
  const [open, setOpen] = useState(false);

  return (
    <div className="space-y-2">
      <SectionHeader title={useBridgeStore.getState().direction === "wrap" ? "DESTINATION CHAIN" : "SOURCE CHAIN"} />

      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between rounded-lg border px-3 py-2.5 transition-colors"
        style={{ borderColor: B.borderActive, background: B.bgBase }}
      >
        {selectedChain ? (
          <div className="flex items-center gap-2">
            <ChainBadge chain={selectedChain} showStatus />
            <span className="text-xs" style={{ color: B.textPrimary, fontFamily: FONT.body }}>
              {CHAINS[selectedChain].name}
            </span>
          </div>
        ) : (
          <span className="text-xs" style={{ color: B.textSecondary, fontFamily: FONT.body }}>
            Select chain…
          </span>
        )}
        <ChevronDown size={14} style={{ color: B.textSecondary }} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden rounded-lg border"
            style={{ borderColor: B.borderSubtle }}
          >
            {EXTERNAL_CHAINS.map((c) => {
              const chain = CHAINS[c];
              const active = selectedChain === c;
              return (
                <button
                  key={c}
                  onClick={() => { setSelectedChain(c); setOpen(false); }}
                  disabled={!chain.available}
                  className="flex w-full items-center justify-between border-b px-3 py-2.5 transition-colors last:border-b-0"
                  style={{
                    borderColor: `${B.borderSubtle}60`,
                    background: active ? `${chain.color}10` : "transparent",
                    opacity: chain.available ? 1 : 0.4,
                    cursor: chain.available ? "pointer" : "not-allowed",
                  }}
                >
                  <div className="flex items-center gap-2">
                    <ChainBadge chain={c} showStatus />
                    <span className="text-xs" style={{ color: B.textPrimary, fontFamily: FONT.body }}>
                      {chain.name}
                    </span>
                  </div>
                  <span className="text-[10px]" style={{ color: chain.available ? B.glowEmerald : B.glowCrimson, fontFamily: FONT.display }}>
                    {chain.available ? "AVAILABLE" : "UNAVAILABLE"}
                  </span>
                </button>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── Operation Details ────────────────────────────────────────────────── */

function OperationDetails() {
  const { direction, token, selectedChain, amount } = useBridgeStore();
  const parsedAmount = parseFloat(amount) || 0;
  const isWrap = direction === "wrap";
  const chain = selectedChain ? CHAINS[selectedChain] : null;
  const wrapped = token === "QBC" ? "wQBC" : "wQUSD";

  const { data: fee } = useFeeEstimate(
    direction,
    token,
    selectedChain ?? "ethereum",
    amount
  );

  const [feeExpanded, setFeeExpanded] = useState(false);

  if (parsedAmount <= 0 || !chain || !fee) return null;

  return (
    <Panel accent={isWrap ? B.glowCyan : B.glowGold}>
      <SectionHeader title="OPERATION DETAILS" />

      <div className="space-y-2 text-xs" style={{ fontFamily: FONT.mono }}>
        <div className="flex justify-between">
          <span style={{ color: B.textSecondary }}>TYPE:</span>
          <span style={{ color: B.textPrimary }}>
            {isWrap ? "LOCK & MINT" : "BURN & UNLOCK"}
          </span>
        </div>
        <div className="flex justify-between">
          <span style={{ color: B.textSecondary }}>YOU SEND:</span>
          <span style={{ color: B.textPrimary }}>
            {formatAmount(fee.amount)} {isWrap ? token : wrapped}
          </span>
        </div>
        <div className="flex justify-between">
          <span style={{ color: B.textSecondary }}>BRIDGE FEE:</span>
          <span style={{ color: B.glowAmber }}>
            {formatAmount(fee.totalFeeToken)} {isWrap ? token : wrapped} ({formatPct(fee.totalFeePercent)})
          </span>
        </div>
        <div className="flex justify-between border-t pt-2" style={{ borderColor: `${B.borderSubtle}60` }}>
          <span style={{ color: B.textSecondary }}>YOU RECEIVE:</span>
          <span className="font-bold" style={{ color: isWrap ? B.glowGold : B.glowCyan }}>
            {formatAmount(fee.amountReceived)} {isWrap ? wrapped : token}
          </span>
        </div>

        {/* Expandable fee breakdown */}
        <button
          onClick={() => setFeeExpanded(!feeExpanded)}
          className="flex items-center gap-1 text-[10px] transition-opacity hover:opacity-80"
          style={{ color: B.textSecondary }}
        >
          {feeExpanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
          FEE BREAKDOWN
        </button>

        <AnimatePresence>
          {feeExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="space-y-1 rounded-lg border p-2" style={{ borderColor: `${B.borderSubtle}60`, background: B.bgBase }}>
                <div className="flex justify-between text-[10px]">
                  <span style={{ color: B.textSecondary }}>Protocol fee (0.10%)</span>
                  <span style={{ color: B.textPrimary }}>{formatAmount(fee.protocolFee)}</span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span style={{ color: B.textSecondary }}>Relayer fee (0.05%)</span>
                  <span style={{ color: B.textPrimary }}>{formatAmount(fee.relayerFee)}</span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span style={{ color: B.textSecondary }}>Dest gas (relayer)</span>
                  <span style={{ color: B.textPrimary }}>
                    {formatAmount(fee.destGasQbcEquiv)} (~{formatUsd(fee.destGasUsd)})
                  </span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex justify-between text-[10px]">
          <span style={{ color: B.textSecondary }}>EST. TIME:</span>
          <span style={{ color: B.textPrimary }}>
            {Math.floor(fee.estTimeSeconds.min / 60)}–{Math.ceil(fee.estTimeSeconds.max / 60)} MINUTES
          </span>
        </div>
        <p className="text-[9px]" style={{ color: B.textSecondary }}>
          This is a 1:1 {isWrap ? "wrap" : "unwrap"}. No slippage applies.
        </p>
      </div>
    </Panel>
  );
}

/* ── Receive Panel ────────────────────────────────────────────────────── */

function ReceivePanel() {
  const { direction, token, selectedChain, amount } = useBridgeStore();
  const parsedAmount = parseFloat(amount) || 0;
  const isWrap = direction === "wrap";
  const chain = isWrap
    ? (selectedChain ? CHAINS[selectedChain] : null)
    : CHAINS.qbc_mainnet;
  const wrapped = token === "QBC" ? "wQBC" : "wQUSD";

  const { data: fee } = useFeeEstimate(
    direction,
    token,
    selectedChain ?? "ethereum",
    amount
  );

  if (!chain) {
    return (
      <Panel>
        <SectionHeader title="YOU WILL RECEIVE" />
        <div className="flex flex-col items-center gap-2 py-6">
          <span className="text-xs" style={{ color: B.textSecondary, fontFamily: FONT.body }}>
            Select a {isWrap ? "destination" : "source"} chain
          </span>
        </div>
      </Panel>
    );
  }

  const receiveToken = isWrap ? wrapped : token;
  const receiveColor = isWrap ? tokenColor(wrapped as "wQBC" | "wQUSD") : tokenColor(token);
  const receiveAmount = fee?.amountReceived ?? 0;

  return (
    <Panel accent={receiveColor}>
      <SectionHeader title="YOU WILL RECEIVE" />
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <ChainBadge chain={isWrap ? selectedChain! : "qbc_mainnet"} showStatus />
          <span className="text-xs" style={{ color: B.textPrimary, fontFamily: FONT.body }}>
            {chain.name}
          </span>
        </div>

        {parsedAmount > 0 && fee ? (
          <>
            <div>
              <AnimatedNumber
                value={receiveAmount}
                decimals={6}
                color={receiveColor}
                size="text-2xl"
              />
              <div className="mt-1">
                <TokenBadge token={receiveToken as TokenType} size="md" />
              </div>
              <p className="mt-1 text-[10px]" style={{ color: B.textSecondary, fontFamily: FONT.mono }}>
                ≈ {formatUsd(receiveAmount * (token === "QBC" ? 0.2847 : 1.0012))}
              </p>
            </div>

            <div className="space-y-1 text-[10px]" style={{ fontFamily: FONT.mono }}>
              <div className="flex items-center gap-1">
                <span style={{ color: B.textSecondary }}>To:</span>
                <HashDisplay hash={isWrap ? "0x742d35Cc6634C0532925a3b844Bc9e7595f4f3a" : "QBC1a4f82e9c7b3d6f1234567890abcdef9e2c"} truncLen={6} />
                <CopyButton text={isWrap ? "0x742d35Cc6634C0532925a3b844Bc9e7595f4f3a" : "QBC1a4f82e9c7b3d6f1234567890abcdef9e2c"} />
              </div>
            </div>

            {/* Add to wallet button (wrap only) */}
            {isWrap && (
              <button
                className="flex w-full items-center justify-center gap-2 rounded-lg border py-2 text-[10px] font-bold tracking-wider transition-opacity hover:opacity-80"
                style={{ borderColor: `${receiveColor}40`, color: receiveColor, fontFamily: FONT.display }}
              >
                <Plus size={12} />
                ADD {wrapped} TO WALLET
              </button>
            )}
          </>
        ) : (
          <p className="py-4 text-center text-[10px]" style={{ color: B.textSecondary }}>
            Enter an amount
          </p>
        )}
      </div>
    </Panel>
  );
}

/* ── Action Button ────────────────────────────────────────────────────── */

function ActionButton() {
  const { direction, token, selectedChain, amount, setPreFlightOpen, setWalletModalOpen } = useBridgeStore();
  const parsedAmount = parseFloat(amount) || 0;
  const isWrap = direction === "wrap";
  const balance = token === "QBC" ? 4281.44 : 847.21;

  // Determine button state
  const qbcConnected = false; // mock
  const destConnected = false; // mock

  let label: string;
  let disabled = true;
  let color: string = B.textSecondary;
  let onClick: () => void = () => {};

  if (!qbcConnected) {
    label = "CONNECT QBC WALLET";
    onClick = () => setWalletModalOpen(true);
    disabled = false;
    color = B.textSecondary;
  } else if (!destConnected && selectedChain) {
    label = `CONNECT ${CHAINS[selectedChain].shortName} WALLET`;
    onClick = () => setWalletModalOpen(true);
    disabled = false;
    color = B.textSecondary;
  } else if (!selectedChain) {
    label = "SELECT DESTINATION CHAIN";
  } else if (!amount || parsedAmount <= 0) {
    label = "ENTER AMOUNT";
  } else if (parsedAmount > balance) {
    label = "INSUFFICIENT BALANCE";
    color = B.glowCrimson;
  } else if (parsedAmount > 100000) {
    label = "VAULT LIMIT REACHED";
    color = B.glowAmber;
  } else {
    label = `${isWrap ? "WRAP" : "UNWRAP"} NOW`;
    disabled = false;
    color = isWrap ? B.glowCyan : B.glowGold;
    onClick = () => setPreFlightOpen(true);
  }

  return (
    <GlowButton
      onClick={onClick}
      disabled={disabled && !label.startsWith("CONNECT")}
      color={color}
      variant="primary"
      className={`w-full ${!disabled ? "glow-pulse" : ""}`}
    >
      {label}
    </GlowButton>
  );
}

/* ── Bridge Panel (Main Export) ───────────────────────────────────────── */

export function BridgePanel() {
  const { direction, selectedChain, navigate } = useBridgeStore();
  const isWrap = direction === "wrap";

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4">
      {/* Direction */}
      <DirectionSelector />

      {/* Context */}
      <ContextBanner />

      {/* Three Column Layout */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Column 1: Source */}
        <Panel>
          <SectionHeader title={isWrap ? "YOU SEND" : "YOU SEND"} />
          <div className="space-y-3">
            {/* Fixed chain indicator */}
            <div className="flex items-center gap-2 rounded-lg border px-3 py-2" style={{ borderColor: B.borderSubtle, background: B.bgBase }}>
              <ChainBadge chain={isWrap ? "qbc_mainnet" : (selectedChain ?? "ethereum")} showStatus />
              <span className="text-xs" style={{ color: B.textPrimary, fontFamily: FONT.body }}>
                {isWrap ? "QUBITCOIN MAINNET" : (selectedChain ? CHAINS[selectedChain].name : "Select chain")}
              </span>
            </div>

            {/* Token toggle */}
            <TokenToggle />

            {/* Amount input */}
            <AmountInput />

            {/* Source wallet card (mock) */}
            <div className="rounded-lg border p-3" style={{ borderColor: B.borderSubtle, background: B.bgBase }}>
              <div className="mb-2 text-[9px] uppercase tracking-widest" style={{ color: B.textSecondary, fontFamily: FONT.display }}>
                Connected Wallet
              </div>
              <div className="flex items-center gap-2">
                <Wallet size={12} style={{ color: B.textSecondary }} />
                <span className="text-xs italic" style={{ color: B.textSecondary, fontFamily: FONT.mono }}>
                  Not connected
                </span>
              </div>
            </div>
          </div>
        </Panel>

        {/* Column 2: Bridge Controls */}
        <div className="space-y-4">
          {/* Operation Visual */}
          <Panel>
            <div className="flex flex-col items-center gap-3 py-4">
              {/* Source icon */}
              <div className="flex items-center gap-2">
                {isWrap ? (
                  <Lock size={16} style={{ color: B.glowCyan }} />
                ) : (
                  <Flame size={16} style={{ color: B.glowAmber }} />
                )}
                <span className="text-[10px] font-bold tracking-widest" style={{ color: B.textSecondary, fontFamily: FONT.display }}>
                  {isWrap ? "LOCK" : "BURN"}
                </span>
              </div>

              {/* Token transformation */}
              <div className="flex flex-col items-center gap-1">
                <TokenBadge token={isWrap ? useBridgeStore.getState().token : (useBridgeStore.getState().token === "QBC" ? "wQBC" : "wQUSD")} size="lg" />
                <ArrowDown size={20} style={{ color: B.textSecondary }} />
                <TokenBadge token={isWrap ? (useBridgeStore.getState().token === "QBC" ? "wQBC" : "wQUSD") : useBridgeStore.getState().token} size="lg" />
              </div>

              {/* Destination icon */}
              <div className="flex items-center gap-2">
                {isWrap ? (
                  <Plus size={16} style={{ color: B.glowGold }} />
                ) : (
                  <Unlock size={16} style={{ color: B.glowCyan }} />
                )}
                <span className="text-[10px] font-bold tracking-widest" style={{ color: B.textSecondary, fontFamily: FONT.display }}>
                  {isWrap ? "MINT" : "UNLOCK"}
                </span>
              </div>
            </div>
          </Panel>

          {/* Operation Details */}
          <OperationDetails />

          {/* Action Button */}
          <ActionButton />
        </div>

        {/* Column 3: Destination / Chain Select + Receive */}
        <div className="space-y-4">
          {/* Chain selector (only in column where it's interactive) */}
          {isWrap ? (
            <ChainSelector />
          ) : (
            <>
              <ChainSelector />
            </>
          )}

          {/* Receive panel */}
          <ReceivePanel />

          {/* Vault backing */}
          <div className="text-center">
            <VaultBackingBadge onClick={() => navigate("vault")} />
          </div>
        </div>
      </div>
    </div>
  );
}
