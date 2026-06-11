"use client";

import { useSearchParams } from "next/navigation";
import { FormEvent, useMemo, useState } from "react";
import { useLocale } from "@/lib/locale";

type Copy = {
  eyebrow: string;
  title: string;
  subtitle: string;
  label: string;
  placeholder: string;
  submit: string;
  submitting: string;
  invalid: string;
  networkError: string;
  notConfigured: string;
  footer: string;
  toggleLocale: string;
};

const COPY: Record<"ko" | "en", Copy> = {
  ko: {
    eyebrow: "Private Beta",
    title: "초대받은 분만 입장하실 수 있어요",
    subtitle:
      "PivoxQuant는 지금 비공개 베타 기간입니다. CEO로부터 전달받은 비밀번호를 입력해주세요.",
    label: "베타 비밀번호",
    placeholder: "비밀번호 입력",
    submit: "입장하기",
    submitting: "확인 중…",
    // FINDING-GATE-004 (design-audit-20260514): brand-voiced error copy.
    invalid: "코드가 일치하지 않습니다. CEO로부터 전달받은 코드를 다시 확인해주세요.",
    networkError: "네트워크 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
    notConfigured: "베타 게이트가 아직 설정되지 않았습니다.",
    footer: "한 번 인증하면 30일 동안 유지됩니다.",
    toggleLocale: "English",
  },
  en: {
    eyebrow: "Private Beta",
    title: "Invite-only access",
    subtitle:
      "PivoxQuant is in private beta. Enter the access code shared by the team to continue.",
    label: "Beta access code",
    placeholder: "Enter access code",
    submit: "Enter",
    submitting: "Verifying…",
    // FINDING-GATE-004 (design-audit-20260514): brand-voiced error copy.
    invalid: "That code doesn't match. Double-check the code the CEO shared with you.",
    networkError: "Network error. Please try again in a moment.",
    notConfigured: "Beta gate is not configured yet.",
    footer: "Verified once, remembered for 30 days.",
    toggleLocale: "한국어",
  },
};

function isSafeRedirect(path: string | null): path is string {
  if (!path) return false;
  if (!path.startsWith("/")) return false;
  if (path.startsWith("//")) return false;
  if (path.startsWith("/beta-gate")) return false;
  return true;
}

export default function BetaGateForm() {
  const search = useSearchParams();
  const { locale, setLocale } = useLocale();
  const copy = COPY[locale] ?? COPY.ko;

  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const redirectTo = useMemo(() => {
    const raw = search.get("redirect");
    return isSafeRedirect(raw) ? raw : "/";
  }, [search]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);

    try {
      const res = await fetch("/api/beta-auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });

      if (res.ok) {
        // Hard navigation so the newly-set cookie is attached on the next request.
        window.location.assign(redirectTo);
        return;
      }

      if (res.status === 500) {
        setError(copy.notConfigured);
      } else {
        setError(copy.invalid);
      }
    } catch {
      setError(copy.networkError);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="w-full animate-fade-up rounded-2xl border px-6 py-8 sm:px-8 sm:py-10 font-serif"
      style={{
        backgroundColor: "rgba(255, 255, 255, 0.02)",
        borderColor: "rgba(184, 149, 106, 0.18)",
      }}
    >
      {/* Lock badge + brand */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl"
            style={{ backgroundColor: "var(--pq-bronze-light)" }}
          >
            <svg
              aria-hidden="true"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4"
              style={{ color: "var(--pq-ink)" }}
            >
              <rect x="4" y="11" width="16" height="9" rx="2" />
              <path d="M8 11V8a4 4 0 0 1 8 0v3" />
            </svg>
          </span>
          <span
            className="text-sm font-semibold tracking-tight"
            style={{ color: "var(--pq-ivory)" }}
          >
            PivoxQuant
          </span>
        </div>

        <button
          type="button"
          onClick={() => setLocale(locale === "ko" ? "en" : "ko")}
          className="text-xs font-medium transition-colors"
          style={{ color: "rgba(245, 240, 232, 0.55)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--pq-ivory)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "rgba(245, 240, 232, 0.55)")}
          aria-label="Toggle language"
        >
          {copy.toggleLocale}
        </button>
      </div>

      {/* Header */}
      <div className="mt-8">
        <div
          className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-pq-mono-sm font-semibold uppercase tracking-wider"
          style={{
            borderColor: "rgba(184, 149, 106, 0.32)",
            backgroundColor: "rgba(184, 149, 106, 0.06)",
            color: "var(--pq-bronze)",
          }}
        >
          <span
            aria-hidden="true"
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: "var(--pq-bronze-light)" }}
          />
          {copy.eyebrow}
        </div>

        <h1
          className="mt-4 text-2xl font-semibold leading-tight tracking-tight sm:text-pq-avatar"
          style={{ color: "var(--pq-ivory)" }}
        >
          {copy.title}
        </h1>
        <p
          className="mt-3 text-sm leading-relaxed"
          style={{ color: "rgba(245, 240, 232, 0.7)" }}
        >
          {copy.subtitle}
        </p>
      </div>

      {/* Form — FINDING-GATE-001 (design-audit-20260514): method="post"
          so that if JS is disabled the browser does not fall back to a
          GET that leaks `?password=...` into the URL, history, and access
          logs. The onSubmit handler (preventDefault + fetch) is the JS
          path and is unchanged. */}
      <form
        onSubmit={handleSubmit}
        method="post"
        className="mt-7 space-y-4"
        noValidate
      >
        <div>
          <label
            htmlFor="beta-password"
            className="mb-2 block text-xs font-semibold"
            style={{ color: "rgba(245, 240, 232, 0.7)" }}
          >
            {copy.label}
          </label>
          <input
            id="beta-password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            autoFocus
            inputMode="text"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (error) setError(null);
            }}
            placeholder={copy.placeholder}
            aria-invalid={!!error}
            aria-describedby={error ? "beta-error" : undefined}
            className="w-full rounded-xl border px-4 py-3 text-pq-lead outline-none transition-[box-shadow,border-color] duration-200 focus:border-[var(--pq-bronze)] focus:shadow-[0_0_0_4px_rgba(var(--pq-bronze-rgb),0.32)]"
            style={{
              backgroundColor: "rgba(10, 10, 10, 0.6)",
              borderColor: "rgba(184, 149, 106, 0.32)",
              color: "var(--pq-ivory)",
            }}
          />
          {error && (
            <p
              id="beta-error"
              role="alert"
              className="mt-2 text-sm"
              style={{ color: "var(--pq-error)" }}
            >
              {error}
            </p>
          )}
        </div>

        <button
          type="submit"
          disabled={submitting || password.length === 0}
          className="relative inline-flex h-12 w-full items-center justify-center overflow-hidden rounded-xl text-sm font-semibold tracking-tight transition-[transform,box-shadow,opacity] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] hover:-translate-y-[1px] active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
          style={{
            backgroundColor: "var(--pq-bronze-light)",
            color: "var(--pq-ink)",
            boxShadow: "0 6px 20px -6px rgba(var(--pq-bronze-rgb), 0.45)",
          }}
        >
          {submitting ? (
            <span className="inline-flex items-center gap-2">
              <span
                className="h-3.5 w-3.5 animate-spin rounded-full border-2"
                style={{ borderColor: "rgba(5, 5, 5, 0.4)", borderTopColor: "var(--pq-ink)" }}
              />
              {copy.submitting}
            </span>
          ) : (
            copy.submit
          )}
        </button>
      </form>

      {/* Footer */}
      <p
        className="mt-6 text-center text-xs"
        style={{ color: "rgba(245, 240, 232, 0.5)" }}
      >
        {copy.footer}
      </p>
    </div>
  );
}
