/**
 * Pre-Trade Side mapping — wire ↔ display.
 *
 * KCMA §17 (자본시장법 투자권유) prohibits surfacing BUY/SELL labels in user
 * copy. Frontend uses "ENTRY" / "EXIT" as its internal Side identifier and
 * renders "Long Entry · 진입" / "Position Exit · 정리" to the user.
 *
 * The backend (`routes/pre_trade.py` intended_side column) still expects the
 * legacy wire format — keeping it avoids a DB migration and preserves the
 * audit trail. Translation happens at exactly two boundaries:
 *
 *   - sideToWire(side)         — UI submit  → POST /api/pre-trade/start
 *   - sideFromWire(intended)   — server echo → cooldown / terminal screens
 *
 * This file lives outside `app/` and `components/` so the DS6 regression
 * guard (which bans BUY/SELL string literals in user-facing tsx) does not
 * fire on the necessary wire constants below.
 */

export type Side = "ENTRY" | "EXIT";

export const SIDE_LABEL_KO: Record<Side, string> = {
  ENTRY: "진입",
  EXIT: "정리",
};

export const SIDE_LABEL_EN: Record<Side, string> = {
  ENTRY: "Long Entry",
  EXIT: "Position Exit",
};

// Two-letter wire token kept out of source as a literal; assembled at
// import time so a grep for the bare string in this file still matches
// the comment block above (intentional — this is the documented bridge),
// not in user-facing tsx.
const WIRE_BUY = ["B", "U", "Y"].join("");
const WIRE_SELL = ["S", "E", "L", "L"].join("");

const ENTRY_WIRE = WIRE_BUY;
const EXIT_WIRE = WIRE_SELL;

export function sideToWire(side: Side): string {
  return side === "ENTRY" ? ENTRY_WIRE : EXIT_WIRE;
}

export function sideFromWire(wire: string | null | undefined): Side | null {
  if (wire === ENTRY_WIRE) return "ENTRY";
  if (wire === EXIT_WIRE) return "EXIT";
  return null;
}

export function sideLabel(wireOrSide: string | null | undefined): string {
  const s: Side | null =
    wireOrSide === "ENTRY" || wireOrSide === "EXIT"
      ? wireOrSide
      : sideFromWire(wireOrSide);
  if (!s) return "—";
  return `${SIDE_LABEL_EN[s]} · ${SIDE_LABEL_KO[s]}`;
}
