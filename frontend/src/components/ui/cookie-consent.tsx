"use client";
import { useEffect, useState } from "react";
import { hasMadeConsentChoice, setConsent, type ConsentChoice } from "@/lib/consent";
import { useT } from "@/lib/locale";

export function CookieConsent() {
  const [show, setShow] = useState(false);
  const t = useT();

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!hasMadeConsentChoice()) setShow(true);
  }, []);

  if (!show) return null;

  const choose = (choice: ConsentChoice) => {
    setConsent(choice);
    setShow(false);
  };

  // Placement / look only (2026-10-09 phone audit). The choice logic, copy,
  // storage and defaults above are untouched. Phone: an ink card that floats
  // ABOVE the bottom nav (globals.css "Cookie banner" lifts it when a nav is
  // on screen) with 48px buttons in one row; desktop: the full-width strip.
  const btn =
    "min-h-[48px] flex-1 px-3 text-sm font-medium transition-colors md:min-h-0 md:flex-none md:px-4 md:py-2";
  return (
    <div
      role="dialog"
      aria-label="Cookie consent"
      data-cookie-banner="true"
      // z-[55]: explicitly above the mobile BottomNav (z-50) instead of tying
      // with it on DOM order; it's a choice the user answers once.
      className="pq-cookie-banner fixed bottom-0 left-0 right-0 z-[55] md:flex md:items-center md:justify-between md:gap-6 md:px-8 md:py-4"
      style={{ color: "var(--pq-ivory)" }}
    >
      <p
        className="mb-3 text-sm leading-relaxed md:mb-0 md:flex-1"
        style={{ color: "rgba(var(--pq-ivory-rgb), 0.78)" }}
      >
        {t("cookieConsent.message")}{" "}
        <a
          href="/privacy"
          className="underline"
          style={{ color: "var(--pq-bronze)" }}
        >
          {t("cookieConsent.privacyPolicy")}
        </a>
      </p>
      <div className="flex gap-2 md:flex-nowrap">
        <button
          type="button"
          onClick={() => choose("rejected")}
          className={btn}
          style={{
            borderRadius: "var(--pq-radius-cta)",
            border: "1px solid var(--pq-border)",
            color: "rgba(var(--pq-ivory-rgb), 0.7)",
            backgroundColor: "transparent",
          }}
        >
          {t("cookieConsent.reject")}
        </button>
        <button
          type="button"
          onClick={() => choose("essential")}
          className={btn}
          style={{
            borderRadius: "var(--pq-radius-cta)",
            border: "1px solid var(--pq-border)",
            color: "rgba(var(--pq-ivory-rgb), 0.85)",
            backgroundColor: "transparent",
          }}
        >
          {t("cookieConsent.essentialOnly")}
        </button>
        <button
          type="button"
          onClick={() => choose("accepted")}
          className={`${btn} font-semibold`}
          style={{
            borderRadius: "var(--pq-radius-cta)",
            backgroundColor: "var(--pq-bronze)",
            color: "var(--pq-ink)",
          }}
        >
          {t("cookieConsent.acceptAll")}
        </button>
      </div>
    </div>
  );
}
