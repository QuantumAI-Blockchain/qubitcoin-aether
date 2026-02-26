"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Bridge — Settings Panel (slide-out)
   RPC configuration, display preferences, notification toggles,
   advanced options.
   ───────────────────────────────────────────────────────────────────────── */

import { useState, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X, Settings, Globe, Eye, Bell, Wrench, CheckCircle, XCircle,
  Loader2, RotateCcw, Trash2, ChevronRight,
} from "lucide-react";
import { useBridgeStore } from "./store";
import { CHAINS, EXTERNAL_CHAINS } from "./chain-config";
import { B, FONT, GlowButton } from "./shared";
import type { ExternalChainId, BridgeSettings, OperationType, TokenType } from "./types";

/* ── RPC Status ──────────────────────────────────────────────────────── */

type RpcStatus = "idle" | "testing" | "ok" | "error";

interface RpcConfig {
  chainId: "qbc_mainnet" | ExternalChainId;
  url: string;
  status: RpcStatus;
  latencyMs: number | null;
}

function defaultRpcConfigs(): RpcConfig[] {
  return [
    { chainId: "qbc_mainnet", url: CHAINS.qbc_mainnet.rpcUrl ?? "http://localhost:5000", status: "idle", latencyMs: null },
    { chainId: "ethereum", url: CHAINS.ethereum.rpcUrl ?? "https://eth.llamarpc.com", status: "idle", latencyMs: null },
    { chainId: "bnb", url: CHAINS.bnb.rpcUrl ?? "https://bsc-dataseed.binance.org", status: "idle", latencyMs: null },
    { chainId: "solana", url: CHAINS.solana.rpcUrl ?? "https://api.mainnet-beta.solana.com", status: "idle", latencyMs: null },
  ];
}

/* ── Toggle Component ────────────────────────────────────────────────── */

function Toggle({
  checked,
  onChange,
  label,
  description,
  color = B.glowCyan,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  description?: string;
  color?: string;
}) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className="flex w-full items-center justify-between rounded-lg p-3 text-left transition-colors hover:opacity-90"
      style={{ background: `${B.bgElevated}80` }}
    >
      <div>
        <span className="text-xs font-bold" style={{ color: B.textPrimary, fontFamily: FONT.body }}>
          {label}
        </span>
        {description && (
          <p className="mt-0.5 text-[10px]" style={{ color: B.textSecondary }}>
            {description}
          </p>
        )}
      </div>
      <div
        className="relative h-5 w-9 rounded-full transition-colors"
        style={{ background: checked ? color : B.borderSubtle }}
      >
        <motion.div
          className="absolute top-0.5 h-4 w-4 rounded-full"
          style={{ background: checked ? "#fff" : B.textSecondary }}
          animate={{ left: checked ? 18 : 2 }}
          transition={{ type: "spring", stiffness: 500, damping: 30 }}
        />
      </div>
    </button>
  );
}

/* ── Select Component ────────────────────────────────────────────────── */

function Select<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div className="flex items-center justify-between rounded-lg p-3" style={{ background: `${B.bgElevated}80` }}>
      <span className="text-xs font-bold" style={{ color: B.textPrimary, fontFamily: FONT.body }}>
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className="rounded-md border px-2 py-1 text-[10px] font-bold outline-none"
        style={{
          background: B.bgPanel,
          borderColor: B.borderSubtle,
          color: B.textPrimary,
          fontFamily: FONT.mono,
        }}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

/* ── Section Header ──────────────────────────────────────────────────── */

function SettingsSection({
  icon: Icon,
  title,
  color = B.textSecondary,
  children,
}: {
  icon: typeof Settings;
  title: string;
  color?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-5">
      <div className="mb-2 flex items-center gap-2">
        <Icon size={12} style={{ color }} />
        <span
          className="text-[10px] font-bold uppercase tracking-[0.15em]"
          style={{ color, fontFamily: FONT.display }}
        >
          {title}
        </span>
      </div>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

/* ── RPC Row ─────────────────────────────────────────────────────────── */

function RpcRow({
  config,
  onUrlChange,
  onTest,
}: {
  config: RpcConfig;
  onUrlChange: (url: string) => void;
  onTest: () => void;
}) {
  const chain = CHAINS[config.chainId];
  const statusIcon =
    config.status === "ok" ? <CheckCircle size={12} style={{ color: B.glowEmerald }} /> :
    config.status === "error" ? <XCircle size={12} style={{ color: B.glowCrimson }} /> :
    config.status === "testing" ? <Loader2 size={12} className="animate-spin" style={{ color: B.glowAmber }} /> :
    null;

  return (
    <div className="rounded-lg border p-3" style={{ borderColor: B.borderSubtle, background: B.bgElevated }}>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[10px] font-bold tracking-wider" style={{ color: chain.color, fontFamily: FONT.display }}>
          {chain.shortName}
        </span>
        <div className="flex items-center gap-2">
          {statusIcon}
          {config.latencyMs !== null && config.status === "ok" && (
            <span className="text-[9px]" style={{ color: B.glowEmerald, fontFamily: FONT.mono }}>
              {config.latencyMs}ms
            </span>
          )}
        </div>
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={config.url}
          onChange={(e) => onUrlChange(e.target.value)}
          className="flex-1 rounded border px-2 py-1.5 text-[10px] outline-none transition-colors focus:border-[#143a5a]"
          style={{
            background: B.bgPanel,
            borderColor: B.borderSubtle,
            color: B.textPrimary,
            fontFamily: FONT.mono,
          }}
          spellCheck={false}
        />
        <button
          onClick={onTest}
          disabled={config.status === "testing"}
          className="rounded border px-2.5 py-1 text-[9px] font-bold tracking-wider transition-opacity hover:opacity-80"
          style={{
            borderColor: B.borderActive,
            color: B.glowCyan,
            fontFamily: FONT.display,
            opacity: config.status === "testing" ? 0.5 : 1,
          }}
        >
          TEST
        </button>
      </div>
    </div>
  );
}

/* ── Main Settings Panel ─────────────────────────────────────────────── */

export function SettingsPanel() {
  const { settingsOpen, setSettingsOpen } = useBridgeStore();

  // Settings state
  const [settings, setSettings] = useState<BridgeSettings>({
    currencyPrimary: "qbc",
    timestampFormat: "relative",
    defaultOperation: "wrap",
    defaultToken: "QBC",
    customReceiveAddress: false,
    expertMode: false,
    notifications: {
      onComplete: true,
      onDelayed: true,
      onLowGas: false,
    },
  });

  // RPC configs
  const [rpcs, setRpcs] = useState<RpcConfig[]>(defaultRpcConfigs);

  // Lock body scroll
  useEffect(() => {
    if (settingsOpen) {
      document.body.style.overflow = "hidden";
      return () => { document.body.style.overflow = ""; };
    }
  }, [settingsOpen]);

  const updateSetting = useCallback(<K extends keyof BridgeSettings>(key: K, value: BridgeSettings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  }, []);

  const updateNotif = useCallback((key: keyof BridgeSettings["notifications"], value: boolean) => {
    setSettings((prev) => ({
      ...prev,
      notifications: { ...prev.notifications, [key]: value },
    }));
  }, []);

  const handleRpcUrlChange = useCallback((idx: number, url: string) => {
    setRpcs((prev) => prev.map((r, i) => (i === idx ? { ...r, url, status: "idle" as RpcStatus, latencyMs: null } : r)));
  }, []);

  const handleTestRpc = useCallback((idx: number) => {
    setRpcs((prev) => prev.map((r, i) => (i === idx ? { ...r, status: "testing" as RpcStatus, latencyMs: null } : r)));

    // Simulate RPC test with mock latency
    const latency = 50 + Math.floor(Math.random() * 200);
    const success = Math.random() > 0.2; // 80% success rate for demo

    setTimeout(() => {
      setRpcs((prev) =>
        prev.map((r, i) =>
          i === idx
            ? { ...r, status: (success ? "ok" : "error") as RpcStatus, latencyMs: success ? latency : null }
            : r
        )
      );
    }, 1200);
  }, []);

  const handleResetDefaults = useCallback(() => {
    setSettings({
      currencyPrimary: "qbc",
      timestampFormat: "relative",
      defaultOperation: "wrap",
      defaultToken: "QBC",
      customReceiveAddress: false,
      expertMode: false,
      notifications: { onComplete: true, onDelayed: true, onLowGas: false },
    });
    setRpcs(defaultRpcConfigs());
  }, []);

  const handleClearHistory = useCallback(() => {
    // In production this would clear localStorage / IndexedDB
    // For mock: no-op but show feedback
  }, []);

  return (
    <AnimatePresence>
      {settingsOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[60]"
            style={{ background: "rgba(2, 4, 8, 0.6)" }}
            onClick={() => setSettingsOpen(false)}
          />

          {/* Slide-out panel */}
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="fixed right-0 top-0 z-[61] flex h-full w-full max-w-md flex-col border-l"
            style={{ background: B.bgPanel, borderColor: B.borderSubtle }}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b px-5 py-4" style={{ borderColor: B.borderSubtle }}>
              <div className="flex items-center gap-2">
                <Settings size={16} style={{ color: B.glowCyan }} />
                <span className="text-sm font-bold tracking-widest" style={{ color: B.textPrimary, fontFamily: FONT.display }}>
                  SETTINGS
                </span>
              </div>
              <button
                onClick={() => setSettingsOpen(false)}
                className="rounded-md p-1.5 transition-opacity hover:opacity-70"
                style={{ color: B.textSecondary }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Scrollable content */}
            <div className="flex-1 overflow-y-auto px-5 py-4" style={{ scrollbarWidth: "thin" }}>

              {/* RPC Configuration */}
              <SettingsSection icon={Globe} title="RPC Endpoints" color={B.glowCyan}>
                <div className="space-y-2">
                  {rpcs.map((rpc, i) => (
                    <RpcRow
                      key={rpc.chainId}
                      config={rpc}
                      onUrlChange={(url) => handleRpcUrlChange(i, url)}
                      onTest={() => handleTestRpc(i)}
                    />
                  ))}
                </div>
              </SettingsSection>

              {/* Display Preferences */}
              <SettingsSection icon={Eye} title="Display" color={B.glowViolet}>
                <Select
                  label="Primary Currency"
                  value={settings.currencyPrimary}
                  onChange={(v) => updateSetting("currencyPrimary", v)}
                  options={[
                    { value: "qbc", label: "QBC (native)" },
                    { value: "usd", label: "USD equivalent" },
                  ]}
                />
                <Select
                  label="Timestamps"
                  value={settings.timestampFormat}
                  onChange={(v) => updateSetting("timestampFormat", v)}
                  options={[
                    { value: "relative", label: "Relative (2m ago)" },
                    { value: "absolute", label: "Absolute (Feb 26, 14:30)" },
                  ]}
                />
                <Select
                  label="Default Operation"
                  value={settings.defaultOperation}
                  onChange={(v) => updateSetting("defaultOperation", v as OperationType)}
                  options={[
                    { value: "wrap", label: "Wrap (QBC → wQBC)" },
                    { value: "unwrap", label: "Unwrap (wQBC → QBC)" },
                  ]}
                />
                <Select
                  label="Default Token"
                  value={settings.defaultToken}
                  onChange={(v) => updateSetting("defaultToken", v as TokenType)}
                  options={[
                    { value: "QBC", label: "QBC" },
                    { value: "QUSD", label: "QUSD" },
                  ]}
                />
              </SettingsSection>

              {/* Notifications */}
              <SettingsSection icon={Bell} title="Notifications" color={B.glowAmber}>
                <Toggle
                  checked={settings.notifications.onComplete}
                  onChange={(v) => updateNotif("onComplete", v)}
                  label="Transaction Complete"
                  description="Notify when a bridge transfer completes"
                  color={B.glowEmerald}
                />
                <Toggle
                  checked={settings.notifications.onDelayed}
                  onChange={(v) => updateNotif("onDelayed", v)}
                  label="Delayed Warning"
                  description="Alert if a transaction exceeds expected time"
                  color={B.glowAmber}
                />
                <Toggle
                  checked={settings.notifications.onLowGas}
                  onChange={(v) => updateNotif("onLowGas", v)}
                  label="Low Gas Warning"
                  description="Alert when destination chain gas is high"
                  color={B.glowCrimson}
                />
              </SettingsSection>

              {/* Advanced */}
              <SettingsSection icon={Wrench} title="Advanced" color={B.textSecondary}>
                <Toggle
                  checked={settings.expertMode}
                  onChange={(v) => updateSetting("expertMode", v)}
                  label="Expert Mode"
                  description="Show raw transaction data, advanced fee controls"
                  color={B.glowViolet}
                />
                <Toggle
                  checked={settings.customReceiveAddress}
                  onChange={(v) => updateSetting("customReceiveAddress", v)}
                  label="Custom Receive Address"
                  description="Send wrapped tokens to a different address"
                  color={B.glowCyan}
                />

                {/* Danger zone */}
                <div className="mt-3 space-y-2">
                  <button
                    onClick={handleClearHistory}
                    className="flex w-full items-center justify-between rounded-lg border p-3 transition-opacity hover:opacity-80"
                    style={{ borderColor: `${B.glowCrimson}20`, background: `${B.glowCrimson}05` }}
                  >
                    <div className="flex items-center gap-2">
                      <Trash2 size={12} style={{ color: B.glowCrimson }} />
                      <span className="text-xs font-bold" style={{ color: B.glowCrimson }}>
                        Clear Local History
                      </span>
                    </div>
                    <ChevronRight size={12} style={{ color: B.glowCrimson }} />
                  </button>

                  <button
                    onClick={handleResetDefaults}
                    className="flex w-full items-center justify-between rounded-lg border p-3 transition-opacity hover:opacity-80"
                    style={{ borderColor: `${B.textSecondary}20`, background: `${B.textSecondary}05` }}
                  >
                    <div className="flex items-center gap-2">
                      <RotateCcw size={12} style={{ color: B.textSecondary }} />
                      <span className="text-xs font-bold" style={{ color: B.textSecondary }}>
                        Reset to Defaults
                      </span>
                    </div>
                    <ChevronRight size={12} style={{ color: B.textSecondary }} />
                  </button>
                </div>
              </SettingsSection>
            </div>

            {/* Footer */}
            <div className="border-t px-5 py-3" style={{ borderColor: B.borderSubtle }}>
              <div className="flex items-center justify-between">
                <span className="text-[9px]" style={{ color: B.textSecondary, fontFamily: FONT.mono }}>
                  QBC Bridge v1.0.0 — Protocol v3.0
                </span>
                <GlowButton
                  onClick={() => setSettingsOpen(false)}
                  variant="secondary"
                  className="!h-8 !text-[10px]"
                >
                  CLOSE
                </GlowButton>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
