"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { API } from "@/lib/endpoints";
import {
  isValidBirthdate,
  isAtLeastMinAge,
  computeAgeYears,
  UNDER_AGE_KO,
  UNDER_AGE_EN,
  BIRTHDATE_LABEL_KO,
  BIRTHDATE_LABEL_EN,
} from "@/lib/age-verification";

function GoogleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18A11.96 11.96 0 0 0 1 12c0 1.94.46 3.77 1.18 5.07l3.66-2.98z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  );
}

function KakaoIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 3C6.48 3 2 6.58 2 10.94c0 2.8 1.86 5.27 4.66 6.67-.15.53-.96 3.41-.99 3.63 0 0-.02.16.08.22.1.06.23.01.23.01.3-.04 3.5-2.3 4.05-2.67.62.09 1.27.14 1.97.14 5.52 0 10-3.58 10-7.94S17.52 3 12 3z"
        fill="#191919"
      />
    </svg>
  );
}

/* ── Legal consent state keys ──
 *
 * Stored briefly in localStorage before OAuth redirect, so that when the
 * OAuth callback returns to /onboarding we can mark the user's consent
 * on first login. Backend persistence is a separate task; this UI
 * enforces the legal contract client-side per §17 금소법 적합성 +
 * 전자상거래법 §17 + PIPA §22 age confirmation.
 */
const CONSENT_STORAGE_KEY = "pivox_signup_consents";

interface Consents {
  terms: boolean;
  non_advisory: boolean;
  age: boolean;
  // PIPA §28-8 (개인정보 국외 이전 별도 동의). 모든 위탁처(Anthropic /
  // Stripe / Vercel / Railway / Google) 가 미국 소재이므로 모든 사용자에게
  // 적용 — 필수 체크 항목.
  cross_border: boolean;
  // 정통망법 §50 marketing — 선택.
  marketing: boolean;
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
          ? "border-[var(--pq-bronze)] bg-[var(--pq-bronze)]"
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

export default function SignupPageV1() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [consents, setConsents] = useState<Consents>({
    terms: false,
    non_advisory: false,
    age: false,
    cross_border: false,
    marketing: false,
  });
  const [birthdate, setBirthdate] = useState("");
  const [allRequired, setAllRequired] = useState(false);
  const [pulseUnchecked, setPulseUnchecked] = useState(false);

  // PIPA §22 ⑥ — 만 14세 미만 fail-fast.
  const ageCheck = useMemo(() => {
    const valid = isValidBirthdate(birthdate);
    return {
      valid,
      eligible: valid && isAtLeastMinAge(birthdate),
      years: valid ? computeAgeYears(birthdate) : -1,
    };
  }, [birthdate]);

  // SHIP-BLOCKER fix 2026-05-11: DOB ≥14 자동으로 agree_age=true 도출.
  // 사용자가 별도 클릭 안 해도 회원가입 funnel 진행 가능 (E2E user-tester
  // P0 회귀). DOB invalid/<14 이면 agree_age=false 로 초기화하여 fail-fast
  // 유지. 사용자는 여전히 수동 토글 가능 (eligible 일 때 label clickable).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setConsents((prev) =>
      prev.age === ageCheck.eligible
        ? prev
        : { ...prev, age: ageCheck.eligible },
    );
  }, [ageCheck.eligible]);

  useEffect(() => {
    // Preserved verbatim from v1 behavior — derived-value refactor is out of
    // scope for the visual-only v2 task per CEO directive.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAllRequired(
      consents.terms
      && consents.non_advisory
      && consents.age
      && ageCheck.eligible
      && consents.cross_border,
    );
  }, [consents, ageCheck.eligible]);

  // Auto-clear the pulse highlight a moment after it fires.
  useEffect(() => {
    if (!pulseUnchecked) return;
    const t = setTimeout(() => setPulseUnchecked(false), 900);
    return () => clearTimeout(t);
  }, [pulseUnchecked]);

  const handleDisabledClick = (e: React.MouseEvent) => {
    e.preventDefault();
    setPulseUnchecked(true);
  };

  useEffect(() => {
    if (!loading && user) {
      router.replace("/home");
    }
  }, [user, loading, router]);

  if (loading) {
    // Page-load skeleton — matches the v1 slate light surface.
    return (
      <div
        className="flex flex-col items-center gap-3 py-16 w-full"
        role="status"
        aria-live="polite"
        aria-label="Loading signup"
      >
        <div className="skeleton h-12 w-12 rounded-xl" />
        <div className="skeleton h-5 w-32 rounded" />
        <div className="skeleton h-3 w-24 rounded" />
        <div className="skeleton mt-4 h-11 w-full max-w-sm rounded-xl" />
        <div className="skeleton h-11 w-full max-w-sm rounded-xl" />
        <span className="sr-only">Loading…</span>
      </div>
    );
  }

  if (user) return null;

  const setConsent = (key: keyof Consents) => (next: boolean) => {
    setConsents((prev) => ({ ...prev, [key]: next }));
  };

  const handleOAuthClick = (url: string) => (e: React.MouseEvent) => {
    if (!allRequired) {
      e.preventDefault();
      return;
    }
    // Persist consent snapshot for OAuth callback handler.
    try {
      window.localStorage.setItem(
        CONSENT_STORAGE_KEY,
        JSON.stringify({
          ...consents,
          // PIPA §22 ⑥ — 만나이 검증 흔적.
          birthdate,
          age_years: ageCheck.years,
          consented_at: new Date().toISOString(),
        }),
      );
    } catch {
      // non-fatal
    }
    window.location.href = url;
  };

  return (
    <div className="flex flex-col items-center">
      {/* Logo */}
      <div className="mb-8 flex flex-col items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-950 border border-accent shadow-lg shadow-accent/20">
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="white"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
            <polyline points="16 7 22 7 22 13" />
          </svg>
        </div>
        <span className="text-lg font-semibold text-slate-900">PivoxQuant</span>
      </div>

      {/* Heading */}
      <h1 className="text-center text-2xl font-bold tracking-tight text-slate-900">
        계정 만들기
      </h1>
      <p className="mt-2 text-center text-sm text-slate-500">
        40개 퀀트 모델을 무료로 시작하세요
      </p>

      {/* Legal consent checkboxes (required before OAuth) */}
      <div className="mt-8 w-full space-y-3 rounded-xl border border-slate-200 bg-slate-50/60 p-4">
        <p className="text-xs font-semibold text-slate-700">가입 전 확인</p>

        {/* 1. 이용약관 + 개인정보처리방침 */}
        <label
          htmlFor="agree_terms"
          className={`flex cursor-pointer items-start gap-2 rounded-md transition-all ${pulseUnchecked && !consents.terms ? "ring-2 ring-rose-400/70 ring-offset-2 ring-offset-slate-50 motion-safe:animate-pulse" : ""}`}
        >
          <Checkbox
            id="agree_terms"
            checked={consents.terms}
            onChange={setConsent("terms")}
          />
          <span className="text-xs leading-relaxed text-slate-600">
            <strong className="text-slate-900">[필수]</strong>{" "}
            <Link
              href="/terms"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-slate-900"
              onClick={(e) => e.stopPropagation()}
            >
              이용약관
            </Link>{" "}
            및{" "}
            <Link
              href="/privacy"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-slate-900"
              onClick={(e) => e.stopPropagation()}
            >
              개인정보처리방침
            </Link>
            에 동의합니다.
          </span>
        </label>

        {/* 2. 투자자문업 아님 고지 (자본시장법) */}
        <label
          htmlFor="agree_non_advisory"
          className={`flex cursor-pointer items-start gap-2 rounded-md transition-all ${pulseUnchecked && !consents.non_advisory ? "ring-2 ring-rose-400/70 ring-offset-2 ring-offset-slate-50 motion-safe:animate-pulse" : ""}`}
        >
          <Checkbox
            id="agree_non_advisory"
            checked={consents.non_advisory}
            onChange={setConsent("non_advisory")}
          />
          <span className="text-xs leading-relaxed text-slate-600">
            <strong className="text-slate-900">[필수]</strong> PivoxQuant는 자본시장법상
            투자자문업이 아니며, 본 서비스의 모든 분석·리포트·시그널은 정보 제공 목적임을
            이해합니다. 투자 판단과 그 결과는 이용자 본인의 책임입니다.
          </span>
        </label>

        {/* 3. 만 14세 이상 (PIPA §22 ⑥) — 생년월일 + 자가선언 이중 방어선 */}
        <div className="flex flex-col gap-2">
          <label htmlFor="agree_birthdate" className="flex flex-col gap-1">
            <span className="text-pq-mono-sm font-semibold text-slate-700">
              {BIRTHDATE_LABEL_KO} · {BIRTHDATE_LABEL_EN}
            </span>
            <input
              id="agree_birthdate"
              type="date"
              value={birthdate}
              max={new Date().toISOString().slice(0, 10)}
              onChange={(e) => setBirthdate(e.target.value)}
              aria-invalid={birthdate !== "" && !ageCheck.eligible}
              aria-describedby="agree_birthdate_msg"
              style={{ colorScheme: "light" }}
              className={`rounded-md border bg-white px-2.5 py-1.5 text-base text-slate-900 ${
                birthdate && !ageCheck.eligible
                  ? "border-rose-400"
                  : "border-slate-300"
              }`}
            />
            {birthdate && !ageCheck.eligible && (
              <span
                id="agree_birthdate_msg"
                role="alert"
                className="text-pq-mono-sm leading-relaxed text-rose-600"
              >
                {UNDER_AGE_KO}
                <br />
                <span className="opacity-70">{UNDER_AGE_EN}</span>
              </span>
            )}
          </label>

          <label
            htmlFor="agree_age"
            className={`flex cursor-pointer items-start gap-2 rounded-md transition-all ${
              pulseUnchecked && !consents.age
                ? "ring-2 ring-rose-400/70 ring-offset-2 ring-offset-slate-50 motion-safe:animate-pulse"
                : ""
            } ${ageCheck.eligible ? "" : "opacity-50 pointer-events-none"}`}
          >
            <Checkbox
              id="agree_age"
              checked={consents.age && ageCheck.eligible}
              onChange={(next) => {
                if (!ageCheck.eligible) return;
                setConsent("age")(next);
              }}
            />
            <span className="text-xs leading-relaxed text-slate-600">
              <strong className="text-slate-900">[필수]</strong> 만 14세
              이상임을 확인합니다. (개인정보보호법 §22 ⑥)
            </span>
          </label>
        </div>

        {/* 4. 개인정보 국외 이전 (PIPA §28-8) */}
        <label
          htmlFor="agree_cross_border"
          className={`flex cursor-pointer items-start gap-2 rounded-md transition-all ${pulseUnchecked && !consents.cross_border ? "ring-2 ring-rose-400/70 ring-offset-2 ring-offset-slate-50 motion-safe:animate-pulse" : ""}`}
        >
          <Checkbox
            id="agree_cross_border"
            checked={consents.cross_border}
            onChange={setConsent("cross_border")}
          />
          <span className="text-xs leading-relaxed text-slate-600">
            <strong className="text-slate-900">[필수]</strong> 개인정보의 국외
            이전에 동의합니다. (PIPA §28-8 — Anthropic / Stripe / Vercel /
            Railway / Google, 미국 소재 위탁처){" "}
            <a
              href="/privacy#cross-border"
              target="_blank"
              rel="noopener"
              className="text-[var(--pq-bronze)] underline"
            >
              보기
            </a>
          </span>
        </label>

        {/* 5. 마케팅 수신 (선택) */}
        <label
          htmlFor="agree_marketing"
          className="flex cursor-pointer items-start gap-2"
        >
          <Checkbox
            id="agree_marketing"
            checked={consents.marketing}
            onChange={setConsent("marketing")}
          />
          <span className="text-xs leading-relaxed text-slate-600">
            <span className="text-slate-500">[선택]</span> 마케팅 정보(이벤트, 신기능
            안내) 수신에 동의합니다.
          </span>
        </label>
      </div>

      {/* OAuth Buttons */}
      <div className="mt-6 flex w-full flex-col gap-3">
        {allRequired ? (
          <a
            href={API.auth.google}
            onClick={handleOAuthClick(API.auth.google)}
            className="flex w-full items-center justify-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700 transition-all duration-200 hover:border-slate-300 hover:bg-slate-50 hover:shadow-sm active:scale-[0.98]"
          >
            <GoogleIcon />
            Google로 계속하기
          </a>
        ) : (
          <button
            type="button"
            aria-disabled="true"
            onClick={handleDisabledClick}
            className="flex w-full cursor-not-allowed items-center justify-center gap-3 rounded-xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm font-medium text-slate-400"
          >
            <GoogleIcon />
            Google로 계속하기
          </button>
        )}

        {allRequired ? (
          <a
            href={API.auth.kakao}
            onClick={handleOAuthClick(API.auth.kakao)}
            className="flex w-full items-center justify-center gap-3 rounded-xl border border-[#FEE500]/20 bg-[#FEE500] px-4 py-3 text-sm font-medium text-[#191919] transition-all duration-200 hover:bg-[#FFEB3B] hover:shadow-sm active:scale-[0.98]"
          >
            <KakaoIcon />
            카카오로 계속하기
          </a>
        ) : (
          <button
            type="button"
            aria-disabled="true"
            onClick={handleDisabledClick}
            className="flex w-full cursor-not-allowed items-center justify-center gap-3 rounded-xl border border-[#FEE500]/20 bg-[#FEE500]/50 px-4 py-3 text-sm font-medium text-[#191919]/40"
          >
            <KakaoIcon />
            카카오로 계속하기
          </button>
        )}
      </div>

      {!allRequired && (
        <p
          className={`mt-3 text-center text-pq-caption ${pulseUnchecked ? "text-rose-500 font-medium" : "text-slate-500"}`}
          role={pulseUnchecked ? "alert" : undefined}
        >
          필수 항목 4개에 모두 동의해야 가입할 수 있습니다.
        </p>
      )}

      {/* Divider */}
      <div className="my-6 flex w-full items-center gap-3">
        <div className="h-px flex-1 bg-slate-200" />
        <span className="text-xs text-slate-400">또는</span>
        <div className="h-px flex-1 bg-slate-200" />
      </div>

      {/* Switch to login */}
      <p className="text-center text-sm text-slate-500">
        이미 계정이 있으신가요?{" "}
        <Link
          href="/login"
          className="font-medium text-[var(--pq-bronze)] hover:text-[var(--pq-bronze-light)] transition-colors"
        >
          로그인
        </Link>
      </p>

      {/* Beta badge */}
      <p className="mt-6 text-center text-xs text-slate-400">
        베타 기간 무료 &middot; 카드 등록 불필요
      </p>
    </div>
  );
}
