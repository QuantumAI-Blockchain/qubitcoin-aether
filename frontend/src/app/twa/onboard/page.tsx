"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { useTelegramStore } from "@/stores/telegram-store";
import { useWalletStore } from "@/stores/wallet-store";
import { api } from "@/lib/api";
import { hapticFeedback, hapticNotification } from "@/lib/telegram";

const STEPS = [
  {
    title: "Welcome to Aether Tree",
    description: "The first on-chain AGI on the Quantum Blockchain",
    emoji: "🌳",
  },
  {
    title: "Earn QBC Rewards",
    description: "Contribute knowledge to the AGI and earn QBC tokens",
    emoji: "💰",
  },
  {
    title: "Create Your Wallet",
    description: "Post-quantum secure wallet powered by Dilithium2",
    emoji: "👛",
    action: true,
  },
];

export default function TWAOnboardPage() {
  const router = useRouter();
  const { user, startParam } = useTelegramStore();
  const { connect } = useWalletStore();
  const [step, setStep] = useState(0);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleNext = useCallback(() => {
    if (step < STEPS.length - 1) {
      setStep((s) => s + 1);
      hapticFeedback("light");
    }
  }, [step]);

  const handleCreateWallet = useCallback(async () => {
    setCreating(true);
    setError(null);
    hapticFeedback("medium");

    try {
      const res = await api.createWallet();
      connect(res.address);

      // Store public key only — private key shown to user to save
      sessionStorage.setItem(`qbc-pubkey-${res.address}`, res.public_key_hex);
      // Show private key for backup (user must copy it manually)
      if (typeof window !== "undefined") {
        const webapp = (await import("@/lib/telegram")).getWebApp();
        webapp?.showAlert(`SAVE YOUR PRIVATE KEY (shown once):\n${res.private_key_hex.slice(0, 40)}...\n\nCopy from console.`);
        console.warn("[QBC] Private key (save this!):", res.private_key_hex);
      }

      // Register affiliate if referred
      if (startParam) {
        await api.aikgsRegisterAffiliate({
          address: res.address,
          referral_code: startParam,
        }).catch(() => {});
      }

      // Link to Telegram
      const { user: tgUser } = useTelegramStore.getState();
      if (tgUser) {
        await api.telegramLinkWallet({
          telegram_user_id: tgUser.id,
          qbc_address: res.address,
        }).catch(() => {});
      }

      hapticNotification("success");
      router.push("/twa");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create wallet");
      hapticNotification("error");
    } finally {
      setCreating(false);
    }
  }, [connect, startParam, router]);

  const handleSkip = useCallback(() => {
    router.push("/twa");
  }, [router]);

  const currentStep = STEPS[step];

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-6">
      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={{ opacity: 0, x: 50 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -50 }}
          className="w-full max-w-sm text-center"
        >
          <div className="mb-6 text-6xl">{currentStep.emoji}</div>
          <h1 className="font-[family-name:var(--font-display)] text-xl font-bold text-text-primary">
            {currentStep.title}
          </h1>
          <p className="mt-2 text-sm text-text-secondary">{currentStep.description}</p>

          {currentStep.action ? (
            <div className="mt-8 space-y-3">
              <button
                onClick={handleCreateWallet}
                disabled={creating}
                className="haptic-tap w-full rounded-2xl bg-quantum-green px-4 py-3 text-sm font-semibold text-void transition disabled:opacity-40"
              >
                {creating ? "Creating Wallet..." : "Create Wallet"}
              </button>
              <button
                onClick={handleSkip}
                className="w-full rounded-2xl bg-bg-panel px-4 py-3 text-sm text-text-secondary transition hover:bg-bg-elevated"
              >
                Skip for now
              </button>
              {error && (
                <p className="text-xs text-red-400">{error}</p>
              )}
            </div>
          ) : (
            <button
              onClick={handleNext}
              className="haptic-tap mt-8 w-full rounded-2xl bg-quantum-violet px-4 py-3 text-sm font-semibold text-white transition"
            >
              Continue
            </button>
          )}
        </motion.div>
      </AnimatePresence>

      {/* Step dots */}
      <div className="mt-8 flex gap-2">
        {STEPS.map((_, i) => (
          <div
            key={i}
            className={`h-2 rounded-full transition-all ${
              i === step ? "w-6 bg-quantum-violet" : "w-2 bg-border-subtle"
            }`}
          />
        ))}
      </div>
    </div>
  );
}
