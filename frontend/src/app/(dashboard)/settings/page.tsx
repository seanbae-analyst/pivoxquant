"use client";

import React, { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import useSWR from "swr";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { useInvestmentProfile } from "@/lib/hooks";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { cn } from "@/lib/utils";
import { Skeleton, CardSkeleton } from "@/components/ui/loading-skeleton";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { ModalShell } from "@/components/ui/modal-shell";
import { useT, useLocale } from "@/lib/locale";
import {
  isPushSupported,
  subscribeToPush,
  unsubscribeFromPush,
  getPushSubscription,
} from "@/lib/push";
import {
  User,
  CreditCard,
  Link2,
  LogOut,
  Trash2,
  ChevronRight,
  Crown,
  AlertTriangle,
  X,
  Check,
  Loader2,
  Settings as SettingsIcon,
  Bell,
  Sunrise,
  Mail,
  MessageCircle,
} from "lucide-react";

/* ── Types ── */

interface SubscriptionResponse {
  tier: string;
  status: string;
  current_period_end?: string;
  cancel_at_period_end?: boolean;
}

/* ── Fetcher ── */

const fetcher = async (url: string) => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

/* ── Tabs ── */

const TAB_CONFIG: { id: string; labelKey: string; icon: React.ElementType }[] = [
  { id: "account", labelKey: "settings.tabs.account", icon: User },
  { id: "subscription", labelKey: "settings.tabs.subscription", icon: CreditCard },
  { id: "connections", labelKey: "settings.tabs.connections", icon: Link2 },
  { id: "notifications", labelKey: "settings.tabs.notifications", icon: Bell },
  { id: "language", labelKey: "settings.tabs.language", icon: SettingsIcon },
];

type TabId = "account" | "subscription" | "connections" | "notifications" | "language";

/* ── Investor Type Labels ── */

const INVESTOR_TYPE_LABELS: Record<string, string> = {
  passive_index_hugger: "패시브 인덱스 추종형",
  steady_accumulator: "꾸준한 축적형",
  value_hunter: "가치 투자형",
  risk_managed_growth: "리스크 관리 성장형",
  swing_trader: "스윙 트레이더",
  momentum_rider: "모멘텀 추종형",
  macro_rotator: "매크로 로테이션형",
  aggressive_scalper: "공격적 스캘퍼",
};

/* ── Delete Account Modal ── */

function DeleteAccountModal({ onClose }: { onClose: () => void }) {
  const t = useT();
  return (
    <ModalShell onClose={onClose} ariaLabel="Delete account">
      <div className="sp-card my-auto max-h-[calc(100dvh-1.5rem)] w-full max-w-sm overflow-y-auto p-5 sm:p-6 sm:max-h-[90vh]">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            <h3 className="text-lg font-bold text-slate-900">{t("settings.deleteAccountTitle")}</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="text-sm text-slate-600 mb-6">
          {t("settings.deleteAccountDesc")}
        </p>
        <div className="flex items-center gap-3">
          <a
            href="mailto:seanbae1521@gmail.com?subject=Account%20Deletion%20Request"
            className="flex-1 rounded-full bg-red-500 px-4 py-2.5 text-center text-sm font-semibold text-white transition-all hover:bg-red-600 active:scale-[0.97]"
          >
            {t("settings.contactSupport")}
          </a>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition-all hover:bg-slate-50 active:scale-[0.97]"
          >
            {t("settings.cancelBtn")}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}

/* ── Account Section ── */

function AccountSection() {
  const { user } = useAuth();
  const { data: profileData, isLoading: profileLoading } = useInvestmentProfile();
  const t = useT();
  const { locale } = useLocale();

  const joinedDate = user
    ? new Date().toLocaleDateString(locale === "ko" ? "ko-KR" : "en-US", { month: "long", year: "numeric" })
    : "";

  const investorType = profileData?.profile?.profile_type ?? null;

  return (
    <div className="space-y-4">
      <h2 className="text-base font-bold text-slate-900">{t("settings.account.title")}</h2>

      <div className="sp-card divide-y divide-slate-100">
        {/* Name */}
        <div className="flex items-center justify-between px-4 py-3.5">
          <span className="text-sm text-slate-500">{t("settings.account.name")}</span>
          <span className="text-sm font-semibold text-slate-900">
            {user?.name || "---"}
          </span>
        </div>

        {/* Email */}
        <div className="flex items-center justify-between px-4 py-3.5">
          <span className="text-sm text-slate-500">{t("settings.account.email")}</span>
          <span className="text-sm font-semibold text-slate-900">
            {user?.email || "---"}
          </span>
        </div>

        {/* Joined */}
        <div className="flex items-center justify-between px-4 py-3.5">
          <span className="text-sm text-slate-500">{t("settings.account.joined")}</span>
          <span className="text-sm font-medium text-slate-700">{joinedDate}</span>
        </div>

        {/* OAuth Provider */}
        {user?.oauth_provider && (
          <div className="flex items-center justify-between px-4 py-3.5">
            <span className="text-sm text-slate-500">{t("settings.account.loginMethod")}</span>
            <span className="text-sm font-medium text-slate-700 capitalize">
              {user.oauth_provider}
            </span>
          </div>
        )}

        {/* Investor Type */}
        <div className="flex items-center justify-between px-4 py-3.5">
          <span className="text-sm text-slate-500">{t("settings.account.investorType")}</span>
          {profileLoading ? (
            <Skeleton className="h-5 w-28" />
          ) : investorType ? (
            <span className="text-sm font-semibold text-purple-600">
              {INVESTOR_TYPE_LABELS[investorType] ?? investorType}
            </span>
          ) : (
            <span className="text-sm text-slate-400">{t("settings.account.notSet")}</span>
          )}
        </div>
      </div>

      {/* Retake Assessment */}
      <Link
        href="/onboarding"
        className="sp-card flex items-center justify-between px-4 py-3.5 group"
      >
        <div>
          <p className="text-sm font-semibold text-slate-900">
            {investorType ? t("settings.account.retakeAssessment") : t("settings.account.takeAssessment")}
          </p>
          <p className="text-xs text-slate-500 mt-0.5">
            {investorType
              ? t("settings.account.retakeSubtitle")
              : t("settings.account.takeSubtitle")}
          </p>
        </div>
        <ChevronRight className="h-4 w-4 text-slate-400 transition-transform group-hover:translate-x-0.5" />
      </Link>
    </div>
  );
}

/* ── Subscription Section ── */

function SubscriptionSection() {
  const { user } = useAuth();
  const { data: subData, isLoading } = useSWR<SubscriptionResponse>(
    API.billing.subscription,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 },
  );
  const t = useT();
  const { locale } = useLocale();

  // Prefer user.subscription_tier from auth (source of truth) over billing endpoint
  const tier = user?.subscription_tier || subData?.tier || "free";
  const isPro = tier === "pro";
  const isPremium = tier === "premium";
  const isPaid = isPro || isPremium;

  const dateLocale = locale === "ko" ? "ko-KR" : "en-US";

  return (
    <div className="space-y-4">
      <h2 className="text-base font-bold text-slate-900">{t("settings.subscription.title")}</h2>

      {isLoading ? (
        <CardSkeleton />
      ) : (
        <>
          <div className="sp-card p-5">
            <div className="flex items-center gap-3 mb-4">
              <div
                className={cn(
                  "flex h-10 w-10 items-center justify-center rounded-xl",
                  isPaid ? "bg-primary-gradient" : "bg-slate-100",
                )}
              >
                <Crown
                  className={cn(
                    "h-5 w-5",
                    isPaid ? "text-white" : "text-slate-400",
                  )}
                />
              </div>
              <div>
                <p className="text-sm font-bold text-slate-900">
                  {tier.charAt(0).toUpperCase() + tier.slice(1)} Plan
                </p>
                <p className="text-xs text-slate-500">
                  {isPaid
                    ? t("settings.subscription.activePlan")
                    : t("settings.subscription.freePlan")}
                </p>
              </div>
            </div>

            {subData?.current_period_end && isPaid && (
              <p className="text-xs text-slate-500 mb-4">
                {subData.cancel_at_period_end
                  ? `${t("settings.subscription.cancelsOn")}: ${new Date(subData.current_period_end).toLocaleDateString(dateLocale)}`
                  : `${t("settings.subscription.renewsOn")}: ${new Date(subData.current_period_end).toLocaleDateString(dateLocale)}`}
              </p>
            )}

            {!isPaid && (
              <Link
                href="/pricing"
                className="flex items-center justify-center gap-2 w-full rounded-full bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-slate-800 active:scale-[0.97]"
              >
                <Crown className="h-4 w-4" />
                {t("settings.subscription.upgradeToPro")}
              </Link>
            )}

            {isPaid && (
              <button
                type="button"
                onClick={async () => {
                  try {
                    const result = await apiFetch<{ url: string }>(
                      API.billing.portal,
                      { method: "POST" },
                    );
                    if (result.url) window.location.href = result.url;
                  } catch {
                    // silent
                  }
                }}
                className="w-full rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition-all hover:bg-slate-50 active:scale-[0.97]"
              >
                {t("settings.subscription.manage")}
              </button>
            )}
          </div>

          {/* Feature comparison teaser */}
          {!isPaid && (
            <div className="sp-card p-4">
              <p className="text-xs font-semibold text-slate-900 mb-3">
                {t("settings.subscription.proFeatures")}
              </p>
              <ul className="space-y-2">
                {[
                  t("settings.subscription.proFeaturesList.0"),
                  t("settings.subscription.proFeaturesList.1"),
                  t("settings.subscription.proFeaturesList.2"),
                  t("settings.subscription.proFeaturesList.3"),
                  t("settings.subscription.proFeaturesList.4"),
                ].map((feat) => (
                  <li
                    key={feat}
                    className="flex items-center gap-2 text-xs text-slate-600"
                  >
                    <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 shrink-0" />
                    {feat}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ── Connections Section ── */

function ConnectionsSection() {
  const [showAlpacaForm, setShowAlpacaForm] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected] = useState(false);
  const t = useT();

  const handleAlpacaConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim() || !apiSecret.trim()) {
      toast.error(t("settings.connections.alpacaCredentialsRequired"));
      return;
    }
    setConnecting(true);
    try {
      await apiFetch(API.broker.sync, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          broker: "alpaca",
          api_key: apiKey.trim(),
          api_secret: apiSecret.trim(),
        }),
      });
      setConnected(true);
      setShowAlpacaForm(false);
      setApiKey("");
      setApiSecret("");
      toast.success(t("settings.connections.alpacaConnectSuccess"));
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : t("settings.connections.alpacaConnectError");
      toast.error(message);
    } finally {
      setConnecting(false);
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-base font-bold text-slate-900">{t("settings.connections.title")}</h2>

      {/* Alpaca */}
      <div className="sp-card p-4">
        <div className="flex items-center gap-3 mb-3">
          <span className="text-lg" role="img" aria-label="US flag">
            &#x1F1FA;&#x1F1F8;
          </span>
          <div className="flex-1">
            <p className="text-sm font-semibold text-slate-900">Alpaca</p>
            <p className="text-xs text-slate-500">
              {t("settings.connections.alpacaDesc")}
            </p>
          </div>
          {connected ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-medium text-emerald-600">
              <Check className="h-3 w-3" />
              {t("settings.connections.connected")}
            </span>
          ) : (
            <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-500">
              {t("settings.connections.notConnected")}
            </span>
          )}
        </div>

        {!connected && !showAlpacaForm && (
          <button
            type="button"
            onClick={() => setShowAlpacaForm(true)}
            className="w-full rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition-all hover:bg-slate-50 active:scale-[0.97]"
          >
            {t("settings.connections.connectAlpaca")}
          </button>
        )}

        {!connected && showAlpacaForm && (
          <form onSubmit={handleAlpacaConnect} className="space-y-3">
            <div>
              <label
                htmlFor="alpaca-api-key"
                className="block text-xs font-medium text-slate-600 mb-1"
              >
                {t("settings.connections.apiKey")}
              </label>
              <input
                id="alpaca-api-key"
                type="text"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="PK..."
                autoComplete="off"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400 transition-colors"
              />
            </div>
            <div>
              <label
                htmlFor="alpaca-api-secret"
                className="block text-xs font-medium text-slate-600 mb-1"
              >
                {t("settings.connections.apiSecret")}
              </label>
              <input
                id="alpaca-api-secret"
                type="password"
                value={apiSecret}
                onChange={(e) => setApiSecret(e.target.value)}
                placeholder="••••••••"
                autoComplete="off"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400 transition-colors"
              />
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={connecting}
                className={cn(
                  "flex-1 flex items-center justify-center gap-2 rounded-full bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-slate-800 active:scale-[0.97]",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                )}
              >
                {connecting && (
                  <Loader2 className="h-4 w-4 animate-spin" />
                )}
                {connecting ? t("settings.connections.connecting") : t("settings.connections.connect")}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowAlpacaForm(false);
                  setApiKey("");
                  setApiSecret("");
                }}
                disabled={connecting}
                className="rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition-all hover:bg-slate-50 active:scale-[0.97] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t("settings.connections.cancel")}
              </button>
            </div>
          </form>
        )}
      </div>

      {/* KIS */}
      <div className="sp-card p-4 opacity-60">
        <div className="flex items-center gap-3 mb-3">
          <span className="text-lg" role="img" aria-label="KR flag">
            &#x1F1F0;&#x1F1F7;
          </span>
          <div className="flex-1">
            <p className="text-sm font-semibold text-slate-900">
              {t("settings.connections.kisName")}
            </p>
            <p className="text-xs text-slate-500">
              {t("settings.connections.kisDesc")}
            </p>
          </div>
          <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-500">
            {t("settings.connections.comingSoon")}
          </span>
        </div>
        <button
          type="button"
          disabled
          className="w-full rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-400 cursor-not-allowed"
        >
          {t("settings.connections.comingSoon")}
        </button>
      </div>

      <p className="text-xs text-slate-400 text-center pt-2">
        {t("settings.connections.brokerNote")}
      </p>
    </div>
  );
}

/* ── Notifications Section ── */

/** Common time options (KST) for the morning brief delivery. */
const TIME_OPTIONS = [
  { value: "06:00", label: "06:00" },
  { value: "07:00", label: "07:00" },
  { value: "08:00", label: "08:00" },
  { value: "09:00", label: "09:00" },
];

function TierBadge({ tier }: { tier: "pro" | "premium" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        tier === "premium"
          ? "bg-gradient-to-r from-purple-500 to-pink-500 text-white"
          : "bg-amber-100 text-amber-700",
      )}
    >
      <Crown className="h-2.5 w-2.5" />
      {tier}
    </span>
  );
}

function ToggleSwitch({
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
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors",
        checked ? "bg-purple-600" : "bg-slate-200",
        disabled && "opacity-50 cursor-not-allowed",
      )}
    >
      <span
        className={cn(
          "inline-block h-[18px] w-[18px] transform rounded-full bg-white shadow transition-transform",
          checked ? "translate-x-[22px]" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

function NotificationsSection() {
  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushSupported, setPushSupported] = useState(true);
  const [pushLoading, setPushLoading] = useState(false);
  const [time, setTime] = useState("06:00");
  const [emailEnabled, setEmailEnabled] = useState(false);
  const t = useT();

  // Get tier for gating
  const { data: subData } = useSWR<SubscriptionResponse>(
    API.billing.subscription,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 },
  );
  const tier = subData?.tier ?? "free";
  const isPro = tier === "pro" || tier === "premium";

  /* Initialize push state + saved time */
  useEffect(() => {
    if (typeof window === "undefined") return;
    const supported = isPushSupported();
    setPushSupported(supported);
    if (!supported) return;
    getPushSubscription()
      .then((sub) => setPushEnabled(!!sub))
      .catch(() => setPushEnabled(false));

    const savedTime = window.localStorage.getItem("sp_mb_time");
    if (savedTime) setTime(savedTime);

    const savedEmail = window.localStorage.getItem("sp_mb_email") === "1";
    setEmailEnabled(savedEmail);
  }, []);

  const handlePushToggle = async (next: boolean) => {
    if (!pushSupported) {
      toast.error(t("settings.notifications.notSupported"));
      return;
    }
    setPushLoading(true);
    try {
      if (next) {
        const sub = await subscribeToPush();
        if (!sub) {
          toast.error(t("settings.notifications.permissionDenied"));
          setPushEnabled(false);
          return;
        }
        setPushEnabled(true);
        toast.success(t("settings.notifications.pushEnabled"));
      } else {
        await unsubscribeFromPush();
        setPushEnabled(false);
        toast.success(t("settings.notifications.pushDisabled"));
      }
    } catch {
      toast.error(t("settings.notifications.pushError"));
    } finally {
      setPushLoading(false);
    }
  };

  const handleTimeChange = (value: string) => {
    setTime(value);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("sp_mb_time", value);
    }
    toast.success(t("settings.notifications.timeChanged"));
  };

  const handleEmailToggle = (next: boolean) => {
    if (!isPro) {
      toast.error(t("settings.notifications.emailProRequired"));
      return;
    }
    setEmailEnabled(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("sp_mb_email", next ? "1" : "0");
    }
    toast.success(next ? t("settings.notifications.emailEnabledSuccess") : t("settings.notifications.emailDisabledSuccess"));
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-bold text-slate-900">{t("settings.notifications.title")}</h2>
        <p className="mt-0.5 text-xs text-slate-500">
          {t("settings.notifications.subtitle")}
        </p>
      </div>

      {/* Morning Brief Push */}
      <div className="sp-card p-4">
        <div className="flex items-start gap-3">
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-orange-500"
            aria-hidden
          >
            <Sunrise className="h-5 w-5 text-white" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-900">
                  {t("settings.notifications.morningBriefTitle")}
                </p>
                <p className="mt-0.5 text-xs text-slate-500">
                  {t("settings.notifications.morningBriefDesc")}
                </p>
              </div>
              <ToggleSwitch
                checked={pushEnabled}
                onChange={handlePushToggle}
                disabled={pushLoading || !pushSupported}
                ariaLabel={t("settings.notifications.morningBriefTitle")}
              />
            </div>

            {!pushSupported && (
              <p className="mt-2 flex items-center gap-1.5 text-[11px] text-amber-600">
                <AlertTriangle className="h-3 w-3" />
                {t("settings.notifications.notSupported")}
              </p>
            )}

            {/* Time selector */}
            <div
              className={cn(
                "mt-3 border-t border-slate-100 pt-3 transition-opacity",
                !pushEnabled && "opacity-40",
              )}
            >
              <label
                htmlFor="mb-time-select"
                className="block text-xs font-medium text-slate-600"
              >
                {t("settings.notifications.timeLabel")}
              </label>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {TIME_OPTIONS.map((opt) => {
                  const active = time === opt.value;
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      disabled={!pushEnabled}
                      onClick={() => handleTimeChange(opt.value)}
                      className={cn(
                        "rounded-full px-3 py-1.5 text-xs font-semibold transition-colors tabular-nums",
                        active
                          ? "bg-slate-900 text-white"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200",
                        !pushEnabled && "cursor-not-allowed",
                      )}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>
              <p className="mt-2 text-[11px] text-slate-400">
                {t("settings.notifications.timeHelp")}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Email (Pro+) */}
      <div className={cn("sp-card p-4", !isPro && "bg-slate-50/30")}>
        <div className="flex items-start gap-3">
          <div
            className={cn(
              "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
              isPro ? "bg-blue-100" : "bg-slate-100",
            )}
            aria-hidden
          >
            <Mail
              className={cn(
                "h-5 w-5",
                isPro ? "text-blue-600" : "text-slate-400",
              )}
            />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-slate-900">
                    {t("settings.notifications.emailTitle")}
                  </p>
                  {!isPro && <TierBadge tier="pro" />}
                </div>
                <p className="mt-0.5 text-xs text-slate-500">
                  {isPro
                    ? t("morningBrief.noPositionsDesc")
                    : t("settings.notifications.emailDesc")}
                </p>
              </div>
              <ToggleSwitch
                checked={emailEnabled}
                onChange={handleEmailToggle}
                disabled={!isPro}
                ariaLabel={t("settings.notifications.emailTitle")}
              />
            </div>

            {!isPro && (
              <Link
                href="/pricing"
                className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-purple-700 hover:text-purple-800"
              >
                {t("settings.subscription.upgradeToPro")}
                <ChevronRight className="h-3 w-3" />
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Kakao (Premium, v2 — disabled) */}
      <div className="sp-card p-4 opacity-60">
        <div className="flex items-start gap-3">
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-yellow-100"
            aria-hidden
          >
            <MessageCircle className="h-5 w-5 text-yellow-600" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-slate-900">
                    {t("settings.notifications.kakaoTitle")}
                  </p>
                  <TierBadge tier="premium" />
                  <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500">
                    {t("settings.connections.comingSoon")}
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-slate-500">
                  {t("settings.notifications.kakaoDesc")}
                </p>
              </div>
              <ToggleSwitch
                checked={false}
                onChange={() => {}}
                disabled
                ariaLabel={t("settings.notifications.kakaoTitle")}
              />
            </div>
          </div>
        </div>
      </div>

      <p className="pt-2 text-center text-[11px] text-slate-400">
        {t("settings.notifications.dismissAnytime")}
      </p>
    </div>
  );
}

/* ── Language Section ── */

function LanguageSection() {
  const { locale, setLocale } = useLocale();
  const t = useT();

  const handleChange = (next: "ko" | "en") => {
    setLocale(next);
    toast.success(t("settings.language.saved"));
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-bold text-slate-900">{t("settings.language.title")}</h2>
        <p className="mt-0.5 text-xs text-slate-500">{t("settings.language.subtitle")}</p>
      </div>

      <div className="sp-card divide-y divide-slate-100">
        {/* Korean */}
        <button
          type="button"
          onClick={() => handleChange("ko")}
          className={cn(
            "flex w-full items-center justify-between px-4 py-3.5 transition-colors hover:bg-slate-50",
          )}
        >
          <div className="flex items-center gap-3">
            <span className="text-lg" role="img" aria-label="Korean flag">&#x1F1F0;&#x1F1F7;</span>
            <span className="text-sm font-medium text-slate-900">{t("settings.language.korean")}</span>
          </div>
          {locale === "ko" && (
            <Check className="h-4 w-4 text-emerald-500" />
          )}
        </button>

        {/* English */}
        <button
          type="button"
          onClick={() => handleChange("en")}
          className={cn(
            "flex w-full items-center justify-between px-4 py-3.5 transition-colors hover:bg-slate-50",
          )}
        >
          <div className="flex items-center gap-3">
            <span className="text-lg" role="img" aria-label="US flag">&#x1F1FA;&#x1F1F8;</span>
            <span className="text-sm font-medium text-slate-900">{t("settings.language.english")}</span>
          </div>
          {locale === "en" && (
            <Check className="h-4 w-4 text-emerald-500" />
          )}
        </button>
      </div>
    </div>
  );
}

/* ── Page ── */

export default function SettingsPage() {
  const router = useRouter();
  const { logout } = useAuth();
  const t = useT();
  const [activeTab, setActiveTab] = useState<TabId>("account");
  const [signingOut, setSigningOut] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);

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
      <div className="mx-auto max-w-3xl space-y-6">
        {/* ── Header ── */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100">
            <SettingsIcon className="h-5 w-5 text-slate-500" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">{t("settings.pageTitle")}</h1>
            <p className="text-sm text-slate-500">
              {t("settings.pageSubtitle")}
            </p>
          </div>
        </div>

        {/* ── Tab navigation ── */}
        <div className="flex gap-2 overflow-x-auto scrollbar-hide pb-1">
          {TAB_CONFIG.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id as TabId)}
                className={cn(
                  "filter-pill flex items-center gap-1.5 whitespace-nowrap",
                  isActive && "active",
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {t(tab.labelKey)}
              </button>
            );
          })}
        </div>

        {/* ── Tab content ── */}
        {activeTab === "account" && <AccountSection />}
        {activeTab === "subscription" && <SubscriptionSection />}
        {activeTab === "connections" && <ConnectionsSection />}
        {activeTab === "notifications" && <NotificationsSection />}
        {activeTab === "language" && <LanguageSection />}

        {/* ── Danger Zone ── */}
        <div className="space-y-3 pt-4 border-t border-slate-100">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            {t("settings.dangerZone")}
          </h2>

          <div className="flex flex-col gap-3 sm:flex-row">
            {/* Sign Out */}
            <button
              type="button"
              onClick={handleSignOut}
              disabled={signingOut}
              className={cn(
                "flex flex-1 items-center justify-center gap-2 rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold transition-all hover:bg-slate-50 active:scale-[0.97]",
                "text-slate-700 disabled:opacity-50 disabled:cursor-not-allowed",
              )}
            >
              <LogOut className="h-4 w-4" />
              {signingOut ? t("settings.signingOut") : t("settings.signOut")}
            </button>

            {/* Delete Account */}
            <button
              type="button"
              onClick={() => setShowDeleteModal(true)}
              className="flex flex-1 items-center justify-center gap-2 rounded-full border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-600 transition-all hover:bg-red-50 active:scale-[0.97]"
            >
              <Trash2 className="h-4 w-4" />
              {t("settings.deleteAccount")}
            </button>
          </div>
        </div>
      </div>

      {/* Delete Account Modal */}
      {showDeleteModal && (
        <DeleteAccountModal onClose={() => setShowDeleteModal(false)} />
      )}
    </ErrorBoundary>
  );
}
