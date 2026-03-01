/** Telegram Web App SDK integration */

/** Telegram WebApp type declarations */
interface TelegramWebApp {
  initData: string;
  initDataUnsafe: {
    user?: {
      id: number;
      first_name: string;
      last_name?: string;
      username?: string;
      language_code?: string;
      is_premium?: boolean;
    };
    start_param?: string;
    chat_type?: string;
    auth_date?: number;
    hash?: string;
  };
  version: string;
  platform: string;
  colorScheme: "light" | "dark";
  themeParams: Record<string, string>;
  isExpanded: boolean;
  viewportHeight: number;
  viewportStableHeight: number;
  BackButton: {
    isVisible: boolean;
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  MainButton: {
    text: string;
    color: string;
    textColor: string;
    isVisible: boolean;
    isActive: boolean;
    show: () => void;
    hide: () => void;
    setText: (text: string) => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
    showProgress: (leaveActive?: boolean) => void;
    hideProgress: () => void;
  };
  HapticFeedback: {
    impactOccurred: (style: "light" | "medium" | "heavy" | "rigid" | "soft") => void;
    notificationOccurred: (type: "error" | "success" | "warning") => void;
    selectionChanged: () => void;
  };
  close: () => void;
  expand: () => void;
  ready: () => void;
  sendData: (data: string) => void;
  openLink: (url: string, options?: { try_instant_view?: boolean }) => void;
  openTelegramLink: (url: string) => void;
  showPopup: (params: {
    title?: string;
    message: string;
    buttons?: Array<{ id?: string; type?: string; text?: string }>;
  }, callback?: (id: string) => void) => void;
  showAlert: (message: string, callback?: () => void) => void;
  showConfirm: (message: string, callback?: (ok: boolean) => void) => void;
  onEvent: (eventType: string, callback: () => void) => void;
  offEvent: (eventType: string, callback: () => void) => void;
}

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
  }
}

/** Check if running inside Telegram Mini App */
export function isTelegramWebApp(): boolean {
  if (typeof window === "undefined") return false;
  return !!window.Telegram?.WebApp?.initData;
}

/** Get the Telegram WebApp instance */
export function getWebApp(): TelegramWebApp | null {
  if (typeof window === "undefined") return null;
  return window.Telegram?.WebApp ?? null;
}

/** Initialize the Telegram Web App */
export function initTelegramApp(): TelegramWebApp | null {
  const webapp = getWebApp();
  if (!webapp) return null;

  // Signal to Telegram that the app is ready
  webapp.ready();

  // Expand to full height
  webapp.expand();

  return webapp;
}

/** Get the start parameter (deep link referral code) */
export function getStartParam(): string {
  const webapp = getWebApp();
  return webapp?.initDataUnsafe?.start_param ?? "";
}

/** Get Telegram user data */
export function getTelegramUser() {
  const webapp = getWebApp();
  return webapp?.initDataUnsafe?.user ?? null;
}

/** Show haptic feedback */
export function hapticFeedback(type: "light" | "medium" | "heavy" = "light") {
  getWebApp()?.HapticFeedback?.impactOccurred(type);
}

/** Show notification haptic */
export function hapticNotification(type: "success" | "warning" | "error") {
  getWebApp()?.HapticFeedback?.notificationOccurred(type);
}

/** Show the back button */
export function showBackButton(callback: () => void) {
  const webapp = getWebApp();
  if (!webapp) return;
  webapp.BackButton.show();
  webapp.BackButton.onClick(callback);
}

/** Hide the back button */
export function hideBackButton() {
  getWebApp()?.BackButton?.hide();
}

/** Show the main button */
export function showMainButton(text: string, callback: () => void) {
  const webapp = getWebApp();
  if (!webapp) return;
  webapp.MainButton.setText(text);
  webapp.MainButton.show();
  webapp.MainButton.onClick(callback);
}

/** Hide the main button */
export function hideMainButton() {
  getWebApp()?.MainButton?.hide();
}

/** Open an external link */
export function openExternalLink(url: string) {
  const webapp = getWebApp();
  if (webapp) {
    webapp.openLink(url);
  } else if (typeof window !== "undefined") {
    window.open(url, "_blank");
  }
}

/** Share via Telegram */
export function shareViaTelegram(url: string) {
  const webapp = getWebApp();
  if (webapp) {
    webapp.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(url)}`);
  }
}

/** Close the Mini App */
export function closeMiniApp() {
  getWebApp()?.close();
}
