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
  const res = await fetch(url, { credentials: "include" });
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
    // Only adopt if it differs — avoid loops.
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
    return API.simulate.counterfactual({
      ticker: form.ticker,
      start_date: form.startDate,
      amount: form.amount,
      recurring: form.recurring,
    });
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
    // (force new SWR key via timestamp suffix that we strip in the fetcher key).
    setActiveQuery(q);
    // Update the URL WITHOUT an App Router navigation. router.push triggers
    // an RSC roundtrip which, under certain edge conditions (auth guard,
    // middleware locale cookie set), was causing the page to bounce to /home
    // or /portfolio. history.replaceState is safe: it updates the bar only.
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", `/simulator/what-if?${q}`);
    }
  }, [form]);

  /* ── Derived ── */

  const shareUrl = useMemo(() => {
    if (typeof window === "undefined") return "";
    if (!activeQuery) return `${window.location.origin}/simulator/what-if`;
    return `${window.location.origin}/simulator/what-if?${activeQuery}`;
  }, [activeQuery]);

  const success: WhatIfSuccessResponse | null =
    data && data.success ? data : null;
  const apiError = data && !data.success ? data : null;

  const busy = isLoading || isValidating;

  /* When a user-initiated calculation completes, scroll the result into view.
     Without this, the result renders below the fold and the page appears
     "empty" — users were confused that nothing happened after "Calculate". */
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
    <main className="min-h-[100dvh] bg-gradient-to-b from-white via-slate-50 to-white">
      {/* Top bar */}
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
          <Link
            href="/"
            className="flex items-center gap-2 text-sm font-bold text-slate-900"
          >
            <div className="h-6 w-6 rounded-lg bg-slate-900" />
            PivoxQuant
          </Link>
          <Link
            href="/signup"
            className="inline-flex h-8 items-center gap-1 rounded-full bg-slate-900 px-3.5 text-[11px] font-bold text-white transition hover:bg-slate-800"
          >
            {t("common.signUp")}
            <ArrowUpRight className="h-3 w-3" />
          </Link>
        </div>
      </header>

      <div className="mx-auto w-full max-w-3xl px-4 pb-12 pt-6 sm:pt-10">
        {/* Hero */}
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="mb-6 sm:mb-8"
        >
          <div className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-600">
            <Clock className="h-3 w-3" />
            {t("whatIf.badge")}
          </div>
          <h1 className="text-3xl font-bold leading-tight tracking-tight text-slate-900 sm:text-5xl">
            {t("whatIf.hero")}
          </h1>
          <p className="mt-2 text-sm text-slate-600 sm:text-base">
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

        {/* Error surface */}
        {(error || apiError) && (
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div className="min-w-0">
              <div className="font-semibold">
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
                <div className="mt-1 text-[11px] text-rose-600">
                  → {apiError.suggestion.reason || apiError.suggestion.value}
                </div>
              ) : null}
            </div>
          </div>
        )}

        {/* Result — anchored for smooth-scroll on calculate.
            The wrapper is a plain block so the result stays in normal
            document flow regardless of what <WhatIfResult> does internally. */}
        <div ref={resultAnchorRef} className="relative">
          {success ? (
            <WhatIfResult data={success} shareUrl={shareUrl} />
          ) : busy ? (
            <div className="mt-6 h-96 animate-pulse rounded-3xl border border-slate-200 bg-slate-50" />
          ) : null}
        </div>

        {/* Disclaimer */}
        <section className="mt-8 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-[11px] leading-relaxed text-slate-600">
          <div className="mb-1 font-semibold text-slate-700">
            {t("whatIf.disclaimer.title")}
          </div>
          <p>{t("whatIf.disclaimer.ko")}</p>
          <p className="mt-1 italic text-slate-500">
            {t("whatIf.disclaimer.en")}
          </p>
        </section>

        {/* Conversion CTA */}
        <section className="mt-8 overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-900 to-slate-800 p-6 text-white sm:p-8">
          <h3 className="text-lg font-bold sm:text-xl">
            이 결과가 마음에 들었다면?
          </h3>
          <p className="mt-1 text-sm text-slate-300">
            PivoxQuant에서 AI 퀀트 시그널로 포트폴리오를 관리해보세요.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link
              href="/signup"
              className="inline-flex h-10 items-center gap-1.5 rounded-full bg-white px-5 text-xs font-bold text-slate-900 transition hover:bg-slate-100"
            >
              {t("common.getStarted")}
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              href="/"
              className="inline-flex h-10 items-center rounded-full border border-white/20 px-5 text-xs font-bold text-white transition hover:bg-white/10"
            >
              {t("common.learnMore")}
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
