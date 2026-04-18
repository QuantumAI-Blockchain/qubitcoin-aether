"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import { WalletButton } from "@/components/wallet/wallet-button";
import { PhiIndicator } from "@/components/ui/phi-indicator";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { LanguageSwitcher } from "@/components/ui/language-switcher";
import { useState, useEffect } from "react";

// Hidden from public nav (pages still accessible by direct URL):
//   { href: "/launchpad", key: "launchpad" },
//   { href: "/invest", key: "invest" },
const navKeys = [
  { href: "/", key: "home" },
  { href: "/aether", key: "aether" },
  { href: "/dashboard", key: "dashboard" },
  { href: "/explorer", key: "explorer" },
  { href: "/exchange", key: "exchange" },
  { href: "/wallet", key: "wallet" },
  { href: "/qvm", key: "qvm" },
  { href: "/bridge", key: "bridge" },
  { href: "/rewards", key: "rewards" },
] as const;

/** Static label lookup for nav items not in translation keys */
const fallbackLabels: Record<string, string> = {
  home: "Home",
  aether: "Aether",
  dashboard: "Dashboard",
  explorer: "Explorer",
  exchange: "Exchange",
  launchpad: "Launchpad",
  wallet: "Wallet",
  qvm: "QVM",
  bridge: "Bridge",
  rewards: "Earn",
};

export function Navbar() {
  const pathname = usePathname();
  const t = useTranslations("nav");
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // Prevent scroll when menu is open
  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [mobileOpen]);

  return (
    <>
      <header className="fixed top-0 z-50 w-full border-b border-border-subtle/60 bg-bg-deep/90 backdrop-blur-md">
        <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2">
            <span className="font-[family-name:var(--font-display)] text-xl font-bold tracking-tight glow-cyan">
              QBC
            </span>
            <span className="hidden font-[family-name:var(--font-reading)] text-sm text-text-secondary sm:inline">
              Quantum Blockchain
            </span>
          </Link>

          {/* Desktop nav links */}
          <ul className="hidden lg:flex items-center gap-1">
            {navKeys.map(({ href, key }) => {
              const active = pathname === href;
              const label = key === "home" ? (fallbackLabels[key]) : (t.has(key) ? t(key) : fallbackLabels[key]);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    className={`relative rounded-md px-3 py-2 font-[family-name:var(--font-display)] text-[11px] uppercase tracking-widest transition-colors ${
                      active
                        ? "glow-cyan"
                        : "text-text-secondary hover:text-text-primary"
                    }`}
                  >
                    {label}
                    {active && (
                      <motion.span
                        layoutId="nav-indicator"
                        className="absolute inset-x-1 -bottom-[1px] h-0.5 bg-glow-cyan"
                        style={{ boxShadow: "0 0 8px rgba(0,212,255,0.5)" }}
                        transition={{ type: "spring", stiffness: 350, damping: 30 }}
                      />
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>

          {/* Right side */}
          <div className="flex items-center gap-3">
            <PhiIndicator />
            <span className="hidden sm:inline-flex"><LanguageSwitcher /></span>
            <span className="hidden sm:inline-flex"><ThemeToggle /></span>
            <WalletButton />
            {/* Hamburger button - mobile only */}
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="lg:hidden relative flex flex-col items-center justify-center w-10 h-10 rounded-md hover:bg-white/5 transition-colors"
              aria-label="Toggle menu"
              aria-expanded={mobileOpen}
            >
              <span className={`block w-5 h-0.5 bg-text-primary transition-all duration-200 ${mobileOpen ? "rotate-45 translate-y-[6px]" : ""}`} />
              <span className={`block w-5 h-0.5 bg-text-primary mt-1.5 transition-all duration-200 ${mobileOpen ? "opacity-0" : ""}`} />
              <span className={`block w-5 h-0.5 bg-text-primary mt-1.5 transition-all duration-200 ${mobileOpen ? "-rotate-45 -translate-y-[6px]" : ""}`} />
            </button>
          </div>
        </nav>
      </header>

      {/* Mobile menu — rendered as a sibling portal outside header to avoid nested fixed issues */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 top-16 z-[9999] bg-bg-deep border-t border-border-subtle/60 overflow-y-auto"
          style={{ WebkitOverflowScrolling: "touch", paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
        >
          <ul className="flex flex-col px-4 py-3 gap-0.5">
            {navKeys.map(({ href, key }) => {
              const active = pathname === href;
              const label = key === "home" ? (fallbackLabels[key]) : (t.has(key) ? t(key) : fallbackLabels[key]);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    onClick={() => setMobileOpen(false)}
                    className={`flex items-center rounded-lg px-4 py-3.5 font-[family-name:var(--font-display)] text-sm uppercase tracking-widest transition-colors min-h-[48px] active:scale-[0.98] ${
                      active
                        ? "glow-cyan bg-glow-cyan/10"
                        : "text-text-secondary hover:text-text-primary hover:bg-white/5"
                    }`}
                  >
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
          {/* Mobile-only controls */}
          <div className="flex items-center gap-4 px-8 py-4 border-t border-border-subtle/40">
            <LanguageSwitcher />
            <ThemeToggle />
          </div>
        </div>
      )}
    </>
  );
}
