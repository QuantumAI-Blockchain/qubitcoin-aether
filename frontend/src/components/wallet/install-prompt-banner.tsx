"use client";

import { useEffect, useState } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

/**
 * PWA install prompt banner — shows when the app can be installed
 * and the user hasn't dismissed it yet.
 */
export function InstallPromptBanner() {
  const [deferredPrompt, setDeferredPrompt] =
    useState<BeforeInstallPromptEvent | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // Check if already dismissed this session
    if (sessionStorage.getItem("qbc-install-dismissed")) {
      setDismissed(true);
      return;
    }

    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
    };

    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  if (!deferredPrompt || dismissed) return null;

  const handleInstall = async () => {
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") {
      setDeferredPrompt(null);
    }
  };

  const handleDismiss = () => {
    setDismissed(true);
    sessionStorage.setItem("qbc-install-dismissed", "1");
  };

  return (
    <div className="fixed bottom-4 left-4 right-4 z-50 mx-auto max-w-md rounded-xl border border-quantum-green/30 bg-bg-panel/95 px-5 py-4 shadow-lg backdrop-blur-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <p className="text-sm font-semibold text-text-primary">
            Install Qubitcoin
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            Add to your home screen for offline access and a native app
            experience.
          </p>
        </div>
        <button
          onClick={handleDismiss}
          className="text-text-secondary hover:text-text-primary"
          aria-label="Dismiss"
        >
          &#10005;
        </button>
      </div>
      <button
        onClick={handleInstall}
        className="mt-3 w-full rounded-lg bg-quantum-green px-4 py-2 text-sm font-semibold text-void transition hover:bg-quantum-green/80"
      >
        Install App
      </button>
    </div>
  );
}
