/**
 * Personal Journal Companion — Closed Beta client hooks.
 *
 * Reflective-only agent surface. Three operating principles baked in:
 *   1. Remember — recall what the user has already written
 *   2. Mirror   — reflect patterns back, no forward prediction
 *   3. Question — ask, don't advise
 *
 * Scope-separated from `lib/cfo/hooks.ts` on purpose. Living CFO is a
 * passive observation layer; Companion is an interactive chat layer.
 * Mixing their caches risks cross-contamination of optimistic state.
 *
 * Backend contract (see reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §6):
 *   GET  /api/agent/status    → AgentStatusResponse
 *   POST /api/agent/query     { message } → AgentResponse
 *   POST /api/agent/waitlist  { email }   → { ok: true }
 *
 * PIPA minimization: chat history is **local-first** — persisted in
 * localStorage, never auto-synced to the server. Explicit opt-in would
 * be required for server mirroring (not in this release).
 *
 * Kill switch: when `status.enabled === false`, callers MUST lock out
 * the UI and surface the Closed-Beta waitlist affordance instead.
 */

"use client";

import useSWR from "swr";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";

/* ─── Types ───────────────────────────────────────────────────────── */

/** Backend Gate verdict after legal pre/post filtering. */
export type GateVerdict =
  | "allowed"
  | "reframed"
  | "refused_advice"
  | "refused_prediction"
  | "refused_guarantee"
  | "refused_other";

/** One POST /api/agent/query turn. */
export interface AgentResponse {
  text: string;
  gate_verdict: GateVerdict;
  request_id: string;
  disclaimer: string;
}

/** GET /api/agent/status — kill-switch + entitlement gate. */
export interface AgentStatusResponse {
  enabled: boolean;
  phase: "closed_beta" | "internal" | "rolling_ga" | "ga";
  legal_status: "experimental" | "licensed" | "unlicensed";
  entitlement_plans: string[]; // e.g. ["premium_plus", "founding_lifetime"]
  rate_limit?: {
    per_minute: number;
    per_day: number;
  } | null;
}

/** Local chat row. `id` is client-generated; `request_id` comes from server. */
export interface CompanionMessage {
  id: string;
  role: "user" | "agent";
  text: string;
  ts: number; // epoch ms
  gate_verdict?: GateVerdict;
  request_id?: string;
  // Transient UX state — not persisted
  pending?: boolean;
  error?: string;
}

/* ─── localStorage (local-first) ──────────────────────────────────── */

const LS_KEY_HISTORY = "pq_companion_history_v1";
const LS_KEY_DISCLAIMER_ACK = "pq_companion_disclaimer_ack_v1";
/** Versioned so a schema change invalidates old data cleanly. */
const HISTORY_VERSION = 1;
/** Cap persisted history to stop localStorage bloat. Oldest is trimmed. */
const HISTORY_MAX = 120;

interface StoredHistory {
  v: number;
  messages: CompanionMessage[];
}

function readHistory(): CompanionMessage[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(LS_KEY_HISTORY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as StoredHistory;
    if (parsed.v !== HISTORY_VERSION) return [];
    return Array.isArray(parsed.messages) ? parsed.messages : [];
  } catch {
    return [];
  }
}

function writeHistory(messages: CompanionMessage[]): void {
  if (typeof window === "undefined") return;
  try {
    const trimmed = messages.slice(-HISTORY_MAX).map((m) => ({
      ...m,
      // Never persist transient flags
      pending: undefined,
      error: undefined,
    }));
    const payload: StoredHistory = { v: HISTORY_VERSION, messages: trimmed };
    window.localStorage.setItem(LS_KEY_HISTORY, JSON.stringify(payload));
  } catch {
    /* quota exceeded — silent */
  }
}

/* ─── Hooks ───────────────────────────────────────────────────────── */

/**
 * Status + kill-switch. 5-minute dedupe; short enough that flipping
 * AGENT_ENABLED=false drains from the UI within a session.
 */
export function useCompanionStatus() {
  return useSWR<AgentStatusResponse>(
    API.agent.status,
    async (url) => {
      try {
        return await apiFetch<AgentStatusResponse>(url);
      } catch (err) {
        // Treat missing endpoint as a conservative "disabled" so the UI
        // falls through to the Closed-Beta waitlist state rather than
        // crashing or showing a broken chat.
        if (err instanceof ApiError && (err.status === 404 || err.status === 501)) {
          return {
            enabled: false,
            phase: "closed_beta",
            legal_status: "experimental",
            entitlement_plans: ["premium_plus", "founding_lifetime"],
            rate_limit: null,
          } as AgentStatusResponse;
        }
        throw err;
      }
    },
    {
      revalidateOnFocus: false,
      dedupingInterval: 300_000,
    },
  );
}

/**
 * localStorage-backed conversation history. Server-side persistence is
 * deliberately out of scope for this release (PIPA minimization).
 *
 * Returns the message list + mutators. Changes to messages are flushed
 * to localStorage synchronously so a hard refresh never drops a turn.
 */
export function useCompanionHistory() {
  const [messages, setMessages] = useState<CompanionMessage[]>([]);

  // Hydrate on mount (client-only to avoid SSR mismatch).
  useEffect(() => {
    setMessages(readHistory());
  }, []);

  const append = useCallback((msg: CompanionMessage) => {
    setMessages((prev) => {
      const next = [...prev, msg];
      writeHistory(next);
      return next;
    });
  }, []);

  const update = useCallback((id: string, patch: Partial<CompanionMessage>) => {
    setMessages((prev) => {
      const next = prev.map((m) => (m.id === id ? { ...m, ...patch } : m));
      writeHistory(next);
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    setMessages([]);
    if (typeof window !== "undefined") {
      try {
        window.localStorage.removeItem(LS_KEY_HISTORY);
      } catch {
        /* noop */
      }
    }
  }, []);

  return { messages, append, update, clear };
}

/**
 * POST /api/agent/query — single turn. Caller owns the local history.
 *
 * Errors surface as ApiError (401/403/429/5xx). The chat panel is
 * responsible for mapping those to UI states (rate-limit countdown,
 * entitlement denial, soft reframe).
 */
export async function sendMessage(message: string, signal?: AbortSignal): Promise<AgentResponse> {
  return apiFetch<AgentResponse>(API.agent.query, {
    method: "POST",
    body: JSON.stringify({ message }),
    signal,
  });
}

/* ─── Entitlement helper ──────────────────────────────────────────── */

/**
 * Returns true when `subscription_tier` is allowed into the Closed Beta.
 * Defaults to ["premium_plus", "founding_lifetime"] when status is not
 * available yet (conservative; fails closed).
 */
export function hasCompanionEntitlement(
  subscriptionTier: string | null | undefined,
  entitlementPlans?: string[],
): boolean {
  if (!subscriptionTier) return false;
  const allowed = entitlementPlans && entitlementPlans.length > 0
    ? entitlementPlans
    : ["premium_plus", "founding_lifetime"];
  return allowed.includes(subscriptionTier.toLowerCase());
}

/* ─── Disclaimer ack (session-start banner) ───────────────────────── */

export function useDisclaimerAck(): {
  acknowledged: boolean;
  acknowledge: () => void;
} {
  const [acknowledged, setAcknowledged] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      setAcknowledged(window.localStorage.getItem(LS_KEY_DISCLAIMER_ACK) === "1");
    } catch {
      setAcknowledged(false);
    }
  }, []);
  const acknowledge = useCallback(() => {
    setAcknowledged(true);
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(LS_KEY_DISCLAIMER_ACK, "1");
      } catch {
        /* noop */
      }
    }
  }, []);
  return { acknowledged, acknowledge };
}
