"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Bridge — Global Header + Network Status Ticker
   ───────────────────────────────────────────────────────────────────────── */

import { memo } from "react";
import { Settings, Wallet, Link2 } from "lucide-react";
import { CHAINS, EXTERNAL_CHAINS } from "./chain-config";
import { useTickerItems } from "./hooks";
import { useBridgeStore } from "./store";
import { useWalletStore } from "@/stores/wallet-store";
import {
  B, FONT, Panel, truncAddr, ChainBadge, GlowButton,
} from "./shared";
import type { ChainId, TickerItem } from "./types";

/* ── Chain Status Pill ────────────────────────────────────────────────── */

const ChainPill = memo(function ChainPill({ chainId }: { chainId: ChainId }) {
  const info = CHAINS[chainId];
  const color = info.color;
  const available = info.available;

  return (
    <div
      className="flex items-center gap-1.5 rounded-full border px-2.5 py-1"
      style={{ borderColor: `${color}30`, background: `${color}08` }}
    >
      <span
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{
          background: available ? "#10b981" : "#dc2626",
          boxShadow: available ? "0 0 6px #10b98180" : "none",
        }}
      />
      <span className="text-[9px] font-bold tracking-widest" style={{ color, fontFamily: FONT.display }}>
        {info.shortName}
      </span>
      <span className="text-[8px]" style={{ color: B.textSecondary }}>
        {available ? "LIVE" : "OFF"}
      </span>
    </div>
  );
});

/* ── Ticker ───────────────────────────────────────────────────────────── */

function NetworkTicker() {
  const { data: items } = useTickerItems();
  if (!items || items.length === 0) return null;

  // Double the items for seamless loop
  const doubled = [...items, ...items];

  return (
    <div
      className="overflow-hidden border-b"
      style={{ background: `${B.bgBase}ee`, borderColor: B.borderSubtle }}
    >
      <div className="bridge-ticker flex whitespace-nowrap py-1">
        {doubled.map((item, i) => (
          <span
            key={`${item.label}-${i}`}
            className="mx-4 inline-flex items-center gap-1.5 text-[10px]"
            style={{ fontFamily: FONT.mono }}
          >
            <span style={{ color: B.textSecondary }}>▸ {item.label}:</span>
            <span style={{ color: item.color ?? B.glowCyan }}>{item.value}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

/* ── Header ───────────────────────────────────────────────────────────── */

export function GlobalHeader() {
  const { setWalletModalOpen, setSettingsOpen, navigate } = useBridgeStore();
  const walletStore = useWalletStore();

  // Read wallet connection state from the global Zustand store
  const qbcConnected = !!walletStore.activeNativeWallet;
  const evmConnected = walletStore.connected;

  return (
    <>
      <header
        className="sticky top-0 z-50 border-b"
        style={{
          background: `${B.bgBase}ee`,
          borderColor: B.borderSubtle,
          backdropFilter: "blur(12px)",
        }}
      >
        <div className="flex items-center justify-between px-4 py-2">
          {/* Back to site + Logo */}
          <div className="flex items-center gap-1">
          <a
            href="/"
            className="flex items-center rounded-md px-1.5 py-1.5 text-xs transition-opacity hover:opacity-80"
            style={{ color: B.textSecondary }}
            title="Back to QBC"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
          </a>
          <button
            onClick={() => navigate("bridge")}
            className="flex items-center gap-2.5"
          >
            {/* Bridge icon SVG */}
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
              <path
                d="M4 18C4 18 8 8 14 8C20 8 24 18 24 18"
                stroke={B.glowCyan}
                strokeWidth="2"
                strokeLinecap="round"
              />
              <circle cx="4" cy="18" r="2" fill={B.glowCyan} />
              <circle cx="24" cy="18" r="2" fill={B.glowGold} />
              <path d="M14 8V4" stroke={B.glowCyan} strokeWidth="1.5" strokeLinecap="round" />
              <rect x="11" y="2" width="6" height="3" rx="1" fill={B.glowCyan} opacity="0.3" />
            </svg>
            <span
              className="text-sm font-bold tracking-[0.2em]"
              style={{ color: B.textPrimary, fontFamily: FONT.display }}
            >
              QBC BRIDGE
            </span>
          </button>
          </div>

          {/* Chain Status Pills */}
          <div className="hidden items-center gap-2 md:flex">
            <ChainPill chainId="qbc_mainnet" />
            {EXTERNAL_CHAINS.map((c) => (
              <ChainPill key={c} chainId={c} />
            ))}
          </div>

          {/* Right: Wallet + Settings */}
          <div className="flex items-center gap-2">
            {qbcConnected || evmConnected ? (
              <div className="flex items-center gap-2">
                {/* Connected wallet badges would go here */}
              </div>
            ) : (
              <GlowButton
                onClick={() => setWalletModalOpen(true)}
                variant="primary"
                className="!h-8 !text-[10px]"
              >
                <Wallet size={12} />
                CONNECT WALLET
              </GlowButton>
            )}

            <button
              onClick={() => setSettingsOpen(true)}
              className="rounded-md p-1.5 transition-opacity hover:opacity-80"
              style={{ color: B.textSecondary }}
            >
              <Settings size={16} />
            </button>
          </div>
        </div>

        {/* Sub-nav */}
        <div className="flex items-center gap-1 border-t px-4 py-1" style={{ borderColor: `${B.borderSubtle}60` }}>
          {[
            { view: "bridge" as const, label: "Bridge" },
            { view: "history" as const, label: "History" },
            { view: "vault" as const, label: "Vault" },
            { view: "fees" as const, label: "Fees" },
          ].map(({ view, label }) => {
            const active = useBridgeStore.getState().view === view;
            return (
              <button
                key={view}
                onClick={() => navigate(view)}
                className="rounded-md px-3 py-1 text-[10px] font-bold tracking-widest transition-colors"
                style={{
                  color: active ? B.glowCyan : B.textSecondary,
                  background: active ? `${B.glowCyan}12` : "transparent",
                  fontFamily: FONT.display,
                }}
              >
                {label.toUpperCase()}
              </button>
            );
          })}
        </div>
      </header>

      <NetworkTicker />
    </>
  );
}
