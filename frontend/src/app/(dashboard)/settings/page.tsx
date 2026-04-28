"use client";

/**
 * /settings — feature-flag toggle between v1 and v2.
 *
 * v1 (default) preserves the legacy operations page (Account / Subscription /
 * Brokers / Preferences / Danger zone).
 *
 * v2 (NEXT_PUBLIC_SETTINGS_V2=true) is the editorial "CFO room dials" layout —
 * 5 sections (A Identity · B Brokers · C Notifications · D Subscription ·
 * E Privacy) with sticky anchor rail. Mirrors the home-v2 / portfolio-v2 /
 * risk-v2 toggle pattern.
 *
 * No banned UI strings. POSITIVE / NEGATIVE / NEUTRAL only — never BUY/SELL.
 */

import V1 from "./_v1/page-v1";
import V2 from "./_v2/page-v2";

export default function SettingsPage() {
  const v2Enabled = process.env.NEXT_PUBLIC_SETTINGS_V2 === "true";
  return v2Enabled ? <V2 /> : <V1 />;
}
