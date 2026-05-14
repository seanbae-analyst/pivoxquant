"use client";

/**
 * /signup v2 — Editorial entry, Vantablack split layout.
 *
 * Toggle: NEXT_PUBLIC_SIGNUP_V2=true (default off; v1 remains live).
 *
 * Function preservation (verbatim from v1):
 * - useAuth + router.replace("/home") on existing session.
 * - Three required + one optional consent (terms / non_advisory / age /
 *   marketing). `allRequired` gates the OAuth buttons.
 * - On click, persist consent snapshot to localStorage under
 *   `pivox_signup_consents` then redirect to API.auth.google / .kakao.
 * - Same CONSENT_STORAGE_KEY constant — OAuth callback handler stays
 *   binary-compatible with v1.
 * - 정통망법 §50 ① server flush: the snapshot is staged in localStorage
 *   pre-OAuth (no session yet), and `flushPendingMarketingConsent()` in
 *   `frontend/src/lib/consents.ts` promotes it to the backend record
 *   (POST /api/consents/marketing) on the first authenticated mount of
 *   the (dashboard) layout. This page intentionally does NOT call the
 *   server here — `current_user` does not yet exist when this handler
 *   fires. Backend dependency: PR #73 (`routes/consents.py`).
 *
 * Visual layer only — Vantablack background, Bronze hairlines, Playfair H1,
 * Source Serif body, JetBrains Mono uppercase OAuth labels.
 */

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

import { AuthHeroV2 } from "@/components/auth/v2/auth-hero-v2";
import { OAuthButtonsV2 } from "@/components/auth/v2/oauth-buttons-v2";
import { AuthLinkV2 } from "@/components/auth/v2/auth-link-v2";
import { Fleuron } from "@/components/ui/editorial";

/* Same key as v1 — OAuth callback handler reads this on first login. */
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

/* Bronze-tinted ink checkbox — visual only, behavior identical to v1. */
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
        background: checked
          ? "var(--pq-bronze, #B8956A)"
          : "transparent",
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

export default function SignupPageV2() {
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

  // PIPA §22 ⑥ — 만 14세 미만 fail-fast (자가선언 + 생년월일 이중 방어).
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

  useEffect(() => {
    if (!pulseUnchecked) return;
    const t = setTimeout(() => setPulseUnchecked(false), 900);
    return () => clearTimeout(t);
  }, [pulseUnchecked]);

  useEffect(() => {
    if (!loading && user) {
      router.replace("/home");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div
        className="flex min-h-[100dvh] items-center justify-center"
        style={{ background: "var(--pq-ink, #050505)" }}
      >
        <div
          className="h-8 w-8 animate-spin rounded-full"
          style={{
            border: "2px solid rgba(245,240,232,0.10)",
            borderTopColor: "var(--pq-bronze, #B8956A)",
          }}
        />
      </div>
    );
  }

  if (user) return null;

  const setConsent = (key: keyof Consents) => (next: boolean) => {
    setConsents((prev) => ({ ...prev, [key]: next }));
  };

  /* Same handler shape as v1 handleOAuthClick — preserves the legal gate
   * + consent snapshot persistence + redirect URL behavior 1:1. */
  const handleOAuthClick =
    (url: string) => (e: React.MouseEvent<HTMLAnchorElement>) => {
      if (!allRequired) {
        e.preventDefault();
        return;
      }
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

  const consentLabelStyle: React.CSSProperties = {
    fontSize: "var(--pq-text-body)",
    lineHeight: 1.55,
    color: "rgba(245,240,232,0.72)",
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
    color: "rgba(245,240,232,0.55)",
  };

  return (
    <div
      className="pq-auth-shell-v2"
      style={{
        // Escape the (auth)/layout.tsx max-w-sm white wrapper without
        // editing the shared layout (v1 still depends on it). Fixed-fill
        // covers the viewport with Vantablack ink underneath the layout.
        position: "fixed",
        inset: 0,
        zIndex: 50,
        minHeight: "100dvh",
        background: "var(--pq-ink, #050505)",
        color: "var(--pq-ivory, #F5F0E8)",
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        // Bronze hairline + 64px nav band lives ABOVE the split grid via
        // grid-template-rows so it sits flush with both panes and never
        // overlaps the form header. Mobile collapses to single column —
        // see <style jsx> below.
        gridTemplateRows: "auto 1fr",
        overflowY: "auto",
      }}
    >
      {/* ── Top: Minimal nav band ──────────────────────────────────────
          E2E P1 #23 fix (2026-05-11): /signup previously had no nav
          chrome — users lost orientation and had no escape hatch back to
          the marketing site. Adds a 64px Bronze-hairlined band with the
          PIVOXQUANT wordmark + "← Back to home" link. Spans both grid
          columns so it never overlaps the form header. */}
      <header
        className="pq-auth-nav-v2"
        style={{
          gridColumn: "1 / -1",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "20px 32px",
          borderBottom: "0.5px solid rgba(184,149,106,0.18)",
          background: "var(--pq-ink, #050505)",
          minHeight: 64,
        }}
      >
        <Link
          href="/"
          aria-label="PivoxQuant home"
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-button)",
            letterSpacing: "0.28em",
            color: "var(--pq-ivory, #F5F0E8)",
            textTransform: "uppercase",
            textDecoration: "none",
          }}
        >
          PIVOXQUANT
        </Link>
        <Link
          href="/"
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.20em",
            color: "rgba(245,240,232,0.65)",
            textTransform: "uppercase",
            textDecoration: "none",
          }}
        >
          ← Back to home
        </Link>
      </header>

      {/* ── Left: Editorial Hero ──────────────────────────────────────── */}
      <div
        className="pq-auth-hero-pane"
        style={{
          display: "flex",
          // E2E P1 #23 fix (2026-05-11): use flex-start (not center) so
          // the form header "Sign up · 가입 전 확인" stays visible when
          // content exceeds viewport height. Flex centering with
          // taller-than-container content cuts off the top in
          // non-scrollable directions. With overflowY:auto on the shell
          // grid, flex-start + padding-top yields the correct scroll.
          alignItems: "flex-start",
          justifyContent: "flex-end",
          borderRight: "0.5px solid rgba(184,149,106,0.18)",
        }}
      >
        <AuthHeroV2
          eyebrow={"PivoxQuant · Entry"}
          headlineHtml={
            'Create your <span class="br">CFO</span>.<br/>The first memo lands <span class="br">Monday 07:00 KST.</span>'
          }
          deck="A weekly editorial, an earnings pre-brief, and a brag card you can ship — drafted by AI, reviewed by you, addressed only to you."
          signature="Beta · Free during preview"
        />
      </div>

      {/* ── Right: Consent + OAuth Card ───────────────────────────────── */}
      <div
        className="pq-auth-card-pane"
        style={{
          display: "flex",
          // E2E P1 #23 fix (2026-05-11): see hero-pane note — flex-start
          // prevents form header "Sign up · 가입 전 확인" cutoff when
          // content exceeds viewport (was top: -138px overflowing).
          alignItems: "flex-start",
          justifyContent: "flex-start",
        }}
      >
        <div
          className="pq-auth-card-inner"
          style={{
            width: "100%",
            maxWidth: 460,
            padding: "64px 56px",
            display: "flex",
            flexDirection: "column",
            gap: 28,
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <span
              className="font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.24em",
                color: "var(--pq-bronze, #B8956A)",
                textTransform: "uppercase",
              }}
            >
              Sign up
            </span>
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
              가입 전 확인
            </h2>
          </div>

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
                onChange={setConsent("terms")}
              />
              <span className="font-serif" style={consentLabelStyle}>
                <span className="font-mono" style={requiredTagStyle}>[필수]</span>
                <Link
                  href="/terms"
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  style={{
                    color: "var(--pq-ivory, #F5F0E8)",
                    textDecoration: "underline",
                    textUnderlineOffset: 2,
                  }}
                >
                  이용약관
                </Link>{" "}
                및{" "}
                <Link
                  href="/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  style={{
                    color: "var(--pq-ivory, #F5F0E8)",
                    textDecoration: "underline",
                    textUnderlineOffset: 2,
                  }}
                >
                  개인정보처리방침
                </Link>
                에 동의합니다.
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
                onChange={setConsent("non_advisory")}
              />
              <span className="font-serif" style={consentLabelStyle}>
                <span className="font-mono" style={requiredTagStyle}>[필수]</span>
                PivoxQuant는 자본시장법상 투자자문업이 아니며, 본 서비스의 모든
                분석·리포트·시그널은 정보 제공 목적임을 이해합니다. 투자 판단과
                그 결과는 이용자 본인의 책임입니다.
              </span>
            </label>

            {/* PIPA §22 ⑥ — 생년월일 + 자가선언 이중 방어선. */}
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <label
                htmlFor="agree_birthdate"
                style={{ display: "flex", flexDirection: "column", gap: 6 }}
              >
                <span className="font-mono" style={requiredTagStyle}>
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
                  style={{
                    background: "transparent",
                    color: "rgba(245,240,232,0.85)",
                    border: `1px solid ${
                      ageCheck.eligible
                        ? "rgba(245,240,232,0.20)"
                        : birthdate
                          ? "rgba(244,108,108,0.6)"
                          : "rgba(245,240,232,0.20)"
                    }`,
                    borderRadius: 2,
                    padding: "8px 10px",
                    fontSize: "var(--pq-text-button)",
                    colorScheme: "dark",
                  }}
                />
                {birthdate && !ageCheck.eligible && (
                  <span
                    id="agree_birthdate_msg"
                    role="alert"
                    style={{
                      fontSize: "var(--pq-text-micro)",
                      lineHeight: 1.5,
                      color: "rgba(244,108,108,0.92)",
                    }}
                  >
                    {UNDER_AGE_KO}
                    <br />
                    <span style={{ opacity: 0.75 }}>{UNDER_AGE_EN}</span>
                  </span>
                )}
              </label>

              <label
                htmlFor="agree_age"
                style={{
                  ...consentRowStyle,
                  ...pulseRowStyle(pulseUnchecked && !consents.age),
                  opacity: ageCheck.eligible ? 1 : 0.5,
                  pointerEvents: ageCheck.eligible ? "auto" : "none",
                }}
              >
                <CheckboxV2
                  id="agree_age"
                  checked={consents.age && ageCheck.eligible}
                  onChange={(next) => {
                    if (!ageCheck.eligible) return;
                    setConsent("age")(next);
                  }}
                />
                <span className="font-serif" style={consentLabelStyle}>
                  <span className="font-mono" style={requiredTagStyle}>[필수]</span>
                  만 14세 이상임을 확인합니다. (개인정보보호법 §22 ⑥)
                </span>
              </label>
            </div>

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
                onChange={setConsent("cross_border")}
              />
              <span className="font-serif" style={consentLabelStyle}>
                <span className="font-mono" style={requiredTagStyle}>[필수]</span>
                개인정보의 국외 이전에 동의합니다. (PIPA §28-8 — Anthropic / Stripe / Vercel / Railway / Google, 미국 소재 위탁처)
                {" "}
                <a
                  href="/privacy#cross-border"
                  target="_blank"
                  rel="noopener"
                  style={{ marginLeft: 4, fontSize: "0.85em" }}
                >
                  보기
                </a>
              </span>
            </label>

            <label htmlFor="agree_marketing" style={consentRowStyle}>
              <CheckboxV2
                id="agree_marketing"
                checked={consents.marketing}
                onChange={setConsent("marketing")}
              />
              <span className="font-serif" style={consentLabelStyle}>
                <span className="font-mono" style={optionalTagStyle}>[선택]</span>
                마케팅 정보(이벤트, 신기능 안내) 수신에 동의합니다.
              </span>
            </label>
          </div>

          {/* OAuth — disabled until allRequired === true (legal gate) */}
          <OAuthButtonsV2
            disabled={!allRequired}
            onGoogleClick={handleOAuthClick(API.auth.google)}
            onKakaoClick={handleOAuthClick(API.auth.kakao)}
            onDisabledClick={() => setPulseUnchecked(true)}
            hint="필수 항목 4개에 모두 동의해야 가입할 수 있습니다."
            hintEmphasized={pulseUnchecked}
          />

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 14,
              padding: "8px 0",
            }}
            aria-hidden="true"
          >
            <span
              style={{
                flex: 1,
                height: 0,
                borderTop: "0.5px solid var(--pq-ivory-line)",
              }}
            />
            <Fleuron size={12} />
            <span
              style={{
                flex: 1,
                height: 0,
                borderTop: "0.5px solid var(--pq-ivory-line)",
              }}
            />
          </div>

          <AuthLinkV2
            prompt="이미 계정이 있으신가요?"
            action="로그인"
            href="/login"
          />

          <p
            className="font-mono uppercase"
            style={{
              marginTop: 6,
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.20em",
              color: "rgba(245,240,232,0.55)",
              textAlign: "center",
              textTransform: "uppercase",
            }}
          >
            Beta · 카드 등록 불필요
          </p>
        </div>
      </div>

      {/* FINDING-MOB-001 (design-audit-20260514): collapse the split grid
          to a single column on phones so the signup form is never pushed
          off-screen. Breakpoint aligned to the 768px tablet threshold; the
          inner card horizontal padding is reduced so 375px viewports never
          trigger a horizontal scrollbar. */}
      <style jsx>{`
        @media (max-width: 767px) {
          :global(.pq-auth-shell-v2) {
            grid-template-columns: 1fr !important;
          }
          :global(.pq-auth-hero-pane) {
            border-right: 0 !important;
            border-bottom: 0.5px solid rgba(184, 149, 106, 0.18) !important;
            justify-content: flex-start !important;
          }
          :global(.pq-auth-card-pane) {
            justify-content: center !important;
          }
          :global(.pq-auth-card-inner) {
            padding: 40px 24px !important;
          }
          :global(.pq-auth-nav-v2) {
            padding: 16px 20px !important;
          }
        }
      `}</style>
    </div>
  );
}
