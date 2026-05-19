"use client";

/**
 * <CapitalCardV2 />
 *
 * Section A3 of /settings v2 — Seed capital (USD + KRW) input card.
 *
 * 2026-05-20 (Wave 5-B SHIP-BLOCKER · feature_preservation fix):
 * V1 settings owned a "Seed capital" section (`SeedCapitalSection`) that
 * lets the user record the total investable capital used for signal
 * sizing + portfolio analytics. That section was dropped from the v2
 * editorial redesign, breaking the feature_preservation contract — a
 * user upgrading to v2 lost the ability to set or revise their seed
 * capital. This component restores parity: same backend wire
 * (`PUT /api/profile/capital`), same validation envelope, same toast
 * vocabulary. Visual layer matches the v2 card grammar (Vantablack +
 * Bronze hairline + Source Serif body + IBM Plex Mono digits) so it
 * slots cleanly into Section A alongside Identity + Sign-in providers.
 *
 * Wire-up
 * -------
 * Host (page-v2.tsx) renders this card inside `<section id="section-a">`.
 * The card owns its own form state + save handler (mirrors V1 pattern);
 * it reads `useAuth().user.available_capital{,_krw}` for the current
 * value and calls `useAuth().refresh()` after a successful save so the
 * rest of the dashboard sees the new number immediately.
 *
 * Legal: persona vocabulary only. No advice strings.
 */

import * as React from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { useT } from "@/lib/locale";
import { fmtUsd, fmtKrw } from "@/lib/format";

const MAX_SEED_CAPITAL = 1_000_000_000;

function parseCapitalInput(raw: string): number | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const n = Number(trimmed.replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
}

interface CapitalUpdateResponse {
  ok: boolean;
  available_capital: number;
  available_capital_krw: number;
}

const ROW_LABEL_STYLE: React.CSSProperties = {
  fontSize: "var(--pq-text-body)",
  color: "var(--pq-ivory)",
};
const ROW_HELP_STYLE: React.CSSProperties = {
  fontSize: "var(--pq-text-body)",
  color: "rgba(245,240,232,0.55)",
  marginTop: 2,
};
const ROW_VALUE_STYLE: React.CSSProperties = {
  fontVariantNumeric: "tabular-nums",
  fontSize: "var(--pq-text-body)",
  color: "rgba(245,240,232,0.82)",
};

export function CapitalCardV2() {
  const { user, refresh } = useAuth();
  const t = useT();

  const [usdInput, setUsdInput] = React.useState("");
  const [krwInput, setKrwInput] = React.useState("");
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    if (!user) return;
    setUsdInput(user.available_capital ? String(user.available_capital) : "");
    setKrwInput(
      user.available_capital_krw ? String(user.available_capital_krw) : "",
    );
  }, [user]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const usd = parseCapitalInput(usdInput);
    const krw = parseCapitalInput(krwInput);

    if (usd === null && krw === null) {
      toast.error(t("settingsV1.toast.seedRequired"));
      return;
    }
    if (usd !== null && (usd < 0 || usd > MAX_SEED_CAPITAL)) {
      toast.error(
        t("settingsV1.toast.seedRangeUsd", {
          max: MAX_SEED_CAPITAL.toLocaleString(),
        }),
      );
      return;
    }
    if (krw !== null && (krw < 0 || krw > MAX_SEED_CAPITAL)) {
      toast.error(
        t("settingsV1.toast.seedRangeKrw", {
          max: MAX_SEED_CAPITAL.toLocaleString(),
        }),
      );
      return;
    }

    setSaving(true);
    try {
      const body: Record<string, number> = {};
      if (usd !== null) body.available_capital_usd = usd;
      if (krw !== null) body.available_capital_krw = krw;
      await apiFetch<CapitalUpdateResponse>(API.profile.capital, {
        method: "POST",
        body: JSON.stringify(body),
      });
      await refresh();
      toast.success(t("settingsV1.toast.seedSaved"));
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : t("settingsV1.toast.seedFailed"),
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      id="capital"
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px solid var(--pq-ivory-line)",
        borderRadius: 4,
        padding: 24,
        position: "relative",
        scrollMarginTop: 96,
      }}
    >
      <span
        className="font-mono uppercase"
        style={{
          position: "absolute",
          top: 14,
          right: 14,
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.2em",
          color: "rgba(245,240,232,0.55)",
        }}
      >
        A3 · Seed capital
      </span>

      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 8,
        }}
      >
        Seed capital · Analysis basis
      </div>
      <p
        className="font-serif"
        style={{
          ...ROW_HELP_STYLE,
          marginTop: 0,
          marginBottom: 16,
        }}
      >
        Total investable capital used in signal sizing and portfolio
        analytics. USD or KRW — set either, or both.
      </p>

      {/* Current values */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: 12,
          padding: "0 0 16px",
          borderBottom: "1px solid var(--pq-ivory-line)",
        }}
      >
        <div>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.18em",
              color: "rgba(245,240,232,0.55)",
              marginBottom: 4,
            }}
          >
            Current USD
          </div>
          <div className="font-mono" style={ROW_VALUE_STYLE}>
            {fmtUsd(user?.available_capital ?? 0)}
          </div>
        </div>
        <div>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.18em",
              color: "rgba(245,240,232,0.55)",
              marginBottom: 4,
            }}
          >
            Current KRW
          </div>
          <div className="font-mono" style={ROW_VALUE_STYLE}>
            {fmtKrw(user?.available_capital_krw ?? 0)}
          </div>
        </div>
      </div>

      {/* Edit form */}
      <form
        onSubmit={handleSave}
        style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 16 }}
      >
        <div>
          <label
            htmlFor="seed-usd-v2"
            className="font-mono uppercase"
            style={{
              display: "block",
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.18em",
              color: "rgba(245,240,232,0.55)",
              marginBottom: 6,
            }}
          >
            USD
          </label>
          <input
            id="seed-usd-v2"
            type="number"
            inputMode="decimal"
            min={0}
            max={MAX_SEED_CAPITAL}
            step="0.01"
            value={usdInput}
            onChange={(e) => setUsdInput(e.target.value)}
            placeholder="10000"
            className="pq-ink-input w-full tabular-nums"
            style={ROW_LABEL_STYLE}
          />
        </div>
        <div>
          <label
            htmlFor="seed-krw-v2"
            className="font-mono uppercase"
            style={{
              display: "block",
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.18em",
              color: "rgba(245,240,232,0.55)",
              marginBottom: 6,
            }}
          >
            KRW
          </label>
          <input
            id="seed-krw-v2"
            type="number"
            inputMode="numeric"
            min={0}
            max={MAX_SEED_CAPITAL}
            step="1"
            value={krwInput}
            onChange={(e) => setKrwInput(e.target.value)}
            placeholder="10000000"
            className="pq-ink-input w-full tabular-nums"
            style={ROW_LABEL_STYLE}
          />
        </div>
        <button
          type="submit"
          disabled={saving}
          className="font-mono uppercase"
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            padding: "11px 20px",
            background: "var(--pq-bronze)",
            color: "var(--pq-ink, #050505)",
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.2em",
            borderRadius: 2,
            border: "none",
            cursor: saving ? "wait" : "pointer",
            opacity: saving ? 0.6 : 1,
          }}
        >
          {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {saving ? "Saving…" : "Save"}
        </button>
      </form>
    </div>
  );
}

export default CapitalCardV2;
