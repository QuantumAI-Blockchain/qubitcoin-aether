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
  { href: "/wallet", label: "Wallet" },
  { href: "/qvm", label: "QVM" },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <header className="fixed top-0 z-50 w-full border-b border-surface-light/50 bg-void/80 backdrop-blur-md">
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2">
          <span className="text-xl font-bold tracking-tight text-quantum-green font-[family-name:var(--font-heading)]">
            QBC
          </span>
          <span className="hidden text-sm text-text-secondary sm:inline">
            Qubitcoin
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
                  className={`relative rounded-md px-3 py-2 text-sm transition-colors ${
                    active
                      ? "text-quantum-green"
                      : "text-text-secondary hover:text-text-primary"
                  }`}
                >
                  {label}
                  {active && (
                    <motion.span
                      layoutId="nav-indicator"
                      className="absolute inset-x-1 -bottom-[1px] h-0.5 bg-quantum-green"
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
