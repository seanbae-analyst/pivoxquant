"use client";

import { useInvestmentProfile } from "@/lib/hooks";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import {
  User, Shield, Target, BarChart3, TrendingUp, Bell,
  Wallet, Link2, RefreshCw,
} from "lucide-react";

const PROFILE_COLORS: Record<string, string> = {
  conservative: "from-blue-500 to-cyan-500",
  balanced: "from-purple-500 to-blue-500",
  growth: "from-purple-600 to-pink-600",
  aggressive: "from-red-500 to-orange-500",
};

const PROFILE_LABELS: Record<string, { en: string; kr: string }> = {
  conservative: { en: "Conservative", kr: "안정형" },
  balanced: { en: "Balanced", kr: "균형형" },
  growth: { en: "Growth", kr: "성장형" },
  aggressive: { en: "Aggressive", kr: "공격형" },
};

export default function ProfilePage() {
  const { user } = useAuth();
  const { data } = useInvestmentProfile();

  if (!data) {
    return (
      <div className="flex items-center justify-center py-20">
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
        <span className="text-slate-500 text-[12px]">Loading...</span>
      </div>
    );
  }

  const profile = data.profile;
  const profileType = profile?.profile_type ?? "balanced";
  const gradient = PROFILE_COLORS[profileType] ?? PROFILE_COLORS.balanced;
  const labels = PROFILE_LABELS[profileType] ?? PROFILE_LABELS.balanced;

  return (
    <div className="space-y-4">
      {/* Page Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Investment Profile</h1>
          <p className="mt-1 text-sm text-slate-500">Your personalized quant engine configuration</p>
        </div>
        <Link href="/onboarding">
          <Button variant="outline" className="gap-2">
            <RefreshCw size={16} />
            {data.has_profile ? `Change Profile (${data.changes_left ?? 0} left)` : "Take Questionnaire"}
          </Button>
        </Link>
      </div>

      {/* Profile Hero Card */}
      {data.has_profile && profile ? (
        <>
          <div className={`relative overflow-hidden rounded-2xl bg-gradient-to-br ${gradient} p-8 text-white`}>
            <div className="absolute inset-0 opacity-10">
              <div className="absolute inset-0" style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, white 1px, transparent 0)', backgroundSize: '32px 32px' }} />
            </div>
            <div className="relative flex items-center gap-6">
              <div className="flex h-20 w-20 items-center justify-center rounded-3xl bg-white/20 backdrop-blur">
                <User size={36} />
              </div>
              <div>
                <p className="text-sm font-semibold text-white/70">{user?.name}</p>
                <h2 className="text-4xl font-bold">{labels.kr}</h2>
                <p className="text-lg text-white/80">{labels.en} Investor</p>
              </div>
            </div>
          </div>

          {/* Quant Parameters Grid */}
          <div>
            <h2 className="mb-4 text-xl font-bold text-slate-900">Quant Engine Parameters</h2>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <ParamCard icon={<BarChart3 size={18} />} label="Tech Weight" value={`${(profile.tech_weight * 100).toFixed(0)}%`} />
              <ParamCard icon={<Shield size={18} />} label="Fund Weight" value={`${(profile.fund_weight * 100).toFixed(0)}%`} />
              <ParamCard icon={<TrendingUp size={18} />} label="News Weight" value={`${(profile.news_weight * 100).toFixed(0)}%`} />
              <ParamCard icon={<Target size={18} />} label="Buy Threshold" value={profile.buy_threshold.toFixed(0)} />
              <ParamCard icon={<Target size={18} />} label="Sell Threshold" value={profile.sell_threshold.toFixed(0)} />
              <ParamCard icon={<TrendingUp size={18} />} label="TP Range" value={`${profile.tp_min}~${profile.tp_max}%`} />
              <ParamCard icon={<Shield size={18} />} label="SL Range" value={`${profile.sl_min}~${profile.sl_max}%`} />
              <ParamCard icon={<Wallet size={18} />} label="Max Positions" value={String(profile.max_positions)} />
            </div>
          </div>

          {/* Settings */}
          <div>
            <h2 className="mb-4 text-xl font-bold text-slate-900">Settings</h2>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <SettingCard icon={<Bell size={18} />} label="Alert Frequency" value={profile.alert_frequency === "realtime" ? "Real-time" : "Daily"} />
              <SettingCard icon={<User size={18} />} label="AI Coaching Style" value={profile.ai_coaching_style.replace("_", " ")} />
              <SettingCard icon={<Target size={18} />} label="Markets" value={profile.preferred_markets === "both" ? "US + Korea" : profile.preferred_markets.toUpperCase()} />
              <SettingCard icon={<BarChart3 size={18} />} label="Auto Trade" value={profile.auto_trade_preference.replace("_", " ")} />
            </div>
          </div>

          {/* Broker Connections (placeholder) */}
          <div>
            <h2 className="mb-4 text-xl font-bold text-slate-900">Broker Connections</h2>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white p-6">
                <div className="flex items-center gap-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-100">
                    <Link2 size={20} className="text-emerald-600" />
                  </div>
                  <div>
                    <p className="font-semibold text-slate-900">Alpaca</p>
                    <p className="text-xs text-slate-500">US Stock Trading</p>
                  </div>
                </div>
                <Button variant="outline" size="sm" disabled>Coming Soon</Button>
              </div>
              <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white p-6">
                <div className="flex items-center gap-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-100">
                    <Link2 size={20} className="text-blue-600" />
                  </div>
                  <div>
                    <p className="font-semibold text-slate-900">KIS (한국투자증권)</p>
                    <p className="text-xs text-slate-500">Korean Stock Trading</p>
                  </div>
                </div>
                <Button variant="outline" size="sm" disabled>Coming Soon</Button>
              </div>
            </div>
          </div>

          {/* Subscription */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-slate-900">Subscription: <span className="capitalize">{data.subscription_tier ?? "free"}</span></p>
                <p className="text-sm text-slate-500">
                  {data.subscription_tier === "free"
                    ? "Upgrade to Pro for unlimited analysis and AI features"
                    : "Thank you for being a Pro subscriber"}
                </p>
              </div>
              {data.subscription_tier === "free" && (
                <Button disabled>Upgrade to Pro — Coming Soon</Button>
              )}
            </div>
          </div>
        </>
      ) : (
        /* No profile yet */
        <div className="rounded-2xl bg-gradient-to-br from-emerald-500/5 to-cyan-500/5 border border-emerald-500/20 p-12 text-center">
          <User size={48} className="mx-auto text-emerald-600" />
          <h2 className="mt-4 text-2xl font-bold text-slate-900">No Profile Yet</h2>
          <p className="mt-2 text-sm text-slate-500">Complete the questionnaire to personalize your quant engine</p>
          <Link href="/onboarding">
            <Button className="mt-6 bg-gradient-to-r from-purple-600 to-pink-600 text-white">
              Take Questionnaire
            </Button>
          </Link>
        </div>
      )}
    </div>
  );
}

function ParamCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex items-center gap-2 text-slate-500">
        {icon}
        <span className="text-xs font-medium">{label}</span>
      </div>
      <p className="mt-2 text-2xl font-bold text-slate-900">{value}</p>
    </div>
  );
}

function SettingCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
        {icon}
      </div>
      <div>
        <p className="text-xs font-medium text-slate-500">{label}</p>
        <p className="font-semibold capitalize text-slate-900">{value}</p>
      </div>
    </div>
  );
}
