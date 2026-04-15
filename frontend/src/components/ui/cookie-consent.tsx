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
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-slate-200 bg-white p-4 shadow-lg md:flex md:items-center md:justify-between md:gap-6 md:px-8"
    >
      <p className="mb-3 text-sm text-slate-600 md:mb-0 md:flex-1">
        {t("cookieConsent.message")}{" "}
        <a href="/privacy" className="underline">
          {t("cookieConsent.privacyPolicy")}
        </a>
      </p>
      <div className="flex flex-wrap gap-2 md:flex-nowrap">
        <button
          type="button"
          onClick={() => choose("rejected")}
          className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
        >
          {t("cookieConsent.reject")}
        </button>
        <button
          type="button"
          onClick={() => choose("essential")}
          className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          {t("cookieConsent.essentialOnly")}
        </button>
        <button
          type="button"
          onClick={() => choose("accepted")}
          className="rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          {t("cookieConsent.acceptAll")}
        </button>
      </div>
    </div>
  );
}
