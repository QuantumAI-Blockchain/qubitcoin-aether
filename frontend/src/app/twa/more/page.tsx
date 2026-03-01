"use client";

import { useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { useTelegramStore } from "@/stores/telegram-store";
import { useWalletStore } from "@/stores/wallet-store";
import { showBackButton, hideBackButton, openExternalLink, closeMiniApp } from "@/lib/telegram";
import { APIKeyManager } from "@/components/aikgs/api-key-manager";

const LINKS = [
  { label: "Bounties", href: "/rewards", icon: "🎯" },
  { label: "Leaderboard", href: "/rewards", icon: "🏆" },
  { label: "Website", href: "https://qbc.network", external: true, icon: "🌐" },
  { label: "Docs", href: "https://qbc.network/docs", external: true, icon: "📄" },
  { label: "Whitepaper", href: "https://qbc.network/docs/whitepaper", external: true, icon: "📑" },
];

export default function TWAMorePage() {
  const { user } = useTelegramStore();
  const { address } = useWalletStore();

  useEffect(() => {
    showBackButton(() => window.history.back());
    return () => hideBackButton();
  }, []);

  return (
    <div className="px-4 pt-4">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-4"
      >
        <h1 className="font-[family-name:var(--font-display)] text-lg font-bold">More</h1>
      </motion.div>

      {/* User info */}
      {user && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="mb-4"
        >
          <Card className="!p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-quantum-violet/20 text-lg">
                {user.first_name[0]}
              </div>
              <div>
                <p className="text-sm font-semibold text-text-primary">
                  {user.first_name} {user.last_name ?? ""}
                </p>
                {user.username && (
                  <p className="text-[10px] text-text-secondary">@{user.username}</p>
                )}
                {user.is_premium && (
                  <span className="inline-block rounded-full bg-golden/20 px-1.5 py-0.5 text-[9px] font-bold text-golden">
                    Premium
                  </span>
                )}
              </div>
            </div>
          </Card>
        </motion.div>
      )}

      {/* Links */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="mb-4 space-y-1"
      >
        {LINKS.map((link) =>
          link.external ? (
            <button
              key={link.label}
              onClick={() => openExternalLink(link.href)}
              className="flex w-full items-center gap-3 rounded-lg bg-bg-panel p-3 text-left transition hover:bg-bg-elevated"
            >
              <span className="text-lg">{link.icon}</span>
              <span className="text-xs font-semibold text-text-primary">{link.label}</span>
              <span className="ml-auto text-text-secondary">→</span>
            </button>
          ) : (
            <Link
              key={link.label}
              href={link.href}
              className="flex items-center gap-3 rounded-lg bg-bg-panel p-3 transition hover:bg-bg-elevated"
            >
              <span className="text-lg">{link.icon}</span>
              <span className="text-xs font-semibold text-text-primary">{link.label}</span>
              <span className="ml-auto text-text-secondary">→</span>
            </Link>
          ),
        )}
      </motion.div>

      {/* API Key Manager */}
      {address && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <APIKeyManager />
        </motion.div>
      )}

      {/* Close Mini App */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="mt-6 text-center"
      >
        <button
          onClick={closeMiniApp}
          className="rounded-lg bg-bg-panel px-4 py-2 text-xs text-text-secondary transition hover:bg-bg-elevated"
        >
          Close Mini App
        </button>
      </motion.div>
    </div>
  );
}
