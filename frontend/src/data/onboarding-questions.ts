/**
 * PivoxQuant Onboarding Questionnaire v2
 * 20 questions across 6 categories.
 * Mirrored from questionnaire.py — hardcoded until the backend v2 endpoint ships.
 */

export interface OnboardingOption {
  value: string | number;
  label: string;
  label_kr: string;
  icon?: string;
  score?: number;
  required?: boolean;
}

export interface OnboardingQuestion {
  id: string;
  category: string;
  category_label: string;
  category_label_kr: string;
  question: string;
  question_kr: string;
  type: "single" | "multi" | "slider" | "multi_required";
  options: OnboardingOption[];
  /** Slider-specific */
  min?: number;
  max?: number;
  min_label?: string;
  max_label?: string;
  min_label_kr?: string;
  max_label_kr?: string;
}

export interface InvestorType {
  label: string;
  label_kr: string;
  description: string;
  description_kr: string;
  trading_style: string;
  typical_holding: string;
}

// ── Questions ────────────────────────────────────────────────────────────────

export const ONBOARDING_QUESTIONS: OnboardingQuestion[] = [
  // ═══ A. INVESTMENT IDENTITY ═══
  {
    id: "experience_years",
    category: "A",
    category_label: "Investment Identity",
    category_label_kr: "투자자 정체성",
    question: "How many years have you been actively investing?",
    question_kr: "투자를 시작한 지 얼마나 되셨나요?",
    type: "single",
    options: [
      { value: "none", label: "No experience yet", label_kr: "아직 투자 경험 없음", icon: "seedling" },
      { value: "lt1", label: "Less than 1 year", label_kr: "1년 미만", icon: "sprout" },
      { value: "1to3", label: "1 - 3 years", label_kr: "1~3년", icon: "leaf" },
      { value: "3to5", label: "3 - 5 years", label_kr: "3~5년", icon: "tree" },
      { value: "5plus", label: "5+ years", label_kr: "5년 이상", icon: "mountain" },
    ],
  },
  {
    id: "asset_types_traded",
    category: "A",
    category_label: "Investment Identity",
    category_label_kr: "투자자 정체성",
    question: "Which asset types have you traded before?",
    question_kr: "지금까지 거래해 본 자산 유형을 모두 선택해 주세요.",
    type: "multi",
    options: [
      { value: "stocks", label: "Individual Stocks", label_kr: "개별 주식" },
      { value: "etfs", label: "ETFs / Index Funds", label_kr: "ETF / 인덱스 펀드" },
      { value: "bonds", label: "Bonds / Fixed Income", label_kr: "채권 / 고정 수익 상품" },
      { value: "options", label: "Options", label_kr: "옵션" },
      { value: "futures", label: "Futures", label_kr: "선물" },
      { value: "crypto", label: "Cryptocurrency", label_kr: "암호화폐" },
      { value: "forex", label: "Forex", label_kr: "외환(FX)" },
      { value: "none", label: "None of the above", label_kr: "해당 없음" },
    ],
  },
  {
    id: "portfolio_size",
    category: "A",
    category_label: "Investment Identity",
    category_label_kr: "투자자 정체성",
    question: "What is the approximate size of your current investment portfolio?",
    question_kr: "현재 보유 중인 투자 포트폴리오 규모는 어느 정도인가요?",
    type: "single",
    options: [
      { value: "lt1k", label: "Under USD 1,000", label_kr: "USD 1,000 미만", icon: "wallet" },
      { value: "1k_10k", label: "USD 1,000 - USD 10,000", label_kr: "USD 1,000 ~ 10,000", icon: "banknote" },
      { value: "10k_50k", label: "USD 10,000 - USD 50,000", label_kr: "USD 10,000 ~ 50,000", icon: "piggy-bank" },
      { value: "50k_200k", label: "USD 50,000 - USD 200,000", label_kr: "USD 50,000 ~ 200,000", icon: "safe" },
      { value: "200k_plus", label: "USD 200,000+", label_kr: "USD 200,000 이상", icon: "building" },
    ],
  },
  {
    id: "monthly_investable",
    category: "A",
    category_label: "Investment Identity",
    category_label_kr: "투자자 정체성",
    question: "How much can you invest additionally each month?",
    question_kr: "매달 추가로 투자할 수 있는 금액은 얼마인가요?",
    type: "single",
    options: [
      { value: "lt100", label: "Under USD 100", label_kr: "USD 100 미만", icon: "coin" },
      { value: "100_500", label: "USD 100 - USD 500", label_kr: "USD 100 ~ 500", icon: "coins" },
      { value: "500_2k", label: "USD 500 - USD 2,000", label_kr: "USD 500 ~ 2,000", icon: "wallet" },
      { value: "2k_5k", label: "USD 2,000 - USD 5,000", label_kr: "USD 2,000 ~ 5,000", icon: "banknote" },
      { value: "5k_plus", label: "USD 5,000+", label_kr: "USD 5,000 이상", icon: "trending-up" },
    ],
  },
  {
    id: "income_stability",
    category: "A",
    category_label: "Investment Identity",
    category_label_kr: "투자자 정체성",
    question: "How stable is your primary income?",
    question_kr: "주된 소득 원천이 얼마나 안정적인가요?",
    type: "single",
    options: [
      { value: "very_stable", label: "Salaried / government job", label_kr: "급여 소득 / 공무원", icon: "shield" },
      { value: "stable", label: "Stable job, some variable", label_kr: "안정적인 직장, 일부 변동 소득", icon: "briefcase" },
      { value: "variable", label: "Freelance / contract", label_kr: "프리랜서 / 계약직", icon: "laptop" },
      { value: "volatile", label: "Commission / gig-based", label_kr: "성과급 / 플랫폼 노동", icon: "zap" },
      { value: "student", label: "Student / not employed", label_kr: "학생 / 미취업", icon: "book" },
    ],
  },

  // ═══ B. STRATEGY PREFERENCES ═══
  {
    id: "trading_frequency",
    category: "B",
    category_label: "Strategy Preferences",
    category_label_kr: "전략 성향",
    question: "How many trades would you ideally make per month?",
    question_kr: "한 달에 이상적으로 몇 번 정도 매매하고 싶으신가요?",
    type: "single",
    options: [
      { value: "rare", label: "0 - 2 (buy and forget)", label_kr: "0~2회 (사두고 잊는 편)", icon: "archive" },
      { value: "few", label: "3 - 5 (occasional)", label_kr: "3~5회 (가끔 매매)", icon: "clock" },
      { value: "moderate", label: "6 - 15 (regular)", label_kr: "6~15회 (정기적 매매)", icon: "repeat" },
      { value: "frequent", label: "16 - 40 (active)", label_kr: "16~40회 (활발한 매매)", icon: "activity" },
      { value: "daily", label: "40+ (daily trader)", label_kr: "40회 이상 (데이 트레이더)", icon: "zap" },
    ],
  },
  {
    id: "holding_period",
    category: "B",
    category_label: "Strategy Preferences",
    category_label_kr: "전략 성향",
    question: "How long do you typically hold a position?",
    question_kr: "보통 포지션을 얼마나 오래 보유하시나요?",
    type: "single",
    options: [
      { value: "intraday", label: "Same day (close by EOD)", label_kr: "당일 (장 마감 전 청산)", icon: "sun" },
      { value: "days", label: "2 - 5 days", label_kr: "2~5일", icon: "calendar" },
      { value: "weeks", label: "1 - 4 weeks", label_kr: "1~4주", icon: "calendar-range" },
      { value: "months", label: "1 - 6 months", label_kr: "1~6개월", icon: "hourglass" },
      { value: "years", label: "6+ months (long-term hold)", label_kr: "6개월 이상 (장기 보유)", icon: "infinity" },
    ],
  },
  {
    id: "rebalance_preference",
    category: "B",
    category_label: "Strategy Preferences",
    category_label_kr: "전략 성향",
    question: "How often would you like to review and rebalance your portfolio?",
    question_kr: "포트폴리오를 얼마나 자주 점검하고 리밸런싱하고 싶으신가요?",
    type: "single",
    options: [
      { value: "auto_daily", label: "Let AI handle it daily", label_kr: "AI가 매일 자동으로 처리", icon: "bot" },
      { value: "weekly", label: "Once a week", label_kr: "주 1회", icon: "calendar" },
      { value: "biweekly", label: "Every two weeks", label_kr: "2주에 1회", icon: "calendar-days" },
      { value: "monthly", label: "Once a month", label_kr: "월 1회", icon: "calendar-check" },
      { value: "quarterly", label: "Once a quarter", label_kr: "분기 1회", icon: "calendar-range" },
    ],
  },
  {
    id: "concentration_preference",
    category: "B",
    category_label: "Strategy Preferences",
    category_label_kr: "전략 성향",
    question: "How many stocks would you prefer to hold at once?",
    question_kr: "동시에 몇 종목 정도를 보유하고 싶으신가요?",
    type: "single",
    options: [
      { value: "ultra_focused", label: "1 - 3 (all-in conviction)", label_kr: "1~3종목 (집중 투자)", icon: "target" },
      { value: "focused", label: "4 - 8 (focused)", label_kr: "4~8종목 (선택과 집중)", icon: "crosshair" },
      { value: "moderate", label: "9 - 15 (balanced)", label_kr: "9~15종목 (균형 배분)", icon: "layers" },
      { value: "diversified", label: "16 - 25 (diversified)", label_kr: "16~25종목 (분산 투자)", icon: "grid" },
      { value: "broad", label: "25+ (very diversified)", label_kr: "25종목 이상 (광범위 분산)", icon: "globe" },
    ],
  },
  {
    id: "leverage_appetite",
    category: "B",
    category_label: "Strategy Preferences",
    category_label_kr: "전략 성향",
    question: "Are you interested in using leverage (margin) or leveraged ETFs?",
    question_kr: "레버리지(신용/마진) 또는 레버리지 ETF를 활용할 의향이 있으신가요?",
    type: "single",
    options: [
      { value: "never", label: "No, cash only", label_kr: "아니요, 현금만 운용", icon: "shield" },
      { value: "etf_only", label: "Only through leveraged ETFs", label_kr: "레버리지 ETF만 활용", icon: "bar-chart" },
      { value: "light", label: "Light margin (up to 1.5x)", label_kr: "소폭 레버리지 (최대 1.5배)", icon: "trending-up" },
      { value: "moderate", label: "Moderate margin (up to 2x)", label_kr: "중간 레버리지 (최대 2배)", icon: "rocket" },
      { value: "full", label: "Full margin where allowed", label_kr: "허용 한도 내 최대 레버리지", icon: "flame" },
    ],
  },

  // ═══ C. RISK PSYCHOLOGY ═══
  {
    id: "scenario_portfolio_drop",
    category: "C",
    category_label: "Risk Psychology",
    category_label_kr: "리스크 심리",
    question: "Your portfolio drops 10% in one week. What do you do?",
    question_kr: "포트폴리오가 1주일 만에 10% 하락했습니다. 어떻게 하시겠어요?",
    type: "single",
    options: [
      { value: "sell_all", label: "Sell everything immediately", label_kr: "즉시 전량 매도", score: 1 },
      { value: "sell_half", label: "Sell about half to reduce exposure", label_kr: "절반 정도 매도해 비중 축소", score: 3 },
      { value: "hold", label: "Hold and wait for recovery", label_kr: "그냥 보유하며 반등 기다림", score: 6 },
      { value: "buy_some", label: "Buy a little more at the dip", label_kr: "조금 더 매수해 평단 낮춤", score: 8 },
      { value: "buy_heavy", label: "Aggressively buy the dip", label_kr: "적극적으로 추가 매수", score: 10 },
    ],
  },
  {
    id: "scenario_single_stock_crash",
    category: "C",
    category_label: "Risk Psychology",
    category_label_kr: "리스크 심리",
    question: "One stock drops 40%, but fundamentals are unchanged. Your move?",
    question_kr: "보유 종목이 40% 급락했지만 펀더멘털에는 변화가 없습니다. 어떻게 하시겠어요?",
    type: "single",
    options: [
      { value: "cut_loss", label: "Sell it -- I can't tolerate that kind of loss", label_kr: "매도 — 이 정도 손실은 감당하기 어렵다", score: 2 },
      { value: "trim", label: "Trim position to reduce risk", label_kr: "일부 매도해 리스크 줄임", score: 4 },
      { value: "hold", label: "Hold -- fundamentals matter more than price", label_kr: "보유 — 펀더멘털이 가격보다 중요하다", score: 6 },
      { value: "avg_down", label: "Average down -- great company at a discount", label_kr: "추가 매수 — 좋은 기업을 싸게 살 기회", score: 8 },
      { value: "double_down", label: "Double the position -- this is a gift", label_kr: "배로 늘림 — 이건 기회다", score: 10 },
    ],
  },
  {
    id: "scenario_market_crash_relative",
    category: "C",
    category_label: "Risk Psychology",
    category_label_kr: "리스크 심리",
    question: "Market crashes 30%, but your portfolio is only down 10%. How do you feel?",
    question_kr: "시장이 30% 폭락했는데 내 포트폴리오는 10%만 하락했습니다. 기분이 어떤가요?",
    type: "single",
    options: [
      { value: "too_much", label: "Still too much loss -- I want even less exposure", label_kr: "그래도 손실이 너무 크다 — 비중을 더 줄이고 싶다", score: 2 },
      { value: "acceptable", label: "Acceptable -- this is what diversification is for", label_kr: "양호하다 — 분산 투자가 제 역할을 한 것", score: 5 },
      { value: "opportunistic", label: "Good -- and I'd use the crash to buy more", label_kr: "좋다 — 폭락을 기회 삼아 추가 매수할 것", score: 8 },
      { value: "regret_upside", label: "I wish I had more exposure to capture the recovery", label_kr: "아쉽다 — 반등 수익을 더 잡으려면 비중이 높았어야 했다", score: 10 },
    ],
  },

  // ═══ D. RETURN EXPECTATIONS ═══
  {
    id: "expected_annual_return",
    category: "D",
    category_label: "Return Expectations",
    category_label_kr: "수익 기대치",
    question: "What annual return do you realistically target? (target only — not guaranteed)",
    question_kr: "연간 목표 수익률은 얼마입니까? (목표 수익률 — 달성 보장 없음)",
    type: "single",
    options: [
      { value: "lt5", label: "Under 5% target (capital preservation) — not guaranteed", label_kr: "연 5% 미만 목표 (원금 보존) — 달성 보장 없음", icon: "shield" },
      { value: "5to10", label: "5 - 10% target (market-matching) — not guaranteed", label_kr: "연 5~10% 목표 (시장 평균 수준) — 달성 보장 없음", icon: "trending-up" },
      { value: "10to20", label: "10 - 20% target (above-benchmark) — not guaranteed", label_kr: "연 10~20% 목표 (시장 상회 지향) — 달성 보장 없음", icon: "rocket" },
      { value: "20to40", label: "20 - 40% target (high growth) — not guaranteed", label_kr: "연 20~40% 목표 (고성장 지향) — 달성 보장 없음", icon: "flame" },
      { value: "40plus", label: "40%+ target (moonshot) — not guaranteed", label_kr: "연 40% 이상 목표 (초고위험) — 달성 보장 없음", icon: "star" },
    ],
  },
  {
    id: "return_vs_stability",
    category: "D",
    category_label: "Return Expectations",
    category_label_kr: "수익 기대치",
    question: "Which 5-year target pattern would you prefer? (illustrative — not guaranteed)",
    question_kr: "5년간 어떤 목표 패턴을 선호합니까? (예시일 뿐 달성 보장 없음)",
    type: "single",
    options: [
      { value: "ultra_steady", label: "Steady +6% target every year (illustrative)", label_kr: "매년 연 +6% 목표 (예시 — 달성 보장 없음)", score: 1 },
      { value: "mostly_steady", label: "Target avg +10%, some flat years (illustrative)", label_kr: "평균 +10% 목표, 일부 연도 보합 (예시 — 달성 보장 없음)", score: 4 },
      { value: "volatile_mid", label: "Target avg +18%, one year could be -15% (illustrative)", label_kr: "평균 +18% 목표, 한 해 -15% 가능 (예시 — 달성 보장 없음)", score: 7 },
      { value: "volatile_high", label: "Target avg +30%, one year could be -25% (illustrative)", label_kr: "평균 +30% 목표, 한 해 -25% 가능 (예시 — 달성 보장 없음)", score: 10 },
    ],
  },
  {
    id: "min_acceptable_return",
    category: "D",
    category_label: "Return Expectations",
    category_label_kr: "수익 기대치",
    question: "What minimum target return would keep you using PivoxQuant? (target only — not guaranteed)",
    question_kr: "PivoxQuant을 계속 이용하기 위해 필요한 최소 목표 수익률은? (목표 수익률 — 달성 보장 없음)",
    type: "single",
    options: [
      { value: "positive", label: "Just don't lose money (target — not guaranteed)", label_kr: "원금 보존 목표 (달성 보장 없음)", icon: "shield" },
      { value: "beat_bank", label: "Above savings rates (~4% target — not guaranteed)", label_kr: "예금 금리 상회 목표 (~연 4% — 달성 보장 없음)", icon: "landmark" },
      { value: "beat_spy", label: "Above S&P 500 (~10% target — not guaranteed)", label_kr: "S&P 500 상회 목표 (~연 10% — 달성 보장 없음)", icon: "trending-up" },
      { value: "beat_20", label: "At least 20%+ target (not guaranteed)", label_kr: "연 20% 이상 목표 (달성 보장 없음)", icon: "rocket" },
    ],
  },

  // ═══ E. MARKET KNOWLEDGE ═══
  {
    id: "knowledge_concepts",
    category: "E",
    category_label: "Market Knowledge",
    category_label_kr: "시장 지식",
    question: "Which of these concepts do you understand well?",
    question_kr: "다음 중 잘 알고 있는 개념을 모두 선택해 주세요.",
    type: "multi",
    options: [
      { value: "pe_ratio", label: "P/E ratio", label_kr: "PER (주가수익비율)", score: 1 },
      { value: "market_cap", label: "Market capitalization", label_kr: "시가총액", score: 1 },
      { value: "short_selling", label: "Short selling", label_kr: "공매도", score: 2 },
      { value: "candlestick", label: "Candlestick charts", label_kr: "캔들 차트", score: 2 },
      { value: "rsi_macd", label: "RSI / MACD indicators", label_kr: "RSI / MACD 지표", score: 2 },
      { value: "options_greeks", label: "Options greeks", label_kr: "옵션 그릭스", score: 3 },
      { value: "beta_alpha", label: "Beta / Alpha", label_kr: "베타 / 알파", score: 2 },
      { value: "kelly_criterion", label: "Kelly criterion", label_kr: "켈리 기준", score: 3 },
      // A beginner who knows none of these MUST be able to advance — without
      // this escape option the wizard dead-ends at step 17 (CEO launch-blocker
      // 2026-05-24). handleMultiToggle clears other picks when "none" is chosen.
      { value: "none", label: "None of these", label_kr: "해당 없음", score: 0 },
    ],
  },
  {
    id: "knowledge_self_rating",
    category: "E",
    category_label: "Market Knowledge",
    category_label_kr: "시장 지식",
    question: "How confident are you reading a stock analysis report?",
    question_kr: "주식 분석 보고서를 얼마나 자신 있게 읽을 수 있나요?",
    type: "slider",
    min: 1,
    max: 5,
    min_label: "I need everything explained",
    max_label: "I can read a 10-K filing",
    min_label_kr: "모든 내용을 설명 들어야 이해 가능",
    max_label_kr: "10-K 사업보고서도 직접 읽을 수 있음",
    options: [
      { value: 1, label: "Need full guidance", label_kr: "전혀 모름" },
      { value: 2, label: "Basic understanding", label_kr: "기초 수준" },
      { value: 3, label: "Comfortable", label_kr: "무난하게 이해" },
      { value: 4, label: "Advanced", label_kr: "심화 수준" },
      { value: 5, label: "Expert", label_kr: "전문가 수준" },
    ],
  },

  // ═══ F. LEGAL & COMPLIANCE ═══
  {
    id: "legal_confirmations",
    category: "F",
    category_label: "Legal & Compliance",
    category_label_kr: "법적 확인",
    question: "Please confirm the following to proceed:",
    question_kr: "계속 진행하려면 아래 내용을 확인해 주세요.",
    type: "multi_required",
    options: [
      { value: "age_18", label: "I am 14 years or older", label_kr: "저는 만 14세 이상입니다.", required: true },
      { value: "experience_acknowledged", label: "I have confirmed my investment experience level accurately", label_kr: "저는 투자 경험 수준을 정확하게 입력하였습니다.", required: true },
      { value: "risk_acknowledged", label: "I understand that all investments carry risk and I may lose money", label_kr: "모든 투자에는 위험이 따르며 원금 손실이 발생할 수 있음을 이해합니다.", required: true },
      { value: "past_performance", label: "I understand that past performance does not guarantee future results", label_kr: "과거 수익률이 미래 성과를 보장하지 않음을 이해합니다.", required: true },
      { value: "ai_advisory", label: "I understand that PivoxQuant provides AI-generated analysis, not licensed financial advice", label_kr: "PivoxQuant은 AI 기반 분석 정보를 제공하며, 정식 투자 자문이 아님을 이해합니다.", required: true },
    ],
  },
];

/** Questions 0-17 are the wizard screens; question 18 (legal) is the final step. */
export const WIZARD_QUESTIONS = ONBOARDING_QUESTIONS.slice(0, 18);
export const LEGAL_QUESTION = ONBOARDING_QUESTIONS[18];

// ── Category metadata ────────────────────────────────────────────────────────

/* Category dot colors — bronze family + KR convention only.
   THE LILA BAN: no violet/blue-AI/pink. Each color carries semantic weight:
   bronze tones for identity/strategy/returns; KR muted red (#D18888) for
   risk-psychology (loss-domain hue); KR muted blue (#7AA0C8) for knowledge
   (trust/library hue); slate-500 for legal (institutional neutral). */
export const CATEGORIES: Record<string, { label: string; label_kr: string; icon: string; color: string }> = {
  A: { label: "Investment Identity", label_kr: "투자자 정체성", icon: "user", color: "#B8956A" },         // pq-bronze
  B: { label: "Strategy Preferences", label_kr: "전략 성향", icon: "settings", color: "#A3845C" },    // pq-bronze-light
  C: { label: "Risk Psychology", label_kr: "리스크 심리", icon: "brain", color: "#D18888" },            // KR muted red
  D: { label: "Return Expectations", label_kr: "수익 기대치", icon: "trending-up", color: "#6F5636" },  // pq-bronze-deep
  E: { label: "Market Knowledge", label_kr: "시장 지식", icon: "book-open", color: "#7AA0C8" },       // KR muted blue
  F: { label: "Legal & Compliance", label_kr: "법적 확인", icon: "shield", color: "#64748b" },        // slate-500 (kept)
};

// ── Investor Types ───────────────────────────────────────────────────────────

export const INVESTOR_TYPES: Record<string, InvestorType> = {
  passive_index_hugger: {
    label: "Passive Index Hugger",
    label_kr: "패시브 인덱스형",
    description: "Prefers broad market exposure with minimal active management. Seeks market-matching returns with the lowest possible effort and fees.",
    description_kr: "시장 전체에 폭넓게 분산 투자하며 적극적인 종목 선택을 최소화하는 유형. 낮은 비용으로 시장 평균 수익을 추구하는 성향.",
    trading_style: "buy_and_hold",
    typical_holding: "years",
  },
  steady_accumulator: {
    label: "Steady Accumulator",
    label_kr: "꾸준 적립형",
    description: "Systematic investor who dollar-cost-averages into quality stocks. Prioritizes consistency over home runs.",
    description_kr: "우량 자산에 정기적으로 분할 매수하며 꾸준히 자산을 쌓아가는 유형. 단기 대박보다 장기적인 일관성을 중시하는 성향.",
    trading_style: "position",
    typical_holding: "months",
  },
  value_hunter: {
    label: "Value Hunter",
    label_kr: "가치 탐색형",
    description: "Seeks undervalued stocks with strong fundamentals. Willing to hold through temporary drawdowns if the thesis holds.",
    description_kr: "탄탄한 펀더멘털을 갖춘 저평가 종목을 발굴하는 유형. 투자 근거가 유효한 한 일시적인 낙폭을 견디며 보유하는 성향.",
    trading_style: "position",
    typical_holding: "months",
  },
  risk_managed_growth: {
    label: "Risk-Managed Growth",
    label_kr: "리스크 관리 성장형",
    description: "Wants above-market returns but with strict downside protection. Uses stop-losses and position sizing rigorously.",
    description_kr: "시장을 상회하는 수익을 추구하되 철저한 하방 방어를 병행하는 유형. 포지션 크기 조절과 손실 한도를 엄격히 관리하는 성향.",
    trading_style: "swing",
    typical_holding: "weeks",
  },
  swing_trader: {
    label: "Swing Trader",
    label_kr: "스윙 트레이더",
    description: "Trades multi-day to multi-week moves. Uses technical setups and momentum signals to time entries and exits.",
    description_kr: "수일~수주 단위의 가격 흐름을 포착하는 유형. 기술적 패턴과 모멘텀 신호를 활용해 진입·청산 시점을 판단하는 성향.",
    trading_style: "swing",
    typical_holding: "weeks",
  },
  momentum_rider: {
    label: "Momentum Rider",
    label_kr: "모멘텀 추종형",
    description: "Chases strong price trends and rides winners. Comfortable with high turnover and concentrated bets on trending stocks.",
    description_kr: "강한 상승 추세를 따라가며 상승하는 종목에 집중 투자하는 유형. 높은 회전율과 트렌드 종목의 집중 비중을 편안하게 받아들이는 성향.",
    trading_style: "swing",
    typical_holding: "days",
  },
  macro_rotator: {
    label: "Macro Rotator",
    label_kr: "매크로 로테이션형",
    description: "Rotates sectors and asset classes based on macro trends. Thinks in terms of economic cycles, interest rates, and global flows.",
    description_kr: "거시경제 흐름에 따라 섹터와 자산군을 순환 교체하는 유형. 경기 사이클, 금리, 글로벌 자금 흐름을 중심으로 포트폴리오를 구성하는 성향.",
    trading_style: "position",
    typical_holding: "months",
  },
  aggressive_scalper: {
    label: "Aggressive Scalper",
    label_kr: "공격형 스캘퍼",
    description: "High-frequency, short-holding-period trader. Targets small profits many times per day with tight risk controls.",
    description_kr: "짧은 보유 시간 안에 소규모 수익을 반복적으로 추구하는 유형. 높은 거래 빈도와 엄격한 리스크 관리를 특징으로 하는 성향.",
    trading_style: "scalp",
    typical_holding: "intraday",
  },
};

// ── Profile highlights per type (shown on result screen) ─────────────────────

export const PROFILE_HIGHLIGHTS: Record<
  string,
  { tagline: string; tagline_kr: string; features: string[]; features_kr: string[] }
> = {
  passive_index_hugger: {
    tagline: "Low-touch investing. Maximum simplicity.",
    tagline_kr: "손이 덜 가는 투자, 최대한 단순하게.",
    features: [
      "Index-tracking model activated",
      "Monthly portfolio rebalance",
      "10% max drawdown target",
    ],
    features_kr: [
      "지수 추종 모델 작동",
      "월 1회 포트폴리오 리밸런스",
      "최대 낙폭 10% 목표",
    ],
  },
  steady_accumulator: {
    tagline: "Consistent, disciplined wealth building.",
    tagline_kr: "꾸준하고 규율 있게 쌓는 자산.",
    features: [
      "DCA + value models activated",
      "Bi-weekly rebalance cycle",
      "8% max drawdown target",
    ],
    features_kr: [
      "분할 매수 + 가치 모델 작동",
      "2주 단위 리밸런스 주기",
      "최대 낙폭 8% 목표",
    ],
  },
  value_hunter: {
    tagline: "Fundamental-driven, contrarian patience.",
    tagline_kr: "펀더멘털 중심, 역발상의 인내.",
    features: [
      "Fundamental screening models activated",
      "Deep value + mean reversion analysis",
      "12% max drawdown target",
    ],
    features_kr: [
      "펀더멘털 스크리닝 모델 작동",
      "딥밸류 + 평균회귀 분석",
      "최대 낙폭 12% 목표",
    ],
  },
  risk_managed_growth: {
    tagline: "Growth with guardrails. Every position has a plan.",
    tagline_kr: "가드레일 위의 성장, 모든 포지션에 계획을.",
    features: [
      "3 quant models activated for you",
      "Strict stop-loss enforcement",
      "8% max drawdown target",
    ],
    features_kr: [
      "퀀트 모델 3종 작동",
      "손실 한도 엄격 관리",
      "최대 낙폭 8% 목표",
    ],
  },
  swing_trader: {
    tagline: "Ride the waves. Technical precision meets patience.",
    tagline_kr: "파도를 타다, 기술적 정밀함과 인내의 만남.",
    features: [
      "4 quant models activated for you",
      "Swing entry/exit signals",
      "7% max drawdown target",
    ],
    features_kr: [
      "퀀트 모델 4종 작동",
      "스윙 진입·청산 신호",
      "최대 낙폭 7% 목표",
    ],
  },
  momentum_rider: {
    tagline: "You thrive on market trends, riding momentum for weeks.",
    tagline_kr: "시장 추세 위에서 몇 주씩 모멘텀을 타는 유형.",
    features: [
      "5 quant models activated for you",
      "Trail-only exit strategy (let winners run)",
      "15% max drawdown target",
    ],
    features_kr: [
      "퀀트 모델 5종 작동",
      "트레일링 청산 전략 (수익 종목은 길게)",
      "최대 낙폭 15% 목표",
    ],
  },
  macro_rotator: {
    tagline: "Think globally. Rotate tactically.",
    tagline_kr: "글로벌하게 보고, 전술적으로 순환.",
    features: [
      "Regime detection + sector rotation models",
      "Cross-asset momentum analysis",
      "10% max drawdown target",
    ],
    features_kr: [
      "국면 감지 + 섹터 로테이션 모델",
      "자산군 간 모멘텀 분석",
      "최대 낙폭 10% 목표",
    ],
  },
  aggressive_scalper: {
    tagline: "Speed is edge. Tight stops, many shots.",
    tagline_kr: "속도가 곧 우위, 짧은 손절과 잦은 시도.",
    features: [
      "Intraday momentum + volatility models",
      "Real-time signal streaming",
      "3% max drawdown target",
    ],
    features_kr: [
      "장중 모멘텀 + 변동성 모델",
      "실시간 신호 스트리밍",
      "최대 낙폭 3% 목표",
    ],
  },
};
