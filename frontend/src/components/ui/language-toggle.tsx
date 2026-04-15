"use client";

import { useLocale } from "@/lib/locale";

/**
 * LanguageToggle — top-bar inline locale switcher
 *
 * Syncs with the same LocaleContext used by the Settings language tab,
 * so both controls stay in sync without any extra state management.
 */
export function LanguageToggle() {
  const { locale, setLocale } = useLocale();

  const toggle = () => {
    setLocale(locale === "ko" ? "en" : "ko");
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={locale === "ko" ? "Switch to English" : "한국어로 변경"}
      className="flex h-10 items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50 px-2.5 text-sm font-medium text-slate-600 transition-colors hover:bg-white hover:border-slate-300 hover:text-slate-800"
    >
      <span className="text-base leading-none" role="img" aria-hidden>
        {locale === "ko" ? "\uD83C\uDDF0\uD83C\uDDF7" : "\uD83C\uDDFA\uD83C\uDDF8"}
      </span>
      <span className="hidden sm:inline tabular-nums">{locale === "ko" ? "KO" : "EN"}</span>
    </button>
  );
}
