// ─── QBC EXCHANGE — Deposit Modal ──────────────────────────────────────────────
"use client";

import React, { memo, useState, useCallback, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useExchangeStore } from "./store";
import { X, FONT, formatSize, formatUsd, panelStyle } from "./shared";
import { TOKENS, CHAINS, FEES, getToken } from "./config";

// ─── DEPOSIT ASSET DEFINITIONS ─────────────────────────────────────────────

interface DepositAssetDef {
  symbol: string;
  sourceSymbol: string;
  sourceChain: string;
  chainLabel: string;
  isCrossChain: boolean;
}

const DEPOSIT_ASSETS: DepositAssetDef[] = [
  { symbol: "QBC", sourceSymbol: "QBC", sourceChain: "qbc", chainLabel: "Qubitcoin", isCrossChain: false },
  { symbol: "QUSD", sourceSymbol: "QUSD", sourceChain: "qbc", chainLabel: "Qubitcoin", isCrossChain: false },
  { symbol: "wETH", sourceSymbol: "ETH", sourceChain: "ethereum", chainLabel: "Ethereum", isCrossChain: true },
  { symbol: "wBNB", sourceSymbol: "BNB", sourceChain: "bnb", chainLabel: "BNB Chain", isCrossChain: true },
  { symbol: "wSOL", sourceSymbol: "SOL", sourceChain: "solana", chainLabel: "Solana", isCrossChain: true },
];

// ─── MOCK WALLET BALANCES ──────────────────────────────────────────────────

const WALLET_BALANCES: Record<string, number> = {
  QBC: 4281.44,
  QUSD: 8421.85,
  ETH: 2.4821,
  BNB: 12.5,
  SOL: 25.3,
};

// ─── PROGRESS STEPS ────────────────────────────────────────────────────────

const CROSS_CHAIN_STEPS = ["SIGNED", "LOCKED", "RELAY", "DEPOSITED", "COMPLETE"] as const;
const NATIVE_STEPS = ["SIGNED", "DEPOSITED", "COMPLETE"] as const;

type DepositStep = 1 | 2 | 3;

// ─── HELPERS ───────────────────────────────────────────────────────────────

function getIconLetter(asset: DepositAssetDef): string {
  const token = getToken(asset.symbol);
  return token?.icon ?? asset.sourceSymbol.charAt(0);
}

function getWalletBalance(asset: DepositAssetDef): number {
  return WALLET_BALANCES[asset.sourceSymbol] ?? 0;
}

function getBridgeFee(amount: number): number {
  return amount * FEES.bridgeFee;
}

// ─── MODAL OVERLAY ─────────────────────────────────────────────────────────

const overlayStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  zIndex: 50,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: "rgba(0, 0, 0, 0.75)",
  backdropFilter: "blur(4px)",
};

const modalStyle: React.CSSProperties = {
  ...panelStyle,
  width: 480,
  maxHeight: "90vh",
  overflow: "hidden",
  display: "flex",
  flexDirection: "column",
  boxShadow: `0 0 60px ${X.glowCyan}10, 0 0 120px ${X.bgBase}`,
};

// ─── COMPONENT ─────────────────────────────────────────────────────────────

const DepositModal = memo(function DepositModal() {
  const open = useExchangeStore((s) => s.depositModalOpen);
  const preselected = useExchangeStore((s) => s.depositAsset);
  const setOpen = useExchangeStore((s) => s.setDepositModalOpen);
  const addToast = useExchangeStore((s) => s.addToast);

  const [step, setStep] = useState<DepositStep>(1);
  const [selectedAsset, setSelectedAsset] = useState<DepositAssetDef | null>(null);
  const [amount, setAmount] = useState("");
  const [progressIndex, setProgressIndex] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Reset state when modal opens
  useEffect(() => {
    if (open) {
      const found = DEPOSIT_ASSETS.find((a) => a.symbol === preselected || a.sourceSymbol === preselected);
      setSelectedAsset(found ?? null);
      setStep(found ? 2 : 1);
      setAmount("");
      setProgressIndex(0);
      setIsProcessing(false);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [open, preselected]);

  const close = useCallback(() => {
    setOpen(false);
    if (timerRef.current) clearInterval(timerRef.current);
  }, [setOpen]);

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) close();
    },
    [close],
  );

  const handleSelectAsset = useCallback((asset: DepositAssetDef) => {
    setSelectedAsset(asset);
    setStep(2);
    setAmount("");
    setProgressIndex(0);
    setIsProcessing(false);
  }, []);

  const handleAmountChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    if (val === "" || /^\d*\.?\d*$/.test(val)) {
      setAmount(val);
    }
  }, []);

  const handleMax = useCallback(() => {
    if (!selectedAsset) return;
    const bal = getWalletBalance(selectedAsset);
    setAmount(bal.toString());
  }, [selectedAsset]);

  const parsedAmount = parseFloat(amount) || 0;
  const balance = selectedAsset ? getWalletBalance(selectedAsset) : 0;
  const isValidAmount = parsedAmount > 0 && parsedAmount <= balance;
  const isCrossChain = selectedAsset?.isCrossChain ?? false;
  const bridgeFee = isCrossChain ? getBridgeFee(parsedAmount) : 0;
  const netDeposit = parsedAmount - bridgeFee;
  const progressSteps = isCrossChain ? CROSS_CHAIN_STEPS : NATIVE_STEPS;
  const isComplete = progressIndex >= progressSteps.length - 1;

  const handleDeposit = useCallback(() => {
    if (!isValidAmount || !selectedAsset) return;
    setStep(3);
    setProgressIndex(0);
    setIsProcessing(true);

    const steps = selectedAsset.isCrossChain ? CROSS_CHAIN_STEPS : NATIVE_STEPS;
    let idx = 0;
    timerRef.current = setInterval(() => {
      idx += 1;
      if (idx >= steps.length - 1) {
        setProgressIndex(steps.length - 1);
        setIsProcessing(false);
        if (timerRef.current) clearInterval(timerRef.current);
        addToast(
          `Deposited ${parsedAmount} ${selectedAsset.sourceSymbol} successfully`,
          "success",
        );
      } else {
        setProgressIndex(idx);
      }
    }, 2000);
  }, [isValidAmount, selectedAsset, parsedAmount, addToast]);

  const handleBack = useCallback(() => {
    if (step === 2) {
      setStep(1);
      setSelectedAsset(null);
    } else if (step === 3 && isComplete) {
      close();
    }
  }, [step, isComplete, close]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          style={overlayStyle}
          onClick={handleBackdropClick}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="deposit-modal-title"
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            style={modalStyle}
          >
            {/* Header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "16px 20px",
                borderBottom: `1px solid ${X.borderSubtle}`,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                {step > 1 && !isProcessing && (
                  <button
                    onClick={handleBack}
                    style={{
                      background: "none",
                      border: "none",
                      color: X.textSecondary,
                      cursor: "pointer",
                      fontSize: 16,
                      padding: "0 4px",
                      fontFamily: FONT.mono,
                    }}
                  >
                    &larr;
                  </button>
                )}
                <span
                  id="deposit-modal-title"
                  style={{
                    fontFamily: FONT.display,
                    fontSize: 14,
                    letterSpacing: "0.08em",
                    color: X.textPrimary,
                    textTransform: "uppercase",
                  }}
                >
                  Deposit
                </span>
                <span
                  style={{
                    fontFamily: FONT.mono,
                    fontSize: 11,
                    color: X.textSecondary,
                  }}
                >
                  Step {step}/3
                </span>
              </div>
              <button
                onClick={close}
                style={{
                  background: "none",
                  border: "none",
                  color: X.textSecondary,
                  cursor: "pointer",
                  fontSize: 20,
                  lineHeight: 1,
                  padding: "0 2px",
                  transition: "color 0.15s",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = X.textPrimary)}
                onMouseLeave={(e) => (e.currentTarget.style.color = X.textSecondary)}
              >
                &times;
              </button>
            </div>

            {/* Body */}
            <div
              className="exchange-scroll"
              style={{
                flex: 1,
                overflowY: "auto",
                padding: "20px",
              }}
            >
              {/* Step 1: Select Asset */}
              {step === 1 && (
                <div>
                  <p
                    style={{
                      fontFamily: FONT.body,
                      fontSize: 13,
                      color: X.textSecondary,
                      marginBottom: 16,
                    }}
                  >
                    Select an asset to deposit into the exchange
                  </p>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr",
                      gap: 10,
                    }}
                  >
                    {DEPOSIT_ASSETS.map((asset) => {
                      const isSelected = selectedAsset?.symbol === asset.symbol;
                      return (
                        <button
                          key={asset.symbol}
                          onClick={() => handleSelectAsset(asset)}
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            gap: 6,
                            padding: "16px 12px",
                            background: isSelected ? X.bgElevated : X.bgBase,
                            border: `1px solid ${isSelected ? X.glowCyan + "60" : X.borderSubtle}`,
                            borderRadius: 8,
                            cursor: "pointer",
                            transition: "all 0.15s",
                          }}
                          onMouseEnter={(e) => {
                            if (!isSelected) {
                              e.currentTarget.style.borderColor = X.borderActive;
                              e.currentTarget.style.background = X.bgElevated;
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (!isSelected) {
                              e.currentTarget.style.borderColor = X.borderSubtle;
                              e.currentTarget.style.background = X.bgBase;
                            }
                          }}
                        >
                          {/* Icon circle */}
                          <div
                            style={{
                              width: 40,
                              height: 40,
                              borderRadius: "50%",
                              background: `linear-gradient(135deg, ${X.glowCyan}20, ${X.glowViolet}20)`,
                              border: `1px solid ${X.glowCyan}30`,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontFamily: FONT.display,
                              fontSize: 16,
                              color: X.glowCyan,
                              fontWeight: 700,
                            }}
                          >
                            {getIconLetter(asset)}
                          </div>
                          <span
                            style={{
                              fontFamily: FONT.display,
                              fontSize: 12,
                              letterSpacing: "0.06em",
                              color: X.textPrimary,
                            }}
                          >
                            {asset.symbol}
                          </span>
                          {asset.isCrossChain && (
                            <span
                              style={{
                                fontFamily: FONT.body,
                                fontSize: 10,
                                color: X.textSecondary,
                              }}
                            >
                              {asset.sourceSymbol} from {asset.chainLabel}
                            </span>
                          )}
                          {!asset.isCrossChain && (
                            <span
                              style={{
                                fontFamily: FONT.body,
                                fontSize: 10,
                                color: X.textSecondary,
                              }}
                            >
                              Native
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Step 2: Enter Amount */}
              {step === 2 && selectedAsset && (
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  {/* Selected asset info */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                      padding: "12px 14px",
                      background: X.bgBase,
                      borderRadius: 8,
                      border: `1px solid ${X.borderSubtle}`,
                    }}
                  >
                    <div
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: "50%",
                        background: `linear-gradient(135deg, ${X.glowCyan}20, ${X.glowViolet}20)`,
                        border: `1px solid ${X.glowCyan}30`,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontFamily: FONT.display,
                        fontSize: 14,
                        color: X.glowCyan,
                        fontWeight: 700,
                      }}
                    >
                      {getIconLetter(selectedAsset)}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div
                        style={{
                          fontFamily: FONT.display,
                          fontSize: 13,
                          color: X.textPrimary,
                          letterSpacing: "0.04em",
                        }}
                      >
                        {selectedAsset.symbol}
                      </div>
                      {selectedAsset.isCrossChain && (
                        <div
                          style={{
                            fontFamily: FONT.body,
                            fontSize: 11,
                            color: X.textSecondary,
                            marginTop: 2,
                          }}
                        >
                          Bridge {selectedAsset.sourceSymbol} from{" "}
                          {CHAINS[selectedAsset.sourceChain]?.name ?? selectedAsset.chainLabel}
                        </div>
                      )}
                      {!selectedAsset.isCrossChain && (
                        <div
                          style={{
                            fontFamily: FONT.body,
                            fontSize: 11,
                            color: X.textSecondary,
                            marginTop: 2,
                          }}
                        >
                          Direct deposit on Qubitcoin
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Wallet balance */}
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <span
                      style={{
                        fontFamily: FONT.body,
                        fontSize: 12,
                        color: X.textSecondary,
                      }}
                    >
                      Wallet Balance
                    </span>
                    <span
                      style={{
                        fontFamily: FONT.mono,
                        fontSize: 13,
                        color: X.textPrimary,
                      }}
                    >
                      {formatSize(balance, 4)} {selectedAsset.sourceSymbol}
                    </span>
                  </div>

                  {/* Amount input */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "12px 14px",
                      background: X.bgBase,
                      border: `1px solid ${amount && !isValidAmount && parsedAmount > 0 ? X.glowCrimson + "60" : X.borderSubtle}`,
                      borderRadius: 8,
                      transition: "border-color 0.15s",
                    }}
                  >
                    <input
                      type="text"
                      inputMode="decimal"
                      value={amount}
                      onChange={handleAmountChange}
                      placeholder="0.00"
                      style={{
                        flex: 1,
                        background: "none",
                        border: "none",
                        outline: "none",
                        fontFamily: FONT.mono,
                        fontSize: 18,
                        color: X.textPrimary,
                      }}
                    />
                    <span
                      style={{
                        fontFamily: FONT.display,
                        fontSize: 12,
                        color: X.textSecondary,
                        letterSpacing: "0.06em",
                        marginRight: 8,
                      }}
                    >
                      {selectedAsset.sourceSymbol}
                    </span>
                    <button
                      onClick={handleMax}
                      style={{
                        fontFamily: FONT.display,
                        fontSize: 10,
                        letterSpacing: "0.08em",
                        color: X.glowCyan,
                        background: X.glowCyan + "12",
                        border: `1px solid ${X.glowCyan}30`,
                        borderRadius: 4,
                        padding: "4px 10px",
                        cursor: "pointer",
                        transition: "all 0.15s",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = X.glowCyan + "25";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = X.glowCyan + "12";
                      }}
                    >
                      MAX
                    </button>
                  </div>

                  {parsedAmount > balance && (
                    <span
                      style={{
                        fontFamily: FONT.body,
                        fontSize: 11,
                        color: X.glowCrimson,
                        marginTop: -8,
                      }}
                    >
                      Insufficient balance
                    </span>
                  )}

                  {/* Cross-chain details */}
                  {isCrossChain && parsedAmount > 0 && (
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 10,
                        padding: "12px 14px",
                        background: X.bgBase,
                        borderRadius: 8,
                        border: `1px solid ${X.borderSubtle}`,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                        }}
                      >
                        <span style={{ fontFamily: FONT.body, fontSize: 12, color: X.textSecondary }}>
                          Bridge Fee ({(FEES.bridgeFee * 100).toFixed(2)}%)
                        </span>
                        <span style={{ fontFamily: FONT.mono, fontSize: 12, color: X.glowAmber }}>
                          -{formatSize(bridgeFee, 6)} {selectedAsset.sourceSymbol}
                        </span>
                      </div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                        }}
                      >
                        <span style={{ fontFamily: FONT.body, fontSize: 12, color: X.textSecondary }}>
                          Net Deposit
                        </span>
                        <span style={{ fontFamily: FONT.mono, fontSize: 12, color: X.glowEmerald }}>
                          {formatSize(netDeposit > 0 ? netDeposit : 0, 6)} {selectedAsset.symbol}
                        </span>
                      </div>
                      <div
                        style={{
                          width: "100%",
                          height: 1,
                          background: X.borderSubtle,
                        }}
                      />
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                        }}
                      >
                        <span style={{ fontFamily: FONT.body, fontSize: 12, color: X.textSecondary }}>
                          Est. Time
                        </span>
                        <span style={{ fontFamily: FONT.mono, fontSize: 12, color: X.textPrimary }}>
                          4-8 minutes
                        </span>
                      </div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                        }}
                      >
                        <span style={{ fontFamily: FONT.body, fontSize: 12, color: X.textSecondary }}>
                          Source Chain
                        </span>
                        <span style={{ fontFamily: FONT.mono, fontSize: 12, color: X.textPrimary }}>
                          {CHAINS[selectedAsset.sourceChain]?.name ?? selectedAsset.chainLabel}
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Native deposit info */}
                  {!isCrossChain && parsedAmount > 0 && (
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 10,
                        padding: "12px 14px",
                        background: X.bgBase,
                        borderRadius: 8,
                        border: `1px solid ${X.borderSubtle}`,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                        }}
                      >
                        <span style={{ fontFamily: FONT.body, fontSize: 12, color: X.textSecondary }}>
                          Bridge Fee
                        </span>
                        <span style={{ fontFamily: FONT.mono, fontSize: 12, color: X.glowEmerald }}>
                          None
                        </span>
                      </div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                        }}
                      >
                        <span style={{ fontFamily: FONT.body, fontSize: 12, color: X.textSecondary }}>
                          Est. Time
                        </span>
                        <span style={{ fontFamily: FONT.mono, fontSize: 12, color: X.textPrimary }}>
                          Near-instant
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Step 3: Progress */}
              {step === 3 && selectedAsset && (
                <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                  {/* Amount summary */}
                  <div
                    style={{
                      textAlign: "center",
                      padding: "12px 0",
                    }}
                  >
                    <div
                      style={{
                        fontFamily: FONT.mono,
                        fontSize: 28,
                        color: X.textPrimary,
                        marginBottom: 4,
                      }}
                    >
                      {formatSize(parsedAmount, 6)}
                    </div>
                    <div
                      style={{
                        fontFamily: FONT.display,
                        fontSize: 12,
                        color: X.textSecondary,
                        letterSpacing: "0.06em",
                      }}
                    >
                      {selectedAsset.sourceSymbol} {isCrossChain ? `\u2192 ${selectedAsset.symbol}` : ""}
                    </div>
                  </div>

                  {/* Progress steps */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
                    {progressSteps.map((stepLabel, idx) => {
                      const isDone = idx <= progressIndex;
                      const isCurrent = idx === progressIndex && !isComplete;
                      const isLast = idx === progressSteps.length - 1;

                      return (
                        <div key={stepLabel} style={{ display: "flex", alignItems: "stretch", gap: 14 }}>
                          {/* Timeline */}
                          <div
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              alignItems: "center",
                              width: 24,
                            }}
                          >
                            {/* Dot */}
                            <div
                              style={{
                                width: 20,
                                height: 20,
                                borderRadius: "50%",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                fontSize: 11,
                                fontFamily: FONT.mono,
                                flexShrink: 0,
                                background: isDone
                                  ? isLast && isComplete
                                    ? X.glowEmerald
                                    : X.glowCyan
                                  : X.bgBase,
                                border: `2px solid ${isDone ? (isLast && isComplete ? X.glowEmerald : X.glowCyan) : X.borderSubtle}`,
                                color: isDone ? X.bgBase : X.textSecondary,
                                transition: "all 0.3s",
                                ...(isCurrent
                                  ? {
                                      boxShadow: `0 0 10px ${X.glowCyan}60`,
                                    }
                                  : {}),
                              }}
                            >
                              {isDone ? "\u2713" : ""}
                            </div>
                            {/* Connecting line */}
                            {!isLast && (
                              <div
                                style={{
                                  width: 2,
                                  flex: 1,
                                  minHeight: 24,
                                  background: idx < progressIndex ? X.glowCyan + "60" : X.borderSubtle,
                                  transition: "background 0.3s",
                                }}
                              />
                            )}
                          </div>
                          {/* Label */}
                          <div
                            style={{
                              paddingBottom: isLast ? 0 : 16,
                              display: "flex",
                              flexDirection: "column",
                              justifyContent: "center",
                              minHeight: 20,
                            }}
                          >
                            <span
                              style={{
                                fontFamily: FONT.display,
                                fontSize: 11,
                                letterSpacing: "0.08em",
                                color: isDone ? X.textPrimary : X.textSecondary,
                                transition: "color 0.3s",
                              }}
                            >
                              {stepLabel}
                            </span>
                            {isCurrent && (
                              <span
                                style={{
                                  fontFamily: FONT.body,
                                  fontSize: 10,
                                  color: X.glowCyan,
                                  marginTop: 2,
                                }}
                              >
                                Processing...
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Completion message */}
                  {isComplete && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3 }}
                      style={{
                        textAlign: "center",
                        padding: "16px",
                        background: X.glowEmerald + "10",
                        border: `1px solid ${X.glowEmerald}30`,
                        borderRadius: 8,
                      }}
                    >
                      <div
                        style={{
                          fontSize: 32,
                          marginBottom: 8,
                          color: X.glowEmerald,
                        }}
                      >
                        &#10003;
                      </div>
                      <div
                        style={{
                          fontFamily: FONT.display,
                          fontSize: 13,
                          color: X.glowEmerald,
                          letterSpacing: "0.06em",
                          marginBottom: 4,
                        }}
                      >
                        DEPOSIT COMPLETE
                      </div>
                      <div
                        style={{
                          fontFamily: FONT.body,
                          fontSize: 12,
                          color: X.textSecondary,
                        }}
                      >
                        {isCrossChain
                          ? `${formatSize(netDeposit, 6)} ${selectedAsset.symbol} credited to your exchange account`
                          : `${formatSize(parsedAmount, 6)} ${selectedAsset.symbol} credited to your exchange account`}
                      </div>
                    </motion.div>
                  )}
                </div>
              )}
            </div>

            {/* Footer */}
            <div
              style={{
                display: "flex",
                gap: 10,
                padding: "16px 20px",
                borderTop: `1px solid ${X.borderSubtle}`,
              }}
            >
              {step === 3 && isComplete ? (
                <button
                  onClick={close}
                  style={{
                    flex: 1,
                    padding: "10px 0",
                    fontFamily: FONT.display,
                    fontSize: 12,
                    letterSpacing: "0.08em",
                    color: X.bgBase,
                    background: X.glowEmerald,
                    border: "none",
                    borderRadius: 6,
                    cursor: "pointer",
                    transition: "opacity 0.15s",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.85")}
                  onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
                >
                  DONE
                </button>
              ) : (
                <>
                  <button
                    onClick={close}
                    disabled={isProcessing}
                    style={{
                      flex: 1,
                      padding: "10px 0",
                      fontFamily: FONT.display,
                      fontSize: 12,
                      letterSpacing: "0.08em",
                      color: isProcessing ? X.textSecondary + "60" : X.textSecondary,
                      background: X.bgBase,
                      border: `1px solid ${X.borderSubtle}`,
                      borderRadius: 6,
                      cursor: isProcessing ? "not-allowed" : "pointer",
                      transition: "all 0.15s",
                    }}
                  >
                    CANCEL
                  </button>
                  {step === 2 && (
                    <button
                      onClick={handleDeposit}
                      disabled={!isValidAmount}
                      style={{
                        flex: 1,
                        padding: "10px 0",
                        fontFamily: FONT.display,
                        fontSize: 12,
                        letterSpacing: "0.08em",
                        color: isValidAmount ? X.bgBase : X.textSecondary + "60",
                        background: isValidAmount ? X.glowCyan : X.bgElevated,
                        border: isValidAmount ? "none" : `1px solid ${X.borderSubtle}`,
                        borderRadius: 6,
                        cursor: isValidAmount ? "pointer" : "not-allowed",
                        transition: "all 0.15s",
                        ...(isValidAmount
                          ? { boxShadow: `0 0 20px ${X.glowCyan}30` }
                          : {}),
                      }}
                      onMouseEnter={(e) => {
                        if (isValidAmount) e.currentTarget.style.opacity = "0.85";
                      }}
                      onMouseLeave={(e) => {
                        if (isValidAmount) e.currentTarget.style.opacity = "1";
                      }}
                    >
                      DEPOSIT
                    </button>
                  )}
                  {step === 3 && isProcessing && (
                    <button
                      disabled
                      style={{
                        flex: 1,
                        padding: "10px 0",
                        fontFamily: FONT.display,
                        fontSize: 12,
                        letterSpacing: "0.08em",
                        color: X.glowCyan,
                        background: X.glowCyan + "12",
                        border: `1px solid ${X.glowCyan}30`,
                        borderRadius: 6,
                        cursor: "not-allowed",
                      }}
                    >
                      PROCESSING...
                    </button>
                  )}
                </>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
});

export default DepositModal;
