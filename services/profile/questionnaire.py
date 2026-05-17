"""
PivoxQuant — Comprehensive Onboarding Questionnaire v2
20 questions across 6 categories for precise quant strategy matching.

Each question maps to specific quant engine parameters.
The scoring algorithm produces one of 8 distinct investor types,
each with its own quant strategy combination.

Categories:
  A. Investment Identity (5 questions)
  B. Strategy Preferences (5 questions)
  C. Risk Psychology (4 questions)
  D. Return Expectations (3 questions)
  E. Market Knowledge (2 questions)
  F. Legal & Compliance (1 compound question)
"""

from typing import Any

# ---------------------------------------------------------------------------
# Questionnaire definition
# ---------------------------------------------------------------------------

QUESTIONNAIRE_V2: list[dict[str, Any]] = [
    # =====================================================================
    # A. INVESTMENT IDENTITY — Who are you?
    # =====================================================================
    {
        "id": "experience_years",
        "category": "A",
        "category_label": "Investment Identity",
        "category_label_kr": "투자 프로필",
        "question": "How many years have you been actively investing?",
        "question_kr": "주식 투자 경력은 몇 년인가요?",
        "type": "single",
        "options": [
            {"value": "none",  "label": "No experience yet",     "label_kr": "아직 없음",   "icon": "seedling"},
            {"value": "lt1",   "label": "Less than 1 year",      "label_kr": "1년 미만",    "icon": "sprout"},
            {"value": "1to3",  "label": "1 - 3 years",           "label_kr": "1~3년",       "icon": "leaf"},
            {"value": "3to5",  "label": "3 - 5 years",           "label_kr": "3~5년",       "icon": "tree"},
            {"value": "5plus", "label": "5+ years",              "label_kr": "5년 이상",    "icon": "mountain"},
        ],
        "maps_to": "experience_level, knowledge_score, ui_complexity",
        "weight": 7,
    },
    {
        "id": "asset_types_traded",
        "category": "A",
        "category_label": "Investment Identity",
        "category_label_kr": "투자 프로필",
        "question": "Which asset types have you traded before? (Select all)",
        "question_kr": "어떤 자산을 거래해 본 적이 있나요? (복수 선택)",
        "type": "multi",
        "options": [
            {"value": "stocks",     "label": "Individual Stocks",  "label_kr": "개별 주식"},
            {"value": "etfs",       "label": "ETFs / Index Funds", "label_kr": "ETF / 인덱스 펀드"},
            {"value": "bonds",      "label": "Bonds / Fixed Income","label_kr": "채권"},
            {"value": "options",    "label": "Options",            "label_kr": "옵션"},
            {"value": "futures",    "label": "Futures",            "label_kr": "선물"},
            {"value": "crypto",     "label": "Cryptocurrency",     "label_kr": "암호화폐"},
            {"value": "forex",      "label": "Forex",              "label_kr": "외환"},
            {"value": "none",       "label": "None of the above",  "label_kr": "해당 없음"},
        ],
        "maps_to": "experience_level, knowledge_score, eligible_strategies",
        "weight": 6,
    },
    {
        "id": "portfolio_size",
        "category": "A",
        "category_label": "Investment Identity",
        "category_label_kr": "투자 프로필",
        "question": "What is the approximate size of your current investment portfolio?",
        "question_kr": "현재 투자 자산 규모는 대략 어느 정도인가요?",
        "type": "single",
        "options": [
            {"value": "lt1k",    "label": "Under $1,000",         "label_kr": "100만원 미만",       "icon": "wallet"},
            {"value": "1k_10k",  "label": "$1,000 - $10,000",     "label_kr": "100만~1,000만원",    "icon": "banknote"},
            {"value": "10k_50k", "label": "$10,000 - $50,000",    "label_kr": "1,000만~5,000만원",  "icon": "piggy-bank"},
            {"value": "50k_200k","label": "$50,000 - $200,000",   "label_kr": "5,000만~2억원",      "icon": "safe"},
            {"value": "200k_plus","label":"$200,000+",             "label_kr": "2억원 이상",         "icon": "building"},
        ],
        "maps_to": "capital_tier, max_positions, position_sizing",
        "weight": 8,
    },
    {
        "id": "monthly_investable",
        "category": "A",
        "category_label": "Investment Identity",
        "category_label_kr": "투자 프로필",
        "question": "How much can you invest additionally each month?",
        "question_kr": "매월 추가로 투자할 수 있는 금액은?",
        "type": "single",
        "options": [
            {"value": "lt100",    "label": "Under $100",           "label_kr": "10만원 미만",       "icon": "coin"},
            {"value": "100_500",  "label": "$100 - $500",          "label_kr": "10만~50만원",       "icon": "coins"},
            {"value": "500_2k",   "label": "$500 - $2,000",        "label_kr": "50만~200만원",      "icon": "wallet"},
            {"value": "2k_5k",    "label": "$2,000 - $5,000",      "label_kr": "200만~500만원",     "icon": "banknote"},
            {"value": "5k_plus",  "label": "$5,000+",              "label_kr": "500만원 이상",      "icon": "trending-up"},
        ],
        "maps_to": "dca_amount, rebalance_frequency, capital_tier",
        "weight": 5,
    },
    {
        "id": "income_stability",
        "category": "A",
        "category_label": "Investment Identity",
        "category_label_kr": "투자 프로필",
        "question": "How stable is your primary income?",
        "question_kr": "주 수입원은 얼마나 안정적인가요?",
        "type": "single",
        "options": [
            {"value": "very_stable","label": "Salaried / government job","label_kr": "정규직 / 공무원",      "icon": "shield"},
            {"value": "stable",     "label": "Stable job, some variable","label_kr": "안정적 (일부 변동)",    "icon": "briefcase"},
            {"value": "variable",   "label": "Freelance / contract",     "label_kr": "프리랜서 / 계약직",    "icon": "laptop"},
            {"value": "volatile",   "label": "Commission / gig-based",   "label_kr": "성과급 / 긱 이코노미", "icon": "zap"},
            {"value": "student",    "label": "Student / not employed",    "label_kr": "학생 / 미취업",       "icon": "book"},
        ],
        "maps_to": "max_drawdown_tolerance, sl_multiplier, emergency_buffer",
        "weight": 7,
    },

    # =====================================================================
    # B. STRATEGY PREFERENCES — How do you want to invest?
    # =====================================================================
    {
        "id": "trading_frequency",
        "category": "B",
        "category_label": "Strategy Preferences",
        "category_label_kr": "전략 선호도",
        "question": "How many trades would you ideally make per month?",
        "question_kr": "한 달에 몇 번 정도 매매하고 싶으세요?",
        "type": "single",
        "options": [
            {"value": "rare",     "label": "0 - 2 (buy and forget)",  "label_kr": "0~2회 (사서 묻어두기)",  "icon": "archive"},
            {"value": "few",      "label": "3 - 5 (occasional)",      "label_kr": "3~5회 (가끔)",           "icon": "clock"},
            {"value": "moderate", "label": "6 - 15 (regular)",        "label_kr": "6~15회 (정기적)",        "icon": "repeat"},
            {"value": "frequent", "label": "16 - 40 (active)",        "label_kr": "16~40회 (활발)",         "icon": "activity"},
            {"value": "daily",    "label": "40+ (daily trader)",      "label_kr": "40회+ (데이 트레이더)", "icon": "zap"},
        ],
        "maps_to": "trading_style, alert_frequency, scan_interval",
        "weight": 9,
    },
    {
        "id": "holding_period",
        "category": "B",
        "category_label": "Strategy Preferences",
        "category_label_kr": "전략 선호도",
        "question": "How long do you typically hold a position?",
        "question_kr": "보통 포지션을 얼마나 오래 보유하나요?",
        "type": "single",
        "options": [
            {"value": "intraday",  "label": "Same day (close by EOD)",     "label_kr": "당일 (장 마감 전 청산)",  "icon": "sun"},
            {"value": "days",      "label": "2 - 5 days",                   "label_kr": "2~5일",                  "icon": "calendar"},
            {"value": "weeks",     "label": "1 - 4 weeks",                  "label_kr": "1~4주",                  "icon": "calendar-range"},
            {"value": "months",    "label": "1 - 6 months",                 "label_kr": "1~6개월",                "icon": "hourglass"},
            {"value": "years",     "label": "6+ months (long-term hold)",   "label_kr": "6개월+ (장기 보유)",     "icon": "infinity"},
        ],
        "maps_to": "trading_style, tp_timeframe, sl_timeframe, rebalance_frequency",
        "weight": 9,
    },
    {
        "id": "rebalance_preference",
        "category": "B",
        "category_label": "Strategy Preferences",
        "category_label_kr": "전략 선호도",
        "question": "How often would you like to review and rebalance your portfolio?",
        "question_kr": "포트폴리오를 얼마나 자주 리밸런싱하고 싶으세요?",
        "type": "single",
        "options": [
            {"value": "auto_daily", "label": "Let AI handle it daily",    "label_kr": "AI가 매일 관리",      "icon": "bot"},
            {"value": "weekly",     "label": "Once a week",               "label_kr": "주 1회",              "icon": "calendar"},
            {"value": "biweekly",   "label": "Every two weeks",           "label_kr": "2주마다",             "icon": "calendar-days"},
            {"value": "monthly",    "label": "Once a month",              "label_kr": "월 1회",              "icon": "calendar-check"},
            {"value": "quarterly",  "label": "Once a quarter",            "label_kr": "분기 1회",            "icon": "calendar-range"},
        ],
        "maps_to": "rebalance_frequency, auto_trade_preference, alert_frequency",
        "weight": 6,
    },
    {
        "id": "concentration_preference",
        "category": "B",
        "category_label": "Strategy Preferences",
        "category_label_kr": "전략 선호도",
        "question": "How many stocks would you prefer to hold at once?",
        "question_kr": "동시에 몇 종목을 보유하고 싶으세요?",
        "type": "single",
        "options": [
            {"value": "ultra_focused","label": "1 - 3 (all-in conviction)","label_kr": "1~3종목 (확신 집중)", "icon": "target"},
            {"value": "focused",      "label": "4 - 8 (focused)",         "label_kr": "4~8종목 (집중)",      "icon": "crosshair"},
            {"value": "moderate",     "label": "9 - 15 (balanced)",       "label_kr": "9~15종목 (균형)",     "icon": "layers"},
            {"value": "diversified",  "label": "16 - 25 (diversified)",   "label_kr": "16~25종목 (분산)",    "icon": "grid"},
            {"value": "broad",        "label": "25+ (very diversified)",   "label_kr": "25종목+ (광범위 분산)","icon": "globe"},
        ],
        "maps_to": "max_positions, concentration, position_sizing, max_alloc_pct",
        "weight": 7,
    },
    {
        "id": "leverage_appetite",
        "category": "B",
        "category_label": "Strategy Preferences",
        "category_label_kr": "전략 선호도",
        "question": "Are you interested in using leverage (margin) or leveraged ETFs?",
        "question_kr": "레버리지(신용거래)나 레버리지 ETF에 관심이 있나요?",
        "type": "single",
        "options": [
            {"value": "never",   "label": "No, cash only",                 "label_kr": "절대 안 함 (현금만)",      "icon": "shield"},
            {"value": "etf_only","label": "Only through leveraged ETFs",    "label_kr": "레버리지 ETF만",          "icon": "bar-chart"},
            {"value": "light",   "label": "Light margin (up to 1.5x)",      "label_kr": "소폭 신용 (1.5배까지)",   "icon": "trending-up"},
            {"value": "moderate","label": "Moderate margin (up to 2x)",      "label_kr": "중간 신용 (2배까지)",    "icon": "rocket"},
            {"value": "full",    "label": "Full margin where allowed",       "label_kr": "가능한 최대 레버리지",   "icon": "flame"},
        ],
        "maps_to": "leverage_enabled, max_leverage_ratio, risk_score",
        "weight": 8,
    },

    # =====================================================================
    # C. RISK PSYCHOLOGY — How do you ACTUALLY handle risk?
    # =====================================================================
    {
        "id": "scenario_portfolio_drop",
        "category": "C",
        "category_label": "Risk Psychology",
        "category_label_kr": "리스크 심리",
        "question": "Your portfolio drops 10% in one week. What do you do?",
        "question_kr": "일주일 만에 포트폴리오가 -10% 하락했습니다. 어떻게 하시겠어요?",
        "type": "single",
        "options": [
            {"value": "sell_all",  "label": "Sell everything immediately",          "label_kr": "즉시 전량 매도",           "score": 1},
            {"value": "sell_half", "label": "Sell about half to reduce exposure",    "label_kr": "절반 정도 매도해서 리스크 줄이기", "score": 3},
            {"value": "hold",      "label": "Hold and wait for recovery",            "label_kr": "보유하고 회복 기다리기",    "score": 6},
            {"value": "buy_some",  "label": "Buy a little more at the dip",          "label_kr": "소폭 추가 매수",           "score": 8},
            {"value": "buy_heavy", "label": "Aggressively buy the dip",              "label_kr": "적극적으로 물타기",         "score": 10},
        ],
        "maps_to": "risk_score, sl_min, sl_max, max_drawdown_tolerance",
        "weight": 10,
    },
    {
        "id": "scenario_single_stock_crash",
        "category": "C",
        "category_label": "Risk Psychology",
        "category_label_kr": "리스크 심리",
        "question": "One stock in your portfolio drops 40%, but the company's fundamentals are unchanged. Your move?",
        "question_kr": "보유 종목 하나가 -40% 급락했지만 회사의 기본 펀더멘탈은 변함없습니다. 어떻게 하시겠어요?",
        "type": "single",
        "options": [
            {"value": "cut_loss",    "label": "Sell it -- I can't tolerate that kind of loss",
             "label_kr": "매도 -- 그 정도 손실은 견딜 수 없음",                "score": 2},
            {"value": "trim",        "label": "Trim position to reduce risk",
             "label_kr": "포지션 줄여서 리스크 축소",                          "score": 4},
            {"value": "hold",        "label": "Hold -- fundamentals matter more than price",
             "label_kr": "보유 -- 가격보다 펀더멘탈이 중요",                   "score": 6},
            {"value": "avg_down",    "label": "Average down -- great company at a discount",
             "label_kr": "물타기 -- 좋은 회사를 할인가에",                     "score": 8},
            {"value": "double_down", "label": "Double the position -- this is a gift",
             "label_kr": "포지션 2배 -- 이건 기회",                            "score": 10},
        ],
        "maps_to": "risk_score, loss_aversion_score, sl_behavior",
        "weight": 9,
    },
    {
        "id": "scenario_market_crash_relative",
        "category": "C",
        "category_label": "Risk Psychology",
        "category_label_kr": "리스크 심리",
        "question": "The market crashes 30%, but your portfolio is only down 10% thanks to diversification. How do you feel?",
        "question_kr": "시장이 -30% 폭락했지만, 분산 투자 덕분에 내 포트폴리오는 -10%만 하락. 어떤 생각이 드나요?",
        "type": "single",
        "options": [
            {"value": "too_much",      "label": "Still too much loss -- I want even less exposure",
             "label_kr": "그래도 손실이 크다 -- 더 보수적으로",                "score": 2},
            {"value": "acceptable",    "label": "Acceptable -- this is what diversification is for",
             "label_kr": "괜찮다 -- 분산 투자의 효과",                        "score": 5},
            {"value": "opportunistic", "label": "Good -- and I'd use the crash to buy more",
             "label_kr": "좋다 -- 폭락을 매수 기회로 활용하겠다",             "score": 8},
            {"value": "regret_upside", "label": "I wish I had more exposure to capture the recovery",
             "label_kr": "반등 수익을 위해 더 공격적이었으면 좋았겠다",        "score": 10},
        ],
        "maps_to": "risk_score, max_drawdown_tolerance, concentration",
        "weight": 8,
    },
    {
        "id": "loss_aversion_coinflip",
        "category": "C",
        "category_label": "Risk Psychology",
        "category_label_kr": "리스크 심리",
        "question": "Would you take this bet? A fair coin flip: heads you win $200, tails you lose $100.",
        "question_kr": "이 내기를 하시겠어요? 동전 던지기: 앞면이면 +$200, 뒷면이면 -$100.",
        "type": "single",
        "options": [
            {"value": "never",        "label": "No -- I hate losing money, even in favorable bets",
             "label_kr": "절대 안 함 -- 유리한 내기라도 돈 잃는 건 싫음",       "score": 1},
            {"value": "maybe_small",  "label": "Maybe once if the amount was smaller",
             "label_kr": "금액이 적으면 한 번은 할 수도",                       "score": 4},
            {"value": "yes_once",     "label": "Yes, I'd take it once",
             "label_kr": "네, 한 번은 하겠어요",                               "score": 7},
            {"value": "yes_repeat",   "label": "Yes, and I'd repeat it many times -- the math is in my favor",
             "label_kr": "네, 여러 번 반복하겠어요 -- 수학적으로 유리하니까",   "score": 10},
        ],
        "maps_to": "loss_aversion_score, risk_score, kelly_fraction_multiplier",
        "weight": 8,
    },

    # =====================================================================
    # D. RETURN EXPECTATIONS — Calibrating reality
    # =====================================================================
    {
        "id": "expected_annual_return",
        "category": "D",
        "category_label": "Return Expectations",
        "category_label_kr": "수익 기대치",
        "question": "What annual return do you realistically expect? (The S&P 500 has averaged about 10% per year historically.)",
        "question_kr": "현실적으로 기대하는 연간 수익률은? (S&P 500 역사적 평균은 약 연 10%입니다.)",
        "type": "single",
        "options": [
            {"value": "lt5",    "label": "Under 5% (capital preservation focus)",
             "label_kr": "5% 미만 (자산 보존 중심)",                            "icon": "shield"},
            {"value": "5to10",  "label": "5% - 10% (match the market)",
             "label_kr": "5~10% (시장 수준)",                                   "icon": "trending-up"},
            {"value": "10to20", "label": "10% - 20% (beat the market)",
             "label_kr": "10~20% (시장 초과 수익)",                             "icon": "rocket"},
            {"value": "20to40", "label": "20% - 40% (high growth, higher risk)",
             "label_kr": "20~40% (고성장, 고위험)",                             "icon": "flame"},
            {"value": "40plus", "label": "40%+ (moonshot territory)",
             "label_kr": "40%+ (하이리스크 하이리턴)",                          "icon": "star"},
        ],
        "maps_to": "expected_return, tp_min, tp_max, strategy_aggressiveness",
        "weight": 7,
    },
    {
        "id": "return_vs_stability",
        "category": "D",
        "category_label": "Return Expectations",
        "category_label_kr": "수익 기대치",
        "question": "Which would you prefer over 5 years?",
        "question_kr": "5년간 어떤 수익 패턴을 선호하시나요?",
        "type": "single",
        "options": [
            {"value": "ultra_steady",  "label": "Steady +6% every year, no drama",
             "label_kr": "매년 안정적 +6%, 변동 없음",                           "score": 1},
            {"value": "mostly_steady", "label": "Average +10%, but some years flat or slightly negative",
             "label_kr": "평균 +10%, 일부 해 보합 또는 소폭 마이너스",           "score": 4},
            {"value": "volatile_mid",  "label": "Average +18%, but one year could be -15%",
             "label_kr": "평균 +18%, 한 해는 -15%까지 가능",                    "score": 7},
            {"value": "volatile_high", "label": "Average +30%, but one year could be -25%",
             "label_kr": "평균 +30%, 한 해는 -25%까지 가능",                    "score": 10},
        ],
        "maps_to": "volatility_tolerance, max_drawdown_tolerance, strategy_aggressiveness",
        "weight": 9,
    },
    {
        "id": "min_acceptable_return",
        "category": "D",
        "category_label": "Return Expectations",
        "category_label_kr": "수익 기대치",
        "question": "What is the minimum annual return that would keep you using PivoxQuant?",
        "question_kr": "PivoxQuant을 계속 사용하기 위한 최소 연간 수익률은?",
        "type": "single",
        "options": [
            {"value": "positive",  "label": "Just don't lose money",
             "label_kr": "손실만 안 나면 됨",                                    "icon": "shield"},
            {"value": "beat_bank", "label": "Beat savings account rates (~4%)",
             "label_kr": "예금 금리 이상 (~4%)",                                 "icon": "landmark"},
            {"value": "beat_spy",  "label": "Beat the S&P 500 (~10%)",
             "label_kr": "S&P 500 이상 (~10%)",                                  "icon": "trending-up"},
            {"value": "beat_20",   "label": "Need at least 20%+",
             "label_kr": "최소 20% 이상 필요",                                   "icon": "rocket"},
        ],
        "maps_to": "expected_return, churn_risk_flag, coaching_intensity",
        "weight": 5,
    },

    # =====================================================================
    # E. MARKET KNOWLEDGE — Skill-based feature routing
    # =====================================================================
    {
        "id": "knowledge_concepts",
        "category": "E",
        "category_label": "Market Knowledge",
        "category_label_kr": "시장 지식",
        "question": "Which of these concepts do you understand well? (Select all that apply)",
        "question_kr": "다음 중 잘 이해하고 있는 개념을 모두 선택하세요.",
        "type": "multi",
        "options": [
            {"value": "pe_ratio",       "label": "P/E ratio",             "label_kr": "PER (주가수익비율)",      "score": 1},
            {"value": "market_cap",     "label": "Market capitalization",  "label_kr": "시가총액",              "score": 1},
            {"value": "short_selling",  "label": "Short selling",          "label_kr": "공매도",                "score": 2},
            {"value": "candlestick",    "label": "Candlestick charts",     "label_kr": "캔들스틱 차트",         "score": 2},
            {"value": "rsi_macd",       "label": "RSI / MACD indicators",  "label_kr": "RSI / MACD 보조지표",  "score": 2},
            {"value": "options_greeks", "label": "Options greeks",         "label_kr": "옵션 그릭스",           "score": 3},
            {"value": "beta_alpha",     "label": "Beta / Alpha",           "label_kr": "베타 / 알파",           "score": 2},
            {"value": "kelly_criterion","label": "Kelly criterion",        "label_kr": "켈리 기준법",           "score": 3},
        ],
        "maps_to": "knowledge_score, ui_complexity, feature_visibility",
        "weight": 6,
    },
    {
        "id": "knowledge_self_rating",
        "category": "E",
        "category_label": "Market Knowledge",
        "category_label_kr": "시장 지식",
        "question": "How confident are you reading a stock analysis report?",
        "question_kr": "주식 분석 리포트를 읽을 때 얼마나 자신 있나요?",
        "type": "slider",
        "min": 1,
        "max": 5,
        "min_label": "I need everything explained",
        "max_label": "I can read a 10-K filing",
        "min_label_kr": "모든 것을 설명해 줘야 함",
        "max_label_kr": "사업보고서를 직접 읽을 수 있음",
        "options": [
            {"value": 1, "label": "Need full guidance",  "label_kr": "완전 가이드 필요"},
            {"value": 2, "label": "Basic understanding",  "label_kr": "기초 이해"},
            {"value": 3, "label": "Comfortable",           "label_kr": "자신 있음"},
            {"value": 4, "label": "Advanced",              "label_kr": "고급"},
            {"value": 5, "label": "Expert",                "label_kr": "전문가"},
        ],
        "maps_to": "knowledge_score, ui_complexity, ai_coaching_style",
        "weight": 5,
    },

    # =====================================================================
    # F. LEGAL & COMPLIANCE
    # =====================================================================
    {
        "id": "legal_confirmations",
        "category": "F",
        "category_label": "Legal & Compliance",
        "category_label_kr": "법적 확인",
        "question": "Please confirm the following to proceed:",
        "question_kr": "계속하려면 다음을 확인해 주세요:",
        "type": "multi_required",
        "options": [
            {"value": "age_18",
             "label": "I am 18 years or older",
             "label_kr": "만 18세 이상입니다",
             "required": True},
            {"value": "experience_acknowledged",
             "label": "I have confirmed my investment experience level accurately",
             "label_kr": "투자 경험 수준을 정확하게 확인했습니다",
             "required": True},
            {"value": "risk_acknowledged",
             "label": "I understand that all investments carry risk and I may lose money",
             "label_kr": "모든 투자에는 위험이 있으며 손실이 발생할 수 있음을 이해합니다",
             "required": True},
            {"value": "past_performance",
             "label": "I understand that past performance does not guarantee future results",
             "label_kr": "과거 수익률이 미래 수익을 보장하지 않음을 이해합니다",
             "required": True},
            {"value": "ai_advisory",
             "label": "I understand that PivoxQuant provides AI-generated analysis, not licensed financial advice",
             "label_kr": "PivoxQuant은 AI 분석을 제공하며, 공인 투자자문이 아님을 이해합니다",
             "required": True},
        ],
        "maps_to": "legal_confirmed",
        "weight": 10,
    },
]


# ---------------------------------------------------------------------------
# 8 Investor Types
# ---------------------------------------------------------------------------

INVESTOR_TYPES = {
    "passive_index_hugger": {
        "label": "Passive Index Hugger",
        "label_kr": "패시브 인덱스 추종자",
        "description": "Prefers broad market exposure with minimal active management. Seeks market-matching returns with the lowest possible effort and fees.",
        "description_kr": "최소한의 능동적 관리로 시장 전체에 투자. 최소 노력으로 시장 수준 수익을 추구.",
        "trading_style": "buy_and_hold",
        "typical_holding": "years",
    },
    "steady_accumulator": {
        "label": "Steady Accumulator",
        "label_kr": "꾸준한 적립 투자자",
        "description": "Systematic investor who dollar-cost-averages into quality stocks. Prioritizes consistency over home runs.",
        "description_kr": "우량주에 적립식으로 꾸준히 투자. 대박보다 일관성을 중시.",
        "trading_style": "position",
        "typical_holding": "months",
    },
    "value_hunter": {
        "label": "Value Hunter",
        "label_kr": "가치투자 헌터",
        "description": "Seeks undervalued stocks with strong fundamentals. Willing to hold through temporary drawdowns if the thesis holds.",
        "description_kr": "펀더멘탈이 탄탄한 저평가 종목을 찾아 투자. 투자 논리가 유효하면 일시적 하락도 견딤.",
        "trading_style": "position",
        "typical_holding": "months",
    },
    "risk_managed_growth": {
        "label": "Risk-Managed Growth",
        "label_kr": "리스크 관리형 성장투자",
        "description": "Wants above-market returns but with strict downside protection. Uses stop-losses and position sizing rigorously.",
        "description_kr": "시장 초과 수익을 추구하되 엄격한 하방 보호. 손절과 포지션 사이징을 철저히.",
        "trading_style": "swing",
        "typical_holding": "weeks",
    },
    "swing_trader": {
        "label": "Swing Trader",
        "label_kr": "스윙 트레이더",
        "description": "Trades multi-day to multi-week moves. Uses technical setups and momentum signals to time entries and exits.",
        "description_kr": "수일~수주 단위 움직임을 거래. 기술적 셋업과 모멘텀 시그널로 매매 타이밍을 잡음.",
        "trading_style": "swing",
        "typical_holding": "weeks",
    },
    "momentum_rider": {
        "label": "Momentum Rider",
        "label_kr": "모멘텀 라이더",
        "description": "Chases strong price trends and rides winners. Comfortable with high turnover and concentrated bets on trending stocks.",
        "description_kr": "강한 가격 추세를 추종. 높은 회전율과 트렌딩 종목 집중 투자에 편안함.",
        "trading_style": "swing",
        "typical_holding": "days",
    },
    "macro_rotator": {
        "label": "Macro Rotator",
        "label_kr": "매크로 로테이터",
        "description": "Rotates sectors and asset classes based on macro trends. Thinks in terms of economic cycles, interest rates, and global flows.",
        "description_kr": "매크로 트렌드에 따라 섹터와 자산군을 로테이션. 경기 사이클, 금리, 글로벌 자금 흐름 관점으로 투자.",
        "trading_style": "position",
        "typical_holding": "months",
    },
    "aggressive_scalper": {
        "label": "Aggressive Scalper",
        "label_kr": "공격적 스캘퍼",
        "description": "High-frequency, short-holding-period trader. Targets small profits many times per day with tight risk controls.",
        "description_kr": "고빈도 단타 트레이더. 하루에 여러 번 소폭 수익을 목표. 타이트한 리스크 관리.",
        "trading_style": "scalp",
        "typical_holding": "intraday",
    },
}


# ---------------------------------------------------------------------------
# Quant strategy presets per investor type
# ---------------------------------------------------------------------------

PROFILE_PRESETS_V2 = {
    # --- Passive Index Hugger ---
    "passive_index_hugger": {
        "tech_weight": 0.20, "fund_weight": 0.55, "news_weight": 0.25,
        "tp_min": 3.0, "tp_max": 8.0, "sl_min": 5.0, "sl_max": 10.0,
        "max_positions": 10, "buy_threshold": 78.0, "sell_threshold": 18.0,
        "ai_coaching_style": "educational", "alert_frequency": "weekly",
        # Extended params
        "max_alloc_pct": 15,
        "rebalance_interval_days": 90,
        "trailing_stop_pct": 8.0,
        "max_daily_trades": 2,
        "leverage_allowed": False,
        "preferred_models": ["MeanReversion"],
        "scan_interval_sec": 3600,
    },
    # --- Steady Accumulator ---
    "steady_accumulator": {
        "tech_weight": 0.30, "fund_weight": 0.50, "news_weight": 0.20,
        "tp_min": 5.0, "tp_max": 12.0, "sl_min": 4.0, "sl_max": 8.0,
        "max_positions": 12, "buy_threshold": 73.0, "sell_threshold": 22.0,
        "ai_coaching_style": "balanced", "alert_frequency": "daily",
        "max_alloc_pct": 15,
        "rebalance_interval_days": 30,
        "trailing_stop_pct": 6.0,
        "max_daily_trades": 3,
        "leverage_allowed": False,
        "preferred_models": ["MeanReversion", "FiftyTwoWeekHigh"],
        "scan_interval_sec": 1800,
    },
    # --- Value Hunter ---
    "value_hunter": {
        "tech_weight": 0.25, "fund_weight": 0.55, "news_weight": 0.20,
        "tp_min": 8.0, "tp_max": 25.0, "sl_min": 6.0, "sl_max": 12.0,
        "max_positions": 10, "buy_threshold": 72.0, "sell_threshold": 20.0,
        "ai_coaching_style": "analytical", "alert_frequency": "daily",
        "max_alloc_pct": 20,
        "rebalance_interval_days": 30,
        "trailing_stop_pct": 7.0,
        "max_daily_trades": 3,
        "leverage_allowed": False,
        "preferred_models": ["MeanReversion", "VarianceRatioFilter"],
        "scan_interval_sec": 1800,
    },
    # --- Risk-Managed Growth ---
    "risk_managed_growth": {
        "tech_weight": 0.45, "fund_weight": 0.35, "news_weight": 0.20,
        "tp_min": 10.0, "tp_max": 20.0, "sl_min": 5.0, "sl_max": 8.0,
        "max_positions": 15, "buy_threshold": 70.0, "sell_threshold": 28.0,
        "ai_coaching_style": "balanced", "alert_frequency": "daily",
        "max_alloc_pct": 15,
        "rebalance_interval_days": 14,
        "trailing_stop_pct": 5.0,
        "max_daily_trades": 5,
        "leverage_allowed": False,
        "preferred_models": ["MomentumBreakout", "MeanReversion", "TSMOM"],
        "scan_interval_sec": 900,
    },
    # --- Swing Trader ---
    "swing_trader": {
        "tech_weight": 0.55, "fund_weight": 0.25, "news_weight": 0.20,
        "tp_min": 8.0, "tp_max": 18.0, "sl_min": 4.0, "sl_max": 7.0,
        "max_positions": 8, "buy_threshold": 68.0, "sell_threshold": 30.0,
        "ai_coaching_style": "opportunity", "alert_frequency": "realtime",
        "max_alloc_pct": 20,
        "rebalance_interval_days": 7,
        "trailing_stop_pct": 4.0,
        "max_daily_trades": 8,
        "leverage_allowed": True,
        "preferred_models": ["MomentumBreakout", "TSMOM", "VolatilityRegime"],
        "scan_interval_sec": 300,
    },
    # --- Momentum Rider ---
    "momentum_rider": {
        "tech_weight": 0.60, "fund_weight": 0.15, "news_weight": 0.25,
        "tp_min": 12.0, "tp_max": 30.0, "sl_min": 6.0, "sl_max": 10.0,
        "max_positions": 6, "buy_threshold": 65.0, "sell_threshold": 32.0,
        "ai_coaching_style": "aggressive", "alert_frequency": "realtime",
        "max_alloc_pct": 25,
        "rebalance_interval_days": 7,
        "trailing_stop_pct": 5.0,
        "max_daily_trades": 10,
        "leverage_allowed": True,
        "preferred_models": ["MomentumBreakout", "TSMOM", "FiftyTwoWeekHigh"],
        "scan_interval_sec": 300,
    },
    # --- Macro Rotator ---
    "macro_rotator": {
        "tech_weight": 0.35, "fund_weight": 0.35, "news_weight": 0.30,
        "tp_min": 10.0, "tp_max": 25.0, "sl_min": 5.0, "sl_max": 10.0,
        "max_positions": 12, "buy_threshold": 70.0, "sell_threshold": 25.0,
        "ai_coaching_style": "analytical", "alert_frequency": "daily",
        "max_alloc_pct": 18,
        "rebalance_interval_days": 14,
        "trailing_stop_pct": 6.0,
        "max_daily_trades": 5,
        "leverage_allowed": True,
        "preferred_models": ["VolatilityRegime", "RegimeSwitching", "TSMOM"],
        "scan_interval_sec": 900,
    },
    # --- Aggressive Scalper ---
    "aggressive_scalper": {
        "tech_weight": 0.65, "fund_weight": 0.10, "news_weight": 0.25,
        "tp_min": 2.0, "tp_max": 5.0, "sl_min": 1.0, "sl_max": 3.0,
        "max_positions": 5, "buy_threshold": 62.0, "sell_threshold": 35.0,
        "ai_coaching_style": "aggressive", "alert_frequency": "realtime",
        "max_alloc_pct": 30,
        "rebalance_interval_days": 1,
        "trailing_stop_pct": 2.0,
        "max_daily_trades": 20,
        "leverage_allowed": True,
        "preferred_models": ["MomentumBreakout", "VolatilityRegime"],
        "scan_interval_sec": 60,
    },
}


# ---------------------------------------------------------------------------
# Scoring algorithm: answers -> profile
# ---------------------------------------------------------------------------

def calculate_profile_v2(answers: dict) -> dict:
    """
    Process questionnaire answers into a complete investor profile.

    Returns dict:
        investor_type       : str   — one of 8 types
        risk_score          : int   — 0-100
        experience_level    : str   — beginner / intermediate / advanced / expert
        trading_style       : str   — scalp / day / swing / position / buy_and_hold
        time_commitment     : str   — minimal / moderate / active / full_time
        capital_tier        : str   — micro / small / mid / large / whale
        rebalance_frequency : str   — daily / weekly / biweekly / monthly / quarterly
        concentration       : str   — ultra_focused / focused / moderate / diversified / broad
        max_drawdown_tolerance : float  — percentage
        expected_return     : float — percentage
        knowledge_score     : int   — 0-10
        loss_aversion_score : float — 0-10
        legal_confirmed     : bool
        ui_complexity       : str   — simple / standard / advanced / expert
        volatility_tolerance: str   — low / moderate / high / extreme
    """
    # ----- Dimension scores (each 0-10 scale) -----
    risk_raw = 0.0
    experience_raw = 0.0
    activity_raw = 0.0
    knowledge_raw = 0.0
    return_ambition_raw = 0.0
    loss_aversion_raw = 0.0

    # ---- A: Investment Identity ----

    # A1: Experience years
    exp_map = {"none": 0, "lt1": 2, "1to3": 5, "3to5": 7, "5plus": 10}
    experience_raw += exp_map.get(answers.get("experience_years", ""), 3)

    # A2: Asset types traded (more types = more experienced)
    asset_types = answers.get("asset_types_traded", [])
    if isinstance(asset_types, str):
        asset_types = [asset_types]
    asset_score = 0
    advanced_assets = {"options", "futures", "forex"}
    for asset in asset_types:
        if asset == "none":
            asset_score = 0
            break
        elif asset in advanced_assets:
            asset_score += 2.5
        else:
            asset_score += 1.2
    experience_raw += min(asset_score, 10)

    # A3: Portfolio size -> capital tier
    capital_map = {"lt1k": 1, "1k_10k": 3, "10k_50k": 5, "50k_200k": 8, "200k_plus": 10}
    capital_score = capital_map.get(answers.get("portfolio_size", ""), 3)

    # A4: Monthly investable — feeds capital tier (DCA cadence + sustainable
    # add-on flow). Prior to 2026-05-17 wave D-1 this line computed the value
    # and immediately discarded it (no ``+=`` / no assignment), so the
    # ``monthly_investable`` answer had zero effect on the resulting profile.
    monthly_map = {"lt100": 1, "100_500": 3, "500_2k": 5, "2k_5k": 7, "5k_plus": 10}
    monthly_score = monthly_map.get(answers.get("monthly_investable", ""), 3)

    # A5: Income stability -> inverse risk capacity
    stability_map = {"very_stable": 8, "stable": 6, "variable": 4, "volatile": 2, "student": 1}
    income_stability = stability_map.get(answers.get("income_stability", ""), 5)

    # ---- B: Strategy Preferences ----

    # B1: Trading frequency
    freq_map = {"rare": 1, "few": 3, "moderate": 5, "frequent": 8, "daily": 10}
    activity_raw += freq_map.get(answers.get("trading_frequency", ""), 3)

    # B2: Holding period
    hold_map = {"intraday": 10, "days": 8, "weeks": 5, "months": 3, "years": 1}
    activity_raw += hold_map.get(answers.get("holding_period", ""), 3)

    # B3: Rebalance preference
    rebal_map = {"auto_daily": 9, "weekly": 7, "biweekly": 5, "monthly": 3, "quarterly": 1}
    activity_raw += rebal_map.get(answers.get("rebalance_preference", ""), 3)

    # B4: Concentration preference -> risk signal
    conc_map = {"ultra_focused": 10, "focused": 7, "moderate": 5, "diversified": 3, "broad": 1}
    conc_score = conc_map.get(answers.get("concentration_preference", ""), 5)
    risk_raw += conc_score * 0.5  # concentrated = riskier

    # B5: Leverage appetite -> strong risk signal
    lev_map = {"never": 0, "etf_only": 2, "light": 5, "moderate": 8, "full": 10}
    leverage_score = lev_map.get(answers.get("leverage_appetite", ""), 0)
    risk_raw += leverage_score

    # ---- C: Risk Psychology ----

    # C1: Portfolio drop scenario
    drop_option = answers.get("scenario_portfolio_drop", "hold")
    drop_scores = {"sell_all": 1, "sell_half": 3, "hold": 6, "buy_some": 8, "buy_heavy": 10}
    risk_raw += drop_scores.get(drop_option, 5)

    # C2: Single stock crash scenario
    crash_option = answers.get("scenario_single_stock_crash", "hold")
    crash_scores = {"cut_loss": 2, "trim": 4, "hold": 6, "avg_down": 8, "double_down": 10}
    risk_raw += crash_scores.get(crash_option, 5)

    # C3: Market crash relative performance
    relative_option = answers.get("scenario_market_crash_relative", "acceptable")
    relative_scores = {"too_much": 2, "acceptable": 5, "opportunistic": 8, "regret_upside": 10}
    risk_raw += relative_scores.get(relative_option, 5)

    # C4: Coin flip loss aversion
    coin_option = answers.get("loss_aversion_coinflip", "yes_once")
    coin_scores = {"never": 1, "maybe_small": 4, "yes_once": 7, "yes_repeat": 10}
    la_score = coin_scores.get(coin_option, 5)
    loss_aversion_raw = 10 - la_score  # invert: higher = more loss averse
    risk_raw += la_score

    # ---- D: Return Expectations ----

    # D1: Expected annual return
    ret_map = {"lt5": 1, "5to10": 3, "10to20": 6, "20to40": 8, "40plus": 10}
    return_ambition_raw += ret_map.get(answers.get("expected_annual_return", ""), 5)

    # D2: Return vs stability preference
    rvs_option = answers.get("return_vs_stability", "mostly_steady")
    rvs_scores = {"ultra_steady": 1, "mostly_steady": 4, "volatile_mid": 7, "volatile_high": 10}
    return_ambition_raw += rvs_scores.get(rvs_option, 4)

    # D3: Minimum acceptable return
    min_ret_map = {"positive": 1, "beat_bank": 3, "beat_spy": 6, "beat_20": 9}
    return_ambition_raw += min_ret_map.get(answers.get("min_acceptable_return", ""), 4)

    # ---- E: Market Knowledge ----

    # E1: Concepts known
    concepts = answers.get("knowledge_concepts", [])
    if isinstance(concepts, str):
        concepts = [concepts]
    concept_scores = {
        "pe_ratio": 1, "market_cap": 1, "short_selling": 2, "candlestick": 2,
        "rsi_macd": 2, "options_greeks": 3, "beta_alpha": 2, "kelly_criterion": 3,
    }
    knowledge_raw = sum(concept_scores.get(c, 0) for c in concepts)
    knowledge_raw = min(knowledge_raw, 10)  # cap at 10

    # E2: Self-rating — accept int / float / numeric string. Pre-2026-05-17
    # a ``None`` value (slider skipped on mobile) or a non-numeric list/dict
    # (corrupt client payload) raised TypeError, which the bare ``except
    # Exception`` in routes/profile.py swallowed silently and fell back to
    # the legacy V1 4-tier classifier — masking the bug and downgrading the
    # user's profile. Clamp to 1..5 (slider range) and default to 3 on bad
    # input so every code path stays inside the documented range.
    raw_self_rating = answers.get("knowledge_self_rating", 3)
    try:
        self_rating = float(raw_self_rating) if raw_self_rating is not None else 3.0
    except (ValueError, TypeError):
        self_rating = 3.0
    self_rating = max(1.0, min(5.0, self_rating))
    knowledge_raw = (knowledge_raw + (self_rating * 2)) / 2  # blend
    knowledge_raw = min(knowledge_raw, 10)

    # ---- F: Legal ----
    legal_items = answers.get("legal_confirmations", [])
    if isinstance(legal_items, str):
        legal_items = [legal_items]
    required_legal = {"age_18", "experience_acknowledged", "risk_acknowledged",
                      "past_performance", "ai_advisory"}
    legal_confirmed = required_legal.issubset(set(legal_items))

    # -----------------------------------------------------------------
    # Normalize dimension scores
    # -----------------------------------------------------------------
    # risk_raw has up to 6 contributions: conc*0.5(max5) + lev(10) + drop(10) + crash(10) + relative(10) + coin(10) = max ~55
    risk_normalized = min(risk_raw / 5.5, 10)
    # activity_raw: 3 questions max 10 each = 30
    activity_normalized = min(activity_raw / 3.0, 10)
    # experience_raw: 2 questions max 10 each = 20
    experience_normalized = min(experience_raw / 2.0, 10)
    # return_ambition_raw: 3 questions = max 30
    return_normalized = min(return_ambition_raw / 3.0, 10)

    # -----------------------------------------------------------------
    # Composite risk score (0-100)
    # -----------------------------------------------------------------
    risk_score = round(
        risk_normalized * 40 +        # 40% weight on risk psychology
        activity_normalized * 20 +     # 20% on trading activity level
        return_normalized * 20 +       # 20% on return ambition
        leverage_score * 10 +          # 10% leverage
        conc_score * 10                # 10% concentration
    ) / 10

    risk_score = max(0, min(100, round(risk_score)))

    # -----------------------------------------------------------------
    # Derive categorical fields
    # -----------------------------------------------------------------

    # Experience level
    if experience_normalized <= 2:
        experience_level = "beginner"
    elif experience_normalized <= 5:
        experience_level = "intermediate"
    elif experience_normalized <= 8:
        experience_level = "advanced"
    else:
        experience_level = "expert"

    # Trading style (from holding period + frequency)
    hold_val = answers.get("holding_period", "weeks")
    freq_val = answers.get("trading_frequency", "moderate")
    if hold_val == "intraday" or freq_val == "daily":
        if activity_normalized >= 8:
            trading_style = "scalp"
        else:
            trading_style = "day"
    elif hold_val in ("days", "weeks") or freq_val in ("moderate", "frequent"):
        trading_style = "swing"
    elif hold_val == "months":
        trading_style = "position"
    else:
        trading_style = "buy_and_hold"

    # Time commitment
    if activity_normalized <= 2:
        time_commitment = "minimal"
    elif activity_normalized <= 5:
        time_commitment = "moderate"
    elif activity_normalized <= 8:
        time_commitment = "active"
    else:
        time_commitment = "full_time"

    # Capital tier — blend lump-sum (portfolio_size) with monthly recurring
    # capacity so e.g. a student with $500 saved but $2k/month going in
    # doesn't get pinned to "micro" forever. Weight portfolio_size 70 / 30
    # — current AUM still dominates classification.
    combined_capital = capital_score * 0.7 + monthly_score * 0.3
    if combined_capital <= 2:
        capital_tier = "micro"
    elif combined_capital <= 4:
        capital_tier = "small"
    elif combined_capital <= 6:
        capital_tier = "mid"
    elif combined_capital <= 8:
        capital_tier = "large"
    else:
        capital_tier = "whale"

    # Rebalance frequency
    rebal_val = answers.get("rebalance_preference", "monthly")
    rebalance_map = {
        "auto_daily": "daily", "weekly": "weekly", "biweekly": "biweekly",
        "monthly": "monthly", "quarterly": "quarterly",
    }
    rebalance_frequency = rebalance_map.get(rebal_val, "monthly")

    # Concentration
    conc_val = answers.get("concentration_preference", "moderate")
    concentration = conc_val  # already matches output schema

    # Max drawdown tolerance (derived from risk score + income stability)
    # Higher risk score = higher tolerance, unstable income = lower tolerance
    base_dd = risk_score * 0.35  # 0-35% base from risk score
    stability_modifier = income_stability / 10  # 0.1 - 0.8
    max_drawdown_tolerance = round(base_dd * stability_modifier + 3, 1)  # minimum 3%
    max_drawdown_tolerance = max(3.0, min(40.0, max_drawdown_tolerance))

    # Expected return
    ret_val = answers.get("expected_annual_return", "10to20")
    ret_pct_map = {"lt5": 4, "5to10": 8, "10to20": 15, "20to40": 30, "40plus": 50}
    expected_return = ret_pct_map.get(ret_val, 12)

    # Knowledge score (0-10)
    knowledge_score = max(0, min(10, round(knowledge_raw)))

    # UI complexity
    if knowledge_score <= 2:
        ui_complexity = "simple"
    elif knowledge_score <= 5:
        ui_complexity = "standard"
    elif knowledge_score <= 8:
        ui_complexity = "advanced"
    else:
        ui_complexity = "expert"

    # Volatility tolerance
    rvs_vol_map = {"ultra_steady": "low", "mostly_steady": "moderate",
                   "volatile_mid": "high", "volatile_high": "extreme"}
    volatility_tolerance = rvs_vol_map.get(
        answers.get("return_vs_stability", "mostly_steady"), "moderate"
    )

    # -----------------------------------------------------------------
    # Investor type classification
    # -----------------------------------------------------------------
    investor_type = _classify_investor_type(
        risk_score=risk_score,
        activity_normalized=activity_normalized,
        return_normalized=return_normalized,
        experience_normalized=experience_normalized,
        knowledge_score=knowledge_score,
        trading_style=trading_style,
        leverage_score=leverage_score,
        fund_weight_bias=conc_score,  # proxy for fundamental orientation
        income_stability=income_stability,
    )

    return {
        "investor_type": investor_type,
        "risk_score": risk_score,
        "experience_level": experience_level,
        "trading_style": trading_style,
        "time_commitment": time_commitment,
        "capital_tier": capital_tier,
        "rebalance_frequency": rebalance_frequency,
        "concentration": concentration,
        "max_drawdown_tolerance": max_drawdown_tolerance,
        "expected_return": expected_return,
        "knowledge_score": knowledge_score,
        "loss_aversion_score": round(loss_aversion_raw, 1),
        "legal_confirmed": legal_confirmed,
        "ui_complexity": ui_complexity,
        "volatility_tolerance": volatility_tolerance,
    }


def _classify_investor_type(
    risk_score: float,
    activity_normalized: float,
    return_normalized: float,
    experience_normalized: float,
    knowledge_score: int,
    trading_style: str,
    leverage_score: float,
    fund_weight_bias: float,
    income_stability: float,
) -> str:
    """
    Multi-axis classification into one of 8 investor types.

    Uses a weighted distance approach: compute affinity scores for each type
    and pick the best match.
    """
    # Each type is defined by ideal dimension values (0-10 scale).
    # Format: (risk, activity, return_ambition, experience, knowledge, leverage)
    type_centroids = {
        "passive_index_hugger":   (2.0, 1.0, 2.0, 2.0, 2.0, 0.0),
        "steady_accumulator":     (3.5, 2.5, 4.0, 3.0, 3.5, 0.0),
        "value_hunter":           (4.5, 3.0, 5.5, 6.0, 6.0, 1.0),
        "risk_managed_growth":    (5.0, 5.0, 6.0, 4.5, 5.0, 1.5),
        "swing_trader":           (6.0, 6.5, 6.5, 5.0, 6.0, 3.0),
        "momentum_rider":         (7.5, 7.5, 8.0, 5.5, 5.5, 6.0),
        "macro_rotator":          (5.0, 5.0, 6.0, 7.5, 8.0, 3.0),
        "aggressive_scalper":     (9.5, 9.5, 9.5, 7.0, 7.0, 8.0),
    }

    # Dimension weights (some dimensions matter more for classification)
    dim_weights = (2.5, 2.0, 1.5, 1.0, 1.0, 1.5)

    user_vector = (
        risk_score / 10.0,       # normalize to 0-10
        activity_normalized,
        return_normalized,
        experience_normalized,
        knowledge_score,
        leverage_score,
    )

    best_type = "steady_accumulator"
    best_distance = float("inf")

    for type_name, centroid in type_centroids.items():
        distance = sum(
            w * (u - c) ** 2
            for w, u, c in zip(dim_weights, user_vector, centroid)
        )
        if distance < best_distance:
            best_distance = distance
            best_type = type_name

    # Override rules: certain answer combinations force a type regardless of distance

    # If trading style is scalp and activity is very high, force aggressive_scalper
    if trading_style == "scalp" and activity_normalized >= 8.5:
        best_type = "aggressive_scalper"

    # If risk is very low and activity is very low, force passive
    if risk_score <= 20 and activity_normalized <= 2:
        best_type = "passive_index_hugger"

    # If knowledge is very high, experience high, and activity moderate -> macro rotator affinity
    if knowledge_score >= 8 and experience_normalized >= 7 and 4 <= activity_normalized <= 6:
        best_type = "macro_rotator"

    # High activity + high risk but NOT intraday -> momentum, not scalper
    # Scalper requires the scalp trading_style (intraday + daily frequency)
    if best_type == "aggressive_scalper" and trading_style != "scalp":
        if activity_normalized >= 6 and risk_score / 10.0 >= 6:
            best_type = "momentum_rider"

    return best_type


# ---------------------------------------------------------------------------
# Backward compatibility: map new types to legacy 4-type system
# ---------------------------------------------------------------------------

LEGACY_TYPE_MAP = {
    "passive_index_hugger": "conservative",
    "steady_accumulator":   "balanced",
    "value_hunter":         "balanced",
    "risk_managed_growth":  "growth",
    "swing_trader":         "growth",
    "momentum_rider":       "aggressive",
    "macro_rotator":        "growth",
    "aggressive_scalper":   "aggressive",
}


def get_legacy_type(investor_type: str) -> str:
    """Map new 8-type system to old 4-type for backward compatibility with engine.py."""
    return LEGACY_TYPE_MAP.get(investor_type, "balanced")


def get_preset(investor_type: str) -> dict:
    """Get quant parameter preset for an investor type. Falls back to steady_accumulator."""
    return PROFILE_PRESETS_V2.get(investor_type, PROFILE_PRESETS_V2["steady_accumulator"])
