// ─── QBC EXCHANGE — Order Entry Panel ────────────────────────────────────────
"use client";

import React, { memo, useState, useMemo, useCallback } from "react";
import type { OrderType, TIF } from "./types";
import { useMarket, useBalances } from "./hooks";
import { useExchangeStore } from "./store";
import { X, FONT, formatPrice, formatUsd, panelStyle } from "./shared";
import { FEES, getMarketConfig } from "./config";

// ─── CONSTANTS ──────────────────────────────────────────────────────────────

const ORDER_TYPES: { key: OrderType; label: string }[] = [
  { key: "limit", label: "LIMIT" },
  { key: "market", label: "MARKET" },
  { key: "stop_limit", label: "STOP LIMIT" },
  { key: "stop_market", label: "STOP MARKET" },
];

const TIF_OPTIONS: { key: TIF; label: string; title: string }[] = [
  { key: "gtc", label: "GTC", title: "Good Till Cancelled" },
  { key: "ioc", label: "IOC", title: "Immediate or Cancel" },
  { key: "fok", label: "FOK", title: "Fill or Kill" },
  { key: "post", label: "POST", title: "Post Only (maker)" },
];

const PCT_BUTTONS = [25, 50, 75, 100] as const;

// ─── STYLES ─────────────────────────────────────────────────────────────────

const inputWrapStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 4,
};

const labelStyle: React.CSSProperties = {
  fontFamily: FONT.body,
  fontSize: 11,
  color: X.textSecondary,
  letterSpacing: "0.03em",
};

const baseInputStyle: React.CSSProperties = {
  width: "100%",
  height: 36,
  background: X.bgElevated,
  border: `1px solid ${X.borderSubtle}`,
  borderRadius: 6,
  padding: "0 10px",
  fontFamily: FONT.mono,
  fontSize: 13,
  color: X.textPrimary,
  outline: "none",
  boxSizing: "border-box",
};

const suffixWrapStyle: React.CSSProperties = {
  position: "relative",
  width: "100%",
};

const suffixStyle: React.CSSProperties = {
  position: "absolute",
  right: 10,
  top: "50%",
  transform: "translateY(-50%)",
  fontFamily: FONT.mono,
  fontSize: 11,
  color: X.textSecondary,
  pointerEvents: "none",
};

const errorStyle: React.CSSProperties = {
  fontFamily: FONT.body,
  fontSize: 10,
  color: X.glowCrimson,
  marginTop: 2,
};

// ─── INPUT COMPONENT ────────────────────────────────────────────────────────

const OrderInput = memo(function OrderInput({
  label,
  value,
  onChange,
  suffix,
  placeholder,
  error,
  disabled,
  "aria-label": ariaLabel,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  suffix?: string;
  placeholder?: string;
  error?: string;
  disabled?: boolean;
  "aria-label"?: string;
}) {
  const [focused, setFocused] = useState(false);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const raw = e.target.value;
      // Allow empty, digits, single dot, leading minus for trigger prices
      if (raw === "" || /^-?\d*\.?\d*$/.test(raw)) {
        onChange(raw);
      }
    },
    [onChange],
  );

  return (
    <div style={inputWrapStyle}>
      <label style={labelStyle}>{label}</label>
      <div style={suffixWrapStyle}>
        <input
          type="text"
          inputMode="decimal"
          value={value}
          onChange={handleChange}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder ?? "0.00"}
          disabled={disabled}
          aria-label={ariaLabel ?? label}
          style={{
            ...baseInputStyle,
            borderColor: error
              ? X.glowCrimson
              : focused
                ? X.glowCyan
                : X.borderSubtle,
            opacity: disabled ? 0.5 : 1,
            paddingRight: suffix ? 60 : 10,
          }}
        />
        {suffix && <span style={suffixStyle}>{suffix}</span>}
      </div>
      {error && <span style={errorStyle}>{error}</span>}
    </div>
  );
});

// ─── MAIN COMPONENT ─────────────────────────────────────────────────────────

export const OrderEntry = memo(function OrderEntry() {
  const activeMarket = useExchangeStore((s) => s.activeMarket);
  const orderSide = useExchangeStore((s) => s.orderSide);
  const setOrderSide = useExchangeStore((s) => s.setOrderSide);
  const orderType = useExchangeStore((s) => s.orderType);
  const setOrderType = useExchangeStore((s) => s.setOrderType);
  const orderPrice = useExchangeStore((s) => s.orderPrice);
  const setOrderPrice = useExchangeStore((s) => s.setOrderPrice);
  const orderSize = useExchangeStore((s) => s.orderSize);
  const setOrderSize = useExchangeStore((s) => s.setOrderSize);
  const orderTriggerPrice = useExchangeStore((s) => s.orderTriggerPrice);
  const setOrderTriggerPrice = useExchangeStore((s) => s.setOrderTriggerPrice);
  const orderLeverage = useExchangeStore((s) => s.orderLeverage);
  const setOrderLeverage = useExchangeStore((s) => s.setOrderLeverage);
  const orderTif = useExchangeStore((s) => s.orderTif);
  const setOrderTif = useExchangeStore((s) => s.setOrderTif);
  const orderReduceOnly = useExchangeStore((s) => s.orderReduceOnly);
  const setOrderReduceOnly = useExchangeStore((s) => s.setOrderReduceOnly);
  const addToast = useExchangeStore((s) => s.addToast);

  const { data: market } = useMarket(activeMarket);
  const { data: balances } = useBalances();

  const [submitting, setSubmitting] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const marketConfig = useMemo(
    () => getMarketConfig(activeMarket),
    [activeMarket],
  );

  const isPerp = market?.type === "perp";
  const baseAsset = market?.baseAsset ?? "QBC";
  const quoteAsset = market?.quoteAsset ?? "QUSD";

  // ─── Available balance ──────────────────────────────────────────────────

  const qusdBalance = useMemo(() => {
    if (!balances) return 0;
    const b = balances.find((b) => b.asset === "QUSD");
    return b?.available ?? 0;
  }, [balances]);

  const baseBalance = useMemo(() => {
    if (!balances) return 0;
    const b = balances.find((b) => b.asset === baseAsset);
    return b?.available ?? 0;
  }, [balances, baseAsset]);

  const availableBalance = orderSide === "buy" ? qusdBalance : baseBalance;
  const availableAsset = orderSide === "buy" ? quoteAsset : baseAsset;

  // ─── Parsed values ────────────────────────────────────────────────────

  const priceNum = parseFloat(orderPrice) || 0;
  const sizeNum = parseFloat(orderSize) || 0;
  const triggerNum = parseFloat(orderTriggerPrice) || 0;
  const currentPrice = market?.lastPrice ?? 0;

  const effectivePrice = useMemo(() => {
    if (orderType === "market" || orderType === "stop_market") return currentPrice;
    return priceNum;
  }, [orderType, priceNum, currentPrice]);

  const total = effectivePrice * sizeNum;

  const leveragedMargin = useMemo(() => {
    if (!isPerp || orderLeverage <= 0) return total;
    return total / orderLeverage;
  }, [isPerp, total, orderLeverage]);

  // ─── Fee estimate ─────────────────────────────────────────────────────

  const estFee = useMemo(() => {
    const rate = orderTif === "post" ? FEES.maker : FEES.taker;
    return total * rate;
  }, [total, orderTif]);

  // ─── Validation ───────────────────────────────────────────────────────

  const validation = useMemo(() => {
    const errors: {
      price?: string;
      size?: string;
      triggerPrice?: string;
      balance?: string;
      leverage?: string;
    } = {};

    // Price validation (limit and stop_limit types)
    if (orderType === "limit" || orderType === "stop_limit") {
      if (orderPrice !== "" && priceNum <= 0) {
        errors.price = "Invalid price";
      }
    }

    // Size validation
    if (orderSize !== "" && sizeNum <= 0) {
      errors.size = "Invalid size";
    }

    if (
      orderSize !== "" &&
      marketConfig &&
      sizeNum > 0 &&
      sizeNum < marketConfig.minOrderSize
    ) {
      errors.size = `Min size: ${marketConfig.minOrderSize}`;
    }

    // Trigger price validation
    if (orderType === "stop_limit" || orderType === "stop_market") {
      if (orderTriggerPrice !== "" && triggerNum <= 0) {
        errors.triggerPrice = "Invalid trigger price";
      }
    }

    // Balance validation
    if (sizeNum > 0 && effectivePrice > 0) {
      if (orderSide === "buy") {
        const required = isPerp ? leveragedMargin : total;
        if (required > qusdBalance) {
          errors.balance = `Insufficient ${quoteAsset} balance`;
        }
      } else {
        if (!isPerp && sizeNum > baseBalance) {
          errors.balance = `Insufficient ${baseAsset} balance`;
        }
        if (isPerp && leveragedMargin > qusdBalance) {
          errors.balance = `Insufficient ${quoteAsset} margin`;
        }
      }
    }

    // Leverage validation
    if (isPerp && market && orderLeverage > market.maxLeverage) {
      errors.leverage = "Exceeds maximum leverage";
    }

    return errors;
  }, [
    orderType,
    orderPrice,
    priceNum,
    orderSize,
    sizeNum,
    orderTriggerPrice,
    triggerNum,
    orderSide,
    effectivePrice,
    total,
    leveragedMargin,
    qusdBalance,
    baseBalance,
    isPerp,
    market,
    marketConfig,
    orderLeverage,
    baseAsset,
    quoteAsset,
  ]);

  const hasErrors = Object.keys(validation).length > 0;

  const canSubmit = useMemo(() => {
    if (submitting) return false;
    if (hasErrors) return false;
    if (sizeNum <= 0) return false;
    if (
      (orderType === "limit" || orderType === "stop_limit") &&
      priceNum <= 0
    )
      return false;
    if (
      (orderType === "stop_limit" || orderType === "stop_market") &&
      triggerNum <= 0
    )
      return false;
    return true;
  }, [submitting, hasErrors, sizeNum, priceNum, triggerNum, orderType]);

  // ─── Percentage fill helpers ──────────────────────────────────────────

  const handlePctClick = useCallback(
    (pct: number) => {
      if (orderSide === "buy") {
        if (effectivePrice <= 0 || qusdBalance <= 0) return;
        const maxSize = (qusdBalance * (pct / 100)) / effectivePrice;
        const decimals = marketConfig?.stepSize
          ? Math.max(0, -Math.floor(Math.log10(marketConfig.stepSize)))
          : 2;
        setOrderSize(maxSize.toFixed(decimals));
      } else {
        if (baseBalance <= 0) return;
        const s = baseBalance * (pct / 100);
        const decimals = marketConfig?.stepSize
          ? Math.max(0, -Math.floor(Math.log10(marketConfig.stepSize)))
          : 2;
        setOrderSize(s.toFixed(decimals));
      }
    },
    [
      orderSide,
      effectivePrice,
      qusdBalance,
      baseBalance,
      marketConfig,
      setOrderSize,
    ],
  );

  // ─── Submit ───────────────────────────────────────────────────────────

  const handleSubmit = useCallback(() => {
    if (!canSubmit) return;
    setSubmitting(true);
    // Simulate order submission
    setTimeout(() => {
      setSubmitting(false);
      const sideLabel = orderSide === "buy" ? "BUY" : "SELL";
      addToast(
        `Order submitted: ${sideLabel} ${orderSize} ${baseAsset} @ ${orderType === "market" ? "MARKET" : formatPrice(effectivePrice, market?.decimals ?? 4)}`,
        "success",
      );
      setOrderSize("");
      if (orderType === "limit") setOrderPrice("");
      if (orderType === "stop_limit" || orderType === "stop_market") {
        setOrderTriggerPrice("");
        if (orderType === "stop_limit") setOrderPrice("");
      }
    }, 600);
  }, [
    canSubmit,
    orderSide,
    orderSize,
    baseAsset,
    orderType,
    effectivePrice,
    market,
    addToast,
    setOrderSize,
    setOrderPrice,
    setOrderTriggerPrice,
  ]);

  // ─── RENDER ───────────────────────────────────────────────────────────

  const isBuy = orderSide === "buy";
  const sideColor = isBuy ? X.glowEmerald : X.glowCrimson;

  return (
    <div
      style={{
        ...panelStyle,
        display: "flex",
        flexDirection: "column",
        gap: 0,
        overflow: "hidden",
      }}
    >
      {/* ─── Buy / Sell Toggle ─────────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 0,
        }}
      >
        <button
          onClick={() => setOrderSide("buy")}
          style={{
            height: 40,
            fontFamily: FONT.display,
            fontSize: 12,
            letterSpacing: "0.1em",
            background: isBuy ? X.glowEmerald + "14" : "transparent",
            color: isBuy ? X.glowEmerald : X.textSecondary,
            border: "none",
            borderBottom: isBuy
              ? `2px solid ${X.glowEmerald}`
              : `2px solid ${X.borderSubtle}`,
            cursor: "pointer",
            transition: "all 0.15s",
          }}
        >
          BUY
        </button>
        <button
          onClick={() => setOrderSide("sell")}
          style={{
            height: 40,
            fontFamily: FONT.display,
            fontSize: 12,
            letterSpacing: "0.1em",
            background: !isBuy ? X.glowCrimson + "14" : "transparent",
            color: !isBuy ? X.glowCrimson : X.textSecondary,
            border: "none",
            borderBottom: !isBuy
              ? `2px solid ${X.glowCrimson}`
              : `2px solid ${X.borderSubtle}`,
            cursor: "pointer",
            transition: "all 0.15s",
          }}
        >
          SELL
        </button>
      </div>

      {/* ─── Order Type Tabs ──────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          gap: 0,
          borderBottom: `1px solid ${X.borderSubtle}`,
          overflowX: "auto",
        }}
      >
        {ORDER_TYPES.map((ot) => {
          const active = orderType === ot.key;
          return (
            <button
              key={ot.key}
              onClick={() => setOrderType(ot.key)}
              style={{
                flex: "0 0 auto",
                fontFamily: FONT.display,
                fontSize: 9,
                letterSpacing: "0.06em",
                color: active ? X.glowCyan : X.textSecondary,
                background: "none",
                border: "none",
                borderBottom: active
                  ? `2px solid ${X.glowCyan}`
                  : "2px solid transparent",
                padding: "8px 10px",
                cursor: "pointer",
                whiteSpace: "nowrap",
                transition: "color 0.15s, border-color 0.15s",
              }}
            >
              {ot.label}
            </button>
          );
        })}
      </div>

      {/* ─── Form Body ────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 12,
          padding: 14,
        }}
      >
        {/* Available balance */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span style={{ fontFamily: FONT.body, fontSize: 11, color: X.textSecondary }}>
            Available
          </span>
          <span style={{ fontFamily: FONT.mono, fontSize: 12, color: X.textPrimary }}>
            {formatPrice(availableBalance, 4)} {availableAsset}
          </span>
        </div>

        {/* ── Trigger Price (stop orders) ────────────────────────── */}
        {(orderType === "stop_limit" || orderType === "stop_market") && (
          <OrderInput
            label="Trigger Price"
            value={orderTriggerPrice}
            onChange={setOrderTriggerPrice}
            suffix={quoteAsset}
            placeholder="0.00"
            error={validation.triggerPrice}
            aria-label="Trigger price"
          />
        )}

        {/* ── Price (limit and stop_limit) ───────────────────────── */}
        {(orderType === "limit" || orderType === "stop_limit") && (
          <OrderInput
            label="Price"
            value={orderPrice}
            onChange={setOrderPrice}
            suffix={quoteAsset}
            placeholder="0.00"
            error={validation.price}
            aria-label="Order price"
          />
        )}

        {/* ── Market price display (market orders) ───────────────── */}
        {(orderType === "market" || orderType === "stop_market") && (
          <div style={inputWrapStyle}>
            <label style={labelStyle}>
              {orderType === "market" ? "Est. Fill Price" : "Est. Fill Price"}
            </label>
            <div
              style={{
                ...baseInputStyle,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                background: X.bgElevated,
                opacity: 0.8,
                cursor: "default",
              }}
            >
              <span style={{ color: X.textPrimary }}>
                {currentPrice > 0 ? formatPrice(currentPrice, market?.decimals ?? 4) : "---"}
              </span>
              <span
                style={{
                  fontFamily: FONT.mono,
                  fontSize: 11,
                  color: X.textSecondary,
                }}
              >
                {quoteAsset}
              </span>
            </div>
            {orderType === "market" && sizeNum > 0 && currentPrice > 0 && (
              <span
                style={{
                  fontFamily: FONT.body,
                  fontSize: 10,
                  color: X.textSecondary,
                  marginTop: 2,
                }}
              >
                Market impact: ~{(sizeNum * 0.001).toFixed(4)}%
              </span>
            )}
          </div>
        )}

        {/* ── Size ───────────────────────────────────────────────── */}
        <OrderInput
          label="Size"
          value={orderSize}
          onChange={setOrderSize}
          suffix={baseAsset}
          placeholder="0.00"
          error={validation.size}
          aria-label="Order size"
        />

        {/* ── Percentage Buttons ─────────────────────────────────── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 6 }}>
          {PCT_BUTTONS.map((pct) => (
            <button
              key={pct}
              onClick={() => handlePctClick(pct)}
              style={{
                height: 26,
                fontFamily: FONT.mono,
                fontSize: 11,
                color: X.textSecondary,
                background: X.bgElevated,
                border: `1px solid ${X.borderSubtle}`,
                borderRadius: 4,
                cursor: "pointer",
                transition: "all 0.12s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = sideColor;
                e.currentTarget.style.color = sideColor;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = X.borderSubtle;
                e.currentTarget.style.color = X.textSecondary;
              }}
            >
              {pct}%
            </button>
          ))}
        </div>

        {/* ── Total ──────────────────────────────────────────────── */}
        {effectivePrice > 0 && sizeNum > 0 && (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "8px 10px",
              background: X.bgElevated,
              borderRadius: 6,
              border: `1px solid ${X.borderSubtle}`,
            }}
          >
            <span style={{ fontFamily: FONT.body, fontSize: 11, color: X.textSecondary }}>
              Total
            </span>
            <span style={{ fontFamily: FONT.mono, fontSize: 13, color: X.textPrimary }}>
              {formatPrice(total, 4)} {quoteAsset}
            </span>
          </div>
        )}

        {/* Balance error (shown outside input) */}
        {validation.balance && (
          <span style={errorStyle}>{validation.balance}</span>
        )}

        {/* ── Leverage Slider (perps only) ───────────────────────── */}
        {isPerp && market && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <label style={labelStyle}>Leverage</label>
              <span
                style={{
                  fontFamily: FONT.mono,
                  fontSize: 13,
                  color: X.glowCyan,
                  fontWeight: 600,
                }}
              >
                {orderLeverage}x
              </span>
            </div>
            <input
              type="range"
              min={1}
              max={market.maxLeverage}
              step={1}
              value={orderLeverage}
              onChange={(e) => setOrderLeverage(parseInt(e.target.value, 10))}
              aria-label="Leverage"
              aria-valuemin={1}
              aria-valuemax={market.maxLeverage}
              aria-valuenow={orderLeverage}
              style={{
                width: "100%",
                accentColor: X.glowCyan,
                cursor: "pointer",
                height: 4,
              }}
            />
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontFamily: FONT.mono,
                fontSize: 9,
                color: X.textSecondary,
              }}
            >
              <span>1x</span>
              <span>{market.maxLeverage}x</span>
            </div>
            {validation.leverage && (
              <span style={errorStyle}>{validation.leverage}</span>
            )}

            {/* Position value and margin */}
            {sizeNum > 0 && effectivePrice > 0 && (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  padding: "8px 10px",
                  background: X.bgElevated,
                  borderRadius: 6,
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
                  <span style={{ fontFamily: FONT.body, fontSize: 11, color: X.textSecondary }}>
                    Position Value
                  </span>
                  <span style={{ fontFamily: FONT.mono, fontSize: 12, color: X.textPrimary }}>
                    {formatUsd(total)}
                  </span>
                </div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span style={{ fontFamily: FONT.body, fontSize: 11, color: X.textSecondary }}>
                    Margin Required
                  </span>
                  <span style={{ fontFamily: FONT.mono, fontSize: 12, color: X.glowAmber }}>
                    {formatUsd(leveragedMargin)}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Advanced Section (collapsible) ─────────────────────── */}
        <div>
          <button
            onClick={() => setAdvancedOpen((p) => !p)}
            style={{
              width: "100%",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "4px 0",
            }}
          >
            <span
              style={{
                fontFamily: FONT.body,
                fontSize: 11,
                color: X.textSecondary,
                letterSpacing: "0.03em",
              }}
            >
              Advanced
            </span>
            <span
              style={{
                fontFamily: FONT.mono,
                fontSize: 10,
                color: X.textSecondary,
                transform: advancedOpen ? "rotate(180deg)" : "rotate(0deg)",
                transition: "transform 0.2s",
              }}
            >
              ▼
            </span>
          </button>

          {advancedOpen && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 10,
                paddingTop: 8,
              }}
            >
              {/* TIF selector */}
              <div style={inputWrapStyle}>
                <label style={labelStyle}>Time in Force</label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 4 }}>
                  {TIF_OPTIONS.map((t) => {
                    const active = orderTif === t.key;
                    return (
                      <button
                        key={t.key}
                        onClick={() => setOrderTif(t.key)}
                        title={t.title}
                        style={{
                          height: 28,
                          fontFamily: FONT.display,
                          fontSize: 9,
                          letterSpacing: "0.06em",
                          color: active ? X.glowCyan : X.textSecondary,
                          background: active ? X.glowCyan + "14" : X.bgElevated,
                          border: `1px solid ${active ? X.glowCyan + "60" : X.borderSubtle}`,
                          borderRadius: 4,
                          cursor: "pointer",
                          transition: "all 0.12s",
                        }}
                      >
                        {t.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Reduce-only toggle (perps only) */}
              {isPerp && (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span style={{ fontFamily: FONT.body, fontSize: 11, color: X.textSecondary }}>
                    Reduce Only
                  </span>
                  <button
                    onClick={() => setOrderReduceOnly(!orderReduceOnly)}
                    style={{
                      width: 36,
                      height: 20,
                      borderRadius: 10,
                      border: "none",
                      background: orderReduceOnly
                        ? X.glowCyan
                        : X.borderSubtle,
                      cursor: "pointer",
                      position: "relative",
                      transition: "background 0.2s",
                    }}
                  >
                    <span
                      style={{
                        position: "absolute",
                        top: 2,
                        left: orderReduceOnly ? 18 : 2,
                        width: 16,
                        height: 16,
                        borderRadius: "50%",
                        background: X.textPrimary,
                        transition: "left 0.2s",
                      }}
                    />
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Fee Preview ────────────────────────────────────────── */}
        <div
          style={{
            fontFamily: FONT.mono,
            fontSize: 10,
            color: X.textSecondary,
            lineHeight: 1.6,
            borderTop: `1px solid ${X.borderSubtle}`,
            paddingTop: 10,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Maker: {(FEES.maker * 100).toFixed(2)}%</span>
            <span>Taker: {(FEES.taker * 100).toFixed(2)}%</span>
          </div>
          {total > 0 && (
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginTop: 2,
              }}
            >
              <span>Est. fee</span>
              <span style={{ color: X.textPrimary }}>
                {formatPrice(estFee, 6)} {quoteAsset}
              </span>
            </div>
          )}
        </div>

        {/* ── Signature Info ────────────────────────────────────── */}
        <div
          style={{
            fontFamily: FONT.body,
            fontSize: 9,
            color: X.textSecondary,
            textAlign: "center",
            opacity: 0.6,
            letterSpacing: "0.02em",
          }}
        >
          Orders signed with CRYSTALS-Dilithium2 post-quantum signatures when wallet is connected
        </div>

        {/* ── Submit Button ──────────────────────────────────────── */}
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          style={{
            width: "100%",
            height: 48,
            fontFamily: FONT.display,
            fontSize: 13,
            letterSpacing: "0.1em",
            color: canSubmit ? "#ffffff" : X.textSecondary,
            background: canSubmit
              ? isBuy
                ? X.glowEmerald
                : X.glowCrimson
              : X.borderSubtle,
            border: "none",
            borderRadius: 8,
            cursor: canSubmit ? "pointer" : "not-allowed",
            opacity: canSubmit ? 1 : 0.5,
            transition: "all 0.15s",
            fontWeight: 600,
          }}
          onMouseEnter={(e) => {
            if (canSubmit) {
              e.currentTarget.style.opacity = "0.85";
            }
          }}
          onMouseLeave={(e) => {
            if (canSubmit) {
              e.currentTarget.style.opacity = "1";
            }
          }}
        >
          {submitting
            ? "Submitting..."
            : `${isBuy ? "BUY" : "SELL"} ${baseAsset}`}
        </button>
      </div>
    </div>
  );
});

export default OrderEntry;
