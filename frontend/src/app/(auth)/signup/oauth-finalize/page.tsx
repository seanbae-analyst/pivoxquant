"use client";

/**
 * /signup/oauth-finalize — PIPA §22 ⑥ birthdate interstitial.
 *
 * Reached when the OAuth callback (``routes/auth.py`` Google/Kakao)
 * provisions a User row with ``birthdate IS NULL``. The page captures
 * a yyyy-mm-dd birthdate, POSTs it to ``/api/auth/oauth-finalize``, and
 * redirects to ``next`` (or ``/home``) on success.
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
 * + JetBrains mono labels as ``signup/_v2/page-v2.tsx`` so the page reads
 * as a continuation of the consent flow, not a stand-alone form.
 */

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { apiFetch, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { API } from "@/lib/endpoints";
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
      const next = searchParams.get("next") || "/home";
      router.replace(next);
    }
  }, [loading, user, searchParams, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ageCheck.eligible || submitting) return;
    setSubmitting(true);
    setErrorCode(null);
    try {
      await apiFetch(API.auth.oauthFinalize, {
        method: "POST",
        body: JSON.stringify({ birthdate }),
      });
      // Refresh the cached user so ``birthdate_required`` flips to false
      // before downstream pages mount.
      await refresh();
      const next = searchParams.get("next") || "/home";
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

  const errorMsg = errorCode ? ERROR_COPY[errorCode] : null;

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
              fontSize: 11,
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
              fontSize: 11,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "rgba(245,240,232,0.55)",
            }}
          >
            {BIRTHDATE_LABEL_KO} · {BIRTHDATE_LABEL_EN}
          </span>
          <input
            id="oauth_finalize_birthdate"
            type="date"
            required
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
              fontSize: "var(--pq-text-body)",
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

        <button
          type="submit"
          disabled={!ageCheck.eligible || submitting}
          style={{
            padding: "12px 16px",
            border: "1px solid var(--pq-bronze, #B8956A)",
            background:
              ageCheck.eligible && !submitting
                ? "var(--pq-bronze, #B8956A)"
                : "transparent",
            color:
              ageCheck.eligible && !submitting
                ? "var(--pq-ink, #050505)"
                : "rgba(245,240,232,0.40)",
            fontFamily: "var(--pq-font-mono, 'JetBrains Mono', monospace)",
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            borderRadius: 2,
            cursor:
              ageCheck.eligible && !submitting ? "pointer" : "not-allowed",
            transition: "background-color 200ms cubic-bezier(0.16,1,0.3,1)",
          }}
        >
          {submitting ? "확인 중…" : "계속하기 · Continue"}
        </button>
      </form>
    </div>
  );
}
