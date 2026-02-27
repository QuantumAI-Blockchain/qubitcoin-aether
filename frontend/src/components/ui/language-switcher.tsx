"use client";

import { useState, useRef, useEffect } from "react";
import { useLocale, useTranslations } from "next-intl";

const localeConfig = [
  { code: "en", label: "English", flag: "EN" },
  { code: "zh", label: "\u4e2d\u6587", flag: "ZH" },
  { code: "es", label: "Espa\u00f1ol", flag: "ES" },
] as const;

/**
 * Language switcher dropdown.
 * Sets a cookie (NEXT_LOCALE) and reloads the page to apply the new locale.
 */
export function LanguageSwitcher() {
  const locale = useLocale();
  const t = useTranslations("language");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function switchLocale(newLocale: string) {
    // Set cookie with 1 year expiry
    document.cookie = `NEXT_LOCALE=${newLocale};path=/;max-age=31536000;SameSite=Lax`;
    setOpen(false);
    // Reload to apply new locale
    window.location.reload();
  }

  const currentLocale = localeConfig.find((l) => l.code === locale) ?? localeConfig[0];

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 rounded-lg border border-border-subtle bg-bg-panel px-2.5 py-1.5 text-xs text-text-secondary transition hover:border-glow-cyan/30 hover:text-text-primary"
        aria-label={t("switchTo")}
        title={t("switchTo")}
      >
        <svg
          width="14"
          height="14"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          className="shrink-0"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M12 21a9 9 0 100-18 9 9 0 000 18zM3.6 9h16.8M3.6 15h16.8M12 3a15.3 15.3 0 014 9 15.3 15.3 0 01-4 9 15.3 15.3 0 01-4-9 15.3 15.3 0 014-9z"
          />
        </svg>
        <span className="font-[family-name:var(--font-code)]">
          {currentLocale.flag}
        </span>
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 min-w-[140px] overflow-hidden rounded-xl border border-border-subtle bg-bg-panel shadow-2xl">
          {localeConfig.map((l) => (
            <button
              key={l.code}
              onClick={() => switchLocale(l.code)}
              className={`flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm transition hover:bg-bg-elevated ${
                l.code === locale
                  ? "text-glow-cyan"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              <span className="w-5 font-[family-name:var(--font-code)] text-[10px]">
                {l.flag}
              </span>
              <span>{l.label}</span>
              {l.code === locale && (
                <span className="ml-auto h-1.5 w-1.5 rounded-full bg-glow-cyan" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
