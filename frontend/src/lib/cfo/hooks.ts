/**
 * Living CFO — Layer 2 client hooks.
 *
 * Placeholder SWR hooks and local-storage fallbacks for the "2 years in,
 * knows you better than you know yourself" personal-CFO layer. These
 * wire against endpoints that the backend dev will implement in Wave 3
 * (see endpoints.ts comments). Until then, each hook degrades gracefully
 * to a mocked payload + optimistic local-storage persistence so the
 * UI can be demoed end-to-end in dev.
 *
 * Endpoint contract (to be finalised with backend-dev):
 *   GET  /api/profile/persona           → PersonaResponse
 *   POST /api/profile/feedback          { artifact_id, section, vote }  → { ok: true }
 *   GET  /api/profile/pulse             → PulseResponse (history + next_due_at)
 *   POST /api/profile/pulse             PulseSubmission                 → { ok: true }
 *
 * All endpoints are prefixed under /api/profile/* to keep permissions
 * grouped with the existing Investment Profile surface.
 *
 * SWR cache keys use literal strings so existing keys are never shadowed.
 */

"use client";

import useSWR from "swr";
import { useCallback } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";

/* ═════════════ Types ═════════════ */

// Aligned to backend `services/profile/persona_analytics.PERSONA_CODES`
// (2026-04-23 QA sweep: frontend was 6 codes, backend was 8 — 4 personas
// (quant/speculator/daytrader/beginner) returned from API had no label
// mapping and fell back to the generic "Your personal CFO" string.
// This is the canonical 8-code set shared with
// `services/artifacts/persona_resolver.VALID_PERSONAS` and
// `reports/product/PERSONA_SPEC_2026-04-23.md` §PERSONA_CODES.
export type PersonaId =
  | "growth"
  | "value"
  | "balanced"
  | "income"
  | "quant"
  | "speculator"
  | "daytrader"
  | "beginner";

export interface PersonaScore {
  /** ISO date yyyy-mm-dd */
  date: string;
  /** Persona identifier for that window. */
  persona: PersonaId;
  /** 0–100 confidence score. */
  score: number;
}

export interface PersonaResponse {
  /** The user's self-declared persona (from onboarding). */
  declared: {
    persona: PersonaId;
    label: string;
    tagline: string;
    // 2026-09-29: `score` (25 + risk_tolerance*7) removed — scores are not
    // made; the declared side of declared-vs-observed is /mirror's.
  };
  /** Rolling-window observed persona series — 30 / 60 / 90 day. */
  observed: {
    window_30d: PersonaScore;
    window_60d: PersonaScore;
    window_90d: PersonaScore;
  };
  // 2026-09-29: `sparkline` (12 weekly persona scores) removed with the
  // /mirror PersonaEvolution chart — scores are not made.
  /** When the backend last re-classified. */
  last_computed_at: string | null;
  // 2026-09-29: `drift` (|declared score − observed score|) removed with the
  // declared score it was computed from.
}

export type FeedbackVote = "useful" | "meh" | "skip";

export interface FeedbackSubmission {
  artifact_id: string;
  /** Section or heading being rated. */
  section: string;
  vote: FeedbackVote;
}

export interface PulseEntry {
  /** ISO timestamp. */
  submitted_at: string;
  /** 1–5 Likert scale. */
  mood: number;
  /** 1–5 Likert scale. */
  confidence: number;
  /** Free-form worry. */
  worry: string;
  /** Chosen topic tags. */
  topics: string[];
  /** Free-form learning goal. */
  learn: string;
}

export interface PulseResponse {
  history: PulseEntry[];
  /** ISO timestamp of the next expected pulse. */
  next_due_at: string | null;
  /** Delivery cadence configured by the user. */
  cadence: "weekly" | "biweekly" | "monthly";
}

/* ═════════════ Local-storage fallback ═════════════ */

// ⚠️ persona/rolling/pulse bumped v1 → v2 on 2026-09-06, and the bump is the
// point of the change rather than housekeeping.
//
// Until that day `cfoFetch` answered a backend 404/5xx with fabricated data,
// and these hooks wrote whatever they received straight into localStorage. So
// any browser that loaded /profile or /portfolio while the backend was down is
// holding a cached payload that was never measured — `pq_cfo_persona_v1` with
// `_isMock: true` and persona "growth", `pq_cfo_rolling_v1` with `Math.sin`
// series. The old `_isMock` guard in `cachedPersonaId()` is gone with the mock
// factories, so on the next deploy those stale entries would have been read
// back as if real — and personalised pre-trade hints from them.
//
// A new key orphans them instead of trusting them. The cost is one refetch per
// user; the alternative is silently reviving invented data we just deleted the
// producer of. `feedback` keeps v1 — it never went through cfoFetch.
const LS_KEYS = {
  persona: "pq_cfo_persona_v2",
  feedback: "pq_cfo_feedback_v1",
  pulse: "pq_cfo_pulse_v2",
} as const;

function safeRead<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function safeWrite<T>(key: string, value: T): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* quota exceeded — drop silently */
  }
}

function nextMondayIso(): string {
  const d = new Date();
  const day = d.getUTCDay(); // 0=Sun .. 6=Sat
  const delta = (8 - day) % 7 || 7;
  d.setUTCDate(d.getUTCDate() + delta);
  d.setUTCHours(22, 0, 0, 0); // 07:00 KST = 22:00 prev day UTC
  return d.toISOString();
}

/* ═════════════ Fetcher ═════════════ */

/**
 * Plain authenticated read. Errors propagate to SWR's `error`.
 *
 * ⚠️ 2026-09-06 — this used to take a `fallback: () => T` and return
 * FABRICATED data whenever the backend answered 404, 501 or any 5xx:
 *
 *     if (err.status === 404 || err.status === 501 || err.status >= 500)
 *       return fallback();
 *
 * Three hooks used it — `usePersona`, `useRollingWindow` (removed 2026-09-29
 * with its widget), `usePulse` — and the mocks they fell back to were not
 * empty shells. `mockRolling` generated 30/60/90-day holding-period, turnover
 * and sector-tilt series from `Math.sin`, plus a declared-vs-observed
 * contrast, which `<RollingWindowWidget/>` rendered as "You declared X. Your
 * last 30 days look like Y." on /portfolio. Only
 * `mockPersona` carried an `_isMock` marker, and only /profile ever checked it,
 * so the other surfaces showed invented behavioural analysis with nothing
 * saying so.
 *
 * That is the worst possible failure for this product specifically: the whole
 * claim is that we only reflect the user's own record back and never score or
 * invent. A silent fabrication path contradicts the pitch more than an outage
 * does. Errors now surface as errors — "we cannot compute this right now" is a
 * true statement; an invented gap between the investor you declared and the
 * investor you are is not.
 *
 * Note what deliberately STAYS: each hook's `fallbackData` reads the
 * localStorage cache of that user's OWN last real response. Showing a stale
 * real number is categorically different from showing a synthesised one.
 */
async function cfoFetch<T>(url: string): Promise<T> {
  return apiFetch<T>(url);
}

/* ═════════════ Hooks ═════════════ */

/**
 * Synchronous, network-free read of the user's declared persona from the
 * localStorage cache that `usePersona()` maintains on every fetch.
 *
 * For surfaces that want persona-aware *tone* without owning a fetch —
 * e.g. the pre-trade deposition's per-persona question hints — issuing a
 * request from a sub-component would entangle it with SWR and break the
 * host modals' strict apiFetch call-count tests. Home/Profile/Reports all
 * call `usePersona()`, so in any real session this cache is already warm
 * by the time a trade modal opens. Returns `null` (callers fall back to
 * neutral copy) when the cache is cold.
 *
 * The old `_isMock` guard here is gone with the mock itself (2026-09-06):
 * the cache can now only ever hold a real backend response, so there is no
 * synthetic payload left to refuse to personalise from.
 */
export function cachedPersonaId(): PersonaId | null {
  const cached = safeRead<PersonaResponse>(LS_KEYS.persona);
  if (!cached) return null;
  return cached.declared?.persona ?? null;
}

/** Declared + observed persona (30 / 60 / 90 day). */
export function usePersona() {
  const swr = useSWR<PersonaResponse>(
    API.profile.persona,
    (url) => cfoFetch<PersonaResponse>(url),
    {
      revalidateOnFocus: false,
      dedupingInterval: 300_000,
      fallbackData: safeRead<PersonaResponse>(LS_KEYS.persona) ?? undefined,
    },
  );
  // Persist last known persona so the card never flashes empty on refresh.
  if (swr.data) safeWrite(LS_KEYS.persona, swr.data);
  return swr;
}

/** Section-level feedback recorder. */
export function useFeedback() {
  const submit = useCallback(async (payload: FeedbackSubmission) => {
    // Optimistic local capture — always write first so UI stays responsive
    // even when the backend endpoint is a 404.
    const existing = safeRead<FeedbackSubmission[]>(LS_KEYS.feedback) ?? [];
    existing.push(payload);
    safeWrite(LS_KEYS.feedback, existing.slice(-500));

    try {
      await apiFetch(API.profile.feedback, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      return { ok: true as const };
    } catch (err) {
      if (err instanceof ApiError && (err.status === 404 || err.status === 501)) {
        // Endpoint not live yet — local-only is fine.
        return { ok: true as const, pending_backend: true };
      }
      throw err;
    }
  }, []);

  return { submit };
}

/** Coerce a persisted/raw pulse blob to a valid shape, or `undefined` when it
 * is missing / corrupt / an older schema (no `history` array). Stops a stale
 * `pq_cfo_pulse_v1` snapshot from crashing `[...history]` spreads downstream
 * (same corruption class that already shipped a SHIP-BLOCKER in
 * living-cfo-status.tsx — fixed there at one consumer, here at the root). */
export function coercePulse(
  raw: PulseResponse | null | undefined,
): PulseResponse | undefined {
  if (!raw || !Array.isArray(raw.history)) return undefined;
  return raw;
}

/** Weekly pulse history + submission helper. */
export function usePulse() {
  const swr = useSWR<PulseResponse>(
    API.profile.pulse,
    (url) => cfoFetch<PulseResponse>(url),
    {
      revalidateOnFocus: false,
      dedupingInterval: 300_000,
      fallbackData: coercePulse(safeRead<PulseResponse>(LS_KEYS.pulse)),
    },
  );
  if (swr.data) safeWrite(LS_KEYS.pulse, swr.data);

  const submit = useCallback(
    async (entry: Omit<PulseEntry, "submitted_at">) => {
      const stamped: PulseEntry = {
        submitted_at: new Date().toISOString(),
        ...entry,
      };
      // Empty base for the optimistic write when nothing is cached yet.
      // This was `mockPulse()`, which — unlike the persona/rolling mocks that
      // were deleted with the fabricating fallback — only ever returned an
      // EMPTY history. Inlined rather than kept alive so no "mock" factory
      // survives in this file to be reached for again.
      const current: PulseResponse =
        coercePulse(swr.data) ?? {
          history: [],
          next_due_at: nextMondayIso(),
          cadence: "weekly",
        };
      const optimistic: PulseResponse = {
        ...current,
        history: [...current.history, stamped],
        next_due_at: bumpNextDueAt(current.cadence),
      };
      safeWrite(LS_KEYS.pulse, optimistic);
      await swr.mutate(optimistic, { revalidate: false });

      try {
        await apiFetch(API.profile.pulse, {
          method: "POST",
          body: JSON.stringify(stamped),
        });
      } catch (err) {
        if (err instanceof ApiError && (err.status === 404 || err.status === 501)) {
          return; // local-only success
        }
        // Roll back
        await swr.mutate(current, { revalidate: false });
        throw err;
      }
    },
    [swr],
  );

  return { ...swr, submit };
}

function bumpNextDueAt(cadence: PulseResponse["cadence"]): string {
  const days = cadence === "weekly" ? 7 : cadence === "biweekly" ? 14 : 30;
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString();
}

/* 2026-09-29 — removed (CEO: "유형 라벨·점수는 만들지 않는다"): the persona
 * surface-label helpers — PERSONA_TO_SURFACE, SURFACE_LABELS (성장형/균형형/
 * 수익형), SURFACE_TAGLINES, surfaceLabel, SURFACE_HIGHLIGHTS /
 * declaredSurfaceHighlights (dead — no consumer; its copy still promised
 * "Quant models matched to your profile"), DECLARED_TO_PERSONA,
 * declaredSurfaceLabel and PERSONA_LABELS. Their last consumer,
 * LivingCFOStatusBar, no longer names a type. The 8-code → 3-bucket collapse
 * lives on in the backend (persona_analytics) for internal grouping only. */

/* 2026-09-12 — removed with /profile: PERSONA_TAGLINES, surfaceTagline, the
 * Persona v2 detail / group-benchmark types, and usePersonaDetail /
 * usePersonaBenchmark / usePersonaBenchmarkAll. Their only consumers were the
 * deleted profile page, PersonaV2Card and PeerBenchmarkBlock. The backend
 * routes and the `API.profile.persona*` entries in endpoints.ts are untouched;
 * peer comparison has no UI by decision (2026-09-10). */
