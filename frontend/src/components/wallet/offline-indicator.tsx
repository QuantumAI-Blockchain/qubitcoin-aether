"use client";

import { useEffect, useState } from "react";

/**
 * Offline status indicator — appears as a banner when the user loses
 * internet connectivity.
 */
export function OfflineIndicator() {
  const [isOffline, setIsOffline] = useState(false);

  useEffect(() => {
    const goOffline = () => setIsOffline(true);
    const goOnline = () => setIsOffline(false);

    // Check initial state
    setIsOffline(!navigator.onLine);

    window.addEventListener("offline", goOffline);
    window.addEventListener("online", goOnline);
    return () => {
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online", goOnline);
    };
  }, []);

  if (!isOffline) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-[100] bg-amber-600 px-4 py-2 text-center text-sm font-medium text-void">
      You are offline — cached data may be stale. Queued transactions will send
      when connectivity is restored.
    </div>
  );
}
