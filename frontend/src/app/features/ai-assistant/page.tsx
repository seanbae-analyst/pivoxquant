import Link from "next/link";
import type { Metadata } from "next";
import {
  ArrowLeft,
  ArrowRight,
  Brain,
  CheckCircle2,
  Sparkles,
} from "lucide-react";
import { Eyebrow } from "@/components/landing/eyebrow";
import { SectionCurtain } from "@/components/landing/section-curtain";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";

export const metadata: Metadata = {
  title: "당신의 전속 리서치 데스크 — PivoxQuant",
  description:
    "당신이 자는 동안 리포트가 만들어집니다. Morning Brief, Weekly Memo, Earnings Pre-Brief — 맥킨지 포맷의 분석물이 메일함에 도착합니다.",
};

const conversations = [
  {
    code: "MB",
    question: "Morning Brief · 화요일 06:00 KST",
    answer:
      "간밤 S&P 500 +0.4%, 보유 종목 중 NVDA +1.2% / AAPL -0.3%. 오늘 관찰 포인트: 10시 FOMC 의사록 공개, 당신 포트폴리오 금리 민감도 0.8β. 섹터 로테이션 신호는 에너지 → IT 방향.",
  },
  {
    code: "EP",
    question: "Earnings Pre-Brief · AAPL 실적 30분 전",
    answer:
      "Q3 EPS 컨센 $2.10, 가이던스 범위 $2.05~$2.18. 예상 질문 TOP 5: (1) 중국 매출 회복, (2) Vision Pro 판매량, (3) 서비스 마진, (4) 설비투자 가이던스, (5) 환율 영향. 당신 포지션 비중 18% — 실적 이후 변동성 주시.",
  },
  {
    code: "WM",
    question: "Weekly Investor Memo · 일요일 5p PDF",
    answer:
      "이번 주 포트폴리오 +1.8%, 벤치마크 +0.9% 대비 +0.9%p. 기여 섹터: IT(+1.1), 헬스케어(+0.4). 리스크 관찰: 테크 집중도 65% (목표 상한 40% 초과). 다음 주 관찰 포인트 3가지와 당신 테마의 논리 점검.",
  },
  {
    code: "YW",
    question: "Yearly Wrapped · 12월 31일",
    answer:
      "2026년 당신의 포트폴리오: 누적 +14.2%, 최고 보유일 3월 14일 (+3.1%), 가장 많이 거래한 섹터 반도체 (32회). Spotify Wrapped 스타일 카드 9:16 — 공유 가능. 당신의 투자 한 해가 한 장에.",
  },
];

const knowledgeSources = [
  { label: "당신의 포트폴리오와 실제 포지션" },
  { label: "실시간 시장 데이터·뉴스" },
  { label: "40개 퀀트 모델 출력물" },
  { label: "당신의 위험 허용도 프로필" },
  { label: "섹터·상관관계 분석" },
  { label: "과거 성과 패턴과 벤치마크" },
];

export default function AiAssistantPage() {
  return (
    <div className="min-h-screen bg-[var(--pq-ink)] text-[var(--pq-ivory)]">
      {/* ── Header ── */}
      <header className="border-b border-[rgba(245,240,232,0.08)] bg-[rgba(5,5,5,0.85)] backdrop-blur-xl sticky top-0 z-30">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-4 flex items-center gap-3">
          <Link
            href="/#features"
            className="inline-flex items-center gap-1.5 text-sm text-[rgba(245,240,232,0.55)] hover:text-[var(--pq-bronze)] transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </Link>
          <span className="text-[rgba(245,240,232,0.32)]">/</span>
          <span className="text-sm font-medium text-[var(--pq-ivory)]">Research Desk</span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-12 md:py-20">
        {/* ── Disclaimer ── */}
        <div className="mb-8">
          <DisclaimerBanner type="ai-analysis" />
        </div>

        {/* ── Title ── */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-sm bg-[rgba(184,149,106,0.08)] border border-[rgba(184,149,106,0.18)] mb-6">
            <Brain className="w-6 h-6 text-[var(--pq-bronze)]" />
          </div>
          <h1 className="font-[var(--font-display)] italic text-3xl sm:text-4xl font-medium text-[var(--pq-ivory)] mb-4 tracking-tight">
            당신의 전속 리서치 데스크
          </h1>
          <p className="text-base text-[rgba(245,240,232,0.62)] max-w-xl mx-auto">
            당신은 CFO입니다. 리포트는 저희가 씁니다. 매일 아침 6시, 메일함에.
          </p>
        </div>

        {/* ── 어떤 리포트가 도착하나요? ── */}
        <SectionCurtain divider={false}>
        <section className="mb-16">
          <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-6">어떤 리포트가 도착하나요?</h2>
          <div className="space-y-4">
            {conversations.map((conv, idx) => {
              const ordinal = String(idx + 1).padStart(2, "0");
              return (
                <div
                  key={conv.question}
                  className="rounded-sm border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.02)] p-5"
                >
                  <div className="flex items-start gap-4">
                    <div className="shrink-0 flex flex-col items-start gap-1">
                      <span className="font-[var(--font-serif)] text-[18px] tracking-[0.04em] text-[var(--pq-ivory)]">
                        {conv.code}
                      </span>
                      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-[rgba(245,240,232,0.48)] tabular-nums">
                        {ordinal} / 04
                      </span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="mb-3">
                        <p className="text-sm font-semibold text-[var(--pq-ivory)]">
                          &ldquo;{conv.question}&rdquo;
                        </p>
                      </div>
                      <div className="rounded-sm p-4 border border-[rgba(184,149,106,0.18)] bg-[rgba(184,149,106,0.04)]">
                        <div className="flex items-center gap-1.5 mb-2">
                          <Sparkles className="w-3.5 h-3.5 text-[var(--pq-bronze)]" />
                          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--pq-bronze)]">PivoxQuant Analyst Desk</span>
                        </div>
                        <p className="text-sm text-[rgba(245,240,232,0.82)] leading-relaxed">{conv.answer}</p>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
        </SectionCurtain>

        {/* ── 챗봇이 아닌 리서치 데스크 ── */}
        <SectionCurtain>
        <section className="mb-16">
          <div className="rounded-sm border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.02)] p-6 sm:p-8">
            <div className="mb-6">
              <Eyebrow withDashLeft={false} className="mb-2 flex">
                Research Desk · Method
              </Eyebrow>
              <h2 className="font-[var(--font-serif)] text-lg font-medium text-[var(--pq-ivory)]">챗봇이 아닌 리서치 데스크</h2>
              <p className="text-sm text-[rgba(245,240,232,0.62)] mt-1">당신의 장부를 읽고, 당신의 리포트를 씁니다.</p>
            </div>
            <p className="text-sm text-[rgba(245,240,232,0.82)] leading-relaxed mb-6">
              ChatGPT는 당신이 물어야 답합니다. PivoxQuant는 당신이 자는 동안 만듭니다. 정기 스케줄에 따라 매일·매주·분기별 리포트가 당신의 메일함, PDF, 음성 파일로 발행됩니다. 당신 포트폴리오 한 명만을 위한 리서치 데스크.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {knowledgeSources.map((source) => (
                <div key={source.label} className="flex items-center gap-3 rounded-sm px-4 py-3 border border-[rgba(245,240,232,0.08)] bg-[rgba(0,0,0,0.18)]">
                  <CheckCircle2 className="w-4 h-4 text-[var(--pq-bronze)] shrink-0" />
                  <span className="text-sm text-[rgba(245,240,232,0.82)]">{source.label}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
        </SectionCurtain>

        {/* ── How it works ── */}
        <SectionCurtain>
        <section className="mb-16">
          <h2 className="font-[var(--font-serif)] text-xl font-medium text-[var(--pq-ivory)] mb-6">리포트가 만들어지는 과정</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { step: "01", title: "CFO 프로필 등록", desc: "당신의 포트폴리오, 투자 스타일, 위험 허용도를 온보딩으로 입력합니다." },
              { step: "02", title: "데스크가 데이터 수집", desc: "당신 포지션·시장 데이터·40개 퀀트 모델·섹터 로테이션을 자동으로 읽습니다." },
              { step: "03", title: "리포트 발행", desc: "매일 6시 이메일, 일요일 PDF, 실적 30분 전 프리브리프가 자동 발송됩니다." },
            ].map((item) => (
              <div key={item.step} className="rounded-sm border border-[rgba(245,240,232,0.08)] bg-[rgba(255,255,255,0.02)] p-6 text-center">
                <div className="inline-flex items-center justify-center w-10 h-10 rounded-sm bg-[rgba(184,149,106,0.08)] border border-[rgba(184,149,106,0.18)] text-[var(--pq-bronze)] font-mono text-sm font-medium tabular-nums mb-3">
                  {item.step}
                </div>
                <h3 className="text-sm font-semibold text-[var(--pq-ivory)] mb-2">{item.title}</h3>
                <p className="text-sm text-[rgba(245,240,232,0.62)]">{item.desc}</p>
              </div>
            ))}
          </div>
        </section>
        </SectionCurtain>

        {/* ── CTA ── */}
        <SectionCurtain>
        <section className="text-center py-12 px-6 rounded-sm border border-[rgba(184,149,106,0.18)] bg-[rgba(184,149,106,0.04)]">
          <h2 className="font-[var(--font-display)] italic text-2xl font-medium text-[var(--pq-ivory)] mb-3">
            내일 아침 6시, 첫 리포트가 메일함에.
          </h2>
          <p className="text-[rgba(245,240,232,0.62)] mb-6 max-w-md mx-auto">
            무료 플랜으로 월간 Brag Card부터. Pro로 업그레이드하면 데일리 리포트가 시작됩니다.
          </p>
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 px-7 py-3 rounded-sm bg-[var(--pq-bronze)] text-[var(--pq-ink)] text-sm font-semibold hover:bg-[var(--pq-bronze-light)] transition-all"
          >
            첫 리포트 받아보기
            <ArrowRight className="w-4 h-4" />
          </Link>
        </section>
        </SectionCurtain>
      </main>
    </div>
  );
}
