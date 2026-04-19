"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { cn } from "@/lib/utils";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  Check,
  X,
  Crown,
  Zap,
  Sparkles,
  BarChart3,
  ChevronDown,
  ShieldAlert,
  ArrowLeft,
} from "lucide-react";

/* ── Tier data (4 tiers confirmed 2026-04-19) ── */

type TierKey = "free" | "pro" | "premium" | "elite";

interface PlanFeature {
  label: string;
  free: string | boolean;
  pro: string | boolean;
  premium: string | boolean;
  elite: string | boolean;
}

const PLAN_FEATURES: PlanFeature[] = [
  { label: "Brag Card (인스타 9:16)", free: "월 1회", pro: true, premium: true, elite: true },
  { label: "실적 캘린더 iCal", free: true, pro: true, premium: true, elite: true },
  { label: "관심종목 핫리스트", free: true, pro: true, premium: true, elite: true },
  { label: "Morning Brief (매일 6시)", free: false, pro: true, premium: true, elite: true },
  { label: "Evening Wrap (장마감 정리)", free: false, pro: true, premium: true, elite: true },
  { label: "Weekly Investor Memo (PDF)", free: false, pro: true, premium: true, elite: true },
  { label: "Earnings Pre-Brief (실적 30분 전)", free: false, pro: true, premium: true, elite: true },
  { label: "Thesis Tracker", free: false, pro: true, premium: true, elite: true },
  { label: "Red/Green Alert", free: false, pro: true, premium: true, elite: true },
  { label: "FOMC Playbook", free: false, pro: false, premium: true, elite: true },
  { label: "CPI Brief", free: false, pro: false, premium: true, elite: true },
  { label: "Sector Monthly", free: false, pro: false, premium: true, elite: true },
  { label: "Tax Lot Harvest", free: false, pro: false, premium: true, elite: true },
  { label: "IPO Radar", free: false, pro: false, premium: true, elite: true },
  { label: "Yearly Wrapped", free: false, pro: false, premium: true, elite: true },
  { label: "10-K Personal (분기 사업보고서)", free: false, pro: false, premium: false, elite: true },
  { label: "Annual Letter to Self", free: false, pro: false, premium: false, elite: true },
  { label: "Commute Podcast (음성)", free: false, pro: false, premium: false, elite: true },
  { label: "Quarterly Self-Interview", free: false, pro: false, premium: false, elite: true },
  { label: "Peer Benchmark 리포트", free: false, pro: false, premium: false, elite: true },
  { label: "Stress Test", free: false, pro: false, premium: false, elite: true },
];

/* ── FAQ data ── */

interface FaqItem {
  q: string;
  a: string;
}

const FAQ_ITEMS: FaqItem[] = [
  {
    q: "PivoxQuant은 ChatGPT와 뭐가 다른가요?",
    a: "ChatGPT Plus는 ₩27,000/월, PivoxQuant Elite는 ₩29,900/월 — 거의 같은 가격대입니다. 차이는 결과물 형태입니다. ChatGPT는 당신이 물어야 답합니다. PivoxQuant는 당신이 자는 동안 Morning Brief·Weekly Memo·10-K Personal을 이메일·PDF·음성으로 만들어 둡니다.",
  },
  {
    q: "어느 플랜이 나에게 맞나요?",
    a: "개인 투자자 대부분은 Premium(₩19,900)이 적정선입니다. Morning·Evening·Weekly 데일리 리포트에 FOMC·CPI·Sector Monthly·IPO Radar·Yearly Wrapped 같은 이벤트/분기 리포트까지 모두 포함됩니다. Elite(₩29,900)는 연례 주주서한 포맷·팟캐스트·Peer Benchmark 같은 헤비 유저용입니다.",
  },
  {
    q: "리포트는 어떻게 받나요?",
    a: "Pro 이상 구독 시 매일 아침 6시 Morning Brief 이메일, 매주 일요일 Weekly Memo PDF, 보유 종목 실적 30분 전 Pre-Brief가 자동 발송됩니다. 웹 대시보드 아카이브에서도 언제든 다시 열람할 수 있습니다.",
  },
  {
    q: "무료 플랜에는 무엇이 포함되나요?",
    a: "월간 Brag Card(인스타 9:16 카드), 실적 캘린더 iCal 구독, 관심종목 핫리스트를 제공합니다. 데일리 리포트는 Pro부터 시작합니다.",
  },
  {
    q: "언제든 해지할 수 있나요?",
    a: "네, 언제든 해지 가능합니다. 다음 결제일까지 기능이 유지되며, 이후 자동으로 Free 플랜으로 전환됩니다.",
  },
  {
    q: "리포트는 투자 자문인가요?",
    a: "아닙니다. PivoxQuant는 정보 제공 도구입니다. 리포트는 시장 데이터·재무 지표·관찰 포인트를 정리한 분석물이며, 특정 종목의 매수·매도를 추천하거나 권유하지 않습니다. 모든 투자 판단은 이용자 본인의 책임입니다.",
  },
  {
    q: "VAT 포함 가격인가요?",
    a: "네, 표시 가격은 VAT 포함입니다. 숨겨진 수수료는 없습니다.",
  },
];

/* ── FAQ Accordion Item ── */

function FaqAccordion({ item }: { item: FaqItem }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-b border-slate-100 last:border-0">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center justify-between py-4 text-left"
        aria-expanded={open}
      >
        <span className="text-sm font-semibold text-slate-900 pr-4">
          {item.q}
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-slate-400 transition-transform duration-200",
            open && "rotate-180",
          )}
        />
      </button>
      {open && (
        <p className="pb-4 text-sm text-slate-600 leading-relaxed">
          {item.a}
        </p>
      )}
    </div>
  );
}

/* ── Feature check/cross ── */

function FeatureValue({ value }: { value: string | boolean }) {
  if (value === true)
    return <Check className="h-4 w-4 text-emerald-500 mx-auto" />;
  if (value === false)
    return <X className="h-4 w-4 text-slate-300 mx-auto" />;
  return (
    <span className="text-xs font-medium text-slate-700 text-center block">
      {value}
    </span>
  );
}

/* ── Plan Card ── */

function PlanCard({
  name,
  price,
  period,
  description,
  features,
  cta,
  ctaHref,
  onCtaClick,
  highlighted,
  badge,
  icon,
}: {
  name: string;
  price: string;
  period: string;
  description: string;
  features: string[];
  cta: string;
  ctaHref?: string;
  onCtaClick?: () => void;
  highlighted?: boolean;
  badge?: string;
  icon: React.ReactNode;
}) {
  const buttonClass = highlighted
    ? "w-full rounded-full bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition-all hover:bg-slate-800 active:scale-[0.97]"
    : "w-full rounded-full border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 transition-all hover:bg-slate-50 active:scale-[0.97]";

  return (
    <div
      className={cn(
        "sp-card relative flex flex-col p-6",
        highlighted && "ring-2 ring-accent/40 border-l-2 border-l-accent",
      )}
    >
      {badge && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <span className="inline-flex items-center rounded-full bg-accent px-3 py-1 text-[11px] font-bold text-slate-900">
            {badge}
          </span>
        </div>
      )}

      <div className="flex items-center gap-3 mb-4">
        <div
          className={cn(
            "flex h-10 w-10 items-center justify-center rounded-xl",
            highlighted ? "bg-accent text-slate-900" : "bg-slate-100 text-slate-500",
          )}
        >
          {icon}
        </div>
        <div>
          <p className="text-base font-bold text-slate-900">{name}</p>
          <p className="text-xs text-slate-500">{description}</p>
        </div>
      </div>

      <div className="mb-5">
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-bold text-slate-900 tabular-nums">{price}</span>
          <span className="text-sm text-slate-500">{period}</span>
        </div>
      </div>

      <ul className="flex-1 space-y-2.5 mb-6">
        {features.map((feat) => (
          <li key={feat} className="flex items-start gap-2 text-sm text-slate-600">
            <Check className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
            <span>{feat}</span>
          </li>
        ))}
      </ul>

      {ctaHref ? (
        <Link href={ctaHref} className={buttonClass}>
          {cta}
        </Link>
      ) : (
        <button type="button" onClick={onCtaClick} className={buttonClass}>
          {cta}
        </button>
      )}
    </div>
  );
}

/* ── Page ── */

export default function PricingPage() {
  const [loadingCheckout, setLoadingCheckout] = useState<TierKey | null>(null);

  const handleCheckout = useCallback(async (plan: TierKey) => {
    setLoadingCheckout(plan);
    try {
      const result = await apiFetch<{ url: string }>(API.billing.createCheckout, {
        method: "POST",
        body: JSON.stringify({ plan }),
      });
      if (result.url) {
        window.location.href = result.url;
      }
    } catch {
      // If user is not authenticated, redirect to signup
      window.location.href = "/signup";
    } finally {
      setLoadingCheckout(null);
    }
  }, []);

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-[#fafafa]">
        {/* ── Top navigation ── */}
        <div className="mx-auto max-w-6xl px-4 py-4">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to home
          </Link>
        </div>

        <div className="mx-auto max-w-6xl px-4 pb-20">
          {/* ── Hero ── */}
          <div className="text-center mb-12">
            <h1 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-3">
              받아보는 리포트로 고르세요.
            </h1>
            <p className="text-lg text-slate-500 max-w-xl mx-auto leading-relaxed">
              같은 가격, 다른 제품. ChatGPT는 물어야 답하고, PivoxQuant는 매일 만듭니다.
            </p>
          </div>

          {/* ── Plan Cards (4 tiers) ── */}
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4 mb-16">
            <PlanCard
              name="Free"
              price="₩0"
              period="/월"
              description="맛보기 · 월 3개"
              icon={<BarChart3 className="h-5 w-5" />}
              features={[
                "Brag Card (월 1회)",
                "실적 캘린더 iCal",
                "관심종목 핫리스트",
              ]}
              cta="무료 시작"
              ctaHref="/signup"
            />

            <PlanCard
              name="Pro"
              price="₩9,900"
              period="/월"
              description="데일리 리서치 데스크"
              icon={<Sparkles className="h-5 w-5" />}
              features={[
                "Morning Brief · Evening Wrap",
                "Weekly Investor Memo (PDF)",
                "Earnings Pre-Brief",
                "Thesis Tracker",
                "Red/Green Alert",
              ]}
              cta={loadingCheckout === "pro" ? "로딩..." : "Pro로 구독"}
              onCtaClick={() => handleCheckout("pro")}
            />

            <PlanCard
              name="Premium"
              price="₩19,900"
              period="/월"
              description="분기 리포트 + 시장 이벤트"
              icon={<Crown className="h-5 w-5" />}
              highlighted
              badge="가장 많이 선택"
              features={[
                "Pro 전부 포함",
                "FOMC Playbook · CPI Brief",
                "Sector Monthly",
                "Tax Lot Harvest · IPO Radar",
                "Yearly Wrapped",
              ]}
              cta={
                loadingCheckout === "premium" ? "로딩..." : "Premium으로 구독"
              }
              onCtaClick={() => handleCheckout("premium")}
            />

            <PlanCard
              name="Elite"
              price="₩29,900"
              period="/월"
              description="ChatGPT Plus 가격, 다른 제품"
              icon={<Zap className="h-5 w-5" />}
              features={[
                "Premium 전부 포함",
                "10-K Personal",
                "Annual Letter to Self",
                "Commute Podcast (음성)",
                "Quarterly Self-Interview",
                "Peer Benchmark · Stress Test",
              ]}
              cta={
                loadingCheckout === "elite" ? "로딩..." : "Elite로 구독"
              }
              onCtaClick={() => handleCheckout("elite")}
            />
          </div>

          {/* ── Value Anchor Note ── */}
          <div className="mx-auto max-w-2xl mb-16 rounded-2xl border border-slate-200 bg-white p-5 text-center">
            <p className="text-sm font-semibold text-slate-900 mb-1">
              ChatGPT Plus ₩27,000 · PivoxQuant Elite ₩29,900
            </p>
            <p className="text-xs text-slate-500 leading-relaxed">
              챗봇은 당신이 물어야 답합니다. 리서치 데스크는 매일 스스로 만듭니다.
            </p>
          </div>

          {/* ── Feature Comparison Table ── */}
          <div className="sp-card overflow-hidden mb-16">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="text-base font-bold text-slate-900">
                받아보는 리포트 비교
              </h2>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/50">
                    <th className="px-6 py-3 text-left font-semibold text-slate-500 text-xs uppercase tracking-wider">
                      Feature
                    </th>
                    <th className="px-4 py-3 text-center font-semibold text-slate-500 text-xs uppercase tracking-wider w-24">
                      Free
                    </th>
                    <th className="px-4 py-3 text-center font-semibold text-slate-500 text-xs uppercase tracking-wider w-24">
                      Pro
                    </th>
                    <th className="px-4 py-3 text-center font-semibold text-accent text-xs uppercase tracking-wider w-24">
                      Premium
                    </th>
                    <th className="px-4 py-3 text-center font-semibold text-slate-500 text-xs uppercase tracking-wider w-24">
                      Elite
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {PLAN_FEATURES.map((feat, idx) => (
                    <tr
                      key={feat.label}
                      className={cn(
                        "border-b border-slate-50",
                        idx % 2 === 1 && "bg-slate-50/30",
                      )}
                    >
                      <td className="px-6 py-3 text-sm font-medium text-slate-700">
                        {feat.label}
                      </td>
                      <td className="px-4 py-3">
                        <FeatureValue value={feat.free} />
                      </td>
                      <td className="px-4 py-3">
                        <FeatureValue value={feat.pro} />
                      </td>
                      <td className="px-4 py-3 bg-accent/5">
                        <FeatureValue value={feat.premium} />
                      </td>
                      <td className="px-4 py-3">
                        <FeatureValue value={feat.elite} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── FAQ ── */}
          <div className="max-w-2xl mx-auto mb-16">
            <h2 className="text-xl font-bold text-slate-900 text-center mb-8">
              자주 묻는 질문
            </h2>
            <div className="sp-card px-6">
              {FAQ_ITEMS.map((item) => (
                <FaqAccordion key={item.q} item={item} />
              ))}
            </div>
          </div>

          {/* ── VAT & Disclaimer ── */}
          <div className="text-center space-y-3">
            <p className="text-xs text-slate-500">
              KRW 기준 · VAT 포함 · 언제든 해지 가능
            </p>
            <div className="mx-auto max-w-xl rounded-xl border border-slate-200 bg-slate-50 p-3">
              <div className="flex items-start gap-2">
                <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-slate-400 mt-0.5" />
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  과거 성과는 미래 수익을 보장하지 않습니다. PivoxQuant는 정보 제공 도구이며 투자 자문이 아닙니다.
                  리포트는 시장 데이터·관찰 포인트를 정리한 분석물이며, 특정 종목 매수·매도를 권유하지 않습니다.
                  모든 투자 판단의 책임은 이용자 본인에게 있습니다.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </ErrorBoundary>
  );
}
