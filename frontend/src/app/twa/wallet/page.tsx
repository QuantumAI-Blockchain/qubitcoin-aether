"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { useWalletStore } from "@/stores/wallet-store";
import { useTelegramStore } from "@/stores/telegram-store";
import { api } from "@/lib/api";
import { showBackButton, hideBackButton, hapticFeedback, hapticNotification, getWebApp } from "@/lib/telegram";

export default function TWAWalletPage() {
  const { address, connected, balance, connect, setBalance } = useWalletStore();
  const { user, linkedWallet, setLinkedWallet } = useTelegramStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [privateKeyShown, setPrivateKeyShown] = useState<string | null>(null);

  useEffect(() => {
    showBackButton(() => window.history.back());
    return () => hideBackButton();
  }, []);

  // Refresh balance
  useEffect(() => {
    if (!address) return;
    api.getBalance(address)
      .then((res) => setBalance(parseFloat(res.balance)))
      .catch(() => {});
  }, [address, setBalance]);

  const handleCreateWallet = useCallback(async () => {
    setLoading(true);
    setError(null);
    hapticFeedback("medium");

    try {
      const res = await api.createWallet();
      connect(res.address);

      // Link to telegram
      if (user) {
        await api.telegramLinkWallet({
          telegram_user_id: user.id,
          qbc_address: res.address,
        }).catch(() => {});
        setLinkedWallet(res.address);
      }

      // Store public key only — private key shown once for user to save
      sessionStorage.setItem(`qbc-pubkey-${res.address}`, res.public_key_hex);
      setPrivateKeyShown(res.private_key_hex);

      // Auto-clear private key from memory after 5 minutes
      setTimeout(() => setPrivateKeyShown(null), 5 * 60 * 1000);

      hapticNotification("success");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create wallet");
      hapticNotification("error");
    } finally {
      setLoading(false);
    }
  }, [connect, user, setLinkedWallet]);

  const handleLinkExisting = useCallback(async () => {
    if (!address || !user) return;
    try {
      await api.telegramLinkWallet({
        telegram_user_id: user.id,
        qbc_address: address,
      });
      setLinkedWallet(address);
      hapticNotification("success");
    } catch {
      hapticNotification("error");
    }
  }, [address, user, setLinkedWallet]);

  return (
    <div className="px-4 pt-4">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-4"
      >
        <h1 className="font-[family-name:var(--font-display)] text-lg font-bold glow-cyan">
          Wallet
        </h1>
      </motion.div>

      {connected && address ? (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          {/* Balance card */}
          <Card className="mb-4 text-center" glow="green">
            <p className="text-[10px] text-text-secondary">QBC Balance</p>
            <p className="font-[family-name:var(--font-code)] text-3xl font-bold text-quantum-green">
              {balance?.toFixed(4) ?? "---"}
            </p>
            <p className="mt-2 text-[10px] text-text-secondary">QBC</p>
          </Card>

          {/* Address */}
          <Card className="mb-4">
            <p className="text-[10px] text-text-secondary">Address</p>
            <p className="mt-1 break-all font-[family-name:var(--font-code)] text-xs text-text-primary">
              {address}
            </p>
          </Card>

          {/* Telegram link status */}
          {user && (
            <Card className="mb-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold text-text-primary">Telegram Linked</p>
                  <p className="text-[10px] text-text-secondary">@{user.username || user.first_name}</p>
                </div>
                {linkedWallet ? (
                  <span className="rounded-full bg-quantum-green/20 px-2 py-0.5 text-[10px] font-semibold text-quantum-green">
                    Linked
                  </span>
                ) : (
                  <button
                    onClick={handleLinkExisting}
                    className="haptic-tap rounded-lg bg-quantum-violet px-3 py-1.5 text-[10px] font-semibold text-white"
                  >
                    Link
                  </button>
                )}
              </div>
            </Card>
          )}
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center"
        >
          <Card className="mb-4">
            <div className="py-8">
              <p className="text-4xl">👛</p>
              <h2 className="mt-3 text-sm font-semibold text-text-primary">No Wallet Connected</h2>
              <p className="mt-1 text-xs text-text-secondary">
                Create a QBC wallet to start earning rewards
              </p>
              <button
                onClick={handleCreateWallet}
                disabled={loading}
                className="haptic-tap mt-4 w-full rounded-lg bg-quantum-green px-4 py-3 text-sm font-semibold text-void transition hover:bg-quantum-green/80 disabled:opacity-40"
              >
                {loading ? "Creating..." : "Create QBC Wallet"}
              </button>
            </div>
          </Card>

          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-2">
              <p className="text-xs text-red-400">{error}</p>
            </div>
          )}

          <p className="text-[10px] text-text-secondary/60">
            Keys are generated using post-quantum Dilithium2 signatures
          </p>
        </motion.div>
      )}

      {/* Private key backup prompt — shown once after wallet creation */}
      {privateKeyShown && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-4"
        >
          <Card className="border-amber-500/30 bg-amber-500/5">
            <h3 className="text-xs font-bold text-amber-400">Save Your Private Key</h3>
            <p className="mt-1 text-[10px] text-text-secondary">
              This key is shown only once and is NOT stored by the app. Copy it now and keep it safe.
            </p>
            <div className="mt-2 break-all rounded bg-bg-deep p-2 font-[family-name:var(--font-code)] text-[10px] text-text-primary">
              {privateKeyShown.slice(0, 32)}...
            </div>
            <div className="mt-2 flex gap-2">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(privateKeyShown);
                  hapticNotification("success");
                  const webapp = getWebApp();
                  if (webapp) webapp.showAlert("Private key copied! Store it securely.");
                }}
                className="flex-1 rounded-lg bg-amber-500 px-3 py-2 text-[10px] font-semibold text-void"
              >
                Copy Full Key
              </button>
              <button
                onClick={() => setPrivateKeyShown(null)}
                className="rounded-lg border border-border-subtle px-3 py-2 text-[10px] text-text-secondary"
              >
                I Saved It
              </button>
            </div>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
