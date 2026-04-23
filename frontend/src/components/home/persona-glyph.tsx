/**
 * Persona glyph — subtle mono-font bronze mark shown next to the
 * persona label in the Today Hero eyebrow, PersonaCard header,
 * and the Persona Evolution title.
 *
 * The canonical persona dictionary in `lib/cfo/hooks.ts` exposes 6
 * personas. The product concept (spec §10) references 8 — growth /
 * value / balanced / income / quant / speculator / daytrader /
 * beginner. We never mutate the canonical PersonaId union (Iron
 * Rule: do not change existing hook APIs). Instead, we define a
 * local `NormalizedPersonaId` that extends the 6 with three
 * display-only aliases (`quant`, `speculator`, `daytrader`,
 * `beginner`) and provide a one-way `normalizedPersonaId()` that
 * maps any declared persona — including string subtypes the
 * backend might begin to emit — to the closest display id.
 *
 * Pure data + helpers. No React. Safe on the server.
 */

import type { PersonaId } from "@/lib/cfo/hooks";

export type NormalizedPersonaId =
  | "growth"
  | "value"
  | "balanced"
  | "income"
  | "quant"
  | "speculator"
  | "daytrader"
  | "beginner";

/** Mono glyph assigned to each persona. All are single-width
 *  characters so they don't perturb line-height. Intentionally no
 *  emoji — dossier tone only. */
export const PERSONA_GLYPHS: Record<NormalizedPersonaId, string> = {
  growth: "↗",
  value: "⌖",
  balanced: "◍",
  income: "₩",
  quant: "∑",
  speculator: "↯",
  daytrader: "⏱",
  beginner: "✧",
};

/**
 * Best-effort mapping from the canonical hook PersonaId (or a raw
 * backend string) to the 8-display id. Unknown values fall through
 * to the provided default (usually "balanced").
 */
export function normalizedPersonaId(
  raw: PersonaId | string | null | undefined,
  fallback: NormalizedPersonaId = "balanced",
): NormalizedPersonaId {
  if (!raw) return fallback;
  const key = String(raw).toLowerCase();
  switch (key) {
    // Direct passthrough (also covers the 6 canonical ids).
    case "growth":
    case "value":
    case "balanced":
    case "income":
    case "quant":
    case "speculator":
    case "daytrader":
    case "beginner":
      return key as NormalizedPersonaId;
    // Synonyms from `lib/cfo/hooks.ts` PersonaId union.
    case "momentum":
      return "speculator";
    case "conservative":
      return "income";
    // Onboarding questionnaire types (see settings.INVESTOR_TYPE_LABELS).
    case "passive_index_hugger":
    case "steady_accumulator":
      return "balanced";
    case "value_hunter":
      return "value";
    case "risk_managed_growth":
      return "growth";
    case "swing_trader":
    case "momentum_rider":
      return "speculator";
    case "macro_rotator":
      return "quant";
    case "aggressive_scalper":
      return "daytrader";
    default:
      return fallback;
  }
}

export function getPersonaGlyph(id: NormalizedPersonaId): string {
  return PERSONA_GLYPHS[id];
}
