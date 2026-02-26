"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { WalletButton } from "@/components/wallet/wallet-button";
import { PhiIndicator } from "@/components/ui/phi-indicator";
import { ThemeToggle } from "@/components/ui/theme-toggle";

const links = [
  { href: "/", label: "Home" },
  { href: "/aether", label: "Aether" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/explorer", label: "Explorer" },
  { href: "/wallet", label: "Wallet" },
  { href: "/qvm", label: "QVM" },
  { href: "/bridge", label: "Bridge" },
];

export function Navbar() {
  const pathname = usePathname();

  return (
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

        {/* Nav links */}
        <ul className="flex items-center gap-1">
          {links.map(({ href, label }) => {
            const active = pathname === href;
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
          <ThemeToggle />
          <WalletButton />
        </div>
      </nav>
    </header>
  );
}
