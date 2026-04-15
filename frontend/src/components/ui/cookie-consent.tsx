"use client";
import { useEffect, useState } from "react";
import { hasMadeConsentChoice, setConsent, type ConsentChoice } from "@/lib/consent";

export function CookieConsent() {
  const [show, setShow] = useState(false);

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
        쿠키를 사용해 서비스 품질을 개선합니다. 분석 쿠키는 동의하신 경우에만 활성화됩니다.{" "}
        <a href="/privacy" className="underline">
          개인정보처리방침
        </a>
      </p>
      <div className="flex flex-wrap gap-2 md:flex-nowrap">
        <button
          type="button"
          onClick={() => choose("rejected")}
          className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
        >
          거부
        </button>
        <button
          type="button"
          onClick={() => choose("essential")}
          className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          필수만
        </button>
        <button
          type="button"
          onClick={() => choose("accepted")}
          className="rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          전체 허용
        </button>
      </div>
    </div>
  );
}
