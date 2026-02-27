"use client";
/* ---------------------------------------------------------------------------
   QBC Bridge -- Transaction Status View
   Auto-navigated after signing. Shows real-time progress of a bridge
   operation through its lifecycle stages, plus quantum bridge proof data
   and an event log.
   --------------------------------------------------------------------------- */

import { useState, useMemo, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Copy,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  ArrowLeft,
  Plus,
  RefreshCw,
  Loader2,
  Lock,
  Flame,
  Unlock,
  Shield,
  Sparkles,
  Clock,
  LifeBuoy,
  Eye,
  EyeOff,
} from "lucide-react";
import { useBridgeStore } from "./store";
import { useBridgeTransaction } from "./hooks";
import { CHAINS, getExplorerTxUrl } from "./chain-config";
import {
  B,
  FONT,
  Panel,
  SectionHeader,
  TokenBadge,
  ChainBadge,
  CopyButton,
  HashDisplay,
  GlowButton,
  StatusBadge,
  OperationBadge,
  AnimatedNumber,
  ExtLink,
  truncAddr,
  formatAmount,
  formatDuration,
  timeAgo,
  tokenColor,
  panelStyle,
} from "./shared";
import type { BridgeTx, BridgeStatus, ChainId, OperationType } from "./types";

/* -- Step definitions ------------------------------------------------------- */

interface StepDef {
  label: string;
  icon: typeof Lock;
  description: string;
}

const WRAP_STEPS: StepDef[] = [
  {
    label: "SIGNED",
    icon: Shield,
    description: "Transaction signed with Dilithium2 post-quantum signature and submitted to the Qubitcoin network.",
  },
  {
    label: "QBC LOCKED",
    icon: Lock,
    description: "Your QBC has been locked in the Bridge Vault contract on Qubitcoin Mainnet. Waiting for source chain confirmations.",
  },
  {
    label: "RELAYING",
    icon: Sparkles,
    description: "The Aether relay network is propagating the cross-chain message to the destination chain. Quantum bridge proof is being generated.",
  },
  {
    label: "wQBC MINTED",
    icon: Plus,
    description: "Wrapped tokens have been minted on the destination chain. Waiting for destination confirmations.",
  },
  {
    label: "COMPLETE",
    icon: CheckCircle,
    description: "Bridge operation completed successfully. Wrapped tokens are available in your destination wallet.",
  },
];

const UNWRAP_STEPS: StepDef[] = [
  {
    label: "SIGNED",
    icon: Shield,
    description: "Burn transaction signed on the source chain and submitted to the network.",
  },
  {
    label: "wQBC BURNED",
    icon: Flame,
    description: "Your wrapped tokens have been burned on the source chain. Waiting for source chain confirmations.",
  },
  {
    label: "RELAYING",
    icon: Sparkles,
    description: "The Aether relay network is verifying the burn proof and propagating the unlock message to Qubitcoin Mainnet.",
  },
  {
    label: "QBC UNLOCKED",
    icon: Unlock,
    description: "Native tokens have been unlocked from the Bridge Vault. Waiting for Qubitcoin confirmations.",
  },
  {
    label: "COMPLETE",
    icon: CheckCircle,
    description: "Bridge operation completed successfully. Native tokens are available in your Qubitcoin wallet.",
  },
];

/* -- Determine active step from tx state ------------------------------------ */

function resolveCurrentStep(tx: BridgeTx): number {
  if (tx.status === "complete") return 4;
  if (tx.status === "failed") {
    // Failed at whichever step we can infer
    if (tx.destinationTxHash) return 3;
    if (tx.confirmations.source >= tx.confirmations.sourceRequired) return 2;
    return 1;
  }
  if (tx.status === "refunded") return 4; // show all steps as done (refund path)

  // Pending -- determine from confirmations
  const { source, sourceRequired, destination, destinationRequired } = tx.confirmations;

  if (destination !== null && destination >= destinationRequired) return 4;
  if (destination !== null && destination > 0) return 3;
  if (tx.destinationTxHash) return 3;
  if (source >= sourceRequired) return 2;
  if (source > 0) return 1;
  return 0;
}

function stepStatus(
  stepIndex: number,
  currentStep: number,
  txStatus: BridgeStatus,
): "complete" | "active" | "pending" | "failed" {
  if (txStatus === "failed" && stepIndex === currentStep) return "failed";
  if (stepIndex < currentStep) return "complete";
  if (stepIndex === currentStep) {
    if (txStatus === "complete" || txStatus === "refunded") return "complete";
    return "active";
  }
  return "pending";
}

function stepColor(status: "complete" | "active" | "pending" | "failed"): string {
  switch (status) {
    case "complete":
      return B.glowEmerald;
    case "active":
      return B.glowCyan;
    case "pending":
      return B.textSecondary;
    case "failed":
      return B.glowCrimson;
  }
}

/* -- Step Indicator Component ----------------------------------------------- */

function StepIndicator({
  step,
  index,
  status,
  isLast,
}: {
  step: StepDef;
  index: number;
  status: "complete" | "active" | "pending" | "failed";
  isLast: boolean;
}) {
  const color = stepColor(status);
  const Icon = status === "failed" ? XCircle : status === "complete" ? CheckCircle : step.icon;

  return (
    <div className="flex items-start gap-3">
      {/* Vertical track */}
      <div className="flex flex-col items-center">
        <motion.div
          initial={{ scale: 0.8 }}
          animate={{
            scale: status === "active" ? [1, 1.15, 1] : 1,
            boxShadow:
              status === "active"
                ? [
                    `0 0 0px ${color}00`,
                    `0 0 12px ${color}60`,
                    `0 0 0px ${color}00`,
                  ]
                : `0 0 0px ${color}00`,
          }}
          transition={
            status === "active"
              ? { repeat: Infinity, duration: 2, ease: "easeInOut" }
              : { duration: 0.3 }
          }
          className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border-2"
          style={{
            borderColor: color,
            background:
              status === "complete" || status === "failed"
                ? `${color}20`
                : "transparent",
          }}
        >
          {status === "active" ? (
            <Loader2 size={14} className="animate-spin" style={{ color }} />
          ) : (
            <Icon size={14} style={{ color }} />
          )}
        </motion.div>
        {!isLast && (
          <div
            className="w-0.5 flex-1"
            style={{
              minHeight: 24,
              background:
                status === "complete"
                  ? color
                  : `repeating-linear-gradient(to bottom, ${B.textSecondary}40 0px, ${B.textSecondary}40 4px, transparent 4px, transparent 8px)`,
            }}
          />
        )}
      </div>

      {/* Label */}
      <div className="pb-4">
        <span
          className="text-[11px] font-bold tracking-widest"
          style={{ color, fontFamily: FONT.display }}
        >
          {step.label}
        </span>
      </div>
    </div>
  );
}

/* -- Active Step Detail Card ------------------------------------------------ */

function ActiveStepDetail({
  step,
  status,
}: {
  step: StepDef;
  status: "complete" | "active" | "pending" | "failed";
}) {
  const color = stepColor(status);

  return (
    <motion.div
      key={step.label}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Panel accent={color}>
        <div className="flex items-start gap-3">
          <div
            className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg"
            style={{ background: `${color}15` }}
          >
            {status === "active" ? (
              <Loader2 size={16} className="animate-spin" style={{ color }} />
            ) : status === "failed" ? (
              <XCircle size={16} style={{ color }} />
            ) : (
              <step.icon size={16} style={{ color }} />
            )}
          </div>
          <div>
            <p
              className="text-xs font-bold tracking-widest"
              style={{ color, fontFamily: FONT.display }}
            >
              {status === "active" ? "IN PROGRESS" : status === "failed" ? "FAILED" : "CURRENT STEP"}: {step.label}
            </p>
            <p
              className="mt-1 text-[11px] leading-relaxed"
              style={{ color: B.textSecondary, fontFamily: FONT.body }}
            >
              {step.description}
            </p>
          </div>
        </div>
      </Panel>
    </motion.div>
  );
}

/* -- Confirmation Progress Bar ---------------------------------------------- */

function ConfirmationBar({
  label,
  current,
  required,
  color,
}: {
  label: string;
  current: number;
  required: number;
  color: string;
}) {
  const pct = Math.min((current / required) * 100, 100);
  const done = current >= required;

  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-[10px]" style={{ fontFamily: FONT.mono }}>
        <span style={{ color: B.textSecondary }}>{label}</span>
        <span style={{ color: done ? B.glowEmerald : color }}>
          {current} / {required} confirmations
        </span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full"
        style={{ background: `${B.borderSubtle}60` }}
      >
        <motion.div
          className="h-full rounded-full"
          style={{
            background: done
              ? B.glowEmerald
              : `linear-gradient(90deg, ${color}, ${color}aa)`,
          }}
          initial={{ width: "0%" }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

/* -- Transaction Hashes Panel ----------------------------------------------- */

function TxHashesPanel({ tx }: { tx: BridgeTx }) {
  const sourceChain = CHAINS[tx.sourceChain];
  const destChain = CHAINS[tx.destinationChain];
  const isQbcSource = tx.sourceChain === "qbc_mainnet";

  return (
    <Panel>
      <SectionHeader title="TRANSACTION HASHES" />
      <div className="space-y-3">
        {/* Source TX */}
        <div>
          <div className="mb-1 flex items-center gap-2">
            <ChainBadge chain={tx.sourceChain} />
            <span
              className="text-[9px] font-bold uppercase tracking-widest"
              style={{ color: B.textSecondary, fontFamily: FONT.display }}
            >
              SOURCE TX
            </span>
          </div>
          <div className="flex items-center gap-2">
            <HashDisplay hash={tx.sourceTxHash} truncLen={12} />
            <CopyButton text={tx.sourceTxHash} />
            {isQbcSource ? (
              <ExtLink
                href={getExplorerTxUrl(sourceChain, tx.sourceTxHash)}
                label="QBC EXPLORER"
              />
            ) : (
              <ExtLink
                href={getExplorerTxUrl(sourceChain, tx.sourceTxHash)}
                label={sourceChain.shortName + "SCAN"}
              />
            )}
          </div>
        </div>

        {/* Destination TX */}
        {tx.destinationTxHash ? (
          <div>
            <div className="mb-1 flex items-center gap-2">
              <ChainBadge chain={tx.destinationChain} />
              <span
                className="text-[9px] font-bold uppercase tracking-widest"
                style={{ color: B.textSecondary, fontFamily: FONT.display }}
              >
                DESTINATION TX
              </span>
            </div>
            <div className="flex items-center gap-2">
              <HashDisplay hash={tx.destinationTxHash} truncLen={12} />
              <CopyButton text={tx.destinationTxHash} />
              {tx.destinationChain === "qbc_mainnet" ? (
                <ExtLink
                  href={getExplorerTxUrl(destChain, tx.destinationTxHash)}
                  label="QBC EXPLORER"
                />
              ) : (
                <ExtLink
                  href={getExplorerTxUrl(destChain, tx.destinationTxHash)}
                  label={destChain.shortName + "SCAN"}
                />
              )}
            </div>
          </div>
        ) : (
          <div
            className="rounded-lg border px-3 py-2 text-[10px]"
            style={{
              borderColor: `${B.borderSubtle}60`,
              color: B.textSecondary,
              fontFamily: FONT.mono,
              background: B.bgBase,
            }}
          >
            Destination TX hash will appear once the relay confirms the operation.
          </div>
        )}
      </div>
    </Panel>
  );
}

/* -- Quantum Bridge Proof Panel --------------------------------------------- */

function QuantumProofPanel({ tx }: { tx: BridgeTx }) {
  const [sigExpanded, setSigExpanded] = useState(false);

  const proofFields: Array<{ label: string; value: string; expandable?: boolean }> = [
    { label: "CROSS-CHAIN MSG HASH", value: tx.crossChainMsgHash },
    { label: "DILITHIUM SIGNATURE", value: tx.dilithiumSig, expandable: true },
    { label: "SUSY ALIGNMENT", value: tx.susyAlignmentAtOp.toFixed(6) },
    { label: "AETHER RELAY NODE", value: tx.aetherRelayNodeId },
    { label: "BRIDGE PROTOCOL", value: tx.bridgeProtocolVersion },
  ];

  return (
    <Panel accent={B.glowViolet}>
      <SectionHeader title="QUANTUM BRIDGE PROOF" />
      <div className="space-y-2.5">
        {proofFields.map((field) => (
          <div key={field.label}>
            <span
              className="text-[9px] font-bold uppercase tracking-widest"
              style={{ color: B.textSecondary, fontFamily: FONT.display }}
            >
              {field.label}
            </span>
            <div className="mt-0.5 flex items-center gap-2">
              {field.expandable ? (
                <>
                  <span
                    className="text-[10px] break-all"
                    style={{ color: B.glowViolet, fontFamily: FONT.mono }}
                  >
                    {sigExpanded ? field.value : truncAddr(field.value, 24, 24)}
                  </span>
                  <button
                    onClick={() => setSigExpanded(!sigExpanded)}
                    className="flex-shrink-0"
                    style={{ color: B.textSecondary }}
                  >
                    {sigExpanded ? <EyeOff size={12} /> : <Eye size={12} />}
                  </button>
                  <CopyButton text={field.value} />
                </>
              ) : field.label === "SUSY ALIGNMENT" ? (
                <span
                  className="text-[11px] font-bold"
                  style={{
                    color:
                      tx.susyAlignmentAtOp >= 0.95
                        ? B.glowEmerald
                        : tx.susyAlignmentAtOp >= 0.85
                          ? B.glowAmber
                          : B.glowCrimson,
                    fontFamily: FONT.mono,
                  }}
                >
                  {field.value}
                </span>
              ) : (
                <>
                  <span
                    className="text-[10px]"
                    style={{ color: B.glowCyan, fontFamily: FONT.mono }}
                  >
                    {field.value.length > 50
                      ? truncAddr(field.value, 20, 20)
                      : field.value}
                  </span>
                  {field.value.length > 20 && <CopyButton text={field.value} />}
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

/* -- Event Log -------------------------------------------------------------- */

function EventLog({ events }: { events: BridgeTx["eventLog"] }) {
  const [expanded, setExpanded] = useState(false);

  // Show newest at bottom (events are already in chronological order)
  const displayEvents = expanded ? events : events.slice(-3);

  return (
    <Panel>
      <div className="mb-3 flex items-center justify-between">
        <SectionHeader title="EVENT LOG" />
        {events.length > 3 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-[10px] transition-opacity hover:opacity-80"
            style={{ color: B.glowCyan, fontFamily: FONT.mono }}
          >
            {expanded ? (
              <>
                COLLAPSE <ChevronUp size={10} />
              </>
            ) : (
              <>
                SHOW ALL ({events.length}) <ChevronDown size={10} />
              </>
            )}
          </button>
        )}
      </div>

      <div className="space-y-1.5">
        <AnimatePresence initial={false}>
          {displayEvents.map((evt, i) => {
            const ts = new Date(evt.timestamp * 1000);
            const timeStr = ts.toLocaleTimeString("en-US", {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
              hour12: false,
            });

            return (
              <motion.div
                key={`${evt.timestamp}-${i}`}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.2 }}
                className="flex gap-2 rounded border px-2.5 py-1.5"
                style={{ borderColor: `${B.borderSubtle}40`, background: B.bgBase }}
              >
                <span
                  className="flex-shrink-0 text-[9px]"
                  style={{ color: B.textSecondary, fontFamily: FONT.mono }}
                >
                  [{timeStr}]
                </span>
                <span
                  className="text-[10px]"
                  style={{ color: B.textPrimary, fontFamily: FONT.mono }}
                >
                  {evt.message}
                </span>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </Panel>
  );
}

/* -- Completion State ------------------------------------------------------- */

function CompletionBanner({ tx }: { tx: BridgeTx }) {
  const { navigate } = useBridgeStore();
  const isWrap = tx.operation === "wrap";
  const receiveToken = isWrap
    ? tx.token === "QBC" ? "wQBC" : "wQUSD"
    : tx.token;
  const accentColor = isWrap ? B.glowGold : B.glowCyan;
  const destChain = CHAINS[tx.destinationChain];

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, delay: 0.2 }}
    >
      <Panel accent={B.glowEmerald}>
        <div className="space-y-4 text-center">
          {/* Large checkmark */}
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 200, delay: 0.3 }}
            className="mx-auto flex h-16 w-16 items-center justify-center rounded-full"
            style={{ background: `${B.glowEmerald}15` }}
          >
            <CheckCircle size={36} style={{ color: B.glowEmerald }} />
          </motion.div>

          <div>
            <h3
              className="text-sm font-bold tracking-widest"
              style={{ color: B.glowEmerald, fontFamily: FONT.display }}
            >
              BRIDGE COMPLETE
            </h3>
            <p
              className="mt-1 text-xs"
              style={{ color: B.textSecondary, fontFamily: FONT.body }}
            >
              {isWrap ? "Wrapped" : "Unwrapped"} successfully
              {tx.bridgeTimeSeconds !== null
                ? ` in ${formatDuration(tx.bridgeTimeSeconds)}`
                : ""}
            </p>
          </div>

          {/* Received amount */}
          <div>
            <p
              className="text-[9px] uppercase tracking-widest"
              style={{ color: B.textSecondary, fontFamily: FONT.display }}
            >
              RECEIVED
            </p>
            <div className="mt-1 flex items-center justify-center gap-2">
              <span
                className="text-2xl font-bold"
                style={{
                  color: tokenColor(receiveToken as "QBC" | "QUSD" | "wQBC" | "wQUSD"),
                  fontFamily: FONT.mono,
                }}
              >
                {formatAmount(tx.amountReceived)}
              </span>
              <TokenBadge
                token={receiveToken as "QBC" | "QUSD" | "wQBC" | "wQUSD"}
                size="lg"
              />
            </div>
          </div>

          {/* Action buttons */}
          <div className="space-y-2">
            {/* Most prominent: Add to wallet (wrap only) */}
            {isWrap && (
              <GlowButton
                color={accentColor}
                variant="primary"
                className="w-full"
                onClick={() => {
                  /* Would trigger MetaMask addToken */
                }}
              >
                <Plus size={16} />
                ADD {receiveToken} TO WALLET
              </GlowButton>
            )}

            <div className="flex gap-2">
              <GlowButton
                color={isWrap ? B.glowCyan : B.glowGold}
                variant="secondary"
                className="flex-1"
                onClick={() => navigate("bridge")}
              >
                <RefreshCw size={12} />
                {isWrap ? "WRAP" : "UNWRAP"} AGAIN
              </GlowButton>
              {tx.destinationTxHash && (
                <a
                  href={getExplorerTxUrl(destChain, tx.destinationTxHash)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex flex-1 items-center justify-center gap-2 rounded-lg px-4 text-[11px] font-bold tracking-wider transition-opacity hover:opacity-80"
                  style={{
                    height: 40,
                    color: B.glowCyan,
                    background: `${B.glowCyan}15`,
                    fontFamily: FONT.display,
                  }}
                >
                  <ExternalLink size={12} />
                  VIEW IN EXPLORER
                </a>
              )}
            </div>
          </div>
        </div>
      </Panel>
    </motion.div>
  );
}

/* -- Failed / Stuck State --------------------------------------------------- */

function FailedBanner({ tx }: { tx: BridgeTx }) {
  const { navigate } = useBridgeStore();

  const lastEvent =
    tx.eventLog.length > 0
      ? tx.eventLog[tx.eventLog.length - 1].message
      : "The bridge operation encountered an error.";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <Panel accent={B.glowCrimson}>
        <div className="space-y-3">
          <div className="flex items-start gap-3">
            <div
              className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full"
              style={{ background: `${B.glowCrimson}15` }}
            >
              <AlertTriangle size={20} style={{ color: B.glowCrimson }} />
            </div>
            <div>
              <h3
                className="text-xs font-bold tracking-widest"
                style={{ color: B.glowCrimson, fontFamily: FONT.display }}
              >
                {tx.status === "failed" ? "BRIDGE FAILED" : "BRIDGE REFUNDED"}
              </h3>
              <p
                className="mt-1 text-[11px] leading-relaxed"
                style={{ color: B.textSecondary, fontFamily: FONT.body }}
              >
                {lastEvent}
              </p>
              {tx.status === "failed" && (
                <p
                  className="mt-1 text-[10px]"
                  style={{ color: B.textSecondary, fontFamily: FONT.mono }}
                >
                  Your source funds have not been moved. If the issue persists,
                  contact support with your transaction ID.
                </p>
              )}
            </div>
          </div>

          <div className="flex gap-2">
            <a
              href="mailto:support@qbc.network"
              className="flex flex-1 items-center justify-center gap-2 rounded-lg px-4 text-[11px] font-bold tracking-wider transition-opacity hover:opacity-80"
              style={{
                height: 40,
                color: B.glowAmber,
                background: `${B.glowAmber}15`,
                fontFamily: FONT.display,
              }}
            >
              <LifeBuoy size={12} />
              CONTACT SUPPORT
            </a>
            <GlowButton
              color={B.glowCyan}
              variant="secondary"
              className="flex-1"
              onClick={() => {
                /* Refresh tx data */
              }}
            >
              <RefreshCw size={12} />
              CHECK STATUS
            </GlowButton>
          </div>
        </div>
      </Panel>
    </motion.div>
  );
}

/* -- Not Found State -------------------------------------------------------- */

function TxNotFound({ txId }: { txId: string }) {
  const { navigate } = useBridgeStore();

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <Panel accent={B.glowCrimson}>
        <div className="space-y-4 text-center">
          <div
            className="mx-auto flex h-16 w-16 items-center justify-center rounded-full"
            style={{ background: `${B.glowCrimson}15` }}
          >
            <XCircle size={36} style={{ color: B.glowCrimson }} />
          </div>
          <div>
            <h3
              className="text-sm font-bold tracking-widest"
              style={{ color: B.glowCrimson, fontFamily: FONT.display }}
            >
              TRANSACTION NOT FOUND
            </h3>
            <p
              className="mt-2 text-xs"
              style={{ color: B.textSecondary, fontFamily: FONT.body }}
            >
              Could not find a bridge transaction with ID:
            </p>
            <p
              className="mt-1 text-[11px]"
              style={{ color: B.glowCyan, fontFamily: FONT.mono }}
            >
              {txId}
            </p>
            <p
              className="mt-2 text-[10px]"
              style={{ color: B.textSecondary, fontFamily: FONT.body }}
            >
              This transaction may have expired or the ID may be incorrect.
            </p>
          </div>

          <GlowButton
            color={B.glowCyan}
            variant="secondary"
            onClick={() => navigate("bridge")}
          >
            <ArrowLeft size={14} />
            BACK TO BRIDGE
          </GlowButton>
        </div>
      </Panel>
    </div>
  );
}

/* == TxStatusView (exported) ================================================ */

export function TxStatusViewInner({ txId }: { txId: string }) {
  const { navigate } = useBridgeStore();
  const { data: tx, isLoading, isError } = useBridgeTransaction(txId);

  /* -- Loading state ---------------------------------------------------- */

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <Loader2 size={32} className="mx-auto animate-spin" style={{ color: B.glowCyan }} />
          <p
            className="mt-3 text-xs tracking-widest"
            style={{ color: B.textSecondary, fontFamily: FONT.display }}
          >
            LOADING TRANSACTION
          </p>
        </div>
      </div>
    );
  }

  /* -- Not found -------------------------------------------------------- */

  if (isError || !tx) {
    return <TxNotFound txId={txId} />;
  }

  /* -- Derive display state --------------------------------------------- */

  const isWrap = tx.operation === "wrap";
  const steps = isWrap ? WRAP_STEPS : UNWRAP_STEPS;
  const currentStep = resolveCurrentStep(tx);
  const wrapped = tx.token === "QBC" ? "wQBC" : "wQUSD";
  const accentColor = isWrap ? B.glowGold : B.glowViolet;
  const sourceChain = CHAINS[tx.sourceChain];
  const destChain = CHAINS[tx.destinationChain];
  const isComplete = tx.status === "complete";
  const isFailed = tx.status === "failed";
  const isRefunded = tx.status === "refunded";

  // Build banner text
  const bannerText = isWrap
    ? `WRAPPING ${tx.token} \u2192 ${wrapped} ON ${destChain.name.toUpperCase()}`
    : `UNWRAPPING ${wrapped} \u2192 ${tx.token} FROM ${sourceChain.name.toUpperCase()}`;

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      {/* Back button */}
      <button
        onClick={() => navigate("bridge")}
        className="flex items-center gap-1.5 text-[10px] tracking-wider transition-opacity hover:opacity-80"
        style={{ color: B.textSecondary, fontFamily: FONT.display }}
      >
        <ArrowLeft size={12} />
        BACK TO BRIDGE
      </button>

      {/* Operation type banner */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="overflow-hidden rounded-xl"
        style={{
          background: `linear-gradient(135deg, ${accentColor}20, ${accentColor}05)`,
          border: `1px solid ${accentColor}30`,
        }}
      >
        <div
          className="h-1"
          style={{
            background: `linear-gradient(90deg, ${accentColor}, ${isWrap ? B.glowCyan : B.glowGold})`,
          }}
        />
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <OperationBadge operation={tx.operation} size="md" />
            <span
              className="text-[11px] font-bold tracking-[0.15em]"
              style={{ color: accentColor, fontFamily: FONT.display }}
            >
              {bannerText}
            </span>
          </div>
          <StatusBadge status={tx.status} />
        </div>
      </motion.div>

      {/* Main content: two columns on larger screens */}
      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        {/* Left column: progress + details */}
        <div className="space-y-4">
          {/* Progress stepper */}
          <Panel>
            <SectionHeader title="BRIDGE PROGRESS" />
            <div className="mt-2">
              {steps.map((step, i) => (
                <StepIndicator
                  key={step.label}
                  step={step}
                  index={i}
                  status={stepStatus(i, currentStep, tx.status)}
                  isLast={i === steps.length - 1}
                />
              ))}
            </div>
          </Panel>

          {/* Active step detail */}
          <div aria-live="polite" aria-atomic="true">
            {!isComplete && !isRefunded && (
              <ActiveStepDetail
                step={steps[Math.min(currentStep, steps.length - 1)]}
                status={isFailed ? "failed" : "active"}
              />
            )}

            {/* Completion banner */}
            {isComplete && <CompletionBanner tx={tx} />}

            {/* Failed / refunded banner */}
            {(isFailed || isRefunded) && <FailedBanner tx={tx} />}
          </div>

          {/* Confirmation bars */}
          {tx.status === "pending" && (
            <Panel>
              <SectionHeader title="CONFIRMATIONS" />
              <div className="space-y-3">
                <ConfirmationBar
                  label={`${sourceChain.shortName} SOURCE`}
                  current={tx.confirmations.source}
                  required={tx.confirmations.sourceRequired}
                  color={sourceChain.color}
                />
                {tx.confirmations.destination !== null && (
                  <ConfirmationBar
                    label={`${destChain.shortName} DESTINATION`}
                    current={tx.confirmations.destination}
                    required={tx.confirmations.destinationRequired}
                    color={destChain.color}
                  />
                )}
              </div>
            </Panel>
          )}

          {/* Transaction hashes */}
          <TxHashesPanel tx={tx} />
        </div>

        {/* Right column: proof + event log */}
        <div className="space-y-4">
          {/* Quantum Bridge Proof */}
          <QuantumProofPanel tx={tx} />

          {/* Timing info */}
          <Panel>
            <SectionHeader title="TIMING" />
            <div className="space-y-1.5 text-[10px]" style={{ fontFamily: FONT.mono }}>
              <div className="flex justify-between">
                <span style={{ color: B.textSecondary }}>INITIATED:</span>
                <span style={{ color: B.textPrimary }}>{timeAgo(tx.initiatedAt)}</span>
              </div>
              {tx.completedAt && (
                <div className="flex justify-between">
                  <span style={{ color: B.textSecondary }}>COMPLETED:</span>
                  <span style={{ color: B.glowEmerald }}>{timeAgo(tx.completedAt)}</span>
                </div>
              )}
              {tx.bridgeTimeSeconds !== null && (
                <div className="flex justify-between">
                  <span style={{ color: B.textSecondary }}>BRIDGE TIME:</span>
                  <span style={{ color: B.textPrimary }}>
                    {formatDuration(tx.bridgeTimeSeconds)}
                  </span>
                </div>
              )}
            </div>
          </Panel>

          {/* Amount summary */}
          <Panel>
            <SectionHeader title="AMOUNTS" />
            <div className="space-y-1.5 text-[10px]" style={{ fontFamily: FONT.mono }}>
              <div className="flex justify-between">
                <span style={{ color: B.textSecondary }}>SENT:</span>
                <span style={{ color: B.textPrimary }}>
                  {formatAmount(tx.amountSent)} {isWrap ? tx.token : wrapped}
                </span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: B.textSecondary }}>FEE:</span>
                <span style={{ color: B.glowAmber }}>
                  {formatAmount(tx.totalFee)} ({tx.totalFeePercent.toFixed(3)}%)
                </span>
              </div>
              <div
                className="flex justify-between border-t pt-1.5"
                style={{ borderColor: `${B.borderSubtle}60` }}
              >
                <span style={{ color: B.textSecondary }}>RECEIVED:</span>
                <span
                  className="font-bold"
                  style={{
                    color: tokenColor(
                      (isWrap ? wrapped : tx.token) as "QBC" | "QUSD" | "wQBC" | "wQUSD",
                    ),
                  }}
                >
                  {formatAmount(tx.amountReceived)} {isWrap ? wrapped : tx.token}
                </span>
              </div>
            </div>
          </Panel>

          {/* Event log */}
          <EventLog events={tx.eventLog} />
        </div>
      </div>
    </div>
  );
}

/* == Default export wrapper (reads txId from store) ======================= */

export default function TxStatusView() {
  const txId = useBridgeStore((s) => s.viewParams.txId ?? s.activeTxId ?? "");
  return <TxStatusViewInner txId={txId} />;
}
