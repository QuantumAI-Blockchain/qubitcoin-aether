"use client";

import { useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";

/**
 * Global keyboard shortcuts:
 *   /         → Focus search (if a search input exists) or navigate to dashboard
 *   Escape    → Close any open modal/overlay, blur focused input
 *   Ctrl+K    → Open command palette / navigate to dashboard
 */
export function useKeyboardShortcuts() {
  const router = useRouter();

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isInput =
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable;

      // Escape — blur active input or close overlay
      if (e.key === "Escape") {
        if (document.activeElement instanceof HTMLElement) {
          document.activeElement.blur();
        }
        // Dispatch custom event for modals to listen to
        window.dispatchEvent(new CustomEvent("qbc:escape"));
        return;
      }

      // Skip shortcuts when typing in an input
      if (isInput) return;

      // / — focus first search input on page
      if (e.key === "/") {
        e.preventDefault();
        const searchInput = document.querySelector<HTMLInputElement>(
          'input[type="search"], input[placeholder*="earch"], input[placeholder*="ddress"]',
        );
        if (searchInput) {
          searchInput.focus();
        }
        return;
      }

      // Ctrl+K or Cmd+K — navigate to dashboard
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        router.push("/dashboard");
        return;
      }
    },
    [router],
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);
}
