/**
 * Push Notification Support for Qubitcoin PWA
 *
 * Supports Web Push API for real-time alerts:
 * - New block mined
 * - Incoming transaction
 * - Mining reward received
 * - Finality checkpoint reached
 */

export type NotificationType =
  | "new_block"
  | "incoming_tx"
  | "mining_reward"
  | "finality_checkpoint"
  | "depeg_alert";

export interface QBCNotification {
  type: NotificationType;
  title: string;
  body: string;
  data?: Record<string, string>;
}

/** Check if push notifications are supported. */
export function isPushSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "Notification" in window &&
    "serviceWorker" in navigator &&
    "PushManager" in window
  );
}

/** Get current notification permission status. */
export function getPermissionStatus(): NotificationPermission {
  if (!isPushSupported()) return "denied";
  return Notification.permission;
}

/** Request notification permission from the user. */
export async function requestPermission(): Promise<NotificationPermission> {
  if (!isPushSupported()) return "denied";
  return Notification.requestPermission();
}

/** Show a local notification (no push server needed). */
export async function showNotification(notification: QBCNotification): Promise<void> {
  if (getPermissionStatus() !== "granted") return;

  const reg = await navigator.serviceWorker.ready;
  const options: NotificationOptions & { vibrate?: number[] } = {
    body: notification.body,
    icon: "/icons/icon-192x192.png",
    badge: "/icons/icon-192x192.png",
    tag: notification.type,
    data: notification.data,
    vibrate: [100, 50, 100],
  };
  await reg.showNotification(notification.title, options);
}

/** Notification presets for common events. */
export const notifications = {
  newBlock(height: number): QBCNotification {
    return {
      type: "new_block",
      title: "New Block Mined",
      body: `Block #${height.toLocaleString()} has been mined.`,
      data: { height: String(height) },
    };
  },

  incomingTx(amount: string, from: string): QBCNotification {
    return {
      type: "incoming_tx",
      title: "Incoming Transaction",
      body: `Received ${amount} QBC from ${from.slice(0, 12)}...`,
      data: { amount, from },
    };
  },

  miningReward(amount: string, height: number): QBCNotification {
    return {
      type: "mining_reward",
      title: "Mining Reward",
      body: `Earned ${amount} QBC for block #${height.toLocaleString()}`,
      data: { amount, height: String(height) },
    };
  },

  finalityCheckpoint(height: number): QBCNotification {
    return {
      type: "finality_checkpoint",
      title: "Finality Checkpoint",
      body: `Block #${height.toLocaleString()} has been finalized.`,
      data: { height: String(height) },
    };
  },

  depegAlert(price: number): QBCNotification {
    return {
      type: "depeg_alert",
      title: "QUSD Depeg Alert",
      body: `QUSD price is $${price.toFixed(4)} — outside peg range.`,
      data: { price: String(price) },
    };
  },
};
