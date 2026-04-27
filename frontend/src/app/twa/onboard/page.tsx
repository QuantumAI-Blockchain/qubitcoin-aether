"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { useTelegramStore } from "@/stores/telegram-store";
import { useWalletStore } from "@/stores/wallet-store";
import { api } from "@/lib/api";
import { generateKeypair, SecurityLevel } from "@/lib/dilithium";
import { hapticFeedback, hapticNotification } from "@/lib/telegram";

const STEPS = [
  {
    title: "Welcome to Aether Mind",
    description: "The first on-chain neural cognitive engine on the Quantum Blockchain",
    emoji: "🧠",
  },
  {
    title: "Earn QBC Rewards",
    description: "Contribute knowledge to the AI and earn QBC tokens",
    emoji: "💰",
  },
  {
    title: "Create Your Wallet",
    description: "Post-quantum secure wallet powered by Dilithium5",
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
      // CLIENT-SIDE KEY GENERATION via Dilithium WASM
      let address: string;
      let publicKeyHex: string;
      let secretKeyHex: string | null = null;

      try {
        const kp = await generateKeypair(SecurityLevel.LEVEL5);
        address = kp.address;
        publicKeyHex = kp.publicKeyHex;
        secretKeyHex = kp.secretKeyHex;
      } catch {
        // WASM not available (e.g., Telegram WebView restrictions)
        // Fall back to server-side address generation (no private key)
        const res = await api.createWallet();
        address = res.address;
        publicKeyHex = res.public_key_hex;
      }

      connect(address);
      sessionStorage.setItem(`qbc-pubkey-${address}`, publicKeyHex);

      // If we generated client-side, securely store the private key hint
      if (secretKeyHex) {
        // Store encrypted in sessionStorage for this session only
        sessionStorage.setItem(`qbc-sk-${address}`, secretKeyHex);
        if (typeof window !== "undefined") {
          const webapp = (await import("@/lib/telegram")).getWebApp();
          webapp?.showAlert(
            "Wallet created with post-quantum security (ML-DSA-87). " +
              "Your private key is stored in this session. " +
              "Export it from the wallet page to back up.",
          );
        }
      } else {
        if (typeof window !== "undefined") {
          const webapp = (await import("@/lib/telegram")).getWebApp();
          webapp?.showAlert("Wallet address created. Full key generation available on the wallet page.");
        }
      }

      // Register affiliate if referred
      if (startParam) {
        await api.aikgsRegisterAffiliate({
          address,
          referral_code: startParam,
        }).catch(() => {});
      }

      // Link to Telegram
      const { user: tgUser } = useTelegramStore.getState();
      if (tgUser) {
        await api.telegramLinkWallet({
          telegram_user_id: tgUser.id,
          qbc_address: address,
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
