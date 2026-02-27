// ─── QBC EXCHANGE — Settings Slide-Out Panel ──────────────────────────────────
// Trading preferences, display, notifications, fees, RPC config, expert mode.
// Fixed right-side panel, z-40, 340px wide.
"use client";

import React, { memo, useCallback, useState, useRef, useEffect } from "react";
import { useExchangeStore } from "./store";
import { X, FONT, panelStyle, panelHeaderStyle } from "./shared";
import type { ExchangeSettings as ExchangeSettingsType, OrderType, TIF } from "./types";
import { useFocusTrap } from "@/hooks/use-focus-trap";

// ─── STYLES ────────────────────────────────────────────────────────────────

const PANEL_WIDTH = 340;

const overlayStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  zIndex: 39,
  background: `${X.bgBase}99`,
  backdropFilter: "blur(2px)",
};

const panelContainerStyle: React.CSSProperties = {
  position: "fixed",
  top: 0,
  right: 0,
  bottom: 0,
  width: PANEL_WIDTH,
  zIndex: 40,
  background: X.bgPanel,
  borderLeft: `1px solid ${X.borderSubtle}`,
  display: "flex",
  flexDirection: "column",
  boxShadow: `-8px 0 32px ${X.bgBase}cc`,
  overflowY: "auto",
};

const sectionTitleStyle: React.CSSProperties = {
  fontFamily: FONT.display,
  fontSize: 9,
  letterSpacing: "0.12em",
  color: X.glowCyan,
  textTransform: "uppercase" as const,
  padding: "14px 16px 6px",
  borderBottom: `1px solid ${X.borderSubtle}10`,
};

const rowStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  padding: "10px 16px",
  borderBottom: `1px solid ${X.borderSubtle}18`,
};

const labelTextStyle: React.CSSProperties = {
  fontFamily: FONT.body,
  fontSize: 12,
  color: X.textPrimary,
};

const subLabelStyle: React.CSSProperties = {
  fontFamily: FONT.body,
  fontSize: 10,
  color: X.textSecondary,
  marginTop: 2,
};

const selectStyle: React.CSSProperties = {
  fontFamily: FONT.mono,
  fontSize: 11,
  color: X.textPrimary,
  background: X.bgElevated,
  border: `1px solid ${X.borderSubtle}`,
  borderRadius: 4,
  padding: "4px 8px",
  outline: "none",
  cursor: "pointer",
  minWidth: 100,
  WebkitAppearance: "none",
  MozAppearance: "none",
  appearance: "none",
};

const inputStyle: React.CSSProperties = {
  fontFamily: FONT.mono,
  fontSize: 11,
  color: X.textPrimary,
  background: X.bgElevated,
  border: `1px solid ${X.borderSubtle}`,
  borderRadius: 4,
  padding: "6px 10px",
  outline: "none",
  width: "100%",
};

const feeRowStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  padding: "6px 16px",
};

const feeLabelStyle: React.CSSProperties = {
  fontFamily: FONT.body,
  fontSize: 11,
  color: X.textSecondary,
};

const feeValueStyle: React.CSSProperties = {
  fontFamily: FONT.mono,
  fontSize: 11,
  color: X.textPrimary,
};

const btnStyle: React.CSSProperties = {
  fontFamily: FONT.display,
  fontSize: 10,
  letterSpacing: "0.08em",
  padding: "8px 16px",
  borderRadius: 4,
  border: "none",
  cursor: "pointer",
  textTransform: "uppercase" as const,
};

// ─── TOGGLE SWITCH ─────────────────────────────────────────────────────────

const Toggle = memo(function Toggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (val: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      style={{
        width: 36,
        height: 20,
        borderRadius: 10,
        border: `1px solid ${checked ? X.glowCyan : X.borderSubtle}`,
        background: checked ? X.glowCyan + "30" : X.bgElevated,
        position: "relative",
        cursor: "pointer",
        transition: "background 0.2s, border-color 0.2s",
        padding: 0,
        flexShrink: 0,
      }}
      aria-checked={checked}
      role="switch"
    >
      <div
        style={{
          width: 14,
          height: 14,
          borderRadius: "50%",
          background: checked ? X.glowCyan : X.textSecondary,
          position: "absolute",
          top: 2,
          left: checked ? 18 : 2,
          transition: "left 0.2s, background 0.2s",
          boxShadow: checked ? `0 0 6px ${X.glowCyan}80` : "none",
        }}
      />
    </button>
  );
});

// ─── DROPDOWN ──────────────────────────────────────────────────────────────

function Select<T extends string>({
  value,
  options,
  labels,
  onChange,
}: {
  value: T;
  options: T[];
  labels?: Record<T, string>;
  onChange: (val: T) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as T)}
      style={selectStyle}
    >
      {options.map((opt) => (
        <option key={opt} value={opt} style={{ background: X.bgElevated }}>
          {labels ? labels[opt] : opt}
        </option>
      ))}
    </select>
  );
}

// ─── RPC TEST BUTTON ───────────────────────────────────────────────────────

function RpcTestButton({ url }: { url: string }) {
  const [status, setStatus] = useState<"idle" | "testing" | "ok" | "fail">("idle");

  const test = useCallback(async () => {
    setStatus("testing");
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);
      const res = await fetch(url + "/health", { signal: controller.signal });
      clearTimeout(timeout);
      setStatus(res.ok ? "ok" : "fail");
    } catch {
      setStatus("fail");
    }
    setTimeout(() => setStatus("idle"), 3000);
  }, [url]);

  const color =
    status === "ok"
      ? X.glowEmerald
      : status === "fail"
        ? X.glowCrimson
        : status === "testing"
          ? X.glowAmber
          : X.textSecondary;

  const label =
    status === "ok"
      ? "CONNECTED"
      : status === "fail"
        ? "FAILED"
        : status === "testing"
          ? "TESTING..."
          : "TEST";

  return (
    <button
      type="button"
      onClick={test}
      disabled={status === "testing"}
      style={{
        ...btnStyle,
        background: color + "20",
        color,
        border: `1px solid ${color}40`,
        fontSize: 9,
        padding: "5px 12px",
        marginTop: 6,
        opacity: status === "testing" ? 0.7 : 1,
      }}
    >
      {label}
    </button>
  );
}

// ─── MAIN COMPONENT ────────────────────────────────────────────────────────

const ExchangeSettings = memo(function ExchangeSettings() {
  const isOpen = useExchangeStore((s) => s.settingsPanelOpen);
  const setOpen = useExchangeStore((s) => s.setSettingsPanelOpen);
  const settings = useExchangeStore((s) => s.settings);
  const updateSettings = useExchangeStore((s) => s.updateSettings);
  const addToast = useExchangeStore((s) => s.addToast);
  const panelRef = useRef<HTMLDivElement>(null);

  const closePanel = useCallback(() => setOpen(false), [setOpen]);
  useFocusTrap(panelRef, isOpen, closePanel);

  const handleReset = useCallback(() => {
    updateSettings({
      defaultOrderType: "limit",
      defaultTif: "gtc",
      confirmOrders: true,
      confirmCancels: false,
      candleStyle: "candle",
      orderBookGrouping: 0.0001,
      orderBookRows: 20,
      timestampFormat: "relative",
      soundEnabled: false,
      notifyFilled: true,
      notifyLiquidation: true,
      notifyFunding: false,
      rpcUrl: process.env.NEXT_PUBLIC_RPC_URL ?? "http://localhost:5000",
      expertMode: false,
    });
    addToast("Settings reset to defaults", "info");
  }, [updateSettings, addToast]);

  if (!isOpen) return null;

  return (
    <>
      {/* Overlay backdrop */}
      <div style={overlayStyle} onClick={() => setOpen(false)} />

      {/* Panel */}
      <div ref={panelRef} role="dialog" aria-modal="true" aria-labelledby="settings-panel-title" style={panelContainerStyle} className="exchange-scroll">
        {/* Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "14px 16px",
            borderBottom: `1px solid ${X.borderSubtle}`,
          }}
        >
          <span
            id="settings-panel-title"
            style={{
              fontFamily: FONT.display,
              fontSize: 12,
              letterSpacing: "0.08em",
              color: X.textPrimary,
              textTransform: "uppercase" as const,
            }}
          >
            Exchange Settings
          </span>
          <button
            type="button"
            onClick={() => setOpen(false)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: X.textSecondary,
              fontSize: 18,
              lineHeight: 1,
              padding: "2px 4px",
              fontFamily: FONT.mono,
            }}
            title="Close"
            aria-label="Close settings panel"
          >
            x
          </button>
        </div>

        {/* ── 1. TRADING PREFERENCES ──────────────────────────────────────── */}
        <div style={sectionTitleStyle}>Trading Preferences</div>

        <div style={rowStyle}>
          <div>
            <div style={labelTextStyle}>Default Order Type</div>
            <div style={subLabelStyle}>Pre-selected order type</div>
          </div>
          <Select<OrderType>
            value={settings.defaultOrderType}
            options={["limit", "market", "stop_limit", "stop_market"]}
            labels={{
              limit: "Limit",
              market: "Market",
              stop_limit: "Stop Limit",
              stop_market: "Stop Market",
            }}
            onChange={(v) => updateSettings({ defaultOrderType: v })}
          />
        </div>

        <div style={rowStyle}>
          <div>
            <div style={labelTextStyle}>Default TIF</div>
            <div style={subLabelStyle}>Time-in-force policy</div>
          </div>
          <Select<TIF>
            value={settings.defaultTif}
            options={["gtc", "ioc", "fok", "post"]}
            labels={{
              gtc: "GTC",
              ioc: "IOC",
              fok: "FOK",
              post: "Post Only",
            }}
            onChange={(v) => updateSettings({ defaultTif: v })}
          />
        </div>

        <div style={rowStyle}>
          <div style={labelTextStyle}>Confirm Orders</div>
          <Toggle
            checked={settings.confirmOrders}
            onChange={(v) => updateSettings({ confirmOrders: v })}
          />
        </div>

        <div style={rowStyle}>
          <div style={labelTextStyle}>Confirm Cancels</div>
          <Toggle
            checked={settings.confirmCancels}
            onChange={(v) => updateSettings({ confirmCancels: v })}
          />
        </div>

        {/* ── 2. DISPLAY ──────────────────────────────────────────────────── */}
        <div style={sectionTitleStyle}>Display</div>

        <div style={rowStyle}>
          <div style={labelTextStyle}>Chart Candle Style</div>
          <Select<ExchangeSettingsType["candleStyle"]>
            value={settings.candleStyle}
            options={["candle", "hollow", "bar", "line"]}
            labels={{
              candle: "Candle",
              hollow: "Hollow",
              bar: "Bar",
              line: "Line",
            }}
            onChange={(v) => updateSettings({ candleStyle: v })}
          />
        </div>

        <div style={rowStyle}>
          <div style={labelTextStyle}>Order Book Grouping</div>
          <Select<string>
            value={String(settings.orderBookGrouping)}
            options={["0.0001", "0.001", "0.01", "0.1", "1"]}
            labels={{
              "0.0001": "0.0001",
              "0.001": "0.001",
              "0.01": "0.01",
              "0.1": "0.1",
              "1": "1.00",
            }}
            onChange={(v) => updateSettings({ orderBookGrouping: parseFloat(v) })}
          />
        </div>

        <div style={rowStyle}>
          <div style={labelTextStyle}>Order Book Rows</div>
          <Select<string>
            value={String(settings.orderBookRows)}
            options={["10", "20", "50"]}
            labels={{ "10": "10", "20": "20", "50": "50" }}
            onChange={(v) =>
              updateSettings({ orderBookRows: parseInt(v, 10) as 10 | 20 | 50 })
            }
          />
        </div>

        <div style={rowStyle}>
          <div style={labelTextStyle}>Timestamp Format</div>
          <Select<ExchangeSettingsType["timestampFormat"]>
            value={settings.timestampFormat}
            options={["relative", "utc"]}
            labels={{ relative: "Relative", utc: "UTC" }}
            onChange={(v) => updateSettings({ timestampFormat: v })}
          />
        </div>

        <div style={rowStyle}>
          <div style={labelTextStyle}>Sound Effects</div>
          <Toggle
            checked={settings.soundEnabled}
            onChange={(v) => updateSettings({ soundEnabled: v })}
          />
        </div>

        {/* ── 3. NOTIFICATIONS ────────────────────────────────────────────── */}
        <div style={sectionTitleStyle}>Notifications</div>

        <div style={rowStyle}>
          <div>
            <div style={labelTextStyle}>Order Filled</div>
            <div style={subLabelStyle}>Alert when an order fills</div>
          </div>
          <Toggle
            checked={settings.notifyFilled}
            onChange={(v) => updateSettings({ notifyFilled: v })}
          />
        </div>

        <div style={rowStyle}>
          <div>
            <div style={labelTextStyle}>Liquidation Warning</div>
            <div style={subLabelStyle}>Alert near liquidation price</div>
          </div>
          <Toggle
            checked={settings.notifyLiquidation}
            onChange={(v) => updateSettings({ notifyLiquidation: v })}
          />
        </div>

        <div style={rowStyle}>
          <div>
            <div style={labelTextStyle}>Large Funding</div>
            <div style={subLabelStyle}>Alert on significant funding payments</div>
          </div>
          <Toggle
            checked={settings.notifyFunding}
            onChange={(v) => updateSettings({ notifyFunding: v })}
          />
        </div>

        {/* ── 4. FEES (read-only) ─────────────────────────────────────────── */}
        <div style={sectionTitleStyle}>Fees</div>

        <div
          style={{
            padding: "6px 0 10px",
            borderBottom: `1px solid ${X.borderSubtle}18`,
          }}
        >
          <div style={feeRowStyle}>
            <span style={feeLabelStyle}>Maker Fee</span>
            <span style={feeValueStyle}>0.02%</span>
          </div>
          <div style={feeRowStyle}>
            <span style={feeLabelStyle}>Taker Fee</span>
            <span style={feeValueStyle}>0.05%</span>
          </div>
          <div style={feeRowStyle}>
            <span style={feeLabelStyle}>Quantum Surcharge</span>
            <span
              style={{
                ...feeValueStyle,
                color: X.glowViolet,
              }}
            >
              +0.001%
            </span>
          </div>
          <div
            style={{
              padding: "4px 16px 0",
              fontFamily: FONT.body,
              fontSize: 9,
              color: X.textSecondary,
              lineHeight: 1.5,
            }}
          >
            Quantum surcharge funds on-chain VQE oracle verification and
            Dilithium signature validation for post-quantum security.
          </div>
        </div>

        {/* ── 5. RPC URL ──────────────────────────────────────────────────── */}
        <div style={sectionTitleStyle}>RPC Connection</div>

        <div style={{ padding: "10px 16px", borderBottom: `1px solid ${X.borderSubtle}18` }}>
          <div style={{ ...labelTextStyle, marginBottom: 6 }}>
            Node RPC URL
          </div>
          <input
            type="text"
            value={settings.rpcUrl}
            onChange={(e) => updateSettings({ rpcUrl: e.target.value })}
            placeholder="http://localhost:5000"
            style={inputStyle}
            spellCheck={false}
          />
          <RpcTestButton url={settings.rpcUrl} />
          <div
            style={{
              fontFamily: FONT.body,
              fontSize: 9,
              color: X.textSecondary,
              marginTop: 6,
              lineHeight: 1.5,
            }}
          >
            Connect to a Qubitcoin node for live market data and on-chain order
            execution. Default: localhost:5000.
          </div>
        </div>

        {/* ── 6. EXPERT MODE ──────────────────────────────────────────────── */}
        <div style={sectionTitleStyle}>Advanced</div>

        <div style={rowStyle}>
          <div>
            <div style={labelTextStyle}>Expert Mode</div>
            <div style={subLabelStyle}>
              Show advanced order types, raw bytecodes, gas tuning
            </div>
          </div>
          <Toggle
            checked={settings.expertMode}
            onChange={(v) => updateSettings({ expertMode: v })}
          />
        </div>

        {/* ── 7. RESET ────────────────────────────────────────────────────── */}
        <div style={{ padding: "16px 16px 24px" }}>
          <button
            type="button"
            onClick={handleReset}
            style={{
              ...btnStyle,
              width: "100%",
              background: X.glowCrimson + "18",
              color: X.glowCrimson,
              border: `1px solid ${X.glowCrimson}30`,
              padding: "10px 16px",
            }}
          >
            Reset All Settings
          </button>
          <div
            style={{
              fontFamily: FONT.body,
              fontSize: 9,
              color: X.textSecondary,
              marginTop: 8,
              textAlign: "center",
              lineHeight: 1.5,
            }}
          >
            Restore all exchange settings to their default values.
            <br />
            This cannot be undone.
          </div>
        </div>

        {/* Version footer */}
        <div
          style={{
            padding: "8px 16px 16px",
            fontFamily: FONT.mono,
            fontSize: 9,
            color: X.textSecondary + "80",
            textAlign: "center",
            borderTop: `1px solid ${X.borderSubtle}`,
          }}
        >
          QBC Exchange v0.1.0 &middot; Chain 3301 &middot; Dilithium2
        </div>
      </div>
    </>
  );
});

export default ExchangeSettings;
