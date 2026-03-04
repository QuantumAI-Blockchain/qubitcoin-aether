"use client";

import { useState, useEffect } from "react";
import {
  isPushSupported,
  getPermissionStatus,
  requestPermission,
  showNotification,
  notifications,
} from "@/lib/push-notifications";
import { Card } from "@/components/ui/card";

/**
 * Push Notification Setup panel — allows users to enable/disable
 * push notifications for various blockchain events.
 */
export function PushNotificationSetup() {
  const [supported, setSupported] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission>("default");

  useEffect(() => {
    setSupported(isPushSupported());
    setPermission(getPermissionStatus());
  }, []);

  const handleEnable = async () => {
    const result = await requestPermission();
    setPermission(result);
    if (result === "granted") {
      // Show a test notification
      await showNotification(notifications.newBlock(1));
    }
  };

  if (!supported) {
    return (
      <Card>
        <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold">
          Notifications
        </h3>
        <p className="mt-2 text-sm text-text-secondary">
          Push notifications are not supported in this browser.
        </p>
      </Card>
    );
  }

  return (
    <Card>
      <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold">
        Notifications
      </h3>

      {permission === "granted" ? (
        <div className="mt-3 space-y-3">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-quantum-green" />
            <p className="text-sm text-quantum-green">
              Notifications enabled
            </p>
          </div>
          <p className="text-xs text-text-secondary">
            You will receive alerts for new blocks, incoming transactions,
            mining rewards, and finality checkpoints.
          </p>
        </div>
      ) : permission === "denied" ? (
        <p className="mt-3 text-sm text-red-400">
          Notifications are blocked. Please enable them in your browser
          settings.
        </p>
      ) : (
        <div className="mt-3">
          <p className="text-sm text-text-secondary">
            Enable notifications to receive alerts for blockchain events.
          </p>
          <button
            onClick={handleEnable}
            className="mt-3 rounded-lg bg-quantum-violet px-4 py-2 text-sm font-semibold text-white transition hover:bg-quantum-violet/80"
          >
            Enable Notifications
          </button>
        </div>
      )}
    </Card>
  );
}
