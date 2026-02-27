import { getRequestConfig } from "next-intl/server";
import { cookies, headers } from "next/headers";

/**
 * Supported locales. English is the default.
 */
export const locales = ["en", "zh", "es"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "en";

/** Human-readable locale labels for the language switcher. */
export const localeLabels: Record<Locale, string> = {
  en: "English",
  zh: "中文",
  es: "Espanol",
};

/**
 * Detect the user's preferred locale from cookie, Accept-Language header,
 * or default to "en".
 */
async function getLocale(): Promise<Locale> {
  // 1. Check cookie first (user's explicit choice)
  const cookieStore = await cookies();
  const cookieLocale = cookieStore.get("NEXT_LOCALE")?.value;
  if (cookieLocale && locales.includes(cookieLocale as Locale)) {
    return cookieLocale as Locale;
  }

  // 2. Check Accept-Language header
  const headerStore = await headers();
  const acceptLang = headerStore.get("accept-language") ?? "";
  const preferredLocales = acceptLang
    .split(",")
    .map((part) => part.split(";")[0].trim().split("-")[0])
    .filter((lang): lang is Locale => locales.includes(lang as Locale));

  if (preferredLocales.length > 0) {
    return preferredLocales[0];
  }

  // 3. Default
  return defaultLocale;
}

export default getRequestConfig(async () => {
  const locale = await getLocale();

  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
