/**
 * PivoxQuant Onboarding Questionnaire v3 — 5 questions + 1 legal block.
 *
 * Mirrored from `services/profile/questionnaire.py::QUESTIONNAIRE_V3`
 * (2026-09-06). The backend is the source of truth for scoring; this file
 * only carries the copy the wizard renders. IDs and option values MUST
 * match the backend — `is_v3_answers()` detects a V3 submission by these ids.
 *
 * Why five (docs/strategy/onboarding-questionnaire-v3_2026-09-06.md):
 * every question maps 1:1 onto an axis the product already observes from
 * trade history, so `/mirror` can put "what you said" next to "what you
 * did" on the same scale. Q5 is the free beta's research question and is
 * deliberately not scored. There is no local classifier any more — the
 * result screen renders the user's own answers verbatim, nothing derived.
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
  /** Observed feature key this declaration is reflected against (null = research-only). */
  mirror_axis?: string | null;
}

/** One line the backend echoes back — the user's own answer, verbatim. */
export interface DeclaredStatement {
  id: string;
  value: string;
  question: string;
  question_kr: string;
  label: string;
  label_kr: string;
}

// ── Questions ────────────────────────────────────────────────────────────────

export const ONBOARDING_QUESTIONS: OnboardingQuestion[] = [
  {
    id: "declared_holding",
    category: "A",
    category_label: "Holding habits",
    category_label_kr: "보유 습관",
    question: "When you buy a stock, how long do you usually hold it?",
    question_kr: "한 종목을 사면 보통 얼마나 들고 있나요?",
    type: "single",
    mirror_axis: "holding_period",
    options: [
      { value: "intraday", label: "Within the day", label_kr: "하루 안에 정리해요" },
      { value: "days", label: "A few days", label_kr: "며칠" },
      { value: "weeks", label: "A few weeks", label_kr: "몇 주" },
      { value: "months", label: "A few months", label_kr: "몇 달" },
      { value: "years", label: "A year or longer", label_kr: "1년 이상" },
    ],
  },
  {
    id: "declared_frequency",
    category: "A",
    category_label: "Holding habits",
    category_label_kr: "보유 습관",
    question: "Roughly how many buys and sells do you make in a month?",
    question_kr: "한 달에 매수·매도를 대략 몇 번 하나요?",
    type: "single",
    mirror_axis: "turnover",
    options: [
      { value: "rare", label: "0 – 2", label_kr: "0~2번" },
      { value: "few", label: "3 – 5", label_kr: "3~5번" },
      { value: "moderate", label: "6 – 15", label_kr: "6~15번" },
      { value: "frequent", label: "16 – 40", label_kr: "16~40번" },
      { value: "daily", label: "40+", label_kr: "40번 이상" },
    ],
  },
  {
    id: "declared_positions",
    category: "A",
    category_label: "Holding habits",
    category_label_kr: "보유 습관",
    question: "How many stocks do you usually hold at the same time?",
    question_kr: "보통 몇 종목을 동시에 들고 있나요?",
    type: "single",
    mirror_axis: "ticker_diversity",
    options: [
      { value: "ultra_focused", label: "1 – 3", label_kr: "1~3종목" },
      { value: "focused", label: "4 – 8", label_kr: "4~8종목" },
      { value: "moderate", label: "9 – 15", label_kr: "9~15종목" },
      { value: "diversified", label: "16 – 25", label_kr: "16~25종목" },
      { value: "broad", label: "25+", label_kr: "25종목 이상" },
    ],
  },
  {
    id: "declared_drawdown_response",
    category: "B",
    category_label: "When it drops",
    category_label_kr: "하락 대응",
    question: "Imagine your portfolio falls 10% in one week. What do you actually do?",
    question_kr: "포트폴리오가 한 주에 10% 빠졌다고 상상해 보세요. 실제로 무엇을 하나요?",
    type: "single",
    mirror_axis: "declared_risk",
    options: [
      { value: "sell_all", label: "Sell everything", label_kr: "다 팔아요" },
      { value: "sell_half", label: "Sell some", label_kr: "일부 팔아요" },
      { value: "hold", label: "Leave it", label_kr: "그냥 둬요" },
      { value: "buy_some", label: "Buy a little more", label_kr: "조금 더 사요" },
      { value: "buy_heavy", label: "Buy a lot more", label_kr: "크게 더 사요" },
    ],
  },
  {
    id: "record_habit",
    category: "C",
    category_label: "Recording",
    category_label_kr: "기록",
    question: "Have you ever written down why you made a trade?",
    question_kr: "지금까지 매매 이유를 어딘가에 적어 본 적 있나요?",
    type: "single",
    mirror_axis: null,
    options: [
      { value: "never", label: "No", label_kr: "없어요" },
      { value: "sometimes", label: "Sometimes, a quick note", label_kr: "가끔 메모해요" },
      { value: "regular", label: "Regularly, in a notebook or app", label_kr: "노트나 앱에 꾸준히 적어요" },
      { value: "used_to", label: "I used to, but stopped", label_kr: "예전엔 했는데 지금은 안 해요" },
    ],
  },
  // ═══ F. LEGAL & COMPLIANCE ═══ (ids/values unchanged from v2 — the backend
  // legal gate keys on `legal_confirmations` + these five required values)
  {
    id: "legal_confirmations",
    category: "F",
    category_label: "Legal & Compliance",
    category_label_kr: "법적 확인",
    question: "Please confirm the following to proceed:",
    question_kr: "계속하려면 다음을 확인해 주세요.",
    type: "multi_required",
    options: [
      { value: "age_18", label: "I am 14 years or older", label_kr: "저는 만 14세 이상입니다.", required: true },
      { value: "experience_acknowledged", label: "I have answered about my own habits as accurately as I can", label_kr: "저는 제 투자 습관에 대해 아는 대로 정확하게 답했습니다.", required: true },
      { value: "risk_acknowledged", label: "I understand that all investments carry risk and I may lose money", label_kr: "모든 투자에는 위험이 따르며 원금 손실이 발생할 수 있음을 이해합니다.", required: true },
      { value: "past_performance", label: "I understand that past performance does not guarantee future results", label_kr: "과거 수익률이 미래 성과를 보장하지 않음을 이해합니다.", required: true },
      { value: "ai_advisory", label: "I understand that PivoxQuant reflects back the record I enter myself, and is not licensed financial advice", label_kr: "PivoxQuant은 제가 직접 입력한 기록을 되비추어 보여줄 뿐이며, 정식 투자 자문이 아님을 이해합니다.", required: true },
    ],
  },
];

export const WIZARD_QUESTIONS = ONBOARDING_QUESTIONS.slice(0, 5);
export const LEGAL_QUESTION = ONBOARDING_QUESTIONS[5];

/**
 * The 8 canonical persona codes the backend rule table can emit for a V3
 * declaration (`questionnaire.py::_classify_declared_persona_v3`). Kept here
 * only so tests can pin that every reachable code collapses to one of the 3
 * disclosed buckets (§101) — the wizard itself never renders these.
 */
export const DECLARED_PERSONA_CODES = [
  "growth",
  "value",
  "balanced",
  "income",
  "quant",
  "speculator",
  "daytrader",
  "beginner",
] as const;

// ── Category metadata ────────────────────────────────────────────────────────

/* Category dot colors — bronze family + KR convention only.
   THE LILA BAN: no violet/blue-AI/pink. */
export const CATEGORIES: Record<string, { label: string; label_kr: string; icon: string; color: string }> = {
  A: { label: "Holding habits", label_kr: "보유 습관", icon: "layers", color: "#B8956A" },   // pq-bronze
  B: { label: "When it drops", label_kr: "하락 대응", icon: "trending-down", color: "#D18888" }, // KR muted red
  C: { label: "Recording", label_kr: "기록", icon: "book-open", color: "#A3845C" },         // pq-bronze-light
  F: { label: "Legal & Compliance", label_kr: "법적 확인", icon: "shield", color: "#64748b" }, // slate-500
};
