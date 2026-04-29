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

  return (
    <div
      role="dialog"
      aria-label="Cookie consent"
      className="fixed bottom-0 left-0 right-0 z-50 p-4 md:flex md:items-center md:justify-between md:gap-6 md:px-8"
      style={{
        backgroundColor: "var(--pq-ink)",
        color: "var(--pq-ivory)",
        borderTop: "1px solid var(--pq-border)",
        boxShadow: "0 -8px 24px rgba(0,0,0,0.4)",
      }}
    >
      <p
        className="mb-3 text-sm md:mb-0 md:flex-1"
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
      <div className="flex flex-wrap gap-2 md:flex-nowrap">
        <button
          type="button"
          onClick={() => choose("rejected")}
          className="px-4 py-2 text-sm font-medium transition-colors"
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
          className="px-4 py-2 text-sm font-medium transition-colors"
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
          className="px-4 py-2 text-sm font-semibold transition-colors"
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
