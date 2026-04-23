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
      persona: "growth",
      label: "Growth CFO",
      tagline: "Hunts compounding revenue; tolerates drawdown for multi-year upside.",
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

/** Weekly pulse history + submission helper. */
export function usePulse() {
  const swr = useSWR<PulseResponse>(
    "/api/profile/pulse",
    (url) => cfoFetch<PulseResponse>(url, mockPulse),
    {
      revalidateOnFocus: false,
      dedupingInterval: 300_000,
      fallbackData: safeRead<PulseResponse>(LS_KEYS.pulse) ?? undefined,
    },
  );
  if (swr.data) safeWrite(LS_KEYS.pulse, swr.data);

  const submit = useCallback(
    async (entry: Omit<PulseEntry, "submitted_at">) => {
      const stamped: PulseEntry = {
        submitted_at: new Date().toISOString(),
        ...entry,
      };
      const current = swr.data ?? mockPulse();
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

/* ═════════════ Persona label helpers ═════════════ */

export const PERSONA_LABELS: Record<PersonaId, string> = {
  growth: "Growth CFO",
  value: "Value CFO",
  balanced: "Balanced CFO",
  income: "Income CFO",
  quant: "Quant CFO",
  speculator: "Speculator CFO",
  daytrader: "Daytrader CFO",
  beginner: "Beginner CFO",
};

export const PERSONA_TAGLINES: Record<PersonaId, string> = {
  growth: "내일의 승자를 오늘 담는다.",
  value: "시장이 틀렸다는 확신에 돈을 건다.",
  balanced: "극단이 아닌 일관성.",
  income: "월세처럼 들어오는 배당.",
  quant: "감이 아닌 검증된 엣지.",
  speculator: "큰 변동성에서만 큰 수익.",
  daytrader: "오늘 안에 답을 낸다.",
  beginner: "이해하지 못한 것에 돈을 걸지 않는다.",
};
