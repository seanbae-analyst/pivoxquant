"use client";

/**
 * /settings — Operational controls only.
 *
 * Slimmed 2026-04-24: identity / persona / Living CFO moved to /profile
 * so Settings stays scoped to things the user adjusts, not who they are.
 *
 * Surfaces here: Account (read-only), Subscription, Brokers, Preferences
 * (notifications + language + seed capital), Sign out, Delete account.
 */

import React, { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import useSWR from "swr";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { useBrokerConnections } from "@/lib/hooks";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { KisCard } from "@/components/broker/kis-card";
import { KisConnectModal } from "@/components/broker/kis-connect-modal";
import { AlpacaCard } from "@/components/broker/alpaca-card";
import { AlpacaConnectModal } from "@/components/broker/alpaca-connect-modal";

/**
 * 2026-04-27 (per CEO + legal): PivoxQuant operates Alpaca on a BYO
 * (Bring Your Own Key) model. Each user connects their OWN Alpaca paper
 * account; we forward read-only requests under the user's own license.
 * We do NOT redistribute Alpaca market data — no commercial-data-license
 * obligation on us. Surface gated by NEXT_PUBLIC_ALPACA_ENABLED so the
 * BYO flow can be enabled per-environment without code changes.
 */
const ALPACA_ENABLED = process.env.NEXT_PUBLIC_ALPACA_ENABLED === "1";
import { cn } from "@/lib/utils";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { ModalShell } from "@/components/ui/modal-shell";
import { useLocale } from "@/lib/locale";
import {
  isPushSupported,
  subscribeToPush,
  unsubscribeFromPush,
  getPushSubscription,
} from "@/lib/push";
import {
  LogOut,
  Trash2,
  Crown,
  AlertTriangle,
  X,
  Loader2,
  UserCircle2,
  ChevronRight,
} from "lucide-react";
import { fmtUsd, fmtKrw } from "@/lib/format";

/* ── Fetcher ── */

const fetcher = async (url: string) => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

interface SubscriptionResponse {
  tier: string;
  status: string;
  current_period_end?: string;
  cancel_at_period_end?: boolean;
}

/* ── Section shell ── */

function Section({
  kicker,
  title,
  children,
}: {
  kicker: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4">
      <header>
        <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
          {kicker}
        </div>
        <h2 className="mt-1 font-serif text-2xl text-[var(--pq-ivory)]">
          {title}
        </h2>
      </header>
      {children}
    </section>
  );
}

/* ── Row ── */

function Row({
  label,
  value,
  children,
}: {
  label: string;
  value?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-3 border-b border-[var(--pq-ivory-line-soft)] last:border-b-0">
      <span className="text-sm text-[rgba(245,240,232,0.6)]">{label}</span>
      <span className="text-sm text-[var(--pq-ivory)]">
        {children ?? value ?? "—"}
      </span>
    </div>
  );
}

/* ── Account (read-only) ── */

function AccountSection() {
  const { user } = useAuth();

  return (
    <Section kicker="01 · Account" title="Signed-in identity">
      <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 rounded-[2px]">
        <Row label="Name" value={user?.name ?? "—"} />
        <Row label="Email" value={user?.email ?? "—"} />
        {user?.oauth_provider && (
          <Row
            label="Login"
            value={
              <span className="capitalize">
                {user.oauth_provider === "kakao" ? "Kakao" : user.oauth_provider}
              </span>
            }
          />
        )}
      </div>

      <Link
        href="/profile"
        className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] px-5 py-4 rounded-[2px] flex items-center justify-between hover:border-[var(--pq-bronze)] transition-colors group"
      >
        <div className="flex items-center gap-3">
          <UserCircle2 className="h-4 w-4 text-[var(--pq-bronze)]" />
          <div>
            <div className="font-serif text-base text-[var(--pq-ivory)]">
              Manage profile &amp; persona
            </div>
            <div className="mt-0.5 text-xs text-[rgba(245,240,232,0.5)]">
              Identity, declared persona, Living CFO controls, agent memory.
            </div>
          </div>
        </div>
        <ChevronRight className="h-4 w-4 text-[var(--pq-bronze)] transition-transform group-hover:translate-x-0.5" />
      </Link>
    </Section>
  );
}

/* ── Seed capital ── */

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

function SeedCapitalSection() {
  const { user, refresh } = useAuth();
  const [usdInput, setUsdInput] = useState("");
  const [krwInput, setKrwInput] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
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
      toast.error("Enter USD or KRW seed capital.");
      return;
    }
    if (usd !== null && (usd < 0 || usd > MAX_SEED_CAPITAL)) {
      toast.error(`USD must be 0 – ${MAX_SEED_CAPITAL.toLocaleString()}.`);
      return;
    }
    if (krw !== null && (krw < 0 || krw > MAX_SEED_CAPITAL)) {
      toast.error(`KRW must be 0 – ${MAX_SEED_CAPITAL.toLocaleString()}.`);
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
      toast.success("Seed capital saved.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div id="capital" className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 rounded-[2px] scroll-mt-24">
      <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
        Seed capital · Analysis basis
      </div>
      <p className="mt-2 text-xs text-[rgba(245,240,232,0.5)]">
        Total investable capital used in signal sizing and portfolio analytics.
      </p>

      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <div className="text-pq-eyebrow tracking-[0.18em] uppercase text-[rgba(245,240,232,0.4)]">
            Current USD
          </div>
          <div className="mt-1 font-mono text-sm text-[var(--pq-ivory)] tabular-nums">
            {fmtUsd(user?.available_capital ?? 0)}
          </div>
        </div>
        <div>
          <div className="text-pq-eyebrow tracking-[0.18em] uppercase text-[rgba(245,240,232,0.4)]">
            Current KRW
          </div>
          <div className="mt-1 font-mono text-sm text-[var(--pq-ivory)] tabular-nums">
            {fmtKrw(user?.available_capital_krw ?? 0)}
          </div>
        </div>
      </div>

      <form onSubmit={handleSave} className="mt-5 space-y-3">
        <div>
          <label
            htmlFor="seed-usd"
            className="block text-pq-eyebrow tracking-[0.18em] uppercase text-[rgba(245,240,232,0.5)] mb-1"
          >
            USD
          </label>
          <input
            id="seed-usd"
            type="number"
            inputMode="decimal"
            min={0}
            max={MAX_SEED_CAPITAL}
            step="0.01"
            value={usdInput}
            onChange={(e) => setUsdInput(e.target.value)}
            placeholder="10000"
            className="pq-ink-input w-full tabular-nums"
          />
        </div>
        <div>
          <label
            htmlFor="seed-krw"
            className="block text-pq-eyebrow tracking-[0.18em] uppercase text-[rgba(245,240,232,0.5)] mb-1"
          >
            KRW
          </label>
          <input
            id="seed-krw"
            type="number"
            inputMode="numeric"
            min={0}
            max={MAX_SEED_CAPITAL}
            step="1"
            value={krwInput}
            onChange={(e) => setKrwInput(e.target.value)}
            placeholder="10000000"
            className="pq-ink-input w-full tabular-nums"
          />
        </div>
        <button
          type="submit"
          disabled={saving}
          className="pq-ink-btn-bronze w-full flex items-center justify-center gap-1.5 disabled:opacity-50"
        >
          {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {saving ? "Saving…" : "Save"}
        </button>
      </form>
    </div>
  );
}

/* ── Subscription ── */

function SubscriptionSection() {
  const { user } = useAuth();
  const { data: subData, isLoading } = useSWR<SubscriptionResponse>(
    API.billing.subscription,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 },
  );
  const tier = user?.subscription_tier || subData?.tier || "free";
  const isPaid = tier === "pro" || tier === "premium";

  return (
    <Section kicker="02 · Tier" title="Subscription">
      <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 rounded-[2px]">
        {isLoading ? (
          <div className="h-20 animate-pulse bg-[rgba(255,255,255,0.02)]" />
        ) : (
          <>
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)] flex items-center gap-1.5">
                  <Crown className="h-3 w-3" />
                  {tier} plan
                </div>
                <div className="mt-2 font-serif text-2xl text-[var(--pq-ivory)] capitalize">
                  {tier}
                </div>
              </div>
              {subData?.current_period_end && isPaid && (
                <div className="text-right">
                  <div className="text-pq-eyebrow tracking-[0.18em] uppercase text-[rgba(245,240,232,0.4)]">
                    {subData.cancel_at_period_end ? "Cancels" : "Renews"}
                  </div>
                  <div className="mt-1 text-sm text-[var(--pq-ivory)] tabular-nums">
                    {new Date(subData.current_period_end).toLocaleDateString()}
                  </div>
                </div>
              )}
            </div>

            <div className="mt-5 flex gap-2">
              {!isPaid ? (
                <Link href="/pricing" className="pq-ink-btn-bronze">
                  Upgrade to Pro / Premium
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      const r = await apiFetch<{ url: string }>(
                        API.billing.portal,
                        { method: "POST" },
                      );
                      if (r.url) window.location.href = r.url;
                    } catch {
                      toast.error("Could not open billing portal.");
                    }
                  }}
                  className="pq-ink-btn-ghost"
                >
                  Manage billing
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </Section>
  );
}

/* ── Brokers ── */

function BrokersSection() {
  const { data: brokerData, mutate: refreshBrokers } = useBrokerConnections();
  const [kisModalOpen, setKisModalOpen] = useState(false);
  const [kisSyncing, setKisSyncing] = useState(false);
  const [kisDisconnecting, setKisDisconnecting] = useState(false);
  const [alpacaModalOpen, setAlpacaModalOpen] = useState(false);
  const [alpacaSyncing, setAlpacaSyncing] = useState(false);
  const [alpacaDisconnecting, setAlpacaDisconnecting] = useState(false);

  const handleKisSync = useCallback(async () => {
    setKisSyncing(true);
    try {
      await apiFetch(API.broker.kisSync, { method: "POST" });
      await refreshBrokers();
      toast.success("KIS synchronized.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sync failed.");
    } finally {
      setKisSyncing(false);
    }
  }, [refreshBrokers]);

  const handleKisDisconnect = useCallback(async () => {
    if (!confirm("Disconnect KIS?")) return;
    setKisDisconnecting(true);
    try {
      await apiFetch(API.broker.kisDisconnect, { method: "DELETE" });
      await refreshBrokers();
      toast.success("KIS disconnected.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Disconnect failed.");
    } finally {
      setKisDisconnecting(false);
    }
  }, [refreshBrokers]);

  const handleAlpacaSync = useCallback(async () => {
    setAlpacaSyncing(true);
    try {
      await apiFetch(API.broker.alpacaSync, { method: "POST" });
      await refreshBrokers();
      toast.success("Alpaca synchronized.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sync failed.");
    } finally {
      setAlpacaSyncing(false);
    }
  }, [refreshBrokers]);

  const handleAlpacaDisconnect = useCallback(async () => {
    if (!confirm("Disconnect Alpaca?")) return;
    setAlpacaDisconnecting(true);
    try {
      await apiFetch(API.broker.alpacaDisconnect, { method: "DELETE" });
      await refreshBrokers();
      toast.success("Alpaca disconnected.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Disconnect failed.");
    } finally {
      setAlpacaDisconnecting(false);
    }
  }, [refreshBrokers]);

  return (
    <Section kicker="03 · Brokers" title="Connections">
      <KisCard
        connected={Boolean(brokerData?.kis_connected)}
        lastSync={brokerData?.kis_last_sync ?? null}
        onConnect={() => setKisModalOpen(true)}
        onSync={handleKisSync}
        onDisconnect={handleKisDisconnect}
        syncing={kisSyncing}
        disconnecting={kisDisconnecting}
      />

      {ALPACA_ENABLED && (
        <AlpacaCard
          connected={Boolean(brokerData?.alpaca_connected)}
          mode={brokerData?.alpaca_mode ?? "paper"}
          lastSync={brokerData?.alpaca_last_sync ?? null}
          onConnect={() => setAlpacaModalOpen(true)}
          onSync={handleAlpacaSync}
          onDisconnect={handleAlpacaDisconnect}
          syncing={alpacaSyncing}
          disconnecting={alpacaDisconnecting}
        />
      )}

      <p className="text-xs text-[rgba(245,240,232,0.4)] text-center">
        KIS is read-only. Live order routing is disabled.
      </p>

      {kisModalOpen && (
        <KisConnectModal
          onClose={() => setKisModalOpen(false)}
          onSuccess={() => refreshBrokers()}
        />
      )}
      {ALPACA_ENABLED && alpacaModalOpen && (
        <AlpacaConnectModal
          onClose={() => setAlpacaModalOpen(false)}
          onSuccess={() => refreshBrokers()}
        />
      )}
    </Section>
  );
}

/* ── Toggle ── */

function Toggle({
  checked,
  onChange,
  disabled,
  ariaLabel,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  ariaLabel: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors",
        checked ? "bg-[var(--pq-bronze)]" : "bg-[rgba(245,240,232,0.1)]",
        disabled && "opacity-40 cursor-not-allowed",
      )}
    >
      <span
        className={cn(
          "inline-block h-3.5 w-3.5 rounded-full bg-[var(--pq-ivory)] transition-transform",
          checked ? "translate-x-[18px]" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

/* ── Preferences (notifications + language + seed capital) ── */

function PreferencesSection() {
  const { locale, setLocale } = useLocale();
  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushSupported, setPushSupported] = useState(true);
  const [pushLoading, setPushLoading] = useState(false);
  const [emailEnabled, setEmailEnabled] = useState(false);
  // 정통망법 §50 — global + per-channel email opt-outs persisted server-side.
  // Toggles read OPT-OUT semantics; UI flips them so the user sees
  // "RECEIVE" semantics (checked = receiving).
  const [emailOptOut, setEmailOptOut] = useState(false);
  const [emailOptOutEarnings, setEmailOptOutEarnings] = useState(false);
  const [emailPrefSaving, setEmailPrefSaving] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const supported = isPushSupported();
    setPushSupported(supported);
    if (!supported) return;
    getPushSubscription()
      .then((s) => setPushEnabled(!!s))
      .catch(() => setPushEnabled(false));

    setEmailEnabled(window.localStorage.getItem("sp_mb_email") === "1");

    // Hydrate global + per-channel opt-out flags from /api/profile.
    apiFetch<{
      profile?: { email_opt_out?: boolean; email_opt_out_earnings?: boolean };
      email_opt_out?: boolean;
      email_opt_out_earnings?: boolean;
    }>(API.profile.get)
      .then((data) => {
        // Tolerate both top-level and nested shapes (the GET handler
        // returns the InvestmentProfile, but the User-level flags ride
        // on the auth context — which is hydrated separately. We try
        // both so the UI starts from the truth regardless of where
        // backend chooses to surface them.)
        const g = data?.email_opt_out ?? data?.profile?.email_opt_out;
        const e =
          data?.email_opt_out_earnings ?? data?.profile?.email_opt_out_earnings;
        if (typeof g === "boolean") setEmailOptOut(g);
        if (typeof e === "boolean") setEmailOptOutEarnings(e);
      })
      .catch(() => {
        // Best-effort hydrate; default-false matches server defaults.
      });
  }, []);

  const patchEmailPrefs = useCallback(
    async (patch: {
      email_opt_out?: boolean;
      email_opt_out_earnings?: boolean;
    }) => {
      setEmailPrefSaving(true);
      try {
        const resp = await apiFetch<{
          ok: boolean;
          preferences: {
            email_opt_out: boolean;
            email_opt_out_earnings: boolean;
          };
        }>(API.profile.emailPreferences, {
          method: "PATCH",
          body: JSON.stringify(patch),
        });
        setEmailOptOut(resp.preferences.email_opt_out);
        setEmailOptOutEarnings(resp.preferences.email_opt_out_earnings);
        toast.success("Email preferences saved.");
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : "Failed to save preferences.",
        );
      } finally {
        setEmailPrefSaving(false);
      }
    },
    [],
  );

  const handlePushToggle = async (next: boolean) => {
    if (!pushSupported) {
      toast.error("Push notifications not supported here.");
      return;
    }
    setPushLoading(true);
    try {
      if (next) {
        const sub = await subscribeToPush();
        if (!sub) {
          toast.error("Permission denied.");
          setPushEnabled(false);
          return;
        }
        setPushEnabled(true);
        toast.success("Push enabled.");
      } else {
        await unsubscribeFromPush();
        setPushEnabled(false);
        toast.success("Push disabled.");
      }
    } catch {
      toast.error("Could not update push.");
    } finally {
      setPushLoading(false);
    }
  };

  const handleEmailToggle = (next: boolean) => {
    setEmailEnabled(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("sp_mb_email", next ? "1" : "0");
    }
    toast.success(next ? "Email enabled." : "Email disabled.");
  };

  return (
    <Section kicker="04 · Preferences" title="Notifications & locale">
      <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 rounded-[2px] space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-serif text-base text-[var(--pq-ivory)]">
              Push notifications
            </div>
            <div className="mt-0.5 text-xs text-[rgba(245,240,232,0.5)]">
              Morning brief, signal changes, risk events.
            </div>
          </div>
          <Toggle
            checked={pushEnabled}
            onChange={handlePushToggle}
            disabled={pushLoading || !pushSupported}
            ariaLabel="Push"
          />
        </div>

        <div className="flex items-center justify-between pt-3 border-t border-[var(--pq-ivory-line-soft)]">
          <div>
            <div className="font-serif text-base text-[var(--pq-ivory)]">
              Email delivery
            </div>
            <div className="mt-0.5 text-xs text-[rgba(245,240,232,0.5)]">
              Artifacts and digests to your inbox.
            </div>
          </div>
          <Toggle
            checked={emailEnabled}
            onChange={handleEmailToggle}
            ariaLabel="Email"
          />
        </div>

        {/* 정통망법 §50 — global marketing email opt-out (server-backed). */}
        <div className="flex items-center justify-between pt-3 border-t border-[var(--pq-ivory-line-soft)]">
          <div>
            <div className="font-serif text-base text-[var(--pq-ivory)]">
              모든 마케팅 이메일 받지 않기
            </div>
            <div className="mt-0.5 text-xs text-[rgba(245,240,232,0.5)]">
              Globally unsubscribe from all email — required by 정통망법 §50.
            </div>
          </div>
          <Toggle
            checked={emailOptOut}
            onChange={(next) => patchEmailPrefs({ email_opt_out: next })}
            disabled={emailPrefSaving}
            ariaLabel="Global email opt-out"
          />
        </div>

        {/* Per-channel: earnings pre-brief opt-out. */}
        <div className="flex items-center justify-between pt-3 border-t border-[var(--pq-ivory-line-soft)]">
          <div>
            <div className="font-serif text-base text-[var(--pq-ivory)]">
              실적 발표 알림만 받지 않기
            </div>
            <div className="mt-0.5 text-xs text-[rgba(245,240,232,0.5)]">
              Mute time-sensitive earnings pre-briefs only — other emails
              continue.
            </div>
          </div>
          <Toggle
            checked={emailOptOutEarnings}
            onChange={(next) =>
              patchEmailPrefs({ email_opt_out_earnings: next })
            }
            disabled={emailPrefSaving}
            ariaLabel="Earnings pre-brief opt-out"
          />
        </div>
      </div>

      <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 rounded-[2px]">
        <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)] mb-3">
          Language
        </div>
        <div className="flex gap-2">
          {(["ko", "en"] as const).map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => {
                setLocale(l);
                toast.success("Language updated.");
              }}
              className={cn(
                locale === l ? "pq-ink-btn-bronze" : "pq-ink-btn-ghost",
              )}
            >
              {l === "ko" ? "한국어" : "English"}
            </button>
          ))}
        </div>
      </div>

      <SeedCapitalSection />
    </Section>
  );
}

/* ── Delete modal ── */

function DeleteAccountModal({ onClose }: { onClose: () => void }) {
  return (
    <ModalShell onClose={onClose} ariaLabel="Delete account">
      <div className="my-auto w-full max-w-md bg-[var(--pq-ink)] border border-[rgba(245,240,232,0.12)] p-6 rounded-[2px]">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-red-400" />
            <h3 className="font-serif text-xl text-[var(--pq-ivory)]">
              Delete account
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close delete account dialog"
            className="text-[rgba(245,240,232,0.5)] hover:text-[var(--pq-ivory)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="text-sm text-[rgba(245,240,232,0.6)] mb-6">
          Deletion is permanent and removes all positions, watchlists, and
          delivered artifacts. Email support to proceed.
        </p>
        <div className="flex items-center gap-3">
          <a
            href="mailto:support@pivoxquant.com?subject=Account%20Deletion%20Request"
            className="flex-1 pq-ink-btn-bronze text-center"
          >
            Contact support
          </a>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 pq-ink-btn-ghost"
          >
            Cancel
          </button>
        </div>
      </div>
    </ModalShell>
  );
}

/* ── Page ── */

export default function SettingsPageV1() {
  const router = useRouter();
  const { logout } = useAuth();
  const [signingOut, setSigningOut] = useState(false);
  const [showDelete, setShowDelete] = useState(false);

  const handleSignOut = useCallback(async () => {
    setSigningOut(true);
    try {
      await logout();
      router.replace("/");
    } catch {
      setSigningOut(false);
    }
  }, [logout, router]);

  return (
    <ErrorBoundary>
      <div className="space-y-10">
        {/* ── Header ── */}
        <header>
          <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
            Account · Preferences
          </div>
          <h1 className="mt-2 font-serif text-2xl md:text-3xl text-[var(--pq-ivory)]">
            Settings
          </h1>
          <p className="mt-1 text-xs text-[rgba(245,240,232,0.5)]">
            Subscription, brokers, and preferences. For identity and persona
            controls see{" "}
            <Link href="/profile" className="underline underline-offset-4 hover:text-[var(--pq-bronze)]">
              My Profile
            </Link>
            .
          </p>
        </header>

        <AccountSection />
        <SubscriptionSection />
        <BrokersSection />
        <PreferencesSection />

        {/* ── Danger zone ── */}
        <section className="pt-8 border-t border-[var(--pq-ivory-line)]">
          <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
            Danger zone
          </div>
          <div className="mt-4 flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              onClick={handleSignOut}
              disabled={signingOut}
              className="pq-ink-btn-ghost flex-1 inline-flex items-center justify-center gap-1.5 disabled:opacity-40"
            >
              <LogOut className="h-3.5 w-3.5" />
              {signingOut ? "Signing out…" : "Sign out"}
            </button>
            <button
              type="button"
              onClick={() => setShowDelete(true)}
              className="flex-1 inline-flex items-center justify-center gap-1.5 px-4 py-2 border border-red-500/30 text-red-400 text-xs tracking-[0.18em] uppercase hover:bg-red-500/10 transition-colors"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete account
            </button>
          </div>
        </section>
      </div>

      {showDelete && <DeleteAccountModal onClose={() => setShowDelete(false)} />}
    </ErrorBoundary>
  );
}
