"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Bridge — Wallet Connection Modal
   Full-screen modal with three sections: QBC native, EVM (MetaMask etc),
   and Solana (Phantom etc). Handles wallet detection, connection states,
   and network validation.
   ───────────────────────────────────────────────────────────────────────── */

import { useState, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Wallet, AlertTriangle, Check, ExternalLink, Loader2, Shield, Copy } from "lucide-react";
import { useBridgeStore } from "./store";
import { CHAINS } from "./chain-config";
import { B, FONT, Panel, truncAddr, CopyButton, GlowButton } from "./shared";

/* ── Wallet definitions ──────────────────────────────────────────────── */

interface WalletDef {
  id: string;
  name: string;
  icon: string;         // emoji or SVG path
  category: "qbc" | "evm" | "solana";
  downloadUrl: string;
  detect: () => boolean;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function hasWindowProp(prop: string): boolean {
  return typeof window !== "undefined" && typeof (window as any)[prop] !== "undefined";
}

const WALLET_DEFS: WalletDef[] = [
  /* QBC Native */
  {
    id: "qbc_native",
    name: "QBC Wallet",
    icon: "Q",
    category: "qbc",
    downloadUrl: "https://qbc.network/wallet",
    detect: () => false, // No browser extension yet — mock only
  },
  /* EVM Wallets */
  {
    id: "metamask",
    name: "MetaMask",
    icon: "M",
    category: "evm",
    downloadUrl: "https://metamask.io/download/",
    detect: () => hasWindowProp("ethereum") && !!(window as any).ethereum?.isMetaMask,
  },
  {
    id: "walletconnect",
    name: "WalletConnect",
    icon: "W",
    category: "evm",
    downloadUrl: "https://walletconnect.com/",
    detect: () => true, // Always available (protocol-level, not extension)
  },
  {
    id: "coinbase",
    name: "Coinbase Wallet",
    icon: "C",
    category: "evm",
    downloadUrl: "https://www.coinbase.com/wallet",
    detect: () => hasWindowProp("ethereum") && !!(window as any).ethereum?.isCoinbaseWallet,
  },
  /* Solana Wallets */
  {
    id: "phantom",
    name: "Phantom",
    icon: "P",
    category: "solana",
    downloadUrl: "https://phantom.app/download",
    detect: () => hasWindowProp("solana") && !!(window as any).solana?.isPhantom,
  },
  {
    id: "backpack",
    name: "Backpack",
    icon: "B",
    category: "solana",
    downloadUrl: "https://backpack.app/",
    detect: () => hasWindowProp("backpack"),
  },
  {
    id: "solflare",
    name: "Solflare",
    icon: "S",
    category: "solana",
    downloadUrl: "https://solflare.com/",
    detect: () => hasWindowProp("solflare"),
  },
];
/* eslint-enable @typescript-eslint/no-explicit-any */

/* ── Connection State ────────────────────────────────────────────────── */

interface ConnectionState {
  qbc: { connected: boolean; address: string | null; balance: number };
  evm: { connected: boolean; address: string | null; chainId: string | null; provider: string | null };
  solana: { connected: boolean; address: string | null };
}

const INITIAL_STATE: ConnectionState = {
  qbc: { connected: false, address: null, balance: 0 },
  evm: { connected: false, address: null, chainId: null, provider: null },
  solana: { connected: false, address: null },
};

/* ── Single Wallet Card ──────────────────────────────────────────────── */

function WalletCard({
  def,
  connecting,
  connected,
  address,
  onConnect,
  onDisconnect,
}: {
  def: WalletDef;
  connecting: boolean;
  connected: boolean;
  address: string | null;
  onConnect: () => void;
  onDisconnect: () => void;
}) {
  const detected = def.detect();
  const categoryColor =
    def.category === "qbc" ? B.glowCyan :
    def.category === "evm" ? "#627eea" :
    "#9945ff";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="rounded-lg border p-3 transition-colors"
      style={{
        borderColor: connected ? `${categoryColor}60` : B.borderSubtle,
        background: connected ? `${categoryColor}08` : B.bgElevated,
      }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Icon circle */}
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg text-sm font-bold"
            style={{
              background: `${categoryColor}20`,
              color: categoryColor,
              fontFamily: FONT.display,
            }}
          >
            {def.icon}
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold" style={{ color: B.textPrimary, fontFamily: FONT.display }}>
                {def.name}
              </span>
              {detected && !connected && (
                <span className="rounded px-1.5 py-0.5 text-[8px] font-bold" style={{ color: B.glowEmerald, background: `${B.glowEmerald}15` }}>
                  DETECTED
                </span>
              )}
              {connected && (
                <span className="rounded px-1.5 py-0.5 text-[8px] font-bold" style={{ color: B.glowEmerald, background: `${B.glowEmerald}15` }}>
                  CONNECTED
                </span>
              )}
            </div>
            {connected && address && (
              <div className="mt-0.5 flex items-center gap-1">
                <span className="text-[10px]" style={{ color: B.textSecondary, fontFamily: FONT.mono }}>
                  {truncAddr(address)}
                </span>
                <CopyButton text={address} size={10} />
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {connected ? (
            <button
              onClick={onDisconnect}
              className="rounded-md px-3 py-1.5 text-[10px] font-bold tracking-wider transition-colors hover:opacity-80"
              style={{
                color: B.glowCrimson,
                background: `${B.glowCrimson}15`,
                fontFamily: FONT.display,
              }}
            >
              DISCONNECT
            </button>
          ) : detected || def.id === "walletconnect" ? (
            <button
              onClick={onConnect}
              disabled={connecting}
              className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[10px] font-bold tracking-wider transition-colors hover:opacity-80"
              style={{
                color: categoryColor,
                background: `${categoryColor}15`,
                fontFamily: FONT.display,
                opacity: connecting ? 0.6 : 1,
              }}
            >
              {connecting ? (
                <>
                  <Loader2 size={10} className="animate-spin" />
                  CONNECTING
                </>
              ) : (
                "CONNECT"
              )}
            </button>
          ) : (
            <a
              href={def.downloadUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 rounded-md px-3 py-1.5 text-[10px] font-bold tracking-wider transition-colors hover:opacity-80"
              style={{
                color: B.textSecondary,
                background: `${B.textSecondary}10`,
                fontFamily: FONT.display,
              }}
            >
              INSTALL
              <ExternalLink size={9} />
            </a>
          )}
        </div>
      </div>
    </motion.div>
  );
}

/* ── Category Section ────────────────────────────────────────────────── */

function CategorySection({
  title,
  subtitle,
  color,
  icon,
  children,
}: {
  title: string;
  subtitle: string;
  color: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <div
          className="flex h-6 w-6 items-center justify-center rounded"
          style={{ background: `${color}20`, color }}
        >
          {icon}
        </div>
        <div>
          <h3
            className="text-[11px] font-bold uppercase tracking-widest"
            style={{ color, fontFamily: FONT.display }}
          >
            {title}
          </h3>
          <p className="text-[9px]" style={{ color: B.textSecondary }}>
            {subtitle}
          </p>
        </div>
      </div>
      <div className="space-y-2">
        {children}
      </div>
    </div>
  );
}

/* ── Network Mismatch Warning ────────────────────────────────────────── */

function NetworkWarning({ currentChainId }: { currentChainId: string | null }) {
  if (!currentChainId) return null;

  // Check if the connected EVM chain matches one of our supported chains
  const supportedIds = ["0x1", "0x38"]; // ETH, BNB
  const isSupported = supportedIds.includes(currentChainId);

  if (isSupported) return null;

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      className="mt-2 flex items-center gap-2 rounded-lg border p-2.5"
      style={{
        borderColor: `${B.glowAmber}40`,
        background: `${B.glowAmber}08`,
      }}
    >
      <AlertTriangle size={14} style={{ color: B.glowAmber }} />
      <span className="text-[10px]" style={{ color: B.glowAmber }}>
        Connected to unsupported network (Chain ID: {currentChainId}). Please switch to Ethereum or BNB Smart Chain.
      </span>
    </motion.div>
  );
}

/* ── Mock Addresses ──────────────────────────────────────────────────── */

const MOCK_ADDRS = {
  qbc: "qbc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
  evm: "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
  solana: "7S3P4HxJYt6Sp5BNm3kP8sFCWAebSsYN1pu3kTYYmbby",
};

/* ── Main Modal ──────────────────────────────────────────────────────── */

export function WalletModal() {
  const { walletModalOpen, setWalletModalOpen } = useBridgeStore();
  const [conn, setConn] = useState<ConnectionState>(INITIAL_STATE);
  const [connectingId, setConnectingId] = useState<string | null>(null);

  // Lock body scroll
  useEffect(() => {
    if (walletModalOpen) {
      document.body.style.overflow = "hidden";
      return () => { document.body.style.overflow = ""; };
    }
  }, [walletModalOpen]);

  const handleConnect = useCallback(async (def: WalletDef) => {
    setConnectingId(def.id);

    // Simulated 1.5s connection delay
    await new Promise<void>((r) => setTimeout(r, 1500));

    if (def.category === "qbc") {
      setConn((prev) => ({
        ...prev,
        qbc: { connected: true, address: MOCK_ADDRS.qbc, balance: 12847.331 },
      }));
    } else if (def.category === "evm") {
      setConn((prev) => ({
        ...prev,
        evm: { connected: true, address: MOCK_ADDRS.evm, chainId: "0x1", provider: def.name },
      }));
    } else if (def.category === "solana") {
      setConn((prev) => ({
        ...prev,
        solana: { connected: true, address: MOCK_ADDRS.solana },
      }));
    }

    setConnectingId(null);
  }, []);

  const handleDisconnect = useCallback((category: "qbc" | "evm" | "solana") => {
    setConn((prev) => ({
      ...prev,
      [category]:
        category === "qbc"
          ? { connected: false, address: null, balance: 0 }
          : category === "evm"
            ? { connected: false, address: null, chainId: null, provider: null }
            : { connected: false, address: null },
    }));
  }, []);

  const connectedCount =
    (conn.qbc.connected ? 1 : 0) +
    (conn.evm.connected ? 1 : 0) +
    (conn.solana.connected ? 1 : 0);

  const qbcWallets = WALLET_DEFS.filter((w) => w.category === "qbc");
  const evmWallets = WALLET_DEFS.filter((w) => w.category === "evm");
  const solWallets = WALLET_DEFS.filter((w) => w.category === "solana");

  return (
    <AnimatePresence>
      {walletModalOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[60] flex items-center justify-center p-4"
          style={{ background: "rgba(2, 4, 8, 0.85)", backdropFilter: "blur(8px)" }}
          onClick={(e) => { if (e.target === e.currentTarget) setWalletModalOpen(false); }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="relative w-full max-w-lg overflow-hidden rounded-2xl border"
            style={{
              background: B.bgPanel,
              borderColor: B.borderSubtle,
              maxHeight: "90vh",
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b px-5 py-4" style={{ borderColor: B.borderSubtle }}>
              <div className="flex items-center gap-3">
                <div
                  className="flex h-8 w-8 items-center justify-center rounded-lg"
                  style={{ background: `${B.glowCyan}15` }}
                >
                  <Wallet size={16} style={{ color: B.glowCyan }} />
                </div>
                <div>
                  <h2
                    className="text-sm font-bold tracking-widest"
                    style={{ color: B.textPrimary, fontFamily: FONT.display }}
                  >
                    CONNECT WALLETS
                  </h2>
                  <p className="text-[10px]" style={{ color: B.textSecondary }}>
                    {connectedCount > 0
                      ? `${connectedCount} wallet${connectedCount > 1 ? "s" : ""} connected`
                      : "Connect at least one wallet to use the bridge"}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setWalletModalOpen(false)}
                className="rounded-md p-1.5 transition-opacity hover:opacity-70"
                style={{ color: B.textSecondary }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Scrollable Body */}
            <div className="max-h-[65vh] overflow-y-auto px-5 py-4" style={{ scrollbarWidth: "thin" }}>
              <div className="space-y-6">

                {/* QBC Native */}
                <CategorySection
                  title="QBC Mainnet"
                  subtitle="Lock native QBC and QUSD for wrapping"
                  color={B.glowCyan}
                  icon={<Shield size={12} />}
                >
                  {qbcWallets.map((w) => (
                    <WalletCard
                      key={w.id}
                      def={w}
                      connecting={connectingId === w.id}
                      connected={conn.qbc.connected}
                      address={conn.qbc.address}
                      onConnect={() => handleConnect(w)}
                      onDisconnect={() => handleDisconnect("qbc")}
                    />
                  ))}
                  {conn.qbc.connected && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      className="rounded-lg border p-3"
                      style={{ borderColor: `${B.glowCyan}20`, background: `${B.glowCyan}05` }}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-[10px]" style={{ color: B.textSecondary, fontFamily: FONT.display }}>
                          QBC BALANCE
                        </span>
                        <span className="text-sm font-bold" style={{ color: B.glowCyan, fontFamily: FONT.mono }}>
                          {conn.qbc.balance.toLocaleString()} QBC
                        </span>
                      </div>
                    </motion.div>
                  )}
                </CategorySection>

                {/* EVM Wallets */}
                <CategorySection
                  title="EVM Wallets"
                  subtitle="Receive wQBC/wQUSD on Ethereum and BNB Smart Chain"
                  color="#627eea"
                  icon={<span className="text-[10px] font-bold">ETH</span>}
                >
                  {evmWallets.map((w) => (
                    <WalletCard
                      key={w.id}
                      def={w}
                      connecting={connectingId === w.id}
                      connected={conn.evm.connected && conn.evm.provider === w.name}
                      address={conn.evm.connected && conn.evm.provider === w.name ? conn.evm.address : null}
                      onConnect={() => handleConnect(w)}
                      onDisconnect={() => handleDisconnect("evm")}
                    />
                  ))}
                  <NetworkWarning currentChainId={conn.evm.chainId} />
                </CategorySection>

                {/* Solana Wallets */}
                <CategorySection
                  title="Solana Wallets"
                  subtitle="Receive wQBC/wQUSD as SPL tokens on Solana"
                  color="#9945ff"
                  icon={<span className="text-[10px] font-bold">SOL</span>}
                >
                  {solWallets.map((w) => (
                    <WalletCard
                      key={w.id}
                      def={w}
                      connecting={connectingId === w.id}
                      connected={conn.solana.connected}
                      address={conn.solana.address}
                      onConnect={() => handleConnect(w)}
                      onDisconnect={() => handleDisconnect("solana")}
                    />
                  ))}
                </CategorySection>
              </div>
            </div>

            {/* Footer */}
            <div
              className="flex items-center justify-between border-t px-5 py-3"
              style={{ borderColor: B.borderSubtle }}
            >
              <div className="flex items-center gap-1.5">
                <Shield size={10} style={{ color: B.textSecondary }} />
                <span className="text-[9px]" style={{ color: B.textSecondary }}>
                  Connections are local. We never store private keys.
                </span>
              </div>
              {connectedCount > 0 && (
                <GlowButton
                  onClick={() => setWalletModalOpen(false)}
                  variant="secondary"
                  className="!h-8 !text-[10px]"
                >
                  <Check size={12} />
                  DONE
                </GlowButton>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
