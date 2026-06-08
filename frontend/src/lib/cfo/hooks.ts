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
 *   GET  /api/profile/rolling-window    → RollingWindowResponse
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
    score: number;
  };
  /** Rolling-window observed persona series — 30 / 60 / 90 day. */
  observed: {
    window_30d: PersonaScore;
    window_60d: PersonaScore;
    window_90d: PersonaScore;
  };
  /** Sparkline for the hero card — last 12 weekly snapshots. */
  sparkline: { week: string; score: number }[];
  /** When the backend last re-classified. */
  last_computed_at: string | null;
  /** Drift delta vs declared persona. 0–100; >20 = material drift. */
  drift: number;
  /**
   * True when this payload is local mock data (backend 404/5xx fallback).
   * UI surfaces a "sample data — switches to live after first trade" banner
   * when set. Real backend responses MUST omit this field (or set false).
   */
  _isMock?: boolean;
}

export interface RollingWindowPoint {
  /** ISO date yyyy-mm-dd */
  date: string;
  /** Average holding period in days. */
  holdingPeriod: number;
  /** Portfolio turnover ratio for the window (0–1). */
  turnover: number;
  /** Sector concentration tilt (Herfindahl index, 0–1). */
  sectorTilt: number;
}

export interface RollingWindowResponse {
  series: {
    window_30d: RollingWindowPoint[];
    window_60d: RollingWindowPoint[];
    window_90d: RollingWindowPoint[];
  };
  /** Cross-window comparison for the CFO-vs-actual headline. */
  contrast: {
    declared_persona: PersonaId;
    declared_score: number;
    observed_persona: PersonaId;
    observed_score: number;
    window_days: 30 | 60 | 90;
  };
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

const LS_KEYS = {
  persona: "pq_cfo_persona_v1",
  rolling: "pq_cfo_rolling_v1",
  feedback: "pq_cfo_feedback_v1",
  pulse: "pq_cfo_pulse_v1",
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

/* ═════════════ Mocked payloads (fallback until backend ships) ═════════════ */

function mockPersona(): PersonaResponse {
  return {
    declared: {
      // §101: even the offline mock must carry only a 3-bucket disclosed
      // surface label — never a CFO-style 8-label string.
      persona: "growth",
      label: surfaceLabel("growth"),
      tagline: surfaceTagline("growth"),
      score: 72,
    },
    observed: {
      window_30d: { date: isoToday(-30), persona: "balanced", score: 65 },
      window_60d: { date: isoToday(-60), persona: "growth", score: 69 },
      window_90d: { date: isoToday(-90), persona: "growth", score: 71 },
    },
    sparkline: Array.from({ length: 12 }, (_, i) => ({
      week: isoToday(-7 * (11 - i)),
      score: 62 + Math.round(Math.sin(i / 2) * 6) + (i >= 8 ? -5 : 0),
    })),
    last_computed_at: new Date().toISOString(),
    drift: 7,
    _isMock: true,
  };
}

function mockRolling(): RollingWindowResponse {
  const pts = (n: number): RollingWindowPoint[] =>
    Array.from({ length: n }, (_, i) => ({
      date: isoToday(-(n - i)),
      holdingPeriod: 18 + Math.round(Math.sin(i / 4) * 6),
      turnover: 0.18 + (Math.cos(i / 5) + 1) * 0.08,
      sectorTilt: 0.28 + Math.abs(Math.sin(i / 6)) * 0.12,
    }));
  return {
    series: {
      window_30d: pts(30),
      window_60d: pts(60),
      window_90d: pts(90),
    },
    contrast: {
      declared_persona: "growth",
      declared_score: 72,
      observed_persona: "balanced",
      observed_score: 65,
      window_days: 30,
    },
  };
}

function mockPulse(): PulseResponse {
  return {
    history: [],
    next_due_at: nextMondayIso(),
    cadence: "weekly",
  };
}

function isoToday(offsetDays: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

function nextMondayIso(): string {
  const d = new Date();
  const day = d.getUTCDay(); // 0=Sun .. 6=Sat
  const delta = (8 - day) % 7 || 7;
  d.setUTCDate(d.getUTCDate() + delta);
  d.setUTCHours(22, 0, 0, 0); // 07:00 KST = 22:00 prev day UTC
  return d.toISOString();
}

/* ═════════════ Fetcher — falls back to mock on any 404/5xx ═════════════ */

async function cfoFetch<T>(url: string, fallback: () => T): Promise<T> {
  try {
    return await apiFetch<T>(url);
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 501 || err.status >= 500)) {
      return fallback();
    }
    // 401 → bubble up so AuthGuard can redirect.
    throw err;
  }
}

/* ═════════════ Hooks ═════════════ */

/** Declared + observed persona, with rolling-window drift indicator. */
export function usePersona() {
  const swr = useSWR<PersonaResponse>(
    "/api/profile/persona",
    (url) => cfoFetch<PersonaResponse>(url, mockPersona),
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

/** 30 / 60 / 90 day behavioural vectors for the Rolling Window widget. */
export function useRollingWindow() {
  const swr = useSWR<RollingWindowResponse>(
    "/api/profile/rolling-window",
    (url) => cfoFetch<RollingWindowResponse>(url, mockRolling),
    {
      revalidateOnFocus: false,
      dedupingInterval: 300_000,
      fallbackData: safeRead<RollingWindowResponse>(LS_KEYS.rolling) ?? undefined,
    },
  );
  if (swr.data) safeWrite(LS_KEYS.rolling, swr.data);
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
      await apiFetch("/api/profile/feedback", {
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
function coercePulse(
  raw: PulseResponse | null | undefined,
): PulseResponse | undefined {
  if (!raw || !Array.isArray(raw.history)) return undefined;
  return raw;
}

/** Weekly pulse history + submission helper. */
export function usePulse() {
  const swr = useSWR<PulseResponse>(
    "/api/profile/pulse",
    (url) => cfoFetch<PulseResponse>(url, mockPulse),
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
      const current = coercePulse(swr.data) ?? mockPulse();
      const optimistic: PulseResponse = {
        ...current,
        history: [...current.history, stamped],
        next_due_at: bumpNextDueAt(current.cadence),
      };
      safeWrite(LS_KEYS.pulse, optimistic);
      await swr.mutate(optimistic, { revalidate: false });

      try {
        await apiFetch("/api/profile/pulse", {
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

/* ═════════════ Persona surface label helpers ═════════════
 *
 * §101 compliance (DECISIONS.md ✅확정): the engine keeps all 8 persona
 * codes (growth/value/balanced/income/quant/speculator/daytrader/beginner)
 * for internal grouping + peer-benchmark cohorts, but the user-facing
 * SURFACE must never name a short-horizon persona. Every disclosed label
 * collapses 8 codes → 3 buckets — mirrors backend
 * `services/profile/persona_analytics.PERSONA_TO_SURFACE`:
 *
 *   성장형 (Growth)   ← growth · value · speculator · daytrader
 *   균형형 (Balanced) ← balanced · quant · beginner
 *   수익형 (Income)   ← income
 *
 * `PERSONA_LABELS` / `PERSONA_TAGLINES` therefore map ALL 8 ids onto the
 * 3 disclosed strings — any code rendered through them surfaces one of
 * exactly three labels, so no caller can leak "Speculator"/"Daytrader".
 */

/** Bucket any 8-code persona id → one of 3 disclosed surface buckets. */
const PERSONA_TO_SURFACE: Record<PersonaId, "growth" | "balanced" | "income"> = {
  growth: "growth",
  value: "growth",
  speculator: "growth",
  daytrader: "growth",
  balanced: "balanced",
  quant: "balanced",
  beginner: "balanced",
  income: "income",
};

const SURFACE_LABELS: Record<"growth" | "balanced" | "income", string> = {
  growth: "성장형",
  balanced: "균형형",
  income: "수익형",
};

const SURFACE_TAGLINES: Record<"growth" | "balanced" | "income", string> = {
  growth: "변동을 감수하며 자산 성장을 지향하는 흐름.",
  balanced: "한쪽으로 치우치지 않는 일관된 흐름.",
  income: "꾸준한 현금흐름을 중심에 두는 흐름.",
};

/** Map any 8-code persona id → its 3-bucket disclosed Korean label. */
export function surfaceLabel(persona: PersonaId): string {
  return SURFACE_LABELS[PERSONA_TO_SURFACE[persona] ?? "balanced"];
}

/** Map any 8-code persona id → its 3-bucket disclosed tagline. */
export function surfaceTagline(persona: PersonaId): string {
  return SURFACE_TAGLINES[PERSONA_TO_SURFACE[persona] ?? "balanced"];
}

/**
 * Neutral, §101-safe result-screen body copy keyed by the 3 disclosed
 * surface buckets. Mirrors SURFACE_LABELS / SURFACE_TAGLINES so the
 * onboarding result screen can render tagline + features from the
 * collapsed bucket instead of a granular short-horizon persona's
 * description. No granular short-horizon vocabulary
 * (장중 / 스윙 / 스캘퍼 / 단타 / 실시간 신호 / 잦은 시도 / 투기) appears here —
 * these are 3 disclosed-bucket characterisations only.
 */
const SURFACE_HIGHLIGHTS: Record<
  "growth" | "balanced" | "income",
  { tagline: string; tagline_kr: string; features: string[]; features_kr: string[] }
> = {
  growth: {
    tagline: SURFACE_TAGLINES.growth,
    tagline_kr: SURFACE_TAGLINES.growth,
    features: [
      "Growth-oriented behavioural mirror",
      "Sector & concentration insight",
      "Quant models matched to your profile",
    ],
    features_kr: [
      "성장 지향 행동 거울",
      "섹터·집중도 인사이트",
      "프로필에 맞춘 퀀트 모델",
    ],
  },
  balanced: {
    tagline: SURFACE_TAGLINES.balanced,
    tagline_kr: SURFACE_TAGLINES.balanced,
    features: [
      "Balanced behavioural mirror",
      "Diversification & risk insight",
      "Quant models matched to your profile",
    ],
    features_kr: [
      "균형 잡힌 행동 거울",
      "분산·리스크 인사이트",
      "프로필에 맞춘 퀀트 모델",
    ],
  },
  income: {
    tagline: SURFACE_TAGLINES.income,
    tagline_kr: SURFACE_TAGLINES.income,
    features: [
      "Income-oriented behavioural mirror",
      "Cash-flow & stability insight",
      "Quant models matched to your profile",
    ],
    features_kr: [
      "현금흐름 지향 행동 거울",
      "안정성·현금흐름 인사이트",
      "프로필에 맞춘 퀀트 모델",
    ],
  },
};

export interface SurfaceHighlights {
  tagline: string;
  tagline_kr: string;
  features: string[];
  features_kr: string[];
}

/**
 * Map a raw declared `profile_type` string → its 3-bucket disclosed
 * tagline + features. Returns the 균형형 (balanced) neutral set as a hard
 * fallback for any unknown / empty code, so an unmapped persona can never
 * leak granular short-horizon body copy onto the result screen.
 */
export function declaredSurfaceHighlights(
  profileType: string | null | undefined,
): SurfaceHighlights {
  const code = profileType
    ? DECLARED_TO_PERSONA[profileType.toLowerCase()]
    : undefined;
  const surface = code ? PERSONA_TO_SURFACE[code] : undefined;
  return SURFACE_HIGHLIGHTS[surface ?? "balanced"];
}

/**
 * Map a raw declared `profile_type` column value → 8-code persona id.
 * Mirrors backend `persona_analytics.DECLARED_TO_PERSONA` so any surface
 * that only has the raw onboarding string can still collapse to 3 labels
 * instead of leaking a code like "swing_trader" / "aggressive_scalper".
 */
const DECLARED_TO_PERSONA: Record<string, PersonaId> = {
  // Legacy 4-tier
  conservative: "income",
  balanced: "balanced",
  growth: "growth",
  aggressive: "speculator",
  moderate: "beginner",
  // Questionnaire V2
  momentum_rider: "growth",
  value_hunter: "value",
  risk_managed_growth: "balanced",
  passive_index_hugger: "income",
  macro_rotator: "quant",
  swing_trader: "speculator",
  aggressive_scalper: "daytrader",
  steady_accumulator: "beginner",
  // Canonical persona codes (identity)
  value: "value",
  income: "income",
  quant: "quant",
  speculator: "speculator",
  daytrader: "daytrader",
  beginner: "beginner",
};

/**
 * Map a raw declared `profile_type` string → 3-bucket disclosed label.
 * Returns `null` for an unknown / empty profile_type so callers can keep
 * their own "not set" copy.
 */
export function declaredSurfaceLabel(
  profileType: string | null | undefined,
): string | null {
  if (!profileType) return null;
  const code = DECLARED_TO_PERSONA[profileType.toLowerCase()];
  if (!code) return null;
  return surfaceLabel(code);
}

export const PERSONA_LABELS: Record<PersonaId, string> = {
  growth: SURFACE_LABELS.growth,
  value: SURFACE_LABELS.growth,
  balanced: SURFACE_LABELS.balanced,
  income: SURFACE_LABELS.income,
  quant: SURFACE_LABELS.balanced,
  speculator: SURFACE_LABELS.growth,
  daytrader: SURFACE_LABELS.growth,
  beginner: SURFACE_LABELS.balanced,
};

export const PERSONA_TAGLINES: Record<PersonaId, string> = {
  growth: SURFACE_TAGLINES.growth,
  value: SURFACE_TAGLINES.growth,
  balanced: SURFACE_TAGLINES.balanced,
  income: SURFACE_TAGLINES.income,
  quant: SURFACE_TAGLINES.balanced,
  speculator: SURFACE_TAGLINES.growth,
  daytrader: SURFACE_TAGLINES.growth,
  beginner: SURFACE_TAGLINES.balanced,
};

/* ═════════════ Persona v2 (9-dim classifier) ═════════════
 * Mirrors the backend response shapes in:
 *   services/profile/persona_classifier_v2.classify_persona_multi
 *   services/profile/group_benchmark.get_persona_stats / get_all_persona_stats
 *
 * Wired to the profile page Identity section. All language is
 * *observational* — we never surface "recommend"/"advice" strings.
 */

/** 9 behavioural feature keys (load-bearing order — backend FEATURE_KEYS). */
export type PersonaFeatureKey =
  | "holding_period"
  | "turnover"
  | "sector_diversity"
  | "ticker_diversity"
  | "hold_variance"
  | "loss_cut_discipline"
  | "declared_risk"
  | "conviction_stability"
  | "feedback_engagement";

export interface PersonaBreakdownRow {
  feature: PersonaFeatureKey;
  /** Korean UI label from backend FEATURE_LABELS. */
  label: string;
  /** Observed value in [0, 1]. */
  value: number;
  /** Centroid value of the winning persona in [0, 1]. */
  centroid: number;
  /** 1 - |value - centroid| in [0, 1]. Higher = closer to centroid. */
  closeness: number;
  /** Weight used in the cosine — 0.45 .. 1.25. */
  weight: number;
}

export interface PersonaRankingEntry {
  persona: PersonaId;
  /** Similarity in (0, 1] — higher = closer. */
  similarity: number;
}

export interface PersonaDetailResponse {
  persona: PersonaId;
  label: string;
  tagline: string;
  /** 0..100 confidence in the top-1 persona classification. */
  confidence: number;
  window_days: number;
  /** True when observed trades < MIN_TRADES_FOR_OBSERVATION (10). */
  data_sparse: boolean;
  trade_count: number;
  features: Record<PersonaFeatureKey, number>;
  /** 1 if we had evidence for that feature, 0 if it defaulted to 0.5. */
  present: Record<PersonaFeatureKey, 0 | 1>;
  ranking: PersonaRankingEntry[];
  breakdown: PersonaBreakdownRow[];
  declared_persona: PersonaId | null;
  last_computed_at: string;
}

export interface PersonaExplainResponse {
  persona: PersonaId;
  label: string;
  confidence: number;
  breakdown: PersonaBreakdownRow[];
  features: Record<PersonaFeatureKey, number>;
}

/* ── Group benchmark ── */

export type PersonaBenchmarkWindow = 30 | 90 | 365;

export interface BenchmarkSectorShare {
  sector: string;
  /** Percent share, 0..100. */
  share: number;
}

export interface BenchmarkMistake {
  label: "disposition_effect" | "herding" | "anchoring" | string;
  count: number;
}

export interface BenchmarkStats {
  /** Median trade-level CAGR (%) across the group. */
  avg_cagr: number;
  avg_sharpe: number;
  median_holding_days: number;
  win_rate: number;
  max_drawdown_avg: number;
  most_held_sectors: BenchmarkSectorShare[];
  common_mistakes: BenchmarkMistake[];
  comparison_to_all: {
    avg_cagr_all: number | null;
    avg_sharpe_all: number | null;
    median_holding_days_all: number | null;
  };
  framing: string;
  persona: PersonaId;
  window_days: number;
}

export interface BenchmarkAvailable {
  available: true;
  persona: PersonaId;
  persona_label: string;
  window_days: number;
  stats: BenchmarkStats;
}

export interface BenchmarkUnavailable {
  available: false;
  reason: "insufficient_group_size" | "not_computed";
  persona: PersonaId;
  persona_label: string;
  window_days: number;
}

export type PersonaBenchmarkResponse = BenchmarkAvailable | BenchmarkUnavailable;

export interface PersonaBenchmarkAllResponse {
  window_days: number;
  personas: Record<
    PersonaId,
    | { available: true; label: string; stats: BenchmarkStats }
    | {
        available: false;
        label: string;
        reason: "insufficient_group_size" | "not_computed";
      }
  >;
}

/**
 * Fetch the 9-dim persona classification for the current user.
 *
 * Unlike the CFO hero-card `usePersona()`, this one does **not** fall
 * back to a mock — the backend endpoint is live (routes/profile.py).
 * A brand-new user with no trade history still gets a valid payload
 * with `data_sparse: true` from the backend, so the component can
 * render a "더 많은 거래가 필요합니다" hint instead of an error.
 */
export function usePersonaDetail(windowDays: number = 90) {
  return useSWR<PersonaDetailResponse>(
    API.profile.personaDetail(windowDays),
    (url) => apiFetch<PersonaDetailResponse>(url),
    {
      revalidateOnFocus: false,
      dedupingInterval: 300_000,
    },
  );
}

/**
 * Fetch the user's own-group anonymized benchmark.
 *
 * Returns `available: false` when the persona bucket is < 20 users
 * (legal floor enforced at the service layer). Never leaks individual
 * records — only sector-level aggregates and mistake-label counts.
 */
export function usePersonaBenchmark(windowDays: PersonaBenchmarkWindow = 90) {
  return useSWR<PersonaBenchmarkResponse>(
    API.profile.personaBenchmark(windowDays),
    (url) => apiFetch<PersonaBenchmarkResponse>(url),
    {
      revalidateOnFocus: false,
      dedupingInterval: 600_000,
    },
  );
}

/**
 * Fetch benchmark stats for every persona in parallel (cross-group view).
 * Suppressed personas return `available: false` with a reason.
 */
export function usePersonaBenchmarkAll(
  windowDays: PersonaBenchmarkWindow = 90,
) {
  return useSWR<PersonaBenchmarkAllResponse>(
    API.profile.personaBenchmarkAll(windowDays),
    (url) => apiFetch<PersonaBenchmarkAllResponse>(url),
    {
      revalidateOnFocus: false,
      dedupingInterval: 600_000,
    },
  );
}
