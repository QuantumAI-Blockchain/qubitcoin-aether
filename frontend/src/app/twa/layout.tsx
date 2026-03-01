"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { useTelegramStore } from "@/stores/telegram-store";
import {
  isTelegramWebApp,
  initTelegramApp,
  getTelegramUser,
  getStartParam,
  getWebApp,
} from "@/lib/telegram";

const NAV_ITEMS = [
  { href: "/twa", label: "Home", icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" },
  { href: "/twa/chat", label: "Chat", icon: "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" },
  { href: "/twa/earn", label: "Earn", icon: "M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" },
  { href: "/twa/wallet", label: "Wallet", icon: "M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" },
  { href: "/twa/more", label: "More", icon: "M5 12h.01M12 12h.01M19 12h.01M6 12a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0z" },
];

export default function TWALayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { setIsTWA, setUser, setStartParam, setColorScheme, setViewportHeight } = useTelegramStore();
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    const webapp = initTelegramApp();

    // Store named callbacks for cleanup
    const onThemeChanged = () => {
      const wa = getWebApp();
      if (wa) setColorScheme(wa.colorScheme);
    };
    const onViewportChanged = () => {
      const wa = getWebApp();
      if (wa) setViewportHeight(wa.viewportStableHeight);
    };

    if (webapp) {
      setIsTWA(true);
      const user = getTelegramUser();
      if (user) setUser(user);
      const sp = getStartParam();
      if (sp) setStartParam(sp);
      setColorScheme(webapp.colorScheme);
      setViewportHeight(webapp.viewportHeight);

      webapp.onEvent("themeChanged", onThemeChanged);
      webapp.onEvent("viewportChanged", onViewportChanged);
    } else {
      setIsTWA(isTelegramWebApp());
    }
    setInitialized(true);

    return () => {
      // Clean up event listeners
      const wa = getWebApp();
      if (wa) {
        wa.offEvent("themeChanged", onThemeChanged);
        wa.offEvent("viewportChanged", onViewportChanged);
      }
    };
  }, [setIsTWA, setUser, setStartParam, setColorScheme, setViewportHeight]);

  if (!initialized) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg-deep">
        <div className="phi-spin h-8 w-8 rounded-full border-2 border-quantum-violet/30 border-t-quantum-violet" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-deep twa-safe-area">
      {/* Main content */}
      <main className="flex-1 overflow-y-auto pb-20">
        <ErrorBoundary>{children}</ErrorBoundary>
      </main>

      {/* Bottom navigation */}
      <nav className="fixed bottom-0 left-0 right-0 border-t border-border-subtle bg-bg-panel/95 backdrop-blur-md twa-bottom-nav">
        <div className="mx-auto flex max-w-lg items-center justify-around px-2 py-2">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-label={item.label}
                className={`flex flex-col items-center gap-0.5 px-3 py-1 transition ${
                  active ? "text-quantum-violet" : "text-text-secondary"
                }`}
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.5}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-5 w-5"
                  aria-hidden="true"
                >
                  <path d={item.icon} />
                </svg>
                <span className="text-[10px] font-semibold">{item.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
