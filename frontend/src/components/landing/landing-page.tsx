"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import type { Variants } from "motion/react";
import {
  TrendingUp,
  BarChart3,
  Shield,
  Brain,
  Menu,
  X,
  ArrowRight,
  Check,
  ChevronRight,
  Star,
  Activity,
  Home,
  Target,
  Bell,
  Settings,
  Clock,
} from "lucide-react";

/* ──────────────────────────────────────────────
   Animation variants
   ────────────────────────────────────────────── */

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } },
};

const staggerContainer: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.1 } },
};

const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } },
};

/* ──────────────────────────────────────────────
   Feature data
   ────────────────────────────────────────────── */

const features = [
  {
    id: "01",
    icon: BarChart3,
    title: "Morning Brief",
    description:
      "매일 아침 6시, 내 포트폴리오 기준 시장 요약 리포트. 밤사이 뉴스·지표·섹터 로테이션 5분 안에.",
    href: "/features/quant-scoring",
  },
  {
    id: "02",
    icon: Shield,
    title: "Weekly Investor Memo",
    description:
      "일요일마다 맥킨지 스타일 5페이지 PDF가 메일함에 도착합니다. 분석팀 대신 주간 메모를.",
    href: "/features/risk-defense",
  },
  {
    id: "03",
    icon: Brain,
    title: "Earnings Pre-Brief",
    description:
      "내 종목 실적 발표 30분 전, 예상 질문 TOP 5와 관찰 포인트. 컨퍼런스콜 준비 완료.",
    href: "/features/ai-assistant",
  },
];

const stats = [
  { value: "58+", label: "Quant Models" },
  { value: "7-Layer", label: "Risk Defense" },
  { value: "US + KR", label: "Markets" },
  { value: "-52%", label: "MDD (backtest, past data)", disclaimer: "Past performance does not guarantee future results." },
];

const steps = [
  {
    step: "01",
    title: "CFO 프로필 등록",
    description:
      "20문항 온보딩으로 당신의 투자 스타일과 위험 허용도를 설정합니다. 당신이 CFO, 저희는 애널리스트 팀.",
  },
  {
    step: "02",
    title: "포트폴리오 연동",
    description:
      "Alpaca(미국) 또는 KIS(한국) 계좌를 연결하거나 직접 입력. 분석팀이 당신의 장부를 인수합니다.",
  },
  {
    step: "03",
    title: "리포트를 받아보세요",
    description:
      "매일 아침 Morning Brief, 매주 일요일 5p 메모, 실적 전 프리브리프. 당신이 자는 동안 리포트가 만들어집니다.",
  },
];

const pricingPlans = [
  {
    name: "Free",
    price: "0",
    currency: "",
    period: "",
    description: "맛보기 · 월 3개",
    features: [
      "Brag Card (월 1회)",
      "실적 캘린더",
      "관심종목 핫리스트",
    ],
    cta: "무료 시작",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "9,900",
    currency: "\u20a9",
    period: "/월",
    description: "데일리 리서치 데스크",
    features: [
      "Morning Brief · Evening Wrap",
      "Weekly Investor Memo (PDF)",
      "Earnings Pre-Brief",
      "Thesis Tracker",
      "Red/Green Alert",
    ],
    cta: "Pro로 구독",
    highlighted: false,
  },
  {
    name: "Premium",
    price: "19,900",
    currency: "\u20a9",
    period: "/월",
    description: "분기 리포트 + 시장 이벤트",
    features: [
      "Pro 전부 포함",
      "FOMC Playbook · CPI Brief",
      "Sector Monthly",
      "Tax Lot Harvest · IPO Radar",
      "Yearly Wrapped",
    ],
    cta: "Premium으로 구독",
    highlighted: true,
  },
  {
    name: "Elite",
    price: "29,900",
    currency: "\u20a9",
    period: "/월",
    description: "ChatGPT Plus 가격, 다른 제품",
    features: [
      "Premium 전부 포함",
      "10-K Personal (분기 사업보고서)",
      "Annual Letter to Self",
      "Commute Podcast (음성)",
      "Quarterly Self-Interview",
      "Peer Benchmark · Stress Test",
    ],
    cta: "Elite로 구독",
    highlighted: false,
  },
];

const footerLinks = {
  Product: [
    { label: "Features", href: "#features" },
    { label: "Pricing", href: "#pricing" },
    { label: "Paper Trading", href: "/features/paper-trading" },
  ],
  Company: [
    { label: "Contact", href: "mailto:seanbae1521@gmail.com" },
  ],
  Legal: [
    { label: "Privacy Policy", href: "/privacy" },
    { label: "Terms of Service", href: "/terms" },
    { label: "Disclaimer", href: "/terms" },
  ],
};

/* ──────────────────────────────────────────────
   Equity curve SVG
   ────────────────────────────────────────────── */

function MiniEquityCurve() {
  return (
    <svg viewBox="0 0 200 60" className="w-full h-12" preserveAspectRatio="none">
      <defs>
        <linearGradient id="curveGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0f172a" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#0f172a" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path
        d="M0 45 C20 42, 30 38, 50 35 C70 32, 80 28, 100 30 C120 32, 130 20, 150 15 C170 10, 180 12, 200 8"
        fill="none"
        stroke="#0f172a"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M0 45 C20 42, 30 38, 50 35 C70 32, 80 28, 100 30 C120 32, 130 20, 150 15 C170 10, 180 12, 200 8 L200 60 L0 60 Z"
        fill="url(#curveGrad)"
      />
    </svg>
  );
}

/* ──────────────────────────────────────────────
   Dashboard equity curve (full width section)
   ────────────────────────────────────────────── */

function DashboardEquityCurve() {
  return (
    <svg viewBox="0 0 500 120" className="w-full h-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id="dashCurve" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0f172a" stopOpacity="0.1" />
          <stop offset="100%" stopColor="#0f172a" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path
        d="M0 90 C30 88, 50 80, 80 75 C110 70, 130 65, 160 58 C190 51, 210 55, 240 48 C270 41, 290 38, 320 32 C350 26, 370 30, 400 22 C430 14, 460 18, 500 10"
        fill="none"
        stroke="#0f172a"
        strokeWidth="1.5"
      />
      <path
        d="M0 90 C30 88, 50 80, 80 75 C110 70, 130 65, 160 58 C190 51, 210 55, 240 48 C270 41, 290 38, 320 32 C350 26, 370 30, 400 22 C430 14, 460 18, 500 10 L500 120 L0 120 Z"
        fill="url(#dashCurve)"
      />
    </svg>
  );
}

/* ══════════════════════════════════════════════
   MAIN COMPONENT
   ══════════════════════════════════════════════ */

export default function LandingPage() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const prefersReduced = useReducedMotion();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // If user prefers reduced motion, skip framer variants
  const motionProps = (v: Variants) =>
    prefersReduced
      ? {}
      : {
          initial: "hidden" as const,
          whileInView: "visible" as const,
          viewport: { once: true, margin: "-60px" },
          variants: v,
        };

  // Hero is in the initial viewport — use `animate` instead of `whileInView`
  // so IntersectionObserver timing issues (first paint, hydration after
  // beta-gate redirect) cannot leave elements stuck at opacity:0.
  const heroMotionProps = (v: Variants) =>
    prefersReduced
      ? {}
      : {
          initial: "hidden" as const,
          animate: "visible" as const,
          variants: v,
        };

  return (
    <div className="min-h-screen bg-white text-slate-900 overflow-x-hidden">
      {/* ─── 1. NAVIGATION ─── */}
      <nav
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          scrolled
            ? "bg-white/80 backdrop-blur-xl border-b border-slate-100 shadow-sm"
            : "bg-transparent"
        }`}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-md bg-slate-900 flex items-center justify-center">
                <TrendingUp className="w-4 h-4 text-white" />
              </div>
              <span className="text-base font-semibold text-slate-900 tracking-tight">
                PivoxQuant
              </span>
            </Link>

            {/* Desktop Nav */}
            <div className="hidden md:flex items-center gap-8">
              <a href="#features" className="text-sm text-slate-500 hover:text-slate-900 transition-colors">
                Features
              </a>
              <a href="#how-it-works" className="text-sm text-slate-500 hover:text-slate-900 transition-colors">
                How It Works
              </a>
              <a href="#pricing" className="text-sm text-slate-500 hover:text-slate-900 transition-colors">
                Pricing
              </a>
              <a href="#resources" className="text-sm text-slate-500 hover:text-slate-900 transition-colors">
                Resources
              </a>
            </div>

            {/* Desktop CTA */}
            <div className="hidden md:flex items-center gap-3">
              <Link
                href="/login"
                className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors"
              >
                Sign In
              </Link>
              <Link
                href="/signup"
                className="inline-flex items-center px-5 py-2 rounded-full bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 transition-all active:scale-[0.97]"
              >
                Get Started Free
              </Link>
            </div>

            {/* Mobile hamburger */}
            <button
              className="md:hidden flex h-11 w-11 items-center justify-center rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="md:hidden bg-white border-b border-slate-100 shadow-lg"
          >
            <div className="px-4 py-4 space-y-1">
              <a href="#features" className="block text-sm text-slate-600 hover:text-slate-900 py-3" onClick={() => setMobileMenuOpen(false)}>
                Features
              </a>
              <a href="#how-it-works" className="block text-sm text-slate-600 hover:text-slate-900 py-3" onClick={() => setMobileMenuOpen(false)}>
                How It Works
              </a>
              <a href="#pricing" className="block text-sm text-slate-600 hover:text-slate-900 py-3" onClick={() => setMobileMenuOpen(false)}>
                Pricing
              </a>
              <a href="#resources" className="block text-sm text-slate-600 hover:text-slate-900 py-3" onClick={() => setMobileMenuOpen(false)}>
                Resources
              </a>
              <hr className="border-slate-100" />
              <Link href="/login" className="block text-sm font-medium text-slate-600 py-3">
                Sign In
              </Link>
              <Link
                href="/signup"
                className="block text-center px-5 py-2.5 rounded-full bg-slate-900 text-white text-sm font-semibold"
              >
                Get Started Free
              </Link>
            </div>
          </motion.div>
        )}
      </nav>

      {/* ─── 2. HERO SECTION ─── */}
      <section className="relative pt-28 pb-16 md:pt-32 md:pb-24 border-b border-slate-100">
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] gap-10 lg:gap-16 items-center">
            {/* Left: Text */}
            <motion.div {...heroMotionProps(staggerContainer)} className="max-w-xl">
              {/* Eyebrow — neutral */}
              <motion.div variants={fadeUp} className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md border border-slate-200 bg-white mb-6">
                <span className="w-1.5 h-1.5 rounded-full bg-slate-900" />
                <span className="text-[11px] font-medium text-slate-600 tracking-wide uppercase">당신의 전속 애널리스트 팀 · Beta</span>
              </motion.div>

              {/* Headline — no gradient */}
              <motion.h1 variants={fadeUp} className="font-serif text-[2rem] sm:text-5xl lg:text-[3.25rem] font-semibold leading-[1.1] tracking-tight text-slate-900 mb-5 break-keep">
                ChatGPT는 물어야 답합니다.<br />
                PivoxQuant는 자는 동안 씁니다.
              </motion.h1>

              {/* Subtitle */}
              <motion.p variants={fadeUp} className="text-base md:text-lg text-slate-600 leading-relaxed mb-8">
                매일 아침 6시, 당신 책상에 투자 보고서가 도착합니다.
                Morning Brief, 일요일 5페이지 메모, 실적 프리브리프 — 당신은 CFO, 리포트는 저희가 씁니다.
              </motion.p>

              {/* CTAs — neutral only */}
              <motion.div variants={fadeUp} className="flex flex-wrap gap-2.5 mb-5">
                <Link
                  href="/signup"
                  className="inline-flex items-center gap-2 h-11 px-5 rounded-md bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors active:scale-[0.98]"
                >
                  첫 리포트 받아보기
                  <ArrowRight className="w-4 h-4" />
                </Link>
                <a
                  href="#dashboard-preview"
                  className="inline-flex items-center gap-2 h-11 px-5 rounded-md border border-slate-200 bg-white text-slate-800 text-sm font-medium hover:border-slate-400 transition-colors active:scale-[0.98]"
                >
                  샘플 리포트 보기
                </a>
                <Link
                  href="/simulator/what-if"
                  className="inline-flex items-center gap-2 h-11 px-5 rounded-md text-slate-600 text-sm font-medium hover:text-slate-900 transition-colors"
                >
                  <Clock className="w-4 h-4" />
                  타임머신 시뮬레이터
                </Link>
              </motion.div>

              {/* Trust line */}
              <motion.p variants={fadeUp} className="text-xs text-slate-400">
                카드 등록 불필요 · 베타 기간 무료
              </motion.p>
            </motion.div>

            {/* Right: Dashboard preview card — Bloomberg density */}
            <motion.div {...heroMotionProps(scaleIn)} className="relative">
              <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
                {/* Terminal header */}
                <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-100 bg-slate-50/60">
                  <div className="flex items-center gap-2">
                    <div className="status-dot active" />
                    <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Portfolio · Live</span>
                  </div>
                  <span className="text-[11px] text-slate-400 numeric">14:32:08 KST</span>
                </div>

                {/* Header stats row */}
                <div className="grid grid-cols-3 divide-x divide-slate-100 border-b border-slate-100">
                  <div className="px-4 py-3">
                    <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Equity</p>
                    <p className="text-lg font-semibold text-slate-900 numeric">$127,450</p>
                  </div>
                  <div className="px-4 py-3">
                    <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Day P/L</p>
                    <p className="text-lg font-semibold up-color numeric">+$1,284</p>
                  </div>
                  <div className="px-4 py-3">
                    <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Risk</p>
                    <p className="text-lg font-semibold text-slate-900 numeric">85<span className="text-xs text-slate-400 ml-1">/100</span></p>
                  </div>
                </div>

                {/* Equity curve */}
                <div className="px-4 pt-3 pb-1">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-[10px] uppercase tracking-wider text-slate-400">Equity · 6M</p>
                    <p className="text-[10px] text-slate-500 numeric">+12.4%</p>
                  </div>
                  <MiniEquityCurve />
                </div>

                {/* Positions table — dense */}
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="border-t border-slate-100 bg-slate-50/40">
                      <th className="text-left px-4 py-1.5 text-[10px] uppercase tracking-wider text-slate-400 font-medium">Ticker</th>
                      <th className="text-right px-2 py-1.5 text-[10px] uppercase tracking-wider text-slate-400 font-medium">Price</th>
                      <th className="text-right px-2 py-1.5 text-[10px] uppercase tracking-wider text-slate-400 font-medium">Δ %</th>
                      <th className="text-right px-4 py-1.5 text-[10px] uppercase tracking-wider text-slate-400 font-medium">Score</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    <tr>
                      <td className="px-4 py-2 font-medium text-slate-900 numeric">TICKER A</td>
                      <td className="text-right px-2 py-2 numeric text-slate-700">—</td>
                      <td className="text-right px-2 py-2 numeric text-slate-400">—</td>
                      <td className="text-right px-4 py-2 numeric"><span className="signal-positive text-[11px] font-medium px-1.5 py-0.5 rounded">—</span></td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2 font-medium text-slate-900 numeric">TICKER B</td>
                      <td className="text-right px-2 py-2 numeric text-slate-700">—</td>
                      <td className="text-right px-2 py-2 numeric text-slate-400">—</td>
                      <td className="text-right px-4 py-2 numeric"><span className="signal-positive text-[11px] font-medium px-1.5 py-0.5 rounded">—</span></td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2 font-medium text-slate-900 numeric">TICKER C</td>
                      <td className="text-right px-2 py-2 numeric text-slate-700">—</td>
                      <td className="text-right px-2 py-2 numeric text-slate-400">—</td>
                      <td className="text-right px-4 py-2 numeric"><span className="signal-neutral text-[11px] font-medium px-1.5 py-0.5 rounded">—</span></td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2 font-medium text-slate-900 numeric">TICKER D</td>
                      <td className="text-right px-2 py-2 numeric text-slate-700">—</td>
                      <td className="text-right px-2 py-2 numeric text-slate-400">—</td>
                      <td className="text-right px-4 py-2 numeric"><span className="signal-positive text-[11px] font-medium px-1.5 py-0.5 rounded">—</span></td>
                    </tr>
                  </tbody>
                </table>

                {/* Footer */}
                <div className="flex items-center justify-between px-4 py-2 border-t border-slate-100 bg-slate-50/40">
                  <span className="text-[11px] text-slate-500">58 models · 7 layers active</span>
                  <span className="text-[11px] text-slate-400 numeric">MDD −52% (backtest)</span>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* ─── 3. STATS BAR — dense, numeric, no hype ─── */}
      <section className="bg-slate-950 py-10 md:py-12 border-y border-slate-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            {...motionProps(staggerContainer)}
            className="grid grid-cols-2 md:grid-cols-4 divide-x divide-slate-800"
          >
            {stats.map((stat) => (
              <motion.div key={stat.label} variants={fadeUp} className="px-4 md:px-8 first:pl-0 last:pr-0">
                <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1.5 font-medium">{stat.label}</p>
                <p className="text-2xl md:text-3xl font-semibold text-white numeric">{stat.value}</p>
                {stat.disclaimer && (
                  <p className="text-[9px] text-slate-500 mt-1.5 leading-tight">{stat.disclaimer}</p>
                )}
              </motion.div>
            ))}
          </motion.div>
          <p className="text-[11px] text-slate-500 mt-6 max-w-2xl">
            * Backtest only. Past performance does not guarantee future results. Figures are hypothetical.
          </p>
        </div>
      </section>

      {/* ─── 4. FEATURES — 3 column, monochrome, numbered ─── */}
      <section id="features" className="py-20 md:py-28 border-b border-slate-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div {...motionProps(fadeUp)} className="max-w-2xl mb-14">
            <p className="text-[11px] font-medium text-slate-500 mb-3 uppercase tracking-wider">당신의 리서치 데스크</p>
            <h2 className="font-serif text-3xl md:text-4xl font-semibold text-slate-900 mb-3 tracking-tight">
              챗봇이 아닙니다. 리포트가 나옵니다.
            </h2>
            <p className="text-base text-slate-600 leading-relaxed">
              Seeking Alpha가 만 명에게 보내는 리포트를, 당신 포트폴리오 한 명을 위해. 맥킨지 메모 포맷으로.
            </p>
          </motion.div>

          <motion.div
            {...motionProps(staggerContainer)}
            className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-slate-100 border border-slate-100 rounded-lg overflow-hidden"
          >
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <motion.div
                  key={feature.title}
                  variants={fadeUp}
                  className="bg-white p-8 group hover:bg-slate-50/60 transition-colors ease-apple"
                >
                  <div className="flex items-start justify-between mb-6">
                    <Icon className="w-5 h-5 text-slate-900" strokeWidth={1.5} />
                    <span className="text-[11px] font-medium text-slate-400 numeric tracking-wider">{feature.id}</span>
                  </div>
                  <h3 className="text-base font-semibold text-slate-900 mb-2 tracking-tight">{feature.title}</h3>
                  <p className="text-sm text-slate-600 leading-relaxed mb-5">{feature.description}</p>
                  <Link
                    href={feature.href}
                    className="inline-flex items-center gap-1 text-sm font-medium text-slate-900 border-b border-slate-300 group-hover:border-slate-900 transition-colors pb-0.5"
                  >
                    Learn more <ChevronRight className="w-3.5 h-3.5" strokeWidth={1.75} />
                  </Link>
                </motion.div>
              );
            })}
          </motion.div>
        </div>
      </section>

      {/* ─── 5. DASHBOARD PREVIEW ─── */}
      <section id="dashboard-preview" className="py-20 md:py-28 bg-slate-50/60 border-b border-slate-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div {...motionProps(fadeUp)} className="max-w-2xl mb-10">
            <p className="text-[11px] font-medium text-slate-500 mb-3 uppercase tracking-wider">Dashboard</p>
            <h2 className="font-serif text-3xl md:text-4xl font-semibold text-slate-900 mb-3 tracking-tight">
              포트폴리오 · 리스크 · 시그널 한 화면.
            </h2>
            <p className="text-base text-slate-600 leading-relaxed">
              모든 지표가 동일한 레이어에. 탭 전환 없이 전체를 읽습니다.
            </p>
          </motion.div>

          <motion.div {...motionProps(scaleIn)} className="relative">
            {/* Browser frame */}
            <div className="rounded-xl overflow-hidden border border-slate-200 shadow-2xl bg-white">
              {/* Browser chrome */}
              <div className="flex items-center gap-2 px-4 py-3 bg-slate-100 border-b border-slate-200">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-red-400" />
                  <div className="w-3 h-3 rounded-full bg-amber-400" />
                  <div className="w-3 h-3 rounded-full bg-emerald-400" />
                </div>
                <div className="flex-1 flex items-center gap-2 ml-4">
                  <div className="flex items-center gap-2 px-3 py-1 rounded-md bg-white border border-slate-200 text-xs text-slate-400 flex-1 max-w-md">
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
                    app.pivoxquant.com/home
                  </div>
                </div>
              </div>

              {/* Dashboard body */}
              <div className="flex min-h-[400px] md:min-h-[480px]">
                {/* Sidebar */}
                <div className="hidden md:flex flex-col w-52 border-r border-slate-100 bg-white p-4">
                  <div className="flex items-center gap-2 mb-8">
                    <div className="w-7 h-7 rounded-md bg-slate-900 flex items-center justify-center">
                      <TrendingUp className="w-3.5 h-3.5 text-white" strokeWidth={1.75} />
                    </div>
                    <span className="text-sm font-semibold tracking-tight">PivoxQuant</span>
                  </div>
                  <nav className="space-y-0.5">
                    {[
                      { icon: Home, label: "Home", active: true },
                      { icon: Activity, label: "Market", active: false },
                      { icon: Target, label: "Signals", active: false },
                      { icon: Shield, label: "Risk", active: false },
                      { icon: Brain, label: "Reports", active: false },
                      { icon: Bell, label: "Alerts", active: false },
                      { icon: Settings, label: "Settings", active: false },
                    ].map((item) => (
                      <div
                        key={item.label}
                        className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-[13px] ${
                          item.active
                            ? "bg-slate-100 text-slate-900 font-medium"
                            : "text-slate-500 hover:text-slate-800"
                        }`}
                      >
                        <item.icon className="w-4 h-4" strokeWidth={1.75} />
                        {item.label}
                      </div>
                    ))}
                  </nav>
                </div>

                {/* Main content */}
                <div className="flex-1 p-5 md:p-6">
                  {/* Metric cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
                    <div className="rounded-md border border-slate-200 p-3.5 bg-white">
                      <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-1">Portfolio Value</p>
                      <p className="text-lg font-semibold text-slate-900 numeric">$127,450</p>
                      <p className="text-[11px] up-color font-medium mt-1 numeric">+12.4% all time</p>
                    </div>
                    <div className="rounded-md border border-slate-200 p-3.5 bg-white">
                      <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-1">Risk Score</p>
                      <div className="flex items-baseline gap-2">
                        <p className="text-lg font-semibold text-slate-900 numeric">85</p>
                        <span className="text-[10px] font-medium text-slate-600 border border-slate-200 px-1.5 py-0.5 rounded">SAFE</span>
                      </div>
                      <p className="text-[11px] text-slate-500 mt-1">7 layers active</p>
                    </div>
                    <div className="rounded-md border border-slate-200 p-3.5 bg-white">
                      <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-1">Active Signals</p>
                      <p className="text-lg font-semibold text-slate-900 numeric">14</p>
                      <p className="text-[11px] text-slate-600 font-medium mt-1">3 new today</p>
                    </div>
                  </div>

                  {/* Chart area */}
                  <div className="rounded-md border border-slate-200 p-4 bg-white mb-5">
                    <div className="flex items-center justify-between mb-3">
                      <p className="text-xs font-medium text-slate-700">Portfolio Performance</p>
                      <div className="flex gap-0.5">
                        {["1W", "1M", "3M", "6M", "1Y"].map((t) => (
                          <span
                            key={t}
                            className={`px-1.5 py-0.5 rounded text-[10px] font-medium numeric ${
                              t === "6M" ? "bg-slate-900 text-white" : "text-slate-500 hover:text-slate-800"
                            }`}
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="h-28">
                      <DashboardEquityCurve />
                    </div>
                  </div>

                  {/* Signal list — table style */}
                  <div className="rounded-md border border-slate-200 bg-white overflow-hidden">
                    <div className="px-4 py-2.5 border-b border-slate-100 bg-slate-50/40">
                      <p className="text-[11px] font-medium text-slate-600 uppercase tracking-wider">Recent Signals</p>
                    </div>
                    {[
                      { ticker: "AAPL", name: "Apple", signal: "POSITIVE", score: 78, change: "+1.24%" },
                      { ticker: "MSFT", name: "Microsoft", signal: "POSITIVE", score: 82, change: "+0.82%" },
                      { ticker: "NVDA", name: "NVIDIA", signal: "NEUTRAL", score: 52, change: "−0.34%" },
                    ].map((item) => (
                      <div key={item.ticker} className="flex items-center justify-between px-4 py-2 border-b border-slate-100 last:border-0 hover:bg-slate-50/40">
                        <div className="flex items-center gap-3 min-w-0">
                          <span className="text-[13px] font-medium text-slate-900 numeric">{item.ticker}</span>
                          <span className="text-[11px] text-slate-400 truncate">{item.name}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className={`text-[11px] font-medium numeric ${item.change.startsWith("+") ? "up-color" : "down-color"}`}>{item.change}</span>
                          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded numeric ${item.signal === "POSITIVE" ? "signal-positive" : "signal-neutral"}`}>
                            {item.score}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ─── 6. HOW IT WORKS ─── */}
      <section id="how-it-works" className="py-20 md:py-28 border-b border-slate-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div {...motionProps(fadeUp)} className="max-w-2xl mb-14">
            <p className="text-[11px] font-medium text-slate-500 mb-3 uppercase tracking-wider">How It Works</p>
            <h2 className="font-serif text-3xl md:text-4xl font-semibold text-slate-900 mb-3 tracking-tight">
              3단계, 5분 안에 셋업.
            </h2>
          </motion.div>

          <motion.div
            {...motionProps(staggerContainer)}
            className="grid grid-cols-1 md:grid-cols-3 gap-px bg-slate-100 border border-slate-100 rounded-lg overflow-hidden"
          >
            {steps.map((step) => (
              <motion.div key={step.step} variants={fadeUp} className="bg-white p-8">
                <p className="text-[11px] font-medium text-slate-400 numeric tracking-wider mb-6">{step.step}</p>
                <h3 className="text-base font-semibold text-slate-900 mb-2 tracking-tight">{step.title}</h3>
                <p className="text-sm text-slate-600 leading-relaxed">{step.description}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ─── 7. PRICING ─── */}
      <section id="pricing" className="py-20 md:py-28 bg-slate-50/60 border-b border-slate-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div {...motionProps(fadeUp)} className="max-w-2xl mb-14">
            <p className="text-[11px] font-medium text-slate-500 mb-3 uppercase tracking-wider">Pricing</p>
            <h2 className="font-serif text-3xl md:text-4xl font-semibold text-slate-900 mb-3 tracking-tight">
              명확한 요금제.
            </h2>
            <p className="text-base text-slate-600 leading-relaxed">
              같은 가격, 다른 제품. ChatGPT는 물어야 답하고, PivoxQuant는 매일 만듭니다.
            </p>
          </motion.div>

          <motion.div
            {...motionProps(staggerContainer)}
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
          >
            {pricingPlans.map((plan) => (
              <motion.div
                key={plan.name}
                variants={fadeUp}
                className={`rounded-lg p-7 relative ${
                  plan.highlighted
                    ? "bg-slate-950 text-white border border-slate-900"
                    : "bg-white border border-slate-200"
                }`}
              >
                {plan.highlighted && (
                  <div className="absolute -top-2.5 left-7 px-2 py-0.5 rounded-sm bg-accent text-slate-900 text-[10px] font-semibold tracking-wider uppercase">
                    Most Popular
                  </div>
                )}

                <div className="mb-6">
                  <h3 className={`text-sm font-medium mb-1 uppercase tracking-wider ${plan.highlighted ? "text-slate-300" : "text-slate-500"}`}>
                    {plan.name}
                  </h3>
                  <p className={`text-xs mb-5 ${plan.highlighted ? "text-slate-400" : "text-slate-500"}`}>
                    {plan.description}
                  </p>
                  <div className="flex items-baseline gap-1">
                    <span className={`text-4xl font-semibold numeric tracking-tight ${plan.highlighted ? "text-white" : "text-slate-900"}`}>
                      {plan.currency}{plan.price}
                    </span>
                    {plan.period && (
                      <span className={`text-sm ${plan.highlighted ? "text-slate-400" : "text-slate-500"}`}>
                        {plan.period}
                      </span>
                    )}
                  </div>
                </div>

                <ul className="space-y-2.5 mb-7">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2">
                      <Check className={`w-4 h-4 mt-0.5 shrink-0 ${plan.highlighted ? "text-accent" : "text-slate-900"}`} strokeWidth={2} />
                      <span className={`text-sm ${plan.highlighted ? "text-slate-300" : "text-slate-700"}`}>
                        {feature}
                      </span>
                    </li>
                  ))}
                </ul>

                <Link
                  href="/signup"
                  className={`block text-center w-full h-10 px-4 rounded-md text-sm font-medium leading-10 transition-colors active:scale-[0.98] ${
                    plan.highlighted
                      ? "bg-white text-slate-900 hover:bg-slate-100"
                      : "bg-slate-900 text-white hover:bg-slate-800"
                  }`}
                >
                  {plan.cta}
                </Link>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ─── 8. QUOTE STRIP ─── */}
      <section className="bg-slate-950 py-20 md:py-24 border-y border-slate-900">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div {...motionProps(fadeUp)}>
            <Star className="w-5 h-5 text-accent mb-6" strokeWidth={1.5} />
            <blockquote className="text-2xl md:text-[2rem] font-medium text-white leading-snug mb-8 tracking-tight">
              &ldquo;당신은 당신 포트폴리오의 CFO입니다.<br />
              리서치 데스크는 저희가 운영합니다.&rdquo;
            </blockquote>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-md bg-slate-800 flex items-center justify-center">
                <TrendingUp className="w-4 h-4 text-white" strokeWidth={1.5} />
              </div>
              <div>
                <p className="text-xs font-medium text-white">PivoxQuant Analyst Desk</p>
                <p className="text-[11px] text-slate-400">24시간 운영 · 월 16개 리포트 발행</p>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ─── 9. FINAL CTA ─── */}
      <section className="py-20 md:py-24">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div {...motionProps(fadeUp)}>
            <h2 className="font-serif text-3xl md:text-4xl font-semibold text-slate-900 mb-4 tracking-tight">
              내일 아침 6시, 첫 리포트가 메일함에.
            </h2>
            <p className="text-base text-slate-600 mb-8 max-w-xl leading-relaxed">
              CFO 프로필 등록 · 포트폴리오 연동 · 리포트 구독. 5분이면 시작됩니다.
            </p>
            <div className="flex flex-wrap gap-2.5">
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 h-11 px-6 rounded-md bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors active:scale-[0.98]"
              >
                첫 리포트 받아보기
                <ArrowRight className="w-4 h-4" />
              </Link>
              <a
                href="mailto:seanbae1521@gmail.com"
                className="inline-flex items-center gap-2 h-11 px-6 rounded-md border border-slate-200 text-slate-700 text-sm font-medium hover:border-slate-400 transition-colors active:scale-[0.98]"
              >
                Contact Sales
              </a>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ─── 10. FOOTER ─── */}
      <footer className="border-t border-slate-200 bg-white py-12 md:py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-8 mb-12">
            {/* Brand */}
            <div className="col-span-2">
              <Link href="/" className="flex items-center gap-2.5 mb-4">
                <div className="w-8 h-8 rounded-md bg-slate-900 flex items-center justify-center">
                  <TrendingUp className="w-4 h-4 text-white" strokeWidth={1.75} />
                </div>
                <span className="text-base font-semibold text-slate-900 tracking-tight">
                  PivoxQuant
                </span>
              </Link>
              <p className="text-sm text-slate-500 leading-relaxed max-w-xs">
                당신의 전속 리서치 데스크. 매일 아침 6시, 리포트가 도착합니다.
              </p>
            </div>

            {/* Links */}
            {Object.entries(footerLinks).map(([title, links]) => (
              <div key={title}>
                <h4 className="text-xs font-semibold text-slate-900 uppercase tracking-wider mb-3">{title}</h4>
                <ul className="space-y-2">
                  {links.map((link) => (
                    <li key={link.label}>
                      <a href={link.href} className="text-sm text-slate-400 hover:text-slate-600 transition-colors">
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* Bottom bar */}
          <div className="pt-8 border-t border-slate-100">
            <div className="flex flex-col md:flex-row items-center justify-between gap-4">
              <p className="text-xs text-slate-400">
                &copy; {new Date().getFullYear()} PivoxQuant. All rights reserved.
              </p>
              <a
                href="mailto:seanbae1521@gmail.com"
                className="text-xs text-slate-400 hover:text-slate-600 transition-colors"
              >
                seanbae1521@gmail.com
              </a>
            </div>

            {/* Disclaimer */}
            <p className="text-[10px] text-slate-300 mt-6 text-center leading-relaxed max-w-3xl mx-auto">
              Past performance does not guarantee future results. PivoxQuant provides analytical tools, not investment advice.
              All investing involves risk. Please consult a qualified financial advisor before making investment decisions.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
