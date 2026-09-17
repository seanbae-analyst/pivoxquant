"use client";

/**
 * /signup/oauth-finalize — PIPA §22 ⑥ birthdate interstitial.
 *
 * Reached when the OAuth callback (``routes/auth.py`` Google/Kakao)
 * provisions a User row with ``birthdate IS NULL``. The page captures
 * a yyyy-mm-dd birthdate, POSTs it to ``/api/auth/oauth-finalize``, and
 * redirects to ``next`` (or ``/mirror``) on success.
 *
 * Why a dedicated page (not a modal):
 *   The callback completes a server-side redirect chain and ends with
 *   ``Set-Cookie: session=...``. By the time the user hits the next
 *   protected route, their cookie is fresh — so the interstitial is just
 *   another protected page they have to clear before reaching the
 *   dashboard. Putting it in a modal would couple it to a host page that
 *   may itself need ``birthdate_required = false`` to render properly.
 *
 * Error contract:
 *   The backend returns stable codes (see services/age_verification.py).
 *   We map each to a Korean + English message.
 *
 * Visual layer follows v3 Vantablack lock-in tokens — same Bronze hairline
 * + JetBrains mono labels as ``signup/page.tsx`` so the page reads
 * as a continuation of the consent flow, not a stand-alone form.
 *
 * ── 법정 필수 동의 (2026-09-17 이관) ──────────────────────────────────
 * ``/login`` 과 ``/signup`` 은 같은 OAuth 엔드포인트로 가고, 백엔드 콜백은
 * 계정이 없으면 어느 화면에서 왔든 User 를 만든다. 그래서 "로그인"으로 들어온
 * 신규 사용자는 동의 화면을 한 번도 보지 않고 계정이 생겼다. 이 인터스티셜은
 * ``user.birthdate_required === true`` 인 **신규 OAuth 가입자에게만** 뜨므로,
 * 법정 필수 동의를 받을 유일하게 올바른 자리다. 동의 스택은
 * ``@/components/auth/v2/consent-stack`` 이 소유한다.
 *
 * 어디에 남는가 (증거 강도)
 *   - cross_border → POST /api/consents/cross-border (PIPA §28-8) — 서버 기록
 *   - marketing    → POST /api/consents/marketing (정통망법 §50 ①) — 서버 기록
 *   - terms / non_advisory → **서버 컬럼 없음**. 기존과 동일하게 localStorage
 *     ``pivox_signup_consents`` 스냅숏에만 남는다(브라우저 저장소가 지워지면
 *     증거도 사라진다 — 현행 유지, 서버 컬럼 추가는 별도 백엔드 작업).
 *   - age → 체크 자체는 스냅숏에만 남지만, 생년월일이
 *     ``/api/auth/oauth-finalize`` 로 서버에 저장되므로 간접 증거가 남는다.
 * 두 POST 는 best-effort 다 — 실패해도 플로우를 막지 않는다(기존 marketing
 * flush 와 같은 정책). 스냅숏이 남아 있으므로 (dashboard) 레이아웃의
 * flushPending* 가 다음 마운트에서 재시도한다.
 */

import { safeNext } from "@/lib/safe-next";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { apiFetch, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { API } from "@/lib/endpoints";
import {
  CONSENT_STORAGE_KEY,
  recordCrossBorderConsent,
  recordMarketingConsent,
} from "@/lib/consents";
import {
  allRequiredConsented,
  ConsentStackV2,
  EMPTY_CONSENTS,
  type ConsentKey,
  type ConsentState,
} from "@/components/auth/v2/consent-stack";
import {
  BIRTHDATE_LABEL_EN,
  BIRTHDATE_LABEL_KO,
  computeAgeYears,
  isAtLeastMinAge,
  isValidBirthdate,
  UNDER_AGE_EN,
  UNDER_AGE_KO,
} from "@/lib/age-verification";

/**
 * Map backend i18n code → user-facing copy. The codes are the same
 * keys ``services/age_verification.py`` raises and
 * ``frontend/src/lib/age-verification.ts`` exports.
 */
const ERROR_COPY: Record<string, { ko: string; en: string }> = {
  birthdate_required: {
    ko: "생년월일을 입력해주세요.",
    en: "Please enter your date of birth.",
  },
  birthdate_invalid_format: {
    ko: "yyyy-mm-dd 형식으로 입력해주세요.",
    en: "Please use yyyy-mm-dd format.",
  },
  birthdate_unrealistic: {
    ko: "올바른 생년월일을 입력해주세요.",
    en: "Please enter a realistic date of birth.",
  },
  below_min_age: { ko: UNDER_AGE_KO, en: UNDER_AGE_EN },
  birthdate_already_set: {
    ko: "이미 등록된 생년월일이 있습니다. 고객센터에 문의해주세요.",
    en: "Your date of birth is already on file. Please contact support.",
  },
};


export default function OAuthFinalizePage() {
  const { user, loading, refresh } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [birthdate, setBirthdate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [consents, setConsents] = useState<ConsentState>(EMPTY_CONSENTS);
  const [pulseUnchecked, setPulseUnchecked] = useState(false);

  const setConsent = useCallback((key: ConsentKey, next: boolean) => {
    setConsents((prev) => (prev[key] === next ? prev : { ...prev, [key]: next }));
  }, []);

  // Same client-side rule as signup _v2 — keeps the two surfaces aligned.
  const ageCheck = useMemo(() => {
    const valid = isValidBirthdate(birthdate);
    return {
      valid,
      eligible: valid && isAtLeastMinAge(birthdate),
      years: valid ? computeAgeYears(birthdate) : -1,
    };
  }, [birthdate]);

  // If the user is unauthenticated, send them back to /login. The OAuth
  // callback flow established a session before redirecting here, so an
  // unauthenticated visit means a stale cookie or a direct bookmark.
  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  // If the user *already* has a birthdate (interstitial visited by mistake),
  // skip straight to the destination.
  useEffect(() => {
    if (loading || !user) return;
    if (user.birthdate_required === false) {
      const next = safeNext(searchParams.get("next"));
      router.replace(next);
    }
  }, [loading, user, searchParams, router]);

  // 2026-09-17 — REMOVED: birthdate auto-submit ("2026-05-17 wave 12 UX P1",
  // PR #429). That effect read the `pivox_signup_consents` localStorage
  // snapshot, auto-filled the DOB it found and POSTed
  // `/api/auth/oauth-finalize` immediately, so the interstitial never
  // rendered. That was correct while the consent stack lived on
  // `/signup` *before* OAuth — the snapshot only existed because the user
  // had just ticked every box.
  //
  // It is NOT correct now. The consent stack moved here (see the file
  // header): consent is collected on THIS page, after the OAuth callback,
  // because a new user arriving via `/login` never sees `/signup` at all.
  // An auto-submit would fire before the user could tick anything and
  // would skip the legally required consents entirely — the exact hole
  // this change closes. A stale snapshot from an older session would also
  // finalize the account silently. So: no auto-fill, no auto-POST. The
  // user must see the form, and submit it.
  //
  // (`isValidBirthdate` / `isAtLeastMinAge` are still used by `ageCheck`.)

  // 미체크 항목 붉은 펄스 — signup/page.tsx 와 같은 900ms 자동 해제.
  useEffect(() => {
    if (!pulseUnchecked) return;
    const t = setTimeout(() => setPulseUnchecked(false), 900);
    return () => clearTimeout(t);
  }, [pulseUnchecked]);

  const stageConsentSnapshot = useCallback(
    (dob: string) => {
      // terms / non_advisory 는 서버 컬럼이 없다 → 기존과 동일하게
      // localStorage 스냅숏이 유일한 증거다(파일 상단 주석 참조).
      // marketing / cross_border 도 같이 남겨서, 아래 best-effort POST 가
      // 실패하면 (dashboard) 레이아웃의 flushPending* 가 재시도할 수 있게 한다.
      if (typeof window === "undefined") return;
      try {
        window.localStorage.setItem(
          CONSENT_STORAGE_KEY,
          JSON.stringify({
            ...consents,
            birthdate: dob,
            consented_at: new Date().toISOString(),
          }),
        );
      } catch {
        /* quota / private mode — 증거 저장 실패가 가입을 막으면 안 된다 */
      }
    },
    [consents],
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ageCheck.eligible || !allRequiredConsented(consents) || submitting) {
      return;
    }
    setSubmitting(true);
    setErrorCode(null);
    // 서버 왕복 전에 스냅숏을 먼저 남긴다 — 네트워크가 죽어도 동의 사실은
    // 남고, 재시도 경로(flushPending*)도 이 스냅숏을 본다.
    stageConsentSnapshot(birthdate);
    try {
      // 백엔드 계약 불변 — body 는 여전히 { birthdate } 뿐이다.
      await apiFetch(API.auth.oauthFinalize, {
        method: "POST",
        body: JSON.stringify({ birthdate }),
      });
      // 국외이전(PIPA §28-8) + 마케팅(정통망법 §50 ①) 은 이미 있는 동의
      // 엔드포인트로 기록한다. best-effort — 실패해도 가입을 막지 않는다.
      if (consents.cross_border) {
        try {
          await recordCrossBorderConsent();
        } catch (err) {
          console.error("[oauth-finalize] cross-border consent POST failed:", err);
        }
      }
      if (consents.marketing) {
        try {
          await recordMarketingConsent();
        } catch (err) {
          console.error("[oauth-finalize] marketing consent POST failed:", err);
        }
      }
      // Refresh the cached user so ``birthdate_required`` flips to false
      // before downstream pages mount.
      await refresh();
      const next = safeNext(searchParams.get("next"));
      router.replace(next);
    } catch (err) {
      // ``apiFetch`` throws ``ApiError(status, body.error ?? statusText)``
      // — so the i18n code lands in ``err.message``. Falling back to a
      // generic format error keeps the user out of a stuck state if the
      // server returns an unexpected payload.
      const code =
        err instanceof ApiError && typeof err.message === "string"
          ? err.message
          : "birthdate_invalid_format";
      setErrorCode(code in ERROR_COPY ? code : "birthdate_invalid_format");
      setSubmitting(false);
    }
  };

  if (loading || !user) {
    // Page-load skeleton — Vantablack surface matching the oauth finalize
    // form layout (birthdate field + consent block + CTA). Replaces the
    // legacy animate-spin border indicator so the perceived load is calmer
    // and the layout shift is smaller when the live form mounts.
    return (
      <div
        className="flex min-h-[100dvh] items-center justify-center px-6"
        style={{ background: "var(--pq-ink, #050505)" }}
        role="status"
        aria-live="polite"
        aria-label="Finalizing your account"
      >
        <div className="w-full max-w-sm flex flex-col gap-3">
          <div className="pq-skeleton-dark h-8 w-48 rounded" />
          <div className="pq-skeleton-dark h-4 w-64 rounded" />
          <div className="pq-skeleton-dark mt-6 h-11 w-full rounded-sm" />
          <div className="pq-skeleton-dark mt-2 h-4 w-full rounded" />
          <div className="pq-skeleton-dark h-4 w-5/6 rounded" />
          <div className="pq-skeleton-dark mt-4 h-12 w-full rounded-sm" />
          <span className="sr-only">Finalizing your account…</span>
        </div>
      </div>
    );
  }

  const errorMsg = errorCode ? ERROR_COPY[errorCode] : null;
  // 제출 게이트 — 만 14세 이상 + 필수 4종(terms / non_advisory / age /
  // cross_border) 전부 동의. marketing 은 선택이라 게이트에 들어가지 않는다.
  const consentsReady = allRequiredConsented(consents);
  const canSubmit = ageCheck.eligible && consentsReady && !submitting;

  return (
    <div
      className="flex min-h-[100dvh] items-center justify-center px-6 py-16"
      style={{ background: "var(--pq-ink, #050505)" }}
    >
      <form
        onSubmit={handleSubmit}
        style={{
          width: "100%",
          maxWidth: 420,
          display: "flex",
          flexDirection: "column",
          gap: 24,
        }}
      >
        <header style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <span
            className="font-mono"
            style={{
              fontSize: "var(--pq-text-micro)",
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--pq-bronze, #B8956A)",
            }}
          >
            PIPA §22 ⑥
          </span>
          <h1
            style={{
              fontFamily: "var(--pq-font-display, 'Playfair Display', serif)",
              fontSize: "var(--pq-text-avatar)",
              lineHeight: 1.2,
              color: "rgba(245,240,232,0.96)",
              margin: 0,
            }}
          >
            한 가지만 더 확인할게요
          </h1>
          <p
            style={{
              fontSize: "var(--pq-text-body)",
              lineHeight: 1.6,
              color: "rgba(245,240,232,0.68)",
              margin: 0,
            }}
          >
            개인정보 보호법 §22 ⑥ 에 따라 만 14세 이상 여부를 확인합니다.
            법정대리인 동의 절차는 출시 후 별도 안내드립니다.
          </p>
        </header>

        <label
          htmlFor="oauth_finalize_birthdate"
          style={{ display: "flex", flexDirection: "column", gap: 6 }}
        >
          <span
            className="font-mono"
            style={{
              fontSize: "var(--pq-text-micro)",
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--pq-ivory-dim)",
            }}
          >
            {BIRTHDATE_LABEL_KO} · {BIRTHDATE_LABEL_EN}
          </span>
          <input
            id="oauth_finalize_birthdate"
            type="date"
            required
            className="pq-input-noom"
            value={birthdate}
            max={new Date().toISOString().slice(0, 10)}
            onChange={(e) => {
              setBirthdate(e.target.value);
              setErrorCode(null);
            }}
            aria-invalid={!!errorCode || (birthdate !== "" && !ageCheck.eligible)}
            aria-describedby="oauth_finalize_birthdate_msg"
            style={{
              background: "transparent",
              color: "rgba(245,240,232,0.92)",
              border: `1px solid ${
                errorCode || (birthdate && !ageCheck.eligible)
                  ? "rgba(244,108,108,0.6)"
                  : "rgba(245,240,232,0.20)"
              }`,
              borderRadius: 2,
              padding: "10px 12px",
              colorScheme: "dark",
            }}
          />
          {(errorMsg || (birthdate && !ageCheck.eligible)) && (
            <span
              id="oauth_finalize_birthdate_msg"
              role="alert"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                lineHeight: 1.55,
                color: "rgba(244,108,108,0.92)",
              }}
            >
              {errorMsg ? errorMsg.ko : UNDER_AGE_KO}
              <br />
              <span style={{ opacity: 0.75 }}>
                {errorMsg ? errorMsg.en : UNDER_AGE_EN}
              </span>
            </span>
          )}
        </label>

        {/* 법정 필수 동의 — 생년월일 폼 아래. 신규 OAuth 가입자만 이 페이지를
            보므로, 여기가 `/login` 경유 신규자까지 덮는 유일한 지점이다. */}
        <ConsentStackV2
          consents={consents}
          onChange={setConsent}
          ageEligible={ageCheck.eligible}
          pulseUnchecked={pulseUnchecked}
        />

        {/* 2026-05-17 wave 12 UX P0 과 같은 이유로 래퍼가 클릭을 받는다:
            disabled 버튼은 click 이벤트를 내보내지 않아 모바일(375px)에서
            "왜 안 눌리지" 상태가 된다. 버튼의 pointer-events 를 꺼서 클릭이
            래퍼로 떨어지게 하고, 첫 미충족 항목으로 스크롤 + 펄스. */}
        <div
          onClick={() => {
            if (canSubmit || submitting) return;
            setPulseUnchecked(true);
            const firstMissing =
              (!ageCheck.eligible && "oauth_finalize_birthdate") ||
              (!consents.terms && "agree_terms") ||
              (!consents.non_advisory && "agree_non_advisory") ||
              (!consents.age && "agree_age") ||
              (!consents.cross_border && "agree_cross_border") ||
              null;
            if (firstMissing && typeof document !== "undefined") {
              document
                .getElementById(firstMissing)
                ?.scrollIntoView({ behavior: "smooth", block: "center" });
            }
          }}
          style={{ display: "flex", flexDirection: "column", gap: 8 }}
        >
          <button
            type="submit"
            disabled={!canSubmit}
            style={{
              width: "100%",
              padding: "12px 16px",
              border: "1px solid var(--pq-bronze, #B8956A)",
              background: canSubmit
                ? "var(--pq-bronze, #B8956A)"
                : "transparent",
              color: canSubmit
                ? "var(--pq-ink, #050505)"
                : "rgba(245,240,232,0.40)",
              fontFamily: "var(--pq-font-mono, 'JetBrains Mono', monospace)",
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              borderRadius: 2,
              cursor: canSubmit ? "pointer" : "not-allowed",
              pointerEvents: canSubmit ? "auto" : "none",
              transition: "background-color 200ms cubic-bezier(0.16,1,0.3,1)",
            }}
          >
            {submitting ? "확인 중…" : "계속하기 · Continue"}
          </button>

          {!consentsReady && (
            <span
              className="font-mono"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                lineHeight: 1.6,
                color: pulseUnchecked
                  ? "rgba(244,108,108,0.92)"
                  : "var(--pq-ivory-dim)",
                transition: "color 200ms cubic-bezier(0.16,1,0.3,1)",
              }}
            >
              필수 항목 4개에 모두 동의해야 가입이 완료됩니다.
              <br />
              <span style={{ opacity: 0.75 }}>
                All 4 required consents must be checked to finish signing up.
              </span>
            </span>
          )}
        </div>
      </form>
    </div>
  );
}
