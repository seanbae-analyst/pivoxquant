"use client";

/**
 * ConsentStackV2 — 법정 필수 동의 스택 (4 필수 + 1 선택).
 *
 * Why this component exists
 * -------------------------
 * `/login` 과 `/signup` 은 같은 `API.auth.google` / `API.auth.kakao` 로 간다.
 * 백엔드 콜백(`routes/auth.py` `_provision_google` / `_provision_kakao`)은
 * 계정이 없으면 **어느 화면에서 왔든** User 를 만든다. 즉 신규 사용자가
 * "로그인" 버튼으로 들어오면 동의를 한 번도 보지 않고 계정이 생겼다.
 * 그래서 동의 수집 지점을 OAuth **이전**(signup 화면)에서 OAuth **이후**
 * 인터스티셜(`/signup/oauth-finalize`, `user.birthdate_required === true`
 * 일 때만 렌더)로 옮겼다. 이 컴포넌트가 그 스택이다.
 *
 * 마크업 출처
 * -----------
 * `frontend/src/app/(auth)/signup/page.tsx` 의 `CheckboxV2` + 동의 행을
 * 디자인·문구·a11y 속성 그대로 옮겨왔다. signup 페이지를 import 하지 않는다
 * (그 파일은 독립적으로 교체 중이며, 여기가 동의 UI 의 새 SoT 다).
 *
 * ⚠️ 증거 강도 한계 (현행 유지)
 * -----------------------------
 * 5종 중 서버에 기록되는 것은 2종뿐이다.
 *   - `cross_border` → POST /api/consents/cross-border (PIPA §28-8,
 *     `routes/consents.py`, 타임스탬프 컬럼 `cross_border_consent_at`)
 *   - `marketing`    → POST /api/consents/marketing (정통망법 §50 ①,
 *     `marketing_consent_at`)
 * 나머지 `terms` / `non_advisory` / `age` 는 **대응하는 서버 컬럼이 없다**.
 * 기존과 동일하게 localStorage `pivox_signup_consents` 스냅숏에만 남으므로
 * 브라우저 저장소가 지워지면 증거도 사라진다. (`age` 는 생년월일이
 * `/api/auth/oauth-finalize` 로 서버에 저장되므로 간접 증거는 남는다.)
 * 이 한계는 의도적인 현행 유지이며, 서버 컬럼 추가는 별도 백엔드 작업이다.
 *
 * 문구
 * ----
 * 새 i18n 키를 만들지 않는다(`messages/ko.json` · `en.json` 은 다른 작업에서
 * 수정 중). `useLocale()` 로 컴포넌트 안에서 ko / en 분기한다 — signup 의
 * 한국어 문안을 ko 쪽에 1:1 로 보존했다.
 *
 * 디자인: v3 Vantablack + Bronze 락-인. 기울임 금지, `--pq-*` 토큰만.
 */

import { useEffect } from "react";
import Link from "next/link";

import { useLocale } from "@/lib/locale";

/** 동의 항목 5종 — signup/page.tsx 의 `Consents` 와 키가 동일하다. */
export interface ConsentState {
  /** [필수] 이용약관 + 개인정보처리방침 */
  terms: boolean;
  /** [필수] 자본시장법상 투자자문업 아님 고지 확인 */
  non_advisory: boolean;
  /** [필수] 만 14세 이상 (PIPA §22 ⑥) — 생년월일에서 자동 도출 */
  age: boolean;
  /** [필수] 개인정보 국외 이전 (PIPA §28-8) */
  cross_border: boolean;
  /** [선택] 마케팅 정보 수신 (정통망법 §50 ①) */
  marketing: boolean;
}

export type ConsentKey = keyof ConsentState;

/** 필수 4종 — 제출 게이트가 이 키들만 본다. */
export const REQUIRED_CONSENT_KEYS = [
  "terms",
  "non_advisory",
  "age",
  "cross_border",
] as const satisfies readonly ConsentKey[];

export const EMPTY_CONSENTS: ConsentState = {
  terms: false,
  non_advisory: false,
  age: false,
  cross_border: false,
  marketing: false,
};

/**
 * 필수 4종 전부 true 인지. 호출부(인터스티셜)는 여기에 더해
 * `ageCheck.eligible` 을 AND 로 묶어 제출 버튼을 활성화한다.
 */
export function allRequiredConsented(consents: ConsentState): boolean {
  return REQUIRED_CONSENT_KEYS.every((key) => consents[key]);
}

/* ── styles (signup/page.tsx 에서 그대로) ─────────────────────────────── */

const consentLabelStyle: React.CSSProperties = {
  fontSize: "var(--pq-text-body)",
  lineHeight: 1.55,
  color: "var(--pq-ivory-muted)",
};

const consentRowStyle: React.CSSProperties = {
  // a11y P2 2026-05-03: vertical padding 14px expands hit area to >=44px
  // (16px box + 28px padding). Negative margin preserves visual layout.
  display: "flex",
  alignItems: "flex-start",
  gap: 12,
  cursor: "pointer",
  padding: "14px 4px",
  margin: "-14px -4px",
  borderRadius: 4,
  transition: "box-shadow 200ms cubic-bezier(0.16,1,0.3,1)",
};

const pulseRowStyle = (active: boolean): React.CSSProperties =>
  active
    ? {
        boxShadow: "0 0 0 1.5px rgba(244,108,108,0.85)",
        background: "rgba(244,108,108,0.06)",
      }
    : {};

const requiredTagStyle: React.CSSProperties = {
  fontSize: "var(--pq-text-eyebrow)",
  letterSpacing: "0.18em",
  textTransform: "uppercase",
  color: "var(--pq-bronze, #B8956A)",
  marginRight: 6,
};

const optionalTagStyle: React.CSSProperties = {
  ...requiredTagStyle,
  color: "var(--pq-ivory-dim)",
};

const linkStyle: React.CSSProperties = {
  color: "var(--pq-ivory, #F5F0E8)",
  textDecoration: "underline",
  textUnderlineOffset: 2,
};

/* ── copy (locale 분기 — 새 i18n 키를 만들지 않는다) ──────────────────── */

const COPY = {
  ko: {
    heading: "가입 전 확인",
    requiredTag: "[필수]",
    optionalTag: "[선택]",
    termsBefore: "",
    terms: "이용약관",
    termsMiddle: " 및 ",
    privacy: "개인정보처리방침",
    termsAfter: "에 동의합니다.",
    nonAdvisory:
      "PivoxQuant는 자본시장법상 투자자문업이 아니며, 본 서비스의 모든 분석·리포트·시그널은 정보 제공 목적임을 이해합니다. 투자 판단과 그 결과는 이용자 본인의 책임입니다.",
    age: "만 14세 이상임을 확인합니다. (개인정보보호법 §22 ⑥)",
    crossBorder:
      "개인정보의 국외 이전에 동의합니다. (PIPA §28-8 — Supabase(데이터는 서울 리전 보관) / Render / Vercel / Google / SendGrid 외 8개 위탁처, 상세 목록과 각 위탁처의 이전 항목은 개인정보처리방침 참조)",
    crossBorderLink: "보기",
    marketing: "마케팅 정보(이벤트, 신기능 안내) 수신에 동의합니다.",
  },
  en: {
    heading: "Before you continue",
    requiredTag: "[Required]",
    optionalTag: "[Optional]",
    termsBefore: "I agree to the ",
    terms: "Terms of Service",
    termsMiddle: " and the ",
    privacy: "Privacy Policy",
    termsAfter: ".",
    nonAdvisory:
      "I understand that PivoxQuant is not a licensed investment advisory business under the Financial Investment Services and Capital Markets Act, and that every analysis, report and signal is provided for informational purposes only. Investment decisions and their outcomes remain my own responsibility.",
    age: "I confirm that I am 14 years of age or older. (PIPA Article 22 ⑥)",
    crossBorder:
      "I consent to the cross-border transfer of my personal data. (PIPA Article 28-8 — Supabase (data stored in the Seoul region) / Render / Vercel / Google / SendGrid and 8 processors in total; the full list and the items transferred to each are in the Privacy Policy.)",
    crossBorderLink: "View",
    marketing:
      "I agree to receive marketing messages (events, new feature announcements).",
  },
} as const;

/* ── checkbox (signup/page.tsx CheckboxV2 그대로) ─────────────────────── */

/** Bronze-tinted ink checkbox — visual only. */
function CheckboxV2({
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
      style={{
        marginTop: 2,
        flexShrink: 0,
        display: "flex",
        height: 16,
        width: 16,
        alignItems: "center",
        justifyContent: "center",
        borderRadius: 2,
        border: checked
          ? "1px solid var(--pq-bronze, #B8956A)"
          : "1px solid rgba(245,240,232,0.20)",
        background: checked ? "var(--pq-bronze, #B8956A)" : "transparent",
        transition:
          "background-color 200ms cubic-bezier(0.16,1,0.3,1), border-color 200ms",
        cursor: "pointer",
      }}
    >
      {checked && (
        <svg
          width="10"
          height="10"
          viewBox="0 0 12 12"
          fill="none"
          stroke="var(--pq-ink, #050505)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="2 6 5 9 10 3" />
        </svg>
      )}
    </button>
  );
}

/* ── stack ────────────────────────────────────────────────────────────── */

export interface ConsentStackV2Props {
  /** 현재 동의 상태 (호출부가 소유). */
  consents: ConsentState;
  /** 한 항목 토글. */
  onChange: (key: ConsentKey, next: boolean) => void;
  /**
   * 생년월일이 만 14세 이상인지. `age` 행은 이 값이 false 면 비활성이고,
   * true 로 바뀌면 `age` 가 자동으로 true 가 된다(아래 useEffect).
   */
  ageEligible: boolean;
  /** 미체크 항목을 한 번 붉게 강조 (호출부가 타이머로 해제). */
  pulseUnchecked?: boolean;
  /** 제목 행 숨김 — 호스트 페이지가 이미 제목을 가진 경우. */
  showHeading?: boolean;
}

export function ConsentStackV2({
  consents,
  onChange,
  ageEligible,
  pulseUnchecked = false,
  showHeading = true,
}: ConsentStackV2Props) {
  const { locale } = useLocale();
  const c = COPY[locale === "en" ? "en" : "ko"];

  // SHIP-BLOCKER fix 2026-05-11 (signup/page.tsx 에서 이관): DOB ≥14 이면
  // agree_age=true 를 자동 도출한다. 사용자가 따로 클릭하지 않아도 퍼널이
  // 진행되고, DOB 가 invalid/<14 로 바뀌면 다시 false 로 초기화되어
  // fail-fast 가 유지된다. eligible 일 때는 여전히 수동 토글 가능.
  useEffect(() => {
    if (consents.age !== ageEligible) {
      onChange("age", ageEligible);
    }
  }, [ageEligible, consents.age, onChange]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {showHeading && (
        <h2
          className="font-display"
          style={{
            fontWeight: 500,
            fontSize: "var(--pq-text-quote)",
            lineHeight: 1.2,
            letterSpacing: "-0.01em",
            color: "var(--pq-ivory, #F5F0E8)",
            margin: 0,
          }}
        >
          {c.heading}
        </h2>
      )}

      {/* Consent block — Vantablack ink, Bronze hairlines */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 14,
          padding: 20,
          borderRadius: 2,
          border: "0.5px solid var(--pq-ivory-line)",
          background: "var(--pq-ivory-line-ghost)",
        }}
      >
        <label
          htmlFor="agree_terms"
          style={{
            ...consentRowStyle,
            ...pulseRowStyle(pulseUnchecked && !consents.terms),
          }}
        >
          <CheckboxV2
            id="agree_terms"
            checked={consents.terms}
            onChange={(next) => onChange("terms", next)}
          />
          <span className="font-serif" style={consentLabelStyle}>
            <span className="font-mono" style={requiredTagStyle}>
              {c.requiredTag}
            </span>
            {c.termsBefore}
            <Link
              href="/terms"
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              style={linkStyle}
            >
              {c.terms}
            </Link>
            {c.termsMiddle}
            <Link
              href="/privacy"
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              style={linkStyle}
            >
              {c.privacy}
            </Link>
            {c.termsAfter}
          </span>
        </label>

        <label
          htmlFor="agree_non_advisory"
          style={{
            ...consentRowStyle,
            ...pulseRowStyle(pulseUnchecked && !consents.non_advisory),
          }}
        >
          <CheckboxV2
            id="agree_non_advisory"
            checked={consents.non_advisory}
            onChange={(next) => onChange("non_advisory", next)}
          />
          <span className="font-serif" style={consentLabelStyle}>
            <span className="font-mono" style={requiredTagStyle}>
              {c.requiredTag}
            </span>
            {c.nonAdvisory}
          </span>
        </label>

        {/* PIPA §22 ⑥ — 생년월일 입력은 호스트 페이지가 소유하고, 여기서는
            그 결과(ageEligible)에서 도출된 자가선언 행만 렌더한다. */}
        <label
          htmlFor="agree_age"
          style={{
            ...consentRowStyle,
            ...pulseRowStyle(pulseUnchecked && !consents.age),
            opacity: ageEligible ? 1 : 0.5,
            pointerEvents: ageEligible ? "auto" : "none",
          }}
        >
          <CheckboxV2
            id="agree_age"
            checked={consents.age && ageEligible}
            onChange={(next) => {
              if (!ageEligible) return;
              onChange("age", next);
            }}
          />
          <span className="font-serif" style={consentLabelStyle}>
            <span className="font-mono" style={requiredTagStyle}>
              {c.requiredTag}
            </span>
            {c.age}
          </span>
        </label>

        <label
          htmlFor="agree_cross_border"
          style={{
            ...consentRowStyle,
            ...pulseRowStyle(pulseUnchecked && !consents.cross_border),
          }}
        >
          <CheckboxV2
            id="agree_cross_border"
            checked={consents.cross_border}
            onChange={(next) => onChange("cross_border", next)}
          />
          <span className="font-serif" style={consentLabelStyle}>
            <span className="font-mono" style={requiredTagStyle}>
              {c.requiredTag}
            </span>
            {c.crossBorder}{" "}
            <a
              href="/privacy#cross-border"
              target="_blank"
              rel="noopener"
              onClick={(e) => e.stopPropagation()}
              style={{ marginLeft: 4, fontSize: "0.85em" }}
            >
              {c.crossBorderLink}
            </a>
          </span>
        </label>

        <label htmlFor="agree_marketing" style={consentRowStyle}>
          <CheckboxV2
            id="agree_marketing"
            checked={consents.marketing}
            onChange={(next) => onChange("marketing", next)}
          />
          <span className="font-serif" style={consentLabelStyle}>
            <span className="font-mono" style={optionalTagStyle}>
              {c.optionalTag}
            </span>
            {c.marketing}
          </span>
        </label>
      </div>
    </div>
  );
}

export default ConsentStackV2;
