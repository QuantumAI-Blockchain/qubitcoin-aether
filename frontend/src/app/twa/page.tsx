"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { useTelegramStore } from "@/stores/telegram-store";
import { useWalletStore } from "@/stores/wallet-store";
import { useAIKGSStore } from "@/stores/aikgs-store";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { ContributionIndicator } from "@/components/aikgs/contribution-indicator";

export default function TWAHomePage() {
  const { user, startParam } = useTelegramStore();
  const { connected, address } = useWalletStore();
  const { profile, setProfile } = useAIKGSStore();

  const { data: chainInfo } = useQuery({
    queryKey: ["chain-info"],
    queryFn: api.getChainInfo,
    refetchInterval: 10_000,
  });

  const { data: phi } = useQuery({
    queryKey: ["consciousness"],
    queryFn: api.getPhi,
    refetchInterval: 10_000,
  });

  // Load AIKGS profile
  useEffect(() => {
    if (address) {
      api.aikgsGetProfile(address).then(setProfile).catch(() => {});
    }
  }, [address, setProfile]);

  return (
    <div className="px-4 pt-4">
      {/* Welcome */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-4"
      >
        <h1 className="font-[family-name:var(--font-display)] text-xl font-bold">
          {user ? `Hello, ${user.first_name}` : "Aether Mind"}
        </h1>
        <p className="text-xs text-text-secondary">
          Quantum Blockchain with On-Chain AI
        </p>
      </motion.div>

      {/* Quick stats */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="mb-4 grid grid-cols-2 gap-3"
      >
        <Card className="!p-3">
          <p className="text-[10px] text-text-secondary">Block Height</p>
          <p className="font-[family-name:var(--font-code)] text-lg font-bold text-text-primary">
            {chainInfo?.height?.toLocaleString() ?? "---"}
          </p>
        </Card>
        <Card className="!p-3">
          <p className="text-[10px] text-text-secondary">Phi (&Phi;)</p>
          <p className="font-[family-name:var(--font-code)] text-lg font-bold text-quantum-green">
            {phi?.phi?.toFixed(4) ?? "---"}
          </p>
        </Card>
      </motion.div>

      {/* AIKGS Profile */}
      {profile && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="mb-4"
        >
          <ContributionIndicator />
        </motion.div>
      )}

      {/* Quick actions */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="mb-4 grid grid-cols-2 gap-3"
      >
        <Link href="/twa/chat" className="block">
          <Card className="!p-4 text-center transition hover:border-quantum-violet/30" glow="violet">
            <p className="text-2xl">💬</p>
            <p className="mt-1 text-xs font-semibold text-text-primary">Chat with AI</p>
            <p className="text-[10px] text-text-secondary">Talk to Aether Mind</p>
          </Card>
        </Link>
        <Link href="/twa/earn" className="block">
          <Card className="!p-4 text-center transition hover:border-golden/30">
            <p className="text-2xl">💰</p>
            <p className="mt-1 text-xs font-semibold text-text-primary">Earn QBC</p>
            <p className="text-[10px] text-text-secondary">Contribute knowledge</p>
          </Card>
        </Link>
        <Link href="/twa/wallet" className="block">
          <Card className="!p-4 text-center transition hover:border-quantum-green/30" glow="green">
            <p className="text-2xl">👛</p>
            <p className="mt-1 text-xs font-semibold text-text-primary">Wallet</p>
            <p className="text-[10px] text-text-secondary">
              {connected ? `${address?.slice(0, 8)}...` : "Connect"}
            </p>
          </Card>
        </Link>
        <Link href="/twa/refer" className="block">
          <Card className="!p-4 text-center transition hover:border-glow-cyan/30">
            <p className="text-2xl">🔗</p>
            <p className="mt-1 text-xs font-semibold text-text-primary">Refer</p>
            <p className="text-[10px] text-text-secondary">Earn commissions</p>
          </Card>
        </Link>
      </motion.div>

      {/* Referral banner if start param */}
      {startParam && !connected && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3 }}
        >
          <Card className="border-quantum-violet/30 !bg-quantum-violet/10">
            <p className="text-xs font-semibold text-quantum-violet">You&apos;ve been referred!</p>
            <p className="mt-1 text-[10px] text-text-secondary">
              Connect your wallet to activate the referral code: {startParam}
            </p>
            <Link
              href="/twa/wallet"
              className="mt-2 inline-block rounded-lg bg-quantum-violet px-3 py-1.5 text-[10px] font-semibold text-white"
            >
              Connect Wallet
            </Link>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
