"use client";

/**
 * LegalConsentModal
 *
 * Gates first-time access for OAuth users who skipped the signup page's
 * consent checkboxes (e.g. Kakao/Google login directly). Renders a blocking
 * modal until the three required agreements are accepted:
 *
 *   1. Terms of service + privacy policy (generic)
 *   2. Non-advisory disclosure (자본시장법)
 *   3. Age confirmation — 14+ (PIPA §22)
 *
 * Optional marketing consent is offered but not required.
 *
 * Persists the consent snapshot to localStorage under `pivox_signup_consents`.
 * The caller component reads that key on mount; if present, this modal
 * does not render.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { ModalShell } from "@/components/ui/modal-shell";

const CONSENT_STORAGE_KEY = "pivox_signup_consents";

interface Consents {
  terms: boolean;
  non_advisory: boolean;
  age: boolean;
  marketing: boolean;
}

export function hasLocalConsent(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const raw = window.localStorage.getItem(CONSENT_STORAGE_KEY);
    if (!raw) return false;
    const parsed = JSON.parse(raw) as Partial<Consents>;
    return Boolean(parsed.terms && parsed.non_advisory && parsed.age);
  } catch {
    return false;
  }
}

function Checkbox({
  checked,
  onChange,
  id,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  id: string;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      id={id}
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-all duration-200 ${
        checked
          ? "border-[var(--sp-accent)] bg-[var(--sp-accent)]"
          : "border-slate-300 bg-white hover:border-slate-400"
      }`}
    >
      {checked && (
        <svg
          width="10"
          height="10"
          viewBox="0 0 12 12"
          fill="none"
          stroke="white"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="2 6 5 9 10 3" />
        </svg>
      )}
    </button>
  );
}

export function LegalConsentModal({
  onAgree,
}: {
  onAgree: () => void;
}) {
  const [consents, setConsents] = useState<Consents>({
    terms: false,
    non_advisory: false,
    age: false,
    marketing: false,
  });

  const allRequired = consents.terms && consents.non_advisory && consents.age;

  useEffect(() => {
    // Prevent backdrop close — this modal is legally blocking.
  }, []);

  const setConsent = (key: keyof Consents) => (next: boolean) => {
    setConsents((prev) => ({ ...prev, [key]: next }));
  };

  const handleSubmit = () => {
    if (!allRequired) return;
    try {
      window.localStorage.setItem(
        CONSENT_STORAGE_KEY,
        JSON.stringify({
          ...consents,
          consented_at: new Date().toISOString(),
        }),
      );
    } catch {
      // non-fatal
    }
    onAgree();
  };

  return (
    <ModalShell
      onClose={() => {
        /* blocking — no-op */
      }}
      closeOnBackdrop={false}
      ariaLabel="가입 전 법적 동의"
    >
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <h2 className="text-lg font-bold text-slate-900">가입 전 확인</h2>
        <p className="mt-1 text-xs text-slate-500">
          계속하려면 아래 필수 항목에 동의해 주세요.
        </p>

        <div className="mt-5 space-y-3 rounded-xl border border-slate-200 bg-slate-50/60 p-4">
          {/* 1. 이용약관 + 개인정보처리방침 */}
          <label
            htmlFor="consent_terms"
            className="flex cursor-pointer items-start gap-2"
          >
            <Checkbox
              id="consent_terms"
              checked={consents.terms}
              onChange={setConsent("terms")}
            />
            <span className="text-xs leading-relaxed text-slate-600">
              <strong className="text-slate-900">[필수]</strong>{" "}
              <Link
                href="/terms"
                target="_blank"
                className="underline hover:text-slate-900"
                onClick={(e) => e.stopPropagation()}
              >
                이용약관
              </Link>{" "}
              및{" "}
              <Link
                href="/privacy"
                target="_blank"
                className="underline hover:text-slate-900"
                onClick={(e) => e.stopPropagation()}
              >
                개인정보처리방침
              </Link>
              에 동의합니다.
            </span>
          </label>

          {/* 2. 투자자문업 아님 */}
          <label
            htmlFor="consent_non_advisory"
            className="flex cursor-pointer items-start gap-2"
          >
            <Checkbox
              id="consent_non_advisory"
              checked={consents.non_advisory}
              onChange={setConsent("non_advisory")}
            />
            <span className="text-xs leading-relaxed text-slate-600">
              <strong className="text-slate-900">[필수]</strong> PivoxQuant는
              자본시장법상 투자자문업이 아니며, 본 서비스의 모든 분석·리포트·시그널은
              정보 제공 목적임을 이해합니다.
            </span>
          </label>

          {/* 3. 14세 이상 */}
          <label
            htmlFor="consent_age"
            className="flex cursor-pointer items-start gap-2"
          >
            <Checkbox
              id="consent_age"
              checked={consents.age}
              onChange={setConsent("age")}
            />
            <span className="text-xs leading-relaxed text-slate-600">
              <strong className="text-slate-900">[필수]</strong> 만 14세 이상입니다.
              (개인정보보호법 §22)
            </span>
          </label>

          {/* 4. 마케팅 (선택) */}
          <label
            htmlFor="consent_marketing"
            className="flex cursor-pointer items-start gap-2"
          >
            <Checkbox
              id="consent_marketing"
              checked={consents.marketing}
              onChange={setConsent("marketing")}
            />
            <span className="text-xs leading-relaxed text-slate-600">
              <span className="text-slate-500">[선택]</span> 마케팅 정보 수신에
              동의합니다.
            </span>
          </label>
        </div>

        <button
          type="button"
          disabled={!allRequired}
          onClick={handleSubmit}
          className={`mt-5 w-full rounded-full px-4 py-3 text-sm font-semibold transition-all ${
            allRequired
              ? "bg-slate-900 text-white hover:bg-slate-800 active:scale-[0.97]"
              : "cursor-not-allowed bg-slate-100 text-slate-400"
          }`}
        >
          동의하고 계속하기
        </button>

        {!allRequired && (
          <p className="mt-2 text-center text-[11px] text-slate-400">
            필수 항목 3개에 모두 동의해야 진행할 수 있습니다.
          </p>
        )}
      </div>
    </ModalShell>
  );
}
