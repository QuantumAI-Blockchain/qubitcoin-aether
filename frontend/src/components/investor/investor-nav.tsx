"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  { href: "/invest", label: "Invest" },
  { href: "/invest/dashboard", label: "Dashboard" },
  { href: "/invest/vesting", label: "Vesting" },
  { href: "/invest/documents", label: "Documents" },
] as const;

export function InvestorNav() {
  const pathname = usePathname();

  return (
    <nav className="mb-6 flex gap-1 rounded-lg border border-border-subtle bg-bg-panel p-1">
      {tabs.map(({ href, label }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            className={`flex-1 rounded-md px-4 py-2 text-center font-[family-name:var(--font-display)] text-xs uppercase tracking-widest transition ${
              active
                ? "bg-glow-cyan/15 text-glow-cyan"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
