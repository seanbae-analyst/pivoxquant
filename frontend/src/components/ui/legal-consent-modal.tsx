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
 *   3. Age confirmation — 14+ (PIPA §22)
 *   4. Cross-border data transfer consent (PIPA §28-8, 2024-09 시행) —
 *      Anthropic/Stripe/Vercel/Railway US 이전 동의
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

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { ModalShell } from "@/components/ui/modal-shell";
import {
  isValidBirthdate,
  isAtLeastMinAge,
  computeAgeYears,
  UNDER_AGE_KO,
  UNDER_AGE_EN,
  BIRTHDATE_LABEL_KO,
  BIRTHDATE_LABEL_EN,
} from "@/lib/age-verification";

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
  const [birthdate, setBirthdate] = useState("");

  const ageCheck = useMemo(() => {
    const valid = isValidBirthdate(birthdate);
    return {
      valid,
      eligible: valid && isAtLeastMinAge(birthdate),
      years: valid ? computeAgeYears(birthdate) : -1,
    };
  }, [birthdate]);

  // SHIP-BLOCKER fix 2026-05-11: DOB ≥14 자동으로 agree_age=true 도출.
  // 사용자가 별도 클릭 안 해도 진행 가능 (E2E user-tester P0 회귀). DOB
  // invalid/<14 이면 agree_age=false 로 초기화하여 fail-fast 유지.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setConsents((prev) =>
      prev.age === ageCheck.eligible
        ? prev
        : { ...prev, age: ageCheck.eligible },
    );
  }, [ageCheck.eligible]);

  // PIPA §22 ⑥ — 만 14세 미만은 fail-fast. 자가선언 + 생년월일 이중 검증.
  const ageOk = consents.age && ageCheck.eligible;

  const allRequired =
    consents.terms &&
    consents.non_advisory &&
    ageOk &&
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
          // PIPA §22 ⑥ — 만나이 검증 흔적. 백엔드 promote 시 별도 저장 가능.
          birthdate,
          age_years: ageCheck.years,
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

          {/* 3. 14세 이상 (PIPA §22 ⑥) — 생년월일 + 자가선언 이중 방어선 */}
          <div className="flex flex-col gap-2">
            <label
              htmlFor="consent_birthdate"
              className="flex flex-col gap-1"
            >
              <span
                className="text-pq-mono-sm uppercase tracking-[0.18em]"
                style={{ color: "var(--pq-bronze)" }}
              >
                {BIRTHDATE_LABEL_KO} · {BIRTHDATE_LABEL_EN}
              </span>
              <input
                id="consent_birthdate"
                type="date"
                value={birthdate}
                max={new Date().toISOString().slice(0, 10)}
                onChange={(e) => setBirthdate(e.target.value)}
                aria-invalid={birthdate !== "" && !ageCheck.eligible}
                aria-describedby="consent_birthdate_msg"
                className="rounded-[2px] border bg-transparent px-2 py-1.5 text-xs"
                style={{
                  borderColor: ageCheck.eligible
                    ? "var(--pq-ivory-line)"
                    : birthdate
                      ? "rgba(244,108,108,0.6)"
                      : "var(--pq-ivory-line)",
                  color: "rgba(var(--pq-ivory-rgb), 0.85)",
                  colorScheme: "dark",
                }}
              />
              {birthdate && !ageCheck.eligible && (
                <span
                  id="consent_birthdate_msg"
                  role="alert"
                  className="text-pq-mono-sm leading-relaxed"
                  style={{ color: "rgba(244,108,108,0.92)" }}
                >
                  {UNDER_AGE_KO}
                  <br />
                  <span style={{ opacity: 0.75 }}>{UNDER_AGE_EN}</span>
                </span>
              )}
            </label>

            <label
              htmlFor="consent_age"
              className="flex cursor-pointer items-start gap-2"
              style={{
                opacity: ageCheck.eligible ? 1 : 0.5,
                pointerEvents: ageCheck.eligible ? "auto" : "none",
              }}
            >
              <Checkbox
                id="consent_age"
                checked={consents.age && ageCheck.eligible}
                onChange={(next) => {
                  if (!ageCheck.eligible) return;
                  setConsent("age")(next);
                }}
              />
              <span
                className="text-xs leading-relaxed"
                style={{ color: "rgba(var(--pq-ivory-rgb), 0.78)" }}
              >
                <strong style={{ color: "var(--pq-bronze)" }}>[필수]</strong> 만 14세 이상임을 확인합니다.
                (개인정보보호법 §22 ⑥)
              </span>
            </label>
          </div>

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
              국외 이전(미국 — Anthropic, Stripe, Vercel, Railway)에
              동의합니다. (개인정보보호법 §28-8)
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
            필수 항목 3개에 모두 동의해야 진행할 수 있습니다.
          </p>
        )}
      </div>
    </ModalShell>
  );
}
