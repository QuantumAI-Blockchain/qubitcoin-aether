"use client";

import { useThemeStore } from "@/stores/theme-store";

export function ThemeToggle() {
  const { theme, toggle } = useThemeStore();

  return (
    <button
      onClick={toggle}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      className="rounded-lg p-2 text-text-secondary transition hover:bg-surface-light hover:text-text-primary"
    >
      {theme === "dark" ? (
        /* Sun icon */
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-4 w-4">
          <circle cx="12" cy="12" r="5" strokeWidth={2} />
          <path
            strokeLinecap="round"
            strokeWidth={2}
            d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"
          />
        </svg>
      ) : (
        /* Moon icon */
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-4 w-4">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"
          />
        </svg>
      )}
    </button>
  );
}
