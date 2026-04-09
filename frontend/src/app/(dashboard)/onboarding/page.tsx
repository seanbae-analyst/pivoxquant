"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Logo } from "@/components/ui/logo";
import {
  Sprout, TreePine, Mountain,
  Shield, Wallet, TrendingUp, Rocket,
  ThumbsDown, MinusCircle, Pause, ShoppingCart,
  Zap, Clock, Calendar,
  Flag, Globe,
  Bell, Settings, Bot, Hand,
  Coffee, Monitor,
  CheckCircle2, BarChart3, Sparkles, Leaf,
  Cpu, Heart, Landmark, Flame, ShoppingBag, Factory,
} from "lucide-react";

type Step = number;

const QUESTIONS = [
  {
    id: "experience_level",
    question: "How much investment experience do you have?",
    question_kr: "투자 경험은 어느 정도인가요?",
    type: "single",
    options: [
      { value: "beginner", label: "Beginner", label_kr: "초보 (1년 미만)", icon: Leaf },
      { value: "intermediate", label: "1-3 years", label_kr: "1~3년", icon: Sprout },
      { value: "advanced", label: "3-5 years", label_kr: "3~5년", icon: TreePine },
      { value: "expert", label: "5+ years", label_kr: "5년 이상", icon: Mountain },
    ],
  },
  {
    id: "investment_goal",
    question: "What is your primary investment goal?",
    question_kr: "주요 투자 목표는?",
    type: "single",
    options: [
      { value: "preservation", label: "Capital Preservation", label_kr: "자산 보존", icon: Shield },
      { value: "income", label: "Stable Income", label_kr: "안정적 수익", icon: Wallet },
      { value: "growth", label: "Growth", label_kr: "성장", icon: TrendingUp },
      { value: "aggressive_growth", label: "Aggressive Growth", label_kr: "공격적 성장", icon: Rocket },
    ],
  },
  {
    id: "risk_tolerance",
    question: "If your portfolio dropped 20%, what would you do?",
    question_kr: "포트폴리오가 -20% 하락하면?",
    type: "single",
    options: [
      { value: 2, label: "Sell Everything", label_kr: "전량 매도", icon: ThumbsDown },
      { value: 4, label: "Sell Some", label_kr: "일부 매도", icon: MinusCircle },
      { value: 6, label: "Hold", label_kr: "유지", icon: Pause },
      { value: 9, label: "Buy More", label_kr: "추가 매수", icon: ShoppingCart },
    ],
  },
  {
    id: "time_horizon",
    question: "What is your preferred investment horizon?",
    question_kr: "선호하는 투자 기간은?",
    type: "single",
    options: [
      { value: "short", label: "Short-term", label_kr: "단기 (~3개월)", icon: Zap },
      { value: "medium", label: "Medium", label_kr: "중기 (3~12개월)", icon: Clock },
      { value: "long", label: "Long-term", label_kr: "장기 (1년+)", icon: Calendar },
    ],
  },
  {
    id: "preferred_markets",
    question: "Which markets are you interested in?",
    question_kr: "관심 있는 시장은?",
    type: "single",
    options: [
      { value: "us", label: "US Only", label_kr: "미국만", icon: Flag },
      { value: "kr", label: "Korea Only", label_kr: "한국만", icon: Flag },
      { value: "both", label: "Both US & Korea", label_kr: "둘 다", icon: Globe },
    ],
  },
  {
    id: "preferred_sectors",
    question: "Which sectors interest you? (Select multiple)",
    question_kr: "관심 있는 섹터는? (복수 선택)",
    type: "multi",
    options: [
      { value: "Technology", label: "Tech", label_kr: "기술", icon: Cpu },
      { value: "Healthcare", label: "Healthcare", label_kr: "헬스케어", icon: Heart },
      { value: "Financial Services", label: "Finance", label_kr: "금융", icon: Landmark },
      { value: "Energy", label: "Energy", label_kr: "에너지", icon: Flame },
      { value: "Consumer Cyclical", label: "Consumer", label_kr: "소비재", icon: ShoppingBag },
      { value: "Industrials", label: "Industrials", label_kr: "산업재", icon: Factory },
    ],
  },
  {
    id: "auto_trade_preference",
    question: "How do you want to manage trades?",
    question_kr: "자동 매매에 관심이 있나요?",
    type: "single",
    options: [
      { value: "manual", label: "Manual Only", label_kr: "수동만", icon: Hand },
      { value: "signals", label: "Signal Alerts", label_kr: "시그널 알림", icon: Bell },
      { value: "semi_auto", label: "Semi-Auto", label_kr: "반자동", icon: Settings },
      { value: "full_auto", label: "Full Auto", label_kr: "완전 자동", icon: Bot },
    ],
  },
  {
    id: "daily_time",
    question: "How much time can you spend on investing daily?",
    question_kr: "하루에 투자에 쓸 수 있는 시간은?",
    type: "single",
    options: [
      { value: "minimal", label: "< 10 minutes", label_kr: "10분 이하", icon: Coffee },
      { value: "moderate", label: "30 minutes", label_kr: "30분", icon: Clock },
      { value: "active", label: "1+ hours", label_kr: "1시간 이상", icon: Monitor },
    ],
  },
];

const PROFILE_INFO: Record<string, { title: string; title_kr: string; color: string; desc: string }> = {
  conservative: { title: "Conservative", title_kr: "안정형", color: "from-blue-500 to-cyan-500", desc: "Low risk, steady returns. Focus on capital preservation." },
  balanced: { title: "Balanced", title_kr: "균형형", color: "from-purple-500 to-blue-500", desc: "Moderate risk/reward balance. Diversified approach." },
  growth: { title: "Growth", title_kr: "성장형", color: "from-purple-600 to-pink-600", desc: "Higher risk for higher returns. Opportunity-focused." },
  aggressive: { title: "Aggressive", title_kr: "공격형", color: "from-red-500 to-orange-500", desc: "Maximum growth potential. High risk tolerance." },
};

const QUESTION_COUNT = QUESTIONS.length; // 8
// Total steps: welcome(0) + 8 questions(1-8) + capital(9) + result(10)
const TOTAL_STEPS = QUESTION_COUNT + 3; // 11

export default function OnboardingPage() {
  const router = useRouter();
  const { user, refresh } = useAuth();
  const [step, setStep] = useState<Step>(0);
  const [answers, setAnswers] = useState<Record<string, string | number | string[]>>({});
  const [capitalUsd, setCapitalUsd] = useState("");
  const [capitalKrw, setCapitalKrw] = useState("");
  const [profileResult, setProfileResult] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const setAnswer = (questionId: string, value: string | number) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
    // Auto-advance after selection
    setTimeout(() => setStep((s) => s + 1), 300);
  };

  const toggleMultiAnswer = (questionId: string, value: string) => {
    setAnswers((prev) => {
      const current = (prev[questionId] as string[]) || [];
      const next = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      return { ...prev, [questionId]: next };
    });
  };

  const handleSubmitProfile = async () => {
    setSaving(true);
    try {
      // Save capital first
      const usd = Number(capitalUsd) || 0;
      const krw = Number(capitalKrw) || 0;
      if (usd > 0 || krw > 0) {
        await apiFetch(API.portfolio.capital, {
          method: "PUT",
          body: JSON.stringify({ capital_usd: usd, capital_krw: krw }),
        });
      }

      // Submit onboarding answers
      const res = await apiFetch<{ profile_type: string }>(API.profile.onboarding, {
        method: "POST",
        body: JSON.stringify({ answers }),
      });
      setProfileResult(res.profile_type);
      setStep(TOTAL_STEPS - 1); // Go to result step
    } catch {
      setStep(TOTAL_STEPS - 1);
    } finally {
      setSaving(false);
    }
  };

  const handleFinish = async () => {
    await refresh();
    router.push("/home");
  };

  const capitalStep = QUESTION_COUNT + 1; // step 9
  const resultStep = TOTAL_STEPS - 1;     // step 10
  const currentQuestion = step >= 1 && step <= QUESTION_COUNT ? QUESTIONS[step - 1] : null;
  const progress = Math.round((step / resultStep) * 100);

  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center p-4">
      <div className="w-full max-w-xl">
        {/* Progress bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-zinc-500">
              {step === 0 ? "Welcome" : step <= QUESTION_COUNT ? `Question ${step}/${QUESTION_COUNT}` : step === capitalStep ? "Capital" : "Result"}
            </span>
            <span className="text-xs font-semibold text-zinc-500">{progress}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-purple-600 to-pink-600 transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        <div className="glass-surface rounded-2xl p-8">
          {/* -- Step 0: Welcome -- */}
          {step === 0 && (
            <div className="text-center">
              <Logo size={64} />
              <h1 className="mt-6 text-2xl font-bold tracking-tight text-white">Welcome to StockPilot</h1>
              <p className="mt-2 text-zinc-500">Let&apos;s personalize your quant engine in 2 minutes.</p>
              <div className="mt-8 grid grid-cols-3 gap-4">
                {[
                  { icon: <BarChart3 size={24} className="text-purple-400" />, label: "Quant Analysis", desc: "15+ indicators" },
                  { icon: <Sparkles size={24} className="text-pink-400" />, label: "AI Insights", desc: "Claude-powered" },
                  { icon: <Bot size={24} className="text-emerald-400" />, label: "Auto Trading", desc: "US + KR" },
                ].map((f) => (
                  <div key={f.label} className="rounded-2xl bg-white/5 border border-white/10 p-4">
                    <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-white/10">{f.icon}</div>
                    <p className="text-xs font-semibold text-zinc-300">{f.label}</p>
                    <p className="text-[10px] text-zinc-500">{f.desc}</p>
                  </div>
                ))}
              </div>
              <Button className="mt-8 w-full" onClick={() => setStep(1)}>
                Get Started
              </Button>
              <button onClick={() => router.push("/home")} className="mt-3 block w-full text-center text-xs text-zinc-600 hover:text-zinc-400 spring-transition transition-colors">
                Skip setup
              </button>
            </div>
          )}

          {/* -- Steps 1-8: Questions -- */}
          {currentQuestion && (
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-white">{currentQuestion.question_kr}</h2>
              <p className="mt-1 text-sm text-zinc-500">{currentQuestion.question}</p>

              {currentQuestion.type === "multi" ? (
                /* Multi-select question (sectors) */
                <>
                  <div className="mt-8 grid grid-cols-2 gap-3">
                    {currentQuestion.options.map((opt) => {
                      const Icon = opt.icon;
                      const selectedArr = (answers[currentQuestion.id] as string[]) || [];
                      const selected = selectedArr.includes(String(opt.value));
                      return (
                        <button
                          key={String(opt.value)}
                          onClick={() => toggleMultiAnswer(currentQuestion.id, String(opt.value))}
                          className={`flex items-center gap-3 rounded-2xl border-2 px-4 py-3 text-left transition-all duration-200 ${
                            selected
                              ? "border-purple-500/60 bg-purple-500/10"
                              : "border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/8"
                          }`}
                        >
                          <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
                            selected ? "bg-purple-600 text-white" : "bg-white/10 text-zinc-400"
                          }`}>
                            <Icon size={18} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="font-semibold text-zinc-200 text-sm">{opt.label_kr}</p>
                            <p className="text-[10px] text-zinc-500">{opt.label}</p>
                          </div>
                          {selected && <CheckCircle2 size={18} className="text-purple-400 shrink-0" />}
                        </button>
                      );
                    })}
                  </div>
                  <p className="mt-3 text-center text-xs text-zinc-600">Select one or more sectors, then continue</p>
                  <div className="mt-6 flex gap-3">
                    <Button variant="outline" onClick={() => setStep((s) => s - 1)}>Back</Button>
                    <Button
                      className="flex-1"
                      onClick={() => setStep((s) => s + 1)}
                      disabled={!((answers[currentQuestion.id] as string[])?.length > 0)}
                    >
                      Continue
                    </Button>
                  </div>
                </>
              ) : (
                /* Single-select question */
                <>
                  <div className="mt-8 space-y-3">
                    {currentQuestion.options.map((opt) => {
                      const Icon = opt.icon;
                      const selected = answers[currentQuestion.id] === opt.value;
                      return (
                        <button
                          key={String(opt.value)}
                          onClick={() => setAnswer(currentQuestion.id, opt.value)}
                          className={`flex w-full items-center gap-4 rounded-2xl border-2 px-5 py-4 text-left transition-all duration-200 ${
                            selected
                              ? "border-purple-500/60 bg-purple-500/10"
                              : "border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/8"
                          }`}
                        >
                          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${
                            selected ? "bg-purple-600 text-white" : "bg-white/10 text-zinc-400"
                          }`}>
                            <Icon size={20} />
                          </div>
                          <div className="flex-1">
                            <p className="font-semibold text-zinc-200">{opt.label_kr}</p>
                            <p className="text-xs text-zinc-500">{opt.label}</p>
                          </div>
                          {selected && <CheckCircle2 size={20} className="text-purple-400" />}
                        </button>
                      );
                    })}
                  </div>
                  <div className="mt-6 flex gap-3">
                    <Button variant="outline" onClick={() => setStep((s) => s - 1)}>Back</Button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* -- Capital Step -- */}
          {step === capitalStep && (
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-white">Set Your Capital</h2>
              <p className="mt-1 text-sm text-zinc-500">How much capital do you have available for trading?</p>
              <div className="mt-8 space-y-5">
                <div className="space-y-2">
                  <label className="text-xs font-semibold uppercase tracking-wider text-zinc-500">USD Capital</label>
                  <div className="relative">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-sm text-zinc-500">$</span>
                    <Input
                      type="number"
                      placeholder="10,000"
                      value={capitalUsd}
                      onChange={(e) => setCapitalUsd(e.target.value)}
                      className="pl-8"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-semibold uppercase tracking-wider text-zinc-500">KRW Capital (optional)</label>
                  <div className="relative">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-sm text-zinc-500">&#8361;</span>
                    <Input
                      type="number"
                      placeholder="10,000,000"
                      value={capitalKrw}
                      onChange={(e) => setCapitalKrw(e.target.value)}
                      className="pl-8"
                    />
                  </div>
                </div>
                <p className="text-center text-xs text-zinc-600">You can change this anytime from the dashboard</p>
              </div>
              <div className="mt-8 flex gap-3">
                <Button variant="outline" onClick={() => setStep(QUESTION_COUNT)}>Back</Button>
                <Button className="flex-1" onClick={handleSubmitProfile} disabled={saving}>
                  {saving ? (
                    <span className="flex items-center">
                      <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
                      <span className="text-zinc-400 text-[12px]">Loading...</span>
                    </span>
                  ) : "Analyze My Profile"}
                </Button>
              </div>
            </div>
          )}

          {/* -- Result Step -- */}
          {step === resultStep && (
            <div className="text-center">
              {profileResult && PROFILE_INFO[profileResult] ? (
                <>
                  <div className={`mx-auto flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br ${PROFILE_INFO[profileResult].color} shadow-lg`}>
                    <CheckCircle2 size={36} className="text-white" />
                  </div>
                  <h2 className="mt-6 text-2xl font-bold tracking-tight text-white">
                    {PROFILE_INFO[profileResult].title_kr}
                  </h2>
                  <p className="mt-1 text-lg font-medium text-zinc-400">{PROFILE_INFO[profileResult].title}</p>
                  <p className="mt-3 text-sm text-zinc-500">{PROFILE_INFO[profileResult].desc}</p>

                  <div className="mt-8 rounded-2xl bg-white/5 border border-white/10 p-6 text-left">
                    <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">Quant Engine Auto-Configured</p>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-zinc-500">Technical Weight</span>
                        <span className="font-semibold text-zinc-200">{profileResult === "aggressive" ? "60%" : profileResult === "growth" ? "55%" : profileResult === "balanced" ? "50%" : "40%"}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-zinc-500">Buy Threshold</span>
                        <span className="font-semibold text-zinc-200">{profileResult === "aggressive" ? "60" : profileResult === "growth" ? "65" : profileResult === "balanced" ? "70" : "75"}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-zinc-500">Max Positions</span>
                        <span className="font-semibold text-zinc-200">{profileResult === "aggressive" ? "30" : profileResult === "growth" ? "20" : profileResult === "balanced" ? "15" : "10"}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-zinc-500">AI Coaching</span>
                        <span className="font-semibold capitalize text-zinc-200">{profileResult === "aggressive" ? "Aggressive" : profileResult === "growth" ? "Opportunity" : profileResult === "balanced" ? "Balanced" : "Risk Warning"}</span>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <CheckCircle2 size={48} className="mx-auto text-emerald-500" />
                  <h2 className="mt-4 text-2xl font-bold text-white">You&apos;re All Set!</h2>
                  <p className="mt-2 text-sm text-zinc-500">Your quant engine is ready.</p>
                </>
              )}

              <Button
                className="mt-8 w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white shadow-lg"
                onClick={handleFinish}
              >
                Launch Dashboard
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
