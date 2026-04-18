"use client";

import { useState, useEffect } from "react";
import { useWalletStore } from "@/stores/wallet-store";
import {
  connectWallet,
  isMobile,
  hasInjectedProvider,
  openInMetaMask,
  getMetaMaskInstallUrl,
  isTelegramWebApp,
} from "@/lib/wallet";

export function WalletButton() {
  const { address, connected, connect, disconnect } = useWalletStore();
  const [error, setError] = useState<string | null>(null);
  const [mobile, setMobile] = useState(false);
  const [hasProvider, setHasProvider] = useState(true);

  useEffect(() => {
    setMobile(isMobile());
    setHasProvider(hasInjectedProvider());
  }, []);

  async function handleConnect() {
    setError(null);
    try {
      const { address } = await connectWallet();
      connect(address);
    } catch (err) {
      if (err instanceof Error && err.message === "METAMASK_DEEPLINK") {
        // Deep-link was triggered, don't show error
        return;
      }
      const msg = err instanceof Error ? err.message : "Connection failed";
      setError(msg);
      console.error("Wallet connect failed:", err);
    }
  }

  if (connected && address) {
    return (
      <button
        onClick={disconnect}
        className="rounded-lg border border-glow-cyan/30 bg-bg-panel px-3 py-2 text-xs text-glow-cyan transition hover:bg-glow-cyan/10 active:scale-95 min-h-[40px]"
      >
        {address.slice(0, 6)}...{address.slice(-4)}
      </button>
    );
  }

  // Mobile without injected provider — show deep-link button
  if (mobile && !hasProvider && !isTelegramWebApp()) {
    return (
      <div className="flex flex-col items-center gap-1">
        <button
          onClick={() => openInMetaMask()}
          className="rounded-lg bg-glow-cyan/10 px-3 py-2 text-xs font-medium text-glow-cyan transition hover:bg-glow-cyan/20 active:scale-95 min-h-[40px]"
        >
          Open in MetaMask
        </button>
      </div>
    );
  }

  return (
    <div>
      <button
        onClick={handleConnect}
        className="rounded-lg bg-glow-cyan/10 px-3 py-2 text-xs font-medium text-glow-cyan transition hover:bg-glow-cyan/20 active:scale-95 min-h-[40px]"
      >
        Connect Wallet
      </button>
      {error && (
        <p className="mt-2 max-w-xs text-[10px] leading-relaxed text-red-400">
          {error}
          {!hasProvider && !mobile && (
            <>
              {" "}
              <a
                href={getMetaMaskInstallUrl()}
                target="_blank"
                rel="noopener noreferrer"
                className="underline text-glow-cyan"
              >
                Install MetaMask
              </a>
            </>
          )}
        </p>
      )}
    </div>
  );
}
