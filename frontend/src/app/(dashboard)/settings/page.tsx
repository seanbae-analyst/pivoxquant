"use client";

import { useState, useCallback, useEffect } from "react";
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

const TABS = [
  { id: "account", label: "계정", icon: User },
  { id: "subscription", label: "구독", icon: CreditCard },
  { id: "connections", label: "연동", icon: Link2 },
  { id: "notifications", label: "알림", icon: Bell },
] as const;

type TabId = (typeof TABS)[number]["id"];

/* ── Delete Account Modal ── */

function DeleteAccountModal({ onClose }: { onClose: () => void }) {
  return (
    <ModalShell onClose={onClose} ariaLabel="Delete account">
      <div className="sp-card my-auto max-h-[calc(100dvh-1.5rem)] w-full max-w-sm overflow-y-auto p-5 sm:p-6 sm:max-h-[90vh]">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            <h3 className="text-lg font-bold text-slate-900">계정 삭제</h3>
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
          앱에서 직접 계정 삭제는 현재 지원되지 않습니다. 삭제를 원하시면 고객지원에 문의해 주세요.
        </p>
        <div className="flex items-center gap-3">
          <a
            href="mailto:seanbae1521@gmail.com?subject=Account%20Deletion%20Request"
            className="flex-1 rounded-full bg-red-500 px-4 py-2.5 text-center text-sm font-semibold text-white transition-all hover:bg-red-600 active:scale-[0.97]"
          >
            고객지원 문의
          </a>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition-all hover:bg-slate-50 active:scale-[0.97]"
          >
            취소
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

  const joinedDate = user
    ? new Date().toLocaleDateString("ko-KR", { month: "long", year: "numeric" })
    : "";

  const investorType = profileData?.profile?.profile_type ?? null;

  return (
    <div className="space-y-4">
      <h2 className="text-base font-bold text-slate-900">계정 정보</h2>

      <div className="sp-card divide-y divide-slate-100">
        {/* Name */}
        <div className="flex items-center justify-between px-4 py-3.5">
          <span className="text-sm text-slate-500">이름</span>
          <span className="text-sm font-semibold text-slate-900">
            {user?.name || "---"}
          </span>
        </div>

        {/* Email */}
        <div className="flex items-center justify-between px-4 py-3.5">
          <span className="text-sm text-slate-500">이메일</span>
          <span className="text-sm font-semibold text-slate-900">
            {user?.email || "---"}
          </span>
        </div>

        {/* Joined */}
        <div className="flex items-center justify-between px-4 py-3.5">
          <span className="text-sm text-slate-500">가입일</span>
          <span className="text-sm font-medium text-slate-700">{joinedDate}</span>
        </div>

        {/* OAuth Provider */}
        {user?.oauth_provider && (
          <div className="flex items-center justify-between px-4 py-3.5">
            <span className="text-sm text-slate-500">로그인 방법</span>
            <span className="text-sm font-medium text-slate-700 capitalize">
              {user.oauth_provider}
            </span>
          </div>
        )}

        {/* Investor Type */}
        <div className="flex items-center justify-between px-4 py-3.5">
          <span className="text-sm text-slate-500">투자자 유형</span>
          {profileLoading ? (
            <Skeleton className="h-5 w-28" />
          ) : investorType ? (
            <span className="text-sm font-semibold text-purple-600">
              {investorType}
            </span>
          ) : (
            <span className="text-sm text-slate-400">미설정</span>
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
            {investorType ? "투자자 진단 다시 하기" : "투자자 진단 시작"}
          </p>
          <p className="text-xs text-slate-500 mt-0.5">
            {investorType
              ? "투자자 프로필과 선호도를 업데이트하세요"
              : "나만의 맞춤 투자자 프로필을 설정하세요"}
          </p>
        </div>
        <ChevronRight className="h-4 w-4 text-slate-400 transition-transform group-hover:translate-x-0.5" />
      </Link>
    </div>
  );
}

/* ── Subscription Section ── */

function SubscriptionSection() {
  const { data: subData, isLoading } = useSWR<SubscriptionResponse>(
    API.billing.subscription,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 },
  );

  const tier = subData?.tier ?? "free";
  const isPro = tier === "pro";
  const isPremium = tier === "premium";
  const isPaid = isPro || isPremium;

  return (
    <div className="space-y-4">
      <h2 className="text-base font-bold text-slate-900">구독</h2>

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
                    ? `구독 활성`
                    : "무료 플랜 (기본 기능)"}
                </p>
              </div>
            </div>

            {subData?.current_period_end && isPaid && (
              <p className="text-xs text-slate-500 mb-4">
                {subData.cancel_at_period_end
                  ? `해지 예정: ${new Date(subData.current_period_end).toLocaleDateString("ko-KR")}`
                  : `갱신일: ${new Date(subData.current_period_end).toLocaleDateString("ko-KR")}`}
              </p>
            )}

            {!isPaid && (
              <Link
                href="/pricing"
                className="flex items-center justify-center gap-2 w-full rounded-full bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-slate-800 active:scale-[0.97]"
              >
                <Crown className="h-4 w-4" />
                Pro로 업그레이드
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
                구독 관리
              </button>
            )}
          </div>

          {/* Feature comparison teaser */}
          {!isPaid && (
            <div className="sp-card p-4">
              <p className="text-xs font-semibold text-slate-900 mb-3">
                Pro 플랜 혜택
              </p>
              <ul className="space-y-2">
                {[
                  "종목 무제한 트래킹",
                  "25+ 기술적 지표",
                  "AI Assistant 하루 10회 질문",
                  "전체 리스크 분석 대시보드",
                  "우선 시그널 처리",
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

  const handleAlpacaConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim() || !apiSecret.trim()) {
      toast.error("API Key와 API Secret을 모두 입력해 주세요.");
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
      toast.success("Alpaca가 성공적으로 연결됐습니다!");
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Alpaca 연결에 실패했습니다.";
      toast.error(message);
    } finally {
      setConnecting(false);
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-base font-bold text-slate-900">브로커 연동</h2>

      {/* Alpaca */}
      <div className="sp-card p-4">
        <div className="flex items-center gap-3 mb-3">
          <span className="text-lg" role="img" aria-label="US flag">
            &#x1F1FA;&#x1F1F8;
          </span>
          <div className="flex-1">
            <p className="text-sm font-semibold text-slate-900">Alpaca</p>
            <p className="text-xs text-slate-500">
              Alpaca Markets를 통한 미국 주식 거래
            </p>
          </div>
          {connected ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-medium text-emerald-600">
              <Check className="h-3 w-3" />
              연결됨
            </span>
          ) : (
            <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-500">
              미연결
            </span>
          )}
        </div>

        {!connected && !showAlpacaForm && (
          <button
            type="button"
            onClick={() => setShowAlpacaForm(true)}
            className="w-full rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition-all hover:bg-slate-50 active:scale-[0.97]"
          >
            Alpaca 연결하기
          </button>
        )}

        {!connected && showAlpacaForm && (
          <form onSubmit={handleAlpacaConnect} className="space-y-3">
            <div>
              <label
                htmlFor="alpaca-api-key"
                className="block text-xs font-medium text-slate-600 mb-1"
              >
                API Key
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
                API Secret
              </label>
              <input
                id="alpaca-api-secret"
                type="password"
                value={apiSecret}
                onChange={(e) => setApiSecret(e.target.value)}
                placeholder="Enter your API secret"
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
                {connecting ? "연결 중..." : "연결"}
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
                취소
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
              한국투자증권
            </p>
            <p className="text-xs text-slate-500">
              KIS API를 통한 한국 주식 거래
            </p>
          </div>
          <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-500">
            출시 예정
          </span>
        </div>
        <button
          type="button"
          disabled
          className="w-full rounded-full border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-400 cursor-not-allowed"
        >
          Coming Soon
        </button>
      </div>

      <p className="text-xs text-slate-400 text-center pt-2">
        브로커 연동 시 실시간 포트폴리오 동기화와 자동매매가 가능합니다.
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

    // Local storage-backed preference (backend endpoint not yet finalized)
    const savedTime = window.localStorage.getItem("sp_mb_time");
    if (savedTime) setTime(savedTime);

    const savedEmail = window.localStorage.getItem("sp_mb_email") === "1";
    setEmailEnabled(savedEmail);
  }, []);

  const handlePushToggle = async (next: boolean) => {
    if (!pushSupported) {
      toast.error("이 브라우저는 푸시 알림을 지원하지 않습니다");
      return;
    }
    setPushLoading(true);
    try {
      if (next) {
        const sub = await subscribeToPush();
        if (!sub) {
          toast.error("브라우저 설정에서 알림 권한을 허용해 주세요");
          setPushEnabled(false);
          return;
        }
        setPushEnabled(true);
        toast.success("아침 브리핑 푸시가 활성화됐습니다");
      } else {
        await unsubscribeFromPush();
        setPushEnabled(false);
        toast.success("푸시 알림이 해제됐습니다");
      }
    } catch {
      toast.error("알림 설정에 실패했습니다");
    } finally {
      setPushLoading(false);
    }
  };

  const handleTimeChange = (value: string) => {
    setTime(value);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("sp_mb_time", value);
    }
    toast.success("발송 시간이 변경됐습니다");
  };

  const handleEmailToggle = (next: boolean) => {
    if (!isPro) {
      toast.error("이메일 알림은 Pro 이상 플랜에서 이용할 수 있습니다");
      return;
    }
    setEmailEnabled(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("sp_mb_email", next ? "1" : "0");
    }
    toast.success(next ? "이메일 알림이 활성화됐습니다" : "이메일 알림이 해제됐습니다");
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-bold text-slate-900">알림 설정</h2>
        <p className="mt-0.5 text-xs text-slate-500">
          푸시, 이메일, 카톡 알림을 관리하세요
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
                  아침 브리핑 푸시 알림
                </p>
                <p className="mt-0.5 text-xs text-slate-500">
                  매일 아침, 포트폴리오 요약과 오늘의 일정을 받아보세요
                </p>
              </div>
              <ToggleSwitch
                checked={pushEnabled}
                onChange={handlePushToggle}
                disabled={pushLoading || !pushSupported}
                ariaLabel="아침 브리핑 푸시 알림"
              />
            </div>

            {!pushSupported && (
              <p className="mt-2 flex items-center gap-1.5 text-[11px] text-amber-600">
                <AlertTriangle className="h-3 w-3" />
                이 브라우저는 푸시 알림을 지원하지 않습니다
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
                발송 시간 (KST)
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
                매일 이 시간에 푸시가 발송됩니다 (KST 기준)
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
                    이메일 알림
                  </p>
                  {!isPro && <TierBadge tier="pro" />}
                </div>
                <p className="mt-0.5 text-xs text-slate-500">
                  {isPro
                    ? "가입한 이메일로 매일 아침 브리핑을 받아보세요"
                    : "Pro 이상 플랜에서 이용 가능"}
                </p>
              </div>
              <ToggleSwitch
                checked={emailEnabled}
                onChange={handleEmailToggle}
                disabled={!isPro}
                ariaLabel="이메일 알림"
              />
            </div>

            {!isPro && (
              <Link
                href="/pricing"
                className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-purple-700 hover:text-purple-800"
              >
                Pro 업그레이드
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
                    카톡 알림
                  </p>
                  <TierBadge tier="premium" />
                  <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500">
                    출시 예정
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-slate-500">
                  Premium 플랜에서 곧 제공됩니다 (v2)
                </p>
              </div>
              <ToggleSwitch
                checked={false}
                onChange={() => {}}
                disabled
                ariaLabel="카톡 알림"
              />
            </div>
          </div>
        </div>
      </div>

      <p className="pt-2 text-center text-[11px] text-slate-400">
        알림은 언제든지 해제할 수 있습니다
      </p>
    </div>
  );
}

/* ── Page ── */

export default function SettingsPage() {
  const router = useRouter();
  const { logout } = useAuth();
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
            <h1 className="text-xl font-bold text-slate-900">설정</h1>
            <p className="text-sm text-slate-500">
              계정, 플랜, 연동을 관리하세요
            </p>
          </div>
        </div>

        {/* ── Tab navigation ── */}
        <div className="flex gap-2 overflow-x-auto scrollbar-hide pb-1">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "filter-pill flex items-center gap-1.5 whitespace-nowrap",
                  isActive && "active",
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* ── Tab content ── */}
        {activeTab === "account" && <AccountSection />}
        {activeTab === "subscription" && <SubscriptionSection />}
        {activeTab === "connections" && <ConnectionsSection />}
        {activeTab === "notifications" && <NotificationsSection />}

        {/* ── Danger Zone ── */}
        <div className="space-y-3 pt-4 border-t border-slate-100">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            위험 구역
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
              {signingOut ? "로그아웃 중..." : "로그아웃"}
            </button>

            {/* Delete Account */}
            <button
              type="button"
              onClick={() => setShowDeleteModal(true)}
              className="flex flex-1 items-center justify-center gap-2 rounded-full border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-600 transition-all hover:bg-red-50 active:scale-[0.97]"
            >
              <Trash2 className="h-4 w-4" />
              계정 삭제
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
