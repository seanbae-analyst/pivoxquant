"use client";

/**
 * LegalConsentModal
 *
 * Gates first-time access for OAuth users who skipped the signup page's
 * consent checkboxes (e.g. Kakao/Google login directly). Renders a blocking
 * modal until the four required agreements are accepted:
 *
 *   1. Terms of service + privacy policy (generic)
 *   2. Non-advisory disclosure (자본시장법)
 *   3. Age confirmation — 14+ self-declaration (PIPA §22 ⑥; 2026-09-19:
 *      plain required checkbox, no birthdate is collected)
 *   4. Cross-border data transfer consent (PIPA §28-8, 2024-09 시행) —
 *      미국·프랑스 소재 8개 사업자 (처리방침 §6 이 SoT) 이전 동의
 *
 * Optional marketing consent is offered but not required.
 *
 * H3 fix (2026-05-09 release-prep audit): cross_border was missing from
 * the OAuth-direct-entry path even though the /signup page collected it.
 * Users entering via Kakao/Google directly bypassed the §28-8 obligation
 * — added here so every entry path captures all four required consents.
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
  cross_border: boolean;
  marketing: boolean;
}

export function hasLocalConsent(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const raw = window.localStorage.getItem(CONSENT_STORAGE_KEY);
    if (!raw) return false;
    const parsed = JSON.parse(raw) as Partial<Consents>;
    return Boolean(
      parsed.terms && parsed.non_advisory && parsed.age && parsed.cross_border,
    );
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
      className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-[2px] border transition-all duration-200 ${
        checked
          ? "border-[var(--pq-bronze)] bg-[var(--pq-bronze)]"
          : "border-[rgba(245,240,232,0.3)] bg-transparent hover:border-[var(--pq-bronze-light)]"
      }`}
    >
      {checked && (
        <svg
          width="10"
          height="10"
          viewBox="0 0 12 12"
          fill="none"
          stroke="var(--pq-ink)"
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
    cross_border: false,
    marketing: false,
  });

  // PIPA §22 ⑥ — 만 14세 이상 자가선언 (2026-09-19: 생년월일 미수집).
  const allRequired =
    consents.terms &&
    consents.non_advisory &&
    consents.age &&
    consents.cross_border;

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
      <div
        className="w-full max-w-md p-6"
        style={{
          backgroundColor: "var(--pq-ink)",
          color: "var(--pq-ivory)",
          border: "1px solid var(--pq-border)",
          borderRadius: "var(--pq-radius-card)",
          boxShadow: "0 24px 56px rgba(0,0,0,0.6)",
        }}
      >
        <h2
          className="text-lg font-bold font-display"
          style={{
            color: "var(--pq-ivory)",
            letterSpacing: "var(--pq-track-tight)",
          }}
        >
          가입 전 확인
        </h2>
        <p
          className="mt-1 text-xs"
          style={{ color: "rgba(var(--pq-ivory-rgb), 0.6)" }}
        >
          계속하려면 아래 필수 항목에 동의해 주세요.
        </p>

        <div
          className="mt-5 space-y-3 p-4"
          style={{
            border: "1px solid var(--pq-border)",
            backgroundColor: "rgba(var(--pq-ivory-rgb), 0.03)",
            borderRadius: "var(--pq-radius-card)",
          }}
        >
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
            <span
              className="text-xs leading-relaxed"
              style={{ color: "rgba(var(--pq-ivory-rgb), 0.78)" }}
            >
              <strong style={{ color: "var(--pq-bronze)" }}>[필수]</strong>{" "}
              <Link
                href="/terms"
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
                style={{ color: "var(--pq-ivory)" }}
                onClick={(e) => e.stopPropagation()}
              >
                이용약관
              </Link>{" "}
              및{" "}
              <Link
                href="/privacy"
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
                style={{ color: "var(--pq-ivory)" }}
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
            <span
              className="text-xs leading-relaxed"
              style={{ color: "rgba(var(--pq-ivory-rgb), 0.78)" }}
            >
              <strong style={{ color: "var(--pq-bronze)" }}>[필수]</strong> PivoxQuant는
              자본시장법상 투자자문업이 아니며, 본 서비스의 모든 분석·리포트·시그널은
              정보 제공 목적임을 이해합니다.
            </span>
          </label>

          {/* 3. 14세 이상 자가선언 (PIPA §22 ⑥) — 일반 필수 체크박스 */}
          <label
            htmlFor="consent_age"
            className="flex cursor-pointer items-start gap-2"
          >
            <Checkbox
              id="consent_age"
              checked={consents.age}
              onChange={setConsent("age")}
            />
            <span
              className="text-xs leading-relaxed"
              style={{ color: "rgba(var(--pq-ivory-rgb), 0.78)" }}
            >
              <strong style={{ color: "var(--pq-bronze)" }}>[필수]</strong> 만 14세 이상임을 확인합니다.
              (개인정보보호법 §22 ⑥)
            </span>
          </label>

          {/* 4. 국외 이전 동의 (PIPA §28-8) */}
          <label
            htmlFor="consent_cross_border"
            className="flex cursor-pointer items-start gap-2"
          >
            <Checkbox
              id="consent_cross_border"
              checked={consents.cross_border}
              onChange={setConsent("cross_border")}
            />
            <span
              className="text-xs leading-relaxed"
              style={{ color: "rgba(var(--pq-ivory-rgb), 0.78)" }}
            >
              <strong style={{ color: "var(--pq-bronze)" }}>[필수]</strong> 개인정보의
              국외 이전(미국·프랑스 소재 8개 사업자 — 상세는{" "}
              <Link
                href="/privacy"
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
                style={{ color: "var(--pq-ivory)" }}
                onClick={(e) => e.stopPropagation()}
              >
                개인정보처리방침 §6
              </Link>
              )에 동의합니다. (개인정보보호법 §28-8)
            </span>
          </label>

          {/* 5. 마케팅 (선택) */}
          <label
            htmlFor="consent_marketing"
            className="flex cursor-pointer items-start gap-2"
          >
            <Checkbox
              id="consent_marketing"
              checked={consents.marketing}
              onChange={setConsent("marketing")}
            />
            <span
              className="text-xs leading-relaxed"
              style={{ color: "rgba(var(--pq-ivory-rgb), 0.78)" }}
            >
              <span style={{ color: "rgba(var(--pq-ivory-rgb), 0.5)" }}>[선택]</span> 마케팅 정보 수신에
              동의합니다.
            </span>
          </label>
        </div>

        <button
          type="button"
          disabled={!allRequired}
          onClick={handleSubmit}
          className="mt-5 w-full px-4 py-3 text-sm font-semibold transition-all"
          style={{
            borderRadius: "var(--pq-radius-cta)",
            backgroundColor: allRequired ? "var(--pq-bronze)" : "rgba(var(--pq-ivory-rgb), 0.06)",
            color: allRequired ? "var(--pq-ink)" : "rgba(var(--pq-ivory-rgb), 0.35)",
            cursor: allRequired ? "pointer" : "not-allowed",
            border: allRequired ? "none" : "1px solid var(--pq-border)",
          }}
        >
          동의하고 계속하기
        </button>

        {!allRequired && (
          <p
            className="mt-2 text-center text-pq-mono-sm"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.4)" }}
          >
            {/* 2026-05-15 (bug-hunter Wave 7 HIGH #3): hint text was
                "필수 항목 3개" but actual required checkboxes are 4
                (이용약관 + 투자자문업 아님 + 만 14세 + 개인정보 국외
                이전). The `allRequired` check already
                counted 4 fields + the file's own header comment §8
                names "four required agreements" — only this hint
                string was stale. Stale agreement count is a PIPA /
                약관규제법 surface-accuracy issue (consent must be
                informed). */}
            필수 항목 4개에 모두 동의해야 진행할 수 있습니다.
          </p>
        )}
      </div>
    </ModalShell>
  );
}
