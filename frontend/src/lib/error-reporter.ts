/**
 * Lightweight error reporting for production.
 * In development: logs to console.
 * In production: can POST to a configurable endpoint.
 */

const IS_DEV = process.env.NODE_ENV === "development";
const REPORT_URL = process.env.NEXT_PUBLIC_ERROR_REPORT_URL ?? "";

interface ErrorReport {
  message: string;
  stack?: string;
  url: string;
  timestamp: string;
  userAgent: string;
  extra?: Record<string, unknown>;
}

const recentErrors = new Set<string>();

function dedupKey(msg: string): string {
  return msg.slice(0, 120);
}

export function reportError(
  error: Error | string,
  extra?: Record<string, unknown>,
): void {
  const msg = typeof error === "string" ? error : error.message;
  const stack = typeof error === "string" ? undefined : error.stack;

  // Deduplicate — don't report same error repeatedly
  const key = dedupKey(msg);
  if (recentErrors.has(key)) return;
  recentErrors.add(key);
  if (recentErrors.size > 100) recentErrors.clear();

  const report: ErrorReport = {
    message: msg,
    stack,
    url: typeof window !== "undefined" ? window.location.href : "",
    timestamp: new Date().toISOString(),
    userAgent: typeof navigator !== "undefined" ? navigator.userAgent : "",
    extra,
  };

  if (IS_DEV) {
    console.error("[ErrorReporter]", report);
    return;
  }

  // Production: POST to error endpoint if configured
  if (REPORT_URL) {
    fetch(REPORT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(report),
    }).catch(() => {
      // Swallow — don't let error reporting cause more errors
    });
  }
}

/** Install global error handlers. Call once at app init. */
export function installGlobalErrorHandlers(): void {
  if (typeof window === "undefined") return;

  window.addEventListener("error", (event) => {
    reportError(event.error ?? event.message, {
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    if (reason instanceof Error) {
      reportError(reason, { type: "unhandledrejection" });
    } else {
      reportError(String(reason), { type: "unhandledrejection" });
    }
  });
}
