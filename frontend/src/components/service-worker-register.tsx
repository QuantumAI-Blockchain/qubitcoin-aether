"use client";

import { useEffect } from "react";
import { cacheEvictExpired } from "@/lib/offline-cache";

/**
 * Registers the service worker and performs initial IndexedDB housekeeping.
 * Render this component once in the app layout (inside Providers).
 */
export function ServiceWorkerRegister(): null {
  useEffect(() => {
    // Register service worker
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker
        .register("/sw.js", { scope: "/" })
        .then((registration) => {
          // Check for updates periodically (every 5 minutes)
          setInterval(() => {
            registration.update().catch(() => {});
          }, 5 * 60 * 1000);

          // If a new SW is waiting, notify the user
          registration.addEventListener("updatefound", () => {
            const newWorker = registration.installing;
            if (!newWorker) return;
            newWorker.addEventListener("statechange", () => {
              if (
                newWorker.state === "installed" &&
                navigator.serviceWorker.controller
              ) {
                // New content available — tell SW to activate immediately
                newWorker.postMessage("skipWaiting");
              }
            });
          });
        })
        .catch((err) => {
          console.warn("[SW] Registration failed:", err);
        });

      // Reload page when new SW takes over
      let refreshing = false;
      navigator.serviceWorker.addEventListener("controllerchange", () => {
        if (!refreshing) {
          refreshing = true;
          window.location.reload();
        }
      });
    }

    // Clean up expired IndexedDB cache entries on load
    cacheEvictExpired().catch(() => {});
  }, []);

  return null;
}
