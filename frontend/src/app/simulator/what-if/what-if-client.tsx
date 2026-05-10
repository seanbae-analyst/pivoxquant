"use client";

/**
 * What-If Simulator — Client orchestrator
 *
 * Owns:
 *  - URL query <-> form state sync (new URL shape: ?t=&d=&a=&r=&c=)
 *  - SWR fetch keyed on the current query
 *  - Top-level layout: header → hero → form → result → disclaimer → CTA
 *
 * Everything below is purely presentational.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import useSWR from "swr";
import { motion } from "motion/react";
import { Clock, ArrowUpRight, AlertCircle } from "lucide-react";
import { API } from "@/lib/endpoints";
import { useT } from "@/lib/locale";
import type {
  RecurringMode,
  WhatIfResponse,
  WhatIfSuccessResponse,
} from "@/lib/types";
import { WhatIfForm, type WhatIfFormState } from "./what-if-form";
import { WhatIfResult } from "./what-if-result";

/* ── Defaults: NVDA / COVID bottom / 5M KRW ── */

const DEFAULT_STATE: WhatIfFormState = {
  ticker: "NVDA",
  startDate: "2020-03-23",
  amount: 5_000_000,
  currency: "KRW",
  recurring: null,
};

/* ── URL <-> state helpers ── */

function parseRecurring(v: string | null): RecurringMode {
  if (v === "monthly" || v === "weekly") return v;
  return null;
}

function parseCurrency(v: string | null): "USD" | "KRW" {
  return v === "USD" ? "USD" : "KRW";
}

function stateFromSearchParams(
  sp: URLSearchParams,
): WhatIfFormState {
  // Accept both short keys (t/d/a/r/c) and legacy/descriptive keys
  // (ticker / start_date / amount / recurring / currency) so shared links
  // from older builds still hydrate the form correctly.
  const ticker = (sp.get("t") || sp.get("ticker") || "").toUpperCase();
  const startDate = sp.get("d") || sp.get("start_date") || "";
  const amountRaw = sp.get("a") ?? sp.get("amount");
  const amount = amountRaw ? Number(amountRaw) : NaN;
  const recurring = parseRecurring(sp.get("r") ?? sp.get("recurring"));
  const currency = parseCurrency(sp.get("c") ?? sp.get("currency"));

  if (!ticker || !startDate || !isFinite(amount) || amount <= 0) {
    return DEFAULT_STATE;
  }
  return { ticker, startDate, amount, currency, recurring };
}

function buildQuery(s: WhatIfFormState): string {
  const q = new URLSearchParams({
    t: s.ticker,
    d: s.startDate,
    a: String(s.amount),
    c: s.currency,
  });
  if (s.recurring) q.set("r", s.recurring);
  return q.toString();
}

/* ── SWR fetcher ── */

const fetcher = async (url: string): Promise<WhatIfResponse> => {
  // The SWR key embeds a cache-buster (`&_t=…`) so that clicking "Calculate"
  // with identical inputs still produces a new key and bypasses dedupe.
  // Strip it before hitting the backend — it's a client-only signal.
  let requestUrl = url;
  try {
    const u = new URL(url, typeof window !== "undefined" ? window.location.origin : "http://localhost");
    if (u.searchParams.has("_t")) {
      u.searchParams.delete("_t");
      requestUrl = u.pathname + (u.searchParams.toString() ? `?${u.searchParams.toString()}` : "");
    }
  } catch {
    // Fallback: regex strip
    requestUrl = url.replace(/([?&])_t=\d+(&|$)/, (_m, p1, p2) => (p2 === "&" ? p1 : ""))
      .replace(/[?&]$/, "");
  }
  const res = await fetch(requestUrl, { credentials: "include" });
  // Backend may return 200 with {success:false,...} OR non-2xx — handle both.
  const body = await res.json().catch(() => null);
  if (!body) {
    return {
      success: false,
      error_code: "DATA_UNAVAILABLE",
      message: "Could not parse response",
    };
  }
  return body as WhatIfResponse;
};

/* ── Component ── */

export function WhatIfClient() {
  const t = useT();
  const searchParams = useSearchParams();
  const resultAnchorRef = useRef<HTMLDivElement | null>(null);
  // Track whether the user (as opposed to first-paint hydration) triggered
  // the current request — we only auto-scroll in that case.
  const shouldScrollOnNextResultRef = useRef(false);

  // Bootstrap form state from URL (SSR + client hydration safe).
  const [form, setForm] = useState<WhatIfFormState>(() =>
    stateFromSearchParams(new URLSearchParams(searchParams?.toString() ?? "")),
  );
  // Query used as the SWR key. Changes only when "Calculate" is clicked
  // (or when the URL is edited externally — e.g. shared link).
  const [activeQuery, setActiveQuery] = useState<string | null>(() => {
    // Only fire the initial request if there were real params in the URL
    // OR the default scenario (we do want first-load WOW).
    const parsed = stateFromSearchParams(
      new URLSearchParams(searchParams?.toString() ?? ""),
    );
    return parsed ? buildQuery(parsed) : null;
  });

  /* React to external URL changes (e.g. user hits back button). */
  useEffect(() => {
    const qs = searchParams?.toString() ?? "";
    const next = stateFromSearchParams(new URLSearchParams(qs));
    // Only adopt if it differs — avoid loops. The setState is guarded by an
    // equality check so it won't cascade: prev === next short-circuits.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setForm((prev) => {
      const prevQ = buildQuery(prev);
      const nextQ = buildQuery(next);
      if (prevQ !== nextQ) {
        setActiveQuery(nextQ);
        return next;
      }
      return prev;
    });
  }, [searchParams]);

  /* ── Data fetch ── */

  const swrKey = useMemo(() => {
    if (!activeQuery) return null;
    const base = API.simulate.counterfactual({
      ticker: form.ticker,
      start_date: form.startDate,
      amount: form.amount,
      currency: form.currency,
      recurring: form.recurring,
    });
    // `activeQuery` may carry a `_t=…` cache-buster appended by onSubmit()
    // when the user re-submits identical inputs. Append it to the SWR key
    // so the key differs, bypassing dedupe — the fetcher then strips it
    // before calling the backend.
    const tMatch = activeQuery.match(/(?:^|&)_t=(\d+)/);
    if (!tMatch) return base;
    const sep = base.includes("?") ? "&" : "?";
    return `${base}${sep}_t=${tMatch[1]}`;
  }, [activeQuery, form]);

  const { data, error, isLoading, isValidating } = useSWR<WhatIfResponse>(
    swrKey,
    fetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      dedupingInterval: 60_000,
    },
  );

  /* ── Handlers ── */

  const onSubmit = useCallback(() => {
    if (!form.ticker || !form.startDate || form.amount <= 0) return;
    const q = buildQuery(form);
    shouldScrollOnNextResultRef.current = true;
    // Always trigger a re-fetch, even if the query string is identical
    // (force new SWR key via timestamp suffix that we strip in the fetcher).
    // Without this, clicking "Calculate" twice with the same inputs falls
    // inside SWR's 60s dedupingInterval and the result silently never
    // refreshes — which was the whole B7 symptom ("nothing happens").
    const keyed = `${q}&_t=${Date.now()}`;
    setActiveQuery(keyed);
    // Update the URL WITHOUT an App Router navigation. router.push triggers
    // an RSC roundtrip which, under certain edge conditions (auth guard,
    // middleware locale cookie set), was causing the page to bounce to /home
    // or /portfolio. history.replaceState is safe: it updates the bar only.
    // We omit `_t` from the visible URL — it's purely a client-side key.
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", `/simulator/what-if?${q}`);
    }
  }, [form]);

  /* ── Derived ── */

  const shareUrl = useMemo(() => {
    if (typeof window === "undefined") return "";
    if (!activeQuery) return `${window.location.origin}/simulator/what-if`;
    // Strip the client-side `_t=…` cache-buster from the shared URL so
    // recipients don't see (or preserve) a meaningless timestamp.
    const visible = activeQuery.replace(/(?:^|&)_t=\d+/, "").replace(/^&/, "");
    return `${window.location.origin}/simulator/what-if?${visible}`;
  }, [activeQuery]);

  const success: WhatIfSuccessResponse | null =
    data && data.success ? data : null;
  const apiError = data && !data.success ? data : null;

  const busy = isLoading || isValidating;

  /* When a user-initiated calculation completes, scroll the result into view.
     Without this, the result renders below the fold and the page appears
     "empty" — users were confused that nothing happened after "Calculate". */
  useEffect(() => {
    if (!success || busy) return;
    if (!shouldScrollOnNextResultRef.current) return;
    shouldScrollOnNextResultRef.current = false;
    const node = resultAnchorRef.current;
    if (!node) return;
    // Let the result's enter animation start, then align the top of the card
    // with the viewport. `block: "start"` keeps the form visible above the
    // fold when possible on larger screens.
    const id = window.setTimeout(() => {
      node.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 60);
    return () => window.clearTimeout(id);
  }, [success, busy]);

  return (
    <main
      className="min-h-[100dvh]"
      style={{ backgroundColor: "var(--pq-ink)" }}
    >
      {/* Top bar — Vantablack v3, ivory hairline border */}
      <header
        className="sticky top-0 z-30 border-b backdrop-blur"
        style={{
          backgroundColor: "rgba(5, 5, 5, 0.85)",
          borderColor: "rgba(245, 240, 232, 0.1)",
        }}
      >
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
          <Link
            href="/"
            className="flex items-center gap-2 text-sm font-medium"
            style={{ color: "var(--pq-ivory)" }}
          >
            <div
              className="h-6 w-6 rounded-sm"
              style={{ backgroundColor: "var(--pq-bronze)" }}
            />
            PivoxQuant
          </Link>
          <Link
            href="/signup"
            className="pq-ink-btn-bronze"
            style={{ height: "32px", padding: "0 14px", fontSize: "12px" }}
          >
            {t("common.signUp")}
            <ArrowUpRight className="h-3 w-3" />
          </Link>
        </div>
      </header>

      <div className="mx-auto w-full max-w-3xl px-4 pb-12 pt-6 sm:pt-10">
        {/* Hero — Editorial v3: Eyebrow kicker → Playfair italic H1 → ivory sub */}
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="mb-6 sm:mb-8"
        >
          <div className="pq-ink-kicker mb-3 inline-flex items-center gap-1.5">
            <Clock className="h-3 w-3" />
            {t("whatIf.badge")}
          </div>
          <h1 className="pq-ink-h1">{t("whatIf.hero")}</h1>
          <p
            className="mt-3 font-serif text-sm sm:text-base"
            style={{ color: "rgba(245, 240, 232, 0.65)" }}
          >
            {t("whatIf.sub")}
          </p>
        </motion.section>

        {/* Form */}
        <WhatIfForm
          value={form}
          onChange={setForm}
          onSubmit={onSubmit}
          isLoading={busy}
        />

        {/* Error surface — ink-themed, paper-blue (KR neg) framing */}
        {(error || apiError) && (
          <div
            className="mt-4 flex items-start gap-2 rounded-sm border px-4 py-3 text-xs"
            style={{
              borderColor: "rgba(122, 160, 200, 0.35)",
              backgroundColor: "rgba(122, 160, 200, 0.06)",
              color: "rgba(245, 240, 232, 0.85)",
            }}
          >
            <AlertCircle
              className="mt-0.5 h-4 w-4 shrink-0"
              style={{ color: "#7aa0c8" }}
            />
            <div className="min-w-0">
              <div className="font-medium" style={{ color: "var(--pq-ivory)" }}>
                {apiError?.error_code === "TICKER_NOT_FOUND"
                  ? t("whatIf.errors.notFound")
                  : apiError?.error_code === "DATE_BEFORE_LISTING"
                    ? t("whatIf.errors.beforeListing")
                    : apiError?.error_code === "DATE_IN_FUTURE"
                      ? t("whatIf.errors.futureDate")
                      : apiError?.error_code === "AMOUNT_OUT_OF_RANGE"
                        ? t("whatIf.errors.amountRange")
                        : apiError?.error_code === "DATA_UNAVAILABLE"
                          ? t("whatIf.errors.dataUnavailable")
                          : t("whatIf.errors.generic")}
              </div>
              {apiError?.suggestion?.value ? (
                <div
                  className="mt-1 text-[11px]"
                  style={{ color: "rgba(245, 240, 232, 0.55)" }}
                >
                  → {apiError.suggestion.reason || apiError.suggestion.value}
                </div>
              ) : null}
            </div>
          </div>
        )}

        {/* Result — anchored for smooth-scroll on calculate. */}
        <div ref={resultAnchorRef} className="relative">
          {success ? (
            <WhatIfResult data={success} shareUrl={shareUrl} tickerName={form.tickerName} />
          ) : busy ? (
            <div
              className="mt-6 h-96 animate-pulse rounded-sm border"
              style={{
                borderColor: "var(--pq-ivory-line)",
                backgroundColor: "rgba(255, 255, 255, 0.02)",
              }}
            />
          ) : null}
        </div>

        {/* Disclaimer — ink-themed, bronze-tinted */}
        <section
          className="mt-8 rounded-sm border px-4 py-3 text-[11px] leading-relaxed"
          style={{
            borderColor: "rgba(184, 149, 106, 0.18)",
            backgroundColor: "rgba(184, 149, 106, 0.04)",
            color: "rgba(245, 240, 232, 0.55)",
          }}
        >
          <div
            className="pq-ink-label mb-2"
            style={{ color: "var(--pq-bronze)" }}
          >
            {t("whatIf.disclaimer.title")}
          </div>
          <p>{t("whatIf.disclaimer.ko")}</p>
          <p
            className="mt-1 italic"
            style={{ color: "rgba(245, 240, 232, 0.4)" }}
          >
            {t("whatIf.disclaimer.en")}
          </p>
        </section>

        {/* Conversion CTA — sober ink panel, bronze accent (no white CTA) */}
        <section
          className="mt-8 overflow-hidden rounded-sm border p-6 sm:p-8"
          style={{
            borderColor: "rgba(184, 149, 106, 0.25)",
            backgroundColor: "rgba(255, 255, 255, 0.015)",
          }}
        >
          <h3
            className="font-serif italic text-lg sm:text-xl"
            style={{ color: "var(--pq-ivory)" }}
          >
            이 결과가 마음에 들었다면?
          </h3>
          <p
            className="mt-2 text-sm"
            style={{ color: "rgba(245, 240, 232, 0.6)" }}
          >
            PivoxQuant에서 AI 퀀트 시그널로 포트폴리오를 관리해보세요.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link href="/signup" className="pq-ink-btn-bronze">
              {t("common.getStarted")}
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
            <Link href="/" className="pq-ink-btn-ghost">
              {t("common.learnMore")}
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
