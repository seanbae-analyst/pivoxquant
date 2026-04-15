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
    category_label_kr: "Investment Identity",
    question: "How many years have you been actively investing?",
    question_kr: "How many years have you been actively investing?",
    type: "single",
    options: [
      { value: "none", label: "No experience yet", label_kr: "No experience yet", icon: "seedling" },
      { value: "lt1", label: "Less than 1 year", label_kr: "Less than 1 year", icon: "sprout" },
      { value: "1to3", label: "1 - 3 years", label_kr: "1 - 3 years", icon: "leaf" },
      { value: "3to5", label: "3 - 5 years", label_kr: "3 - 5 years", icon: "tree" },
      { value: "5plus", label: "5+ years", label_kr: "5+ years", icon: "mountain" },
    ],
  },
  {
    id: "asset_types_traded",
    category: "A",
    category_label: "Investment Identity",
    category_label_kr: "Investment Identity",
    question: "Which asset types have you traded before?",
    question_kr: "Which asset types have you traded before?",
    type: "multi",
    options: [
      { value: "stocks", label: "Individual Stocks", label_kr: "Individual Stocks" },
      { value: "etfs", label: "ETFs / Index Funds", label_kr: "ETFs / Index Funds" },
      { value: "bonds", label: "Bonds / Fixed Income", label_kr: "Bonds / Fixed Income" },
      { value: "options", label: "Options", label_kr: "Options" },
      { value: "futures", label: "Futures", label_kr: "Futures" },
      { value: "crypto", label: "Cryptocurrency", label_kr: "Cryptocurrency" },
      { value: "forex", label: "Forex", label_kr: "Forex" },
      { value: "none", label: "None of the above", label_kr: "None of the above" },
    ],
  },
  {
    id: "portfolio_size",
    category: "A",
    category_label: "Investment Identity",
    category_label_kr: "Investment Identity",
    question: "What is the approximate size of your current investment portfolio?",
    question_kr: "What is the approximate size of your current investment portfolio?",
    type: "single",
    options: [
      { value: "lt1k", label: "Under $1,000", label_kr: "Under $1,000", icon: "wallet" },
      { value: "1k_10k", label: "$1,000 - $10,000", label_kr: "$1,000 - $10,000", icon: "banknote" },
      { value: "10k_50k", label: "$10,000 - $50,000", label_kr: "$10,000 - $50,000", icon: "piggy-bank" },
      { value: "50k_200k", label: "$50,000 - $200,000", label_kr: "$50,000 - $200,000", icon: "safe" },
      { value: "200k_plus", label: "$200,000+", label_kr: "$200,000+", icon: "building" },
    ],
  },
  {
    id: "monthly_investable",
    category: "A",
    category_label: "Investment Identity",
    category_label_kr: "Investment Identity",
    question: "How much can you invest additionally each month?",
    question_kr: "How much can you invest additionally each month?",
    type: "single",
    options: [
      { value: "lt100", label: "Under $100", label_kr: "Under $100", icon: "coin" },
      { value: "100_500", label: "$100 - $500", label_kr: "$100 - $500", icon: "coins" },
      { value: "500_2k", label: "$500 - $2,000", label_kr: "$500 - $2,000", icon: "wallet" },
      { value: "2k_5k", label: "$2,000 - $5,000", label_kr: "$2,000 - $5,000", icon: "banknote" },
      { value: "5k_plus", label: "$5,000+", label_kr: "$5,000+", icon: "trending-up" },
    ],
  },
  {
    id: "income_stability",
    category: "A",
    category_label: "Investment Identity",
    category_label_kr: "Investment Identity",
    question: "How stable is your primary income?",
    question_kr: "How stable is your primary income?",
    type: "single",
    options: [
      { value: "very_stable", label: "Salaried / government job", label_kr: "Salaried / government job", icon: "shield" },
      { value: "stable", label: "Stable job, some variable", label_kr: "Stable job, some variable", icon: "briefcase" },
      { value: "variable", label: "Freelance / contract", label_kr: "Freelance / contract", icon: "laptop" },
      { value: "volatile", label: "Commission / gig-based", label_kr: "Commission / gig-based", icon: "zap" },
      { value: "student", label: "Student / not employed", label_kr: "Student / not employed", icon: "book" },
    ],
  },

  // ═══ B. STRATEGY PREFERENCES ═══
  {
    id: "trading_frequency",
    category: "B",
    category_label: "Strategy Preferences",
    category_label_kr: "Strategy Preferences",
    question: "How many trades would you ideally make per month?",
    question_kr: "How many trades would you ideally make per month?",
    type: "single",
    options: [
      { value: "rare", label: "0 - 2 (buy and forget)", label_kr: "0 - 2 (buy and forget)", icon: "archive" },
      { value: "few", label: "3 - 5 (occasional)", label_kr: "3 - 5 (occasional)", icon: "clock" },
      { value: "moderate", label: "6 - 15 (regular)", label_kr: "6 - 15 (regular)", icon: "repeat" },
      { value: "frequent", label: "16 - 40 (active)", label_kr: "16 - 40 (active)", icon: "activity" },
      { value: "daily", label: "40+ (daily trader)", label_kr: "40+ (daily trader)", icon: "zap" },
    ],
  },
  {
    id: "holding_period",
    category: "B",
    category_label: "Strategy Preferences",
    category_label_kr: "Strategy Preferences",
    question: "How long do you typically hold a position?",
    question_kr: "How long do you typically hold a position?",
    type: "single",
    options: [
      { value: "intraday", label: "Same day (close by EOD)", label_kr: "Same day (close by EOD)", icon: "sun" },
      { value: "days", label: "2 - 5 days", label_kr: "2 - 5 days", icon: "calendar" },
      { value: "weeks", label: "1 - 4 weeks", label_kr: "1 - 4 weeks", icon: "calendar-range" },
      { value: "months", label: "1 - 6 months", label_kr: "1 - 6 months", icon: "hourglass" },
      { value: "years", label: "6+ months (long-term hold)", label_kr: "6+ months (long-term hold)", icon: "infinity" },
    ],
  },
  {
    id: "rebalance_preference",
    category: "B",
    category_label: "Strategy Preferences",
    category_label_kr: "Strategy Preferences",
    question: "How often would you like to review and rebalance your portfolio?",
    question_kr: "How often would you like to review and rebalance your portfolio?",
    type: "single",
    options: [
      { value: "auto_daily", label: "Let AI handle it daily", label_kr: "Let AI handle it daily", icon: "bot" },
      { value: "weekly", label: "Once a week", label_kr: "Once a week", icon: "calendar" },
      { value: "biweekly", label: "Every two weeks", label_kr: "Every two weeks", icon: "calendar-days" },
      { value: "monthly", label: "Once a month", label_kr: "Once a month", icon: "calendar-check" },
      { value: "quarterly", label: "Once a quarter", label_kr: "Once a quarter", icon: "calendar-range" },
    ],
  },
  {
    id: "concentration_preference",
    category: "B",
    category_label: "Strategy Preferences",
    category_label_kr: "Strategy Preferences",
    question: "How many stocks would you prefer to hold at once?",
    question_kr: "How many stocks would you prefer to hold at once?",
    type: "single",
    options: [
      { value: "ultra_focused", label: "1 - 3 (all-in conviction)", label_kr: "1 - 3 (all-in conviction)", icon: "target" },
      { value: "focused", label: "4 - 8 (focused)", label_kr: "4 - 8 (focused)", icon: "crosshair" },
      { value: "moderate", label: "9 - 15 (balanced)", label_kr: "9 - 15 (balanced)", icon: "layers" },
      { value: "diversified", label: "16 - 25 (diversified)", label_kr: "16 - 25 (diversified)", icon: "grid" },
      { value: "broad", label: "25+ (very diversified)", label_kr: "25+ (very diversified)", icon: "globe" },
    ],
  },
  {
    id: "leverage_appetite",
    category: "B",
    category_label: "Strategy Preferences",
    category_label_kr: "Strategy Preferences",
    question: "Are you interested in using leverage (margin) or leveraged ETFs?",
    question_kr: "Are you interested in using leverage (margin) or leveraged ETFs?",
    type: "single",
    options: [
      { value: "never", label: "No, cash only", label_kr: "No, cash only", icon: "shield" },
      { value: "etf_only", label: "Only through leveraged ETFs", label_kr: "Only through leveraged ETFs", icon: "bar-chart" },
      { value: "light", label: "Light margin (up to 1.5x)", label_kr: "Light margin (up to 1.5x)", icon: "trending-up" },
      { value: "moderate", label: "Moderate margin (up to 2x)", label_kr: "Moderate margin (up to 2x)", icon: "rocket" },
      { value: "full", label: "Full margin where allowed", label_kr: "Full margin where allowed", icon: "flame" },
    ],
  },

  // ═══ C. RISK PSYCHOLOGY ═══
  {
    id: "scenario_portfolio_drop",
    category: "C",
    category_label: "Risk Psychology",
    category_label_kr: "Risk Psychology",
    question: "Your portfolio drops 10% in one week. What do you do?",
    question_kr: "Your portfolio drops 10% in one week. What do you do?",
    type: "single",
    options: [
      { value: "sell_all", label: "Sell everything immediately", label_kr: "Sell everything immediately", score: 1 },
      { value: "sell_half", label: "Sell about half to reduce exposure", label_kr: "Sell about half to reduce exposure", score: 3 },
      { value: "hold", label: "Hold and wait for recovery", label_kr: "Hold and wait for recovery", score: 6 },
      { value: "buy_some", label: "Buy a little more at the dip", label_kr: "Buy a little more at the dip", score: 8 },
      { value: "buy_heavy", label: "Aggressively buy the dip", label_kr: "Aggressively buy the dip", score: 10 },
    ],
  },
  {
    id: "scenario_single_stock_crash",
    category: "C",
    category_label: "Risk Psychology",
    category_label_kr: "Risk Psychology",
    question: "One stock drops 40%, but fundamentals are unchanged. Your move?",
    question_kr: "One stock drops 40%, but fundamentals are unchanged. Your move?",
    type: "single",
    options: [
      { value: "cut_loss", label: "Sell it -- I can't tolerate that kind of loss", label_kr: "Sell it -- I can't tolerate that kind of loss", score: 2 },
      { value: "trim", label: "Trim position to reduce risk", label_kr: "Trim position to reduce risk", score: 4 },
      { value: "hold", label: "Hold -- fundamentals matter more than price", label_kr: "Hold -- fundamentals matter more than price", score: 6 },
      { value: "avg_down", label: "Average down -- great company at a discount", label_kr: "Average down -- great company at a discount", score: 8 },
      { value: "double_down", label: "Double the position -- this is a gift", label_kr: "Double the position -- this is a gift", score: 10 },
    ],
  },
  {
    id: "scenario_market_crash_relative",
    category: "C",
    category_label: "Risk Psychology",
    category_label_kr: "Risk Psychology",
    question: "Market crashes 30%, but your portfolio is only down 10%. How do you feel?",
    question_kr: "Market crashes 30%, but your portfolio is only down 10%. How do you feel?",
    type: "single",
    options: [
      { value: "too_much", label: "Still too much loss -- I want even less exposure", label_kr: "Still too much loss -- I want even less exposure", score: 2 },
      { value: "acceptable", label: "Acceptable -- this is what diversification is for", label_kr: "Acceptable -- this is what diversification is for", score: 5 },
      { value: "opportunistic", label: "Good -- and I'd use the crash to buy more", label_kr: "Good -- and I'd use the crash to buy more", score: 8 },
      { value: "regret_upside", label: "I wish I had more exposure to capture the recovery", label_kr: "I wish I had more exposure to capture the recovery", score: 10 },
    ],
  },
  {
    id: "loss_aversion_coinflip",
    category: "C",
    category_label: "Risk Psychology",
    category_label_kr: "Risk Psychology",
    question: "Would you take this bet? Heads you win $200, tails you lose $100.",
    question_kr: "Would you take this bet? Heads you win $200, tails you lose $100.",
    type: "single",
    options: [
      { value: "never", label: "No -- I hate losing money, even in favorable bets", label_kr: "No -- I hate losing money, even in favorable bets", score: 1 },
      { value: "maybe_small", label: "Maybe once if the amount was smaller", label_kr: "Maybe once if the amount was smaller", score: 4 },
      { value: "yes_once", label: "Yes, I'd take it once", label_kr: "Yes, I'd take it once", score: 7 },
      { value: "yes_repeat", label: "Yes, and I'd repeat it -- the math is in my favor", label_kr: "Yes, and I'd repeat it -- the math is in my favor", score: 10 },
    ],
  },

  // ═══ D. RETURN EXPECTATIONS ═══
  {
    id: "expected_annual_return",
    category: "D",
    category_label: "Return Expectations",
    category_label_kr: "Return Expectations",
    question: "What annual return do you realistically expect?",
    question_kr: "What annual return do you realistically expect?",
    type: "single",
    options: [
      { value: "lt5", label: "Under 5% (capital preservation)", label_kr: "Under 5% (capital preservation)", icon: "shield" },
      { value: "5to10", label: "5% - 10% (match the market)", label_kr: "5% - 10% (match the market)", icon: "trending-up" },
      { value: "10to20", label: "10% - 20% (beat the market)", label_kr: "10% - 20% (beat the market)", icon: "rocket" },
      { value: "20to40", label: "20% - 40% (high growth)", label_kr: "20% - 40% (high growth)", icon: "flame" },
      { value: "40plus", label: "40%+ (moonshot territory)", label_kr: "40%+ (moonshot territory)", icon: "star" },
    ],
  },
  {
    id: "return_vs_stability",
    category: "D",
    category_label: "Return Expectations",
    category_label_kr: "Return Expectations",
    question: "Which would you prefer over 5 years?",
    question_kr: "Which would you prefer over 5 years?",
    type: "single",
    options: [
      { value: "ultra_steady", label: "Steady +6% every year, no drama", label_kr: "Steady +6% every year, no drama", score: 1 },
      { value: "mostly_steady", label: "Average +10%, but some years flat", label_kr: "Average +10%, but some years flat", score: 4 },
      { value: "volatile_mid", label: "Average +18%, but one year could be -15%", label_kr: "Average +18%, but one year could be -15%", score: 7 },
      { value: "volatile_high", label: "Average +30%, but one year could be -25%", label_kr: "Average +30%, but one year could be -25%", score: 10 },
    ],
  },
  {
    id: "min_acceptable_return",
    category: "D",
    category_label: "Return Expectations",
    category_label_kr: "Return Expectations",
    question: "What is the minimum return that would keep you using PivoxQuant?",
    question_kr: "What is the minimum return that would keep you using PivoxQuant?",
    type: "single",
    options: [
      { value: "positive", label: "Just don't lose money", label_kr: "Just don't lose money", icon: "shield" },
      { value: "beat_bank", label: "Beat savings account rates (~4%)", label_kr: "Beat savings account rates (~4%)", icon: "landmark" },
      { value: "beat_spy", label: "Beat the S&P 500 (~10%)", label_kr: "Beat the S&P 500 (~10%)", icon: "trending-up" },
      { value: "beat_20", label: "Need at least 20%+", label_kr: "Need at least 20%+", icon: "rocket" },
    ],
  },

  // ═══ E. MARKET KNOWLEDGE ═══
  {
    id: "knowledge_concepts",
    category: "E",
    category_label: "Market Knowledge",
    category_label_kr: "Market Knowledge",
    question: "Which of these concepts do you understand well?",
    question_kr: "Which of these concepts do you understand well?",
    type: "multi",
    options: [
      { value: "pe_ratio", label: "P/E ratio", label_kr: "P/E ratio", score: 1 },
      { value: "market_cap", label: "Market capitalization", label_kr: "Market capitalization", score: 1 },
      { value: "short_selling", label: "Short selling", label_kr: "Short selling", score: 2 },
      { value: "candlestick", label: "Candlestick charts", label_kr: "Candlestick charts", score: 2 },
      { value: "rsi_macd", label: "RSI / MACD indicators", label_kr: "RSI / MACD indicators", score: 2 },
      { value: "options_greeks", label: "Options greeks", label_kr: "Options greeks", score: 3 },
      { value: "beta_alpha", label: "Beta / Alpha", label_kr: "Beta / Alpha", score: 2 },
      { value: "kelly_criterion", label: "Kelly criterion", label_kr: "Kelly criterion", score: 3 },
    ],
  },
  {
    id: "knowledge_self_rating",
    category: "E",
    category_label: "Market Knowledge",
    category_label_kr: "Market Knowledge",
    question: "How confident are you reading a stock analysis report?",
    question_kr: "How confident are you reading a stock analysis report?",
    type: "slider",
    min: 1,
    max: 5,
    min_label: "I need everything explained",
    max_label: "I can read a 10-K filing",
    min_label_kr: "I need everything explained",
    max_label_kr: "I can read a 10-K filing",
    options: [
      { value: 1, label: "Need full guidance", label_kr: "Need full guidance" },
      { value: 2, label: "Basic understanding", label_kr: "Basic understanding" },
      { value: 3, label: "Comfortable", label_kr: "Comfortable" },
      { value: 4, label: "Advanced", label_kr: "Advanced" },
      { value: 5, label: "Expert", label_kr: "Expert" },
    ],
  },

  // ═══ F. LEGAL & COMPLIANCE ═══
  {
    id: "legal_confirmations",
    category: "F",
    category_label: "Legal & Compliance",
    category_label_kr: "Legal & Compliance",
    question: "Please confirm the following to proceed:",
    question_kr: "Please confirm the following to proceed:",
    type: "multi_required",
    options: [
      { value: "age_18", label: "I am 18 years or older", label_kr: "I am 18 years or older", required: true },
      { value: "experience_acknowledged", label: "I have confirmed my investment experience level accurately", label_kr: "I have confirmed my investment experience level accurately", required: true },
      { value: "risk_acknowledged", label: "I understand that all investments carry risk and I may lose money", label_kr: "I understand that all investments carry risk and I may lose money", required: true },
      { value: "past_performance", label: "I understand that past performance does not guarantee future results", label_kr: "I understand that past performance does not guarantee future results", required: true },
      { value: "ai_advisory", label: "I understand that PivoxQuant provides AI-generated analysis, not licensed financial advice", label_kr: "I understand that PivoxQuant provides AI-generated analysis, not licensed financial advice", required: true },
    ],
  },
];

/** Questions 0-18 are the wizard screens; question 19 (legal) is the final step. */
export const WIZARD_QUESTIONS = ONBOARDING_QUESTIONS.slice(0, 19);
export const LEGAL_QUESTION = ONBOARDING_QUESTIONS[19];

// ── Category metadata ────────────────────────────────────────────────────────

export const CATEGORIES: Record<string, { label: string; icon: string; color: string }> = {
  A: { label: "Investment Identity", icon: "user", color: "#8b5cf6" },
  B: { label: "Strategy Preferences", icon: "settings", color: "#3b82f6" },
  C: { label: "Risk Psychology", icon: "brain", color: "#ec4899" },
  D: { label: "Return Expectations", icon: "trending-up", color: "#f59e0b" },
  E: { label: "Market Knowledge", icon: "book-open", color: "#10b981" },
  F: { label: "Legal & Compliance", icon: "shield", color: "#64748b" },
};

// ── Investor Types ───────────────────────────────────────────────────────────

export const INVESTOR_TYPES: Record<string, InvestorType> = {
  passive_index_hugger: {
    label: "Passive Index Hugger",
    label_kr: "Passive Index Hugger",
    description: "Prefers broad market exposure with minimal active management. Seeks market-matching returns with the lowest possible effort and fees.",
    description_kr: "Prefers broad market exposure with minimal active management.",
    trading_style: "buy_and_hold",
    typical_holding: "years",
  },
  steady_accumulator: {
    label: "Steady Accumulator",
    label_kr: "Steady Accumulator",
    description: "Systematic investor who dollar-cost-averages into quality stocks. Prioritizes consistency over home runs.",
    description_kr: "Systematic investor who dollar-cost-averages into quality stocks.",
    trading_style: "position",
    typical_holding: "months",
  },
  value_hunter: {
    label: "Value Hunter",
    label_kr: "Value Hunter",
    description: "Seeks undervalued stocks with strong fundamentals. Willing to hold through temporary drawdowns if the thesis holds.",
    description_kr: "Seeks undervalued stocks with strong fundamentals.",
    trading_style: "position",
    typical_holding: "months",
  },
  risk_managed_growth: {
    label: "Risk-Managed Growth",
    label_kr: "Risk-Managed Growth",
    description: "Wants above-market returns but with strict downside protection. Uses stop-losses and position sizing rigorously.",
    description_kr: "Wants above-market returns with strict downside protection.",
    trading_style: "swing",
    typical_holding: "weeks",
  },
  swing_trader: {
    label: "Swing Trader",
    label_kr: "Swing Trader",
    description: "Trades multi-day to multi-week moves. Uses technical setups and momentum signals to time entries and exits.",
    description_kr: "Trades multi-day to multi-week moves using technical setups.",
    trading_style: "swing",
    typical_holding: "weeks",
  },
  momentum_rider: {
    label: "Momentum Rider",
    label_kr: "Momentum Rider",
    description: "Chases strong price trends and rides winners. Comfortable with high turnover and concentrated bets on trending stocks.",
    description_kr: "Chases strong price trends and rides winners.",
    trading_style: "swing",
    typical_holding: "days",
  },
  macro_rotator: {
    label: "Macro Rotator",
    label_kr: "Macro Rotator",
    description: "Rotates sectors and asset classes based on macro trends. Thinks in terms of economic cycles, interest rates, and global flows.",
    description_kr: "Rotates sectors and asset classes based on macro trends.",
    trading_style: "position",
    typical_holding: "months",
  },
  aggressive_scalper: {
    label: "Aggressive Scalper",
    label_kr: "Aggressive Scalper",
    description: "High-frequency, short-holding-period trader. Targets small profits many times per day with tight risk controls.",
    description_kr: "High-frequency trader targeting small profits with tight risk controls.",
    trading_style: "scalp",
    typical_holding: "intraday",
  },
};

// ── Profile highlights per type (shown on result screen) ─────────────────────

export const PROFILE_HIGHLIGHTS: Record<string, { tagline: string; features: string[] }> = {
  passive_index_hugger: {
    tagline: "Low-touch investing. Maximum simplicity.",
    features: [
      "Index-tracking model activated",
      "Monthly portfolio rebalance",
      "10% max drawdown target",
    ],
  },
  steady_accumulator: {
    tagline: "Consistent, disciplined wealth building.",
    features: [
      "DCA + value models activated",
      "Bi-weekly rebalance cycle",
      "8% max drawdown target",
    ],
  },
  value_hunter: {
    tagline: "Fundamental-driven, contrarian patience.",
    features: [
      "Fundamental screening models activated",
      "Deep value + mean reversion analysis",
      "12% max drawdown target",
    ],
  },
  risk_managed_growth: {
    tagline: "Growth with guardrails. Every position has a plan.",
    features: [
      "3 quant models activated for you",
      "Strict stop-loss enforcement",
      "8% max drawdown target",
    ],
  },
  swing_trader: {
    tagline: "Ride the waves. Technical precision meets patience.",
    features: [
      "4 quant models activated for you",
      "Swing entry/exit signals",
      "7% max drawdown target",
    ],
  },
  momentum_rider: {
    tagline: "You thrive on market trends, riding momentum for weeks.",
    features: [
      "5 quant models activated for you",
      "Trail-only exit strategy (let winners run)",
      "15% max drawdown target",
    ],
  },
  macro_rotator: {
    tagline: "Think globally. Rotate tactically.",
    features: [
      "Regime detection + sector rotation models",
      "Cross-asset momentum analysis",
      "10% max drawdown target",
    ],
  },
  aggressive_scalper: {
    tagline: "Speed is edge. Tight stops, many shots.",
    features: [
      "Intraday momentum + volatility models",
      "Real-time signal streaming",
      "3% max drawdown target",
    ],
  },
};
