"""
PivoxQuant — Onboarding Questionnaire V3 (2026-09-06)

Five declarations + one legal block. Each declaration maps 1:1 onto an axis
the product already observes from trade history, so ``/mirror`` can compare
"what you said" with "what you did" on the same scale. Nothing here produces
a score or a grade.

History: V1 (8 questions, 4-tier) and V2 (19 questions, 8 investor types with
quant-engine presets) were removed on 2026-09-06 together with this rewrite —
the quant engine they parameterised was deleted 2026-08-31 and the product
consumed two of V2's fifteen outputs. See
docs/strategy/onboarding-questionnaire-v3_2026-09-06.md and
docs/strategy/onboarding-competitor-research_2026-09-06.md.
"""

from typing import Any

# ---------------------------------------------------------------------------
# Legal block — the disclaimer wall. Ids/values are load-bearing: the routes'
# legal gate requires ``legal_confirmations`` to contain all five values.
# ---------------------------------------------------------------------------

LEGAL_BLOCK: dict[str, Any] = {
    "id": "legal_confirmations",
    "category": "F",
    "category_label": "Legal & Compliance",
    "category_label_kr": "법적 확인",
    "question": "Please confirm the following to proceed:",
    "question_kr": "계속하려면 다음을 확인해 주세요:",
    "type": "multi_required",
    "options": [
        {"value": "age_18",
         "label": "I am 14 years or older",
         "label_kr": "만 14세 이상입니다",
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
        # 2026-09-06 — text aligned with the frontend (ba6dfe48). The AI
        # pipeline was deleted 2026-09-01; this block must not describe
        # processing that no longer happens (SHIP_BLOCKERS R0). The option
        # ``value`` is kept so stored answers / the legal gate stay valid.
        {"value": "ai_advisory",
         "label": "I understand that PivoxQuant reflects back the record I enter myself, and is not licensed financial advice",  # // legal-ok — disclaimer states it is NOT advice
         "label_kr": "PivoxQuant은 제가 직접 입력한 기록을 되비추어 보여줄 뿐이며, 정식 투자 자문이 아님을 이해합니다",
         "required": True},
    ],
    "maps_to": "legal_confirmed",
    "weight": 10,
}


# ═══════════════════════════════════════════════════════════════════════════
# Questionnaire V3 — "declare only what the mirror can reflect back"
# (2026-09-06, docs/strategy/onboarding-questionnaire-v3_2026-09-06.md)
# ═══════════════════════════════════════════════════════════════════════════
#
# Why a V3
# --------
# V2 asked 19 questions to derive 15 fields, of which the product consumed
# two (``profile_type`` and ``risk_tolerance``). Portfolio size, monthly
# investable, income stability, expected return, knowledge score, UI
# complexity, leverage — all computed, none read (0 consumers measured
# 2026-09-06). Worse, ``/mirror`` compared the observed 9-dim behaviour
# vector against the *centroid of the persona label*, never against what
# the user actually said — the answers were discarded after classification.
#
# V3 asks five things, each of which maps 1:1 onto an axis the product
# already observes from trade history (``persona_classifier_v2.FEATURE_KEYS``)
# or onto the one research question the free beta exists to answer
# ("do Korean retail investors record at all"). The answers are persisted
# verbatim (``InvestmentProfile.onboarding_answers_json``) and projected onto
# the observed feature scale (``declared_vector_json``) so the mirror can put
# "what you said" next to "what you did" on the same ruler.
#
# What V3 deliberately is NOT
# ---------------------------
# * Not a risk-grade generator. No 0-100 score, no 5-tier label surfaces.
#   (DECISIONS: AI 점수화 폐기; the competitor research found self-report
#   risk questionnaires explain ≤ R²≈0.28 of behaviour and regulators found
#   9/11 profiling tools defective — a grade would be theatre.)
# * Not predictive. The −10% scenario answer is kept as the user's own
#   sentence to be shown back after a real drawdown, not as a forecast.
# * Not a replacement for the observed classifier. ``investor_type`` is still
#   an 8-code persona so group benchmarks and drift keep working; the code
#   is derived by a readable rule table (§ below) rather than centroid
#   distance, so "why this bucket" can be explained in one line.

QUESTIONNAIRE_V3: list[dict[str, Any]] = [
    {
        "id": "declared_holding",
        "category": "A",
        "category_label": "Holding habits",
        "category_label_kr": "보유 습관",
        "question": "When you buy a stock, how long do you usually hold it?",
        "question_kr": "한 종목을 사면 보통 얼마나 들고 있나요?",
        "type": "single",
        "options": [
            {"value": "intraday", "label": "Within the day",     "label_kr": "하루 안에 정리해요"},
            {"value": "days",     "label": "A few days",         "label_kr": "며칠"},
            {"value": "weeks",    "label": "A few weeks",        "label_kr": "몇 주"},
            {"value": "months",   "label": "A few months",       "label_kr": "몇 달"},
            {"value": "years",    "label": "A year or longer",   "label_kr": "1년 이상"},
        ],
        "mirror_axis": "holding_period",
    },
    {
        "id": "declared_frequency",
        "category": "A",
        "category_label": "Holding habits",
        "category_label_kr": "보유 습관",
        "question": "Roughly how many buys and sells do you make in a month?",
        "question_kr": "한 달에 매수·매도를 대략 몇 번 하나요?",
        "type": "single",
        "options": [
            {"value": "rare",     "label": "0 – 2",   "label_kr": "0~2번"},
            {"value": "few",      "label": "3 – 5",   "label_kr": "3~5번"},
            {"value": "moderate", "label": "6 – 15",  "label_kr": "6~15번"},
            {"value": "frequent", "label": "16 – 40", "label_kr": "16~40번"},
            {"value": "daily",    "label": "40+",     "label_kr": "40번 이상"},
        ],
        "mirror_axis": "turnover",
    },
    {
        "id": "declared_positions",
        "category": "A",
        "category_label": "Holding habits",
        "category_label_kr": "보유 습관",
        "question": "How many stocks do you usually hold at the same time?",
        "question_kr": "보통 몇 종목을 동시에 들고 있나요?",
        "type": "single",
        "options": [
            {"value": "ultra_focused", "label": "1 – 3",   "label_kr": "1~3종목"},
            {"value": "focused",       "label": "4 – 8",   "label_kr": "4~8종목"},
            {"value": "moderate",      "label": "9 – 15",  "label_kr": "9~15종목"},
            {"value": "diversified",   "label": "16 – 25", "label_kr": "16~25종목"},
            {"value": "broad",         "label": "25+",     "label_kr": "25종목 이상"},
        ],
        "mirror_axis": "ticker_diversity",
    },
    {
        "id": "declared_drawdown_response",
        "category": "B",
        "category_label": "When it drops",
        "category_label_kr": "하락 대응",
        "question": "Imagine your portfolio falls 10% in one week. What do you actually do?",
        "question_kr": "포트폴리오가 한 주에 10% 빠졌다고 상상해 보세요. 실제로 무엇을 하나요?",
        "type": "single",
        "options": [
            {"value": "sell_all",  "label": "Sell everything",       "label_kr": "다 팔아요"},
            {"value": "sell_half", "label": "Sell some",             "label_kr": "일부 팔아요"},
            {"value": "hold",      "label": "Leave it",              "label_kr": "그냥 둬요"},
            {"value": "buy_some",  "label": "Buy a little more",     "label_kr": "조금 더 사요"},
            {"value": "buy_heavy", "label": "Buy a lot more",        "label_kr": "크게 더 사요"},
        ],
        "mirror_axis": "declared_risk",
    },
    {
        "id": "record_habit",
        "category": "C",
        "category_label": "Recording",
        "category_label_kr": "기록",
        "question": "Have you ever written down why you made a trade?",
        "question_kr": "지금까지 매매 이유를 어딘가에 적어 본 적 있나요?",
        "type": "single",
        "options": [
            {"value": "never",     "label": "No",                              "label_kr": "없어요"},
            {"value": "sometimes", "label": "Sometimes, a quick note",         "label_kr": "가끔 메모해요"},
            {"value": "regular",   "label": "Regularly, in a notebook or app", "label_kr": "노트나 앱에 꾸준히 적어요"},
            {"value": "used_to",   "label": "I used to, but stopped",          "label_kr": "예전엔 했는데 지금은 안 해요"},
        ],
        # No mirror axis on purpose — this is the beta's research question
        # (CLAUDE.md §제품 전제). Crossed later with pre-trade record rate.
        "mirror_axis": None,
    },
    LEGAL_BLOCK,
]

V3_QUESTION_IDS: frozenset[str] = frozenset(
    q["id"] for q in QUESTIONNAIRE_V3 if q["id"] != "legal_confirmations"
)

# Declared value on the observed feature scale ([0, 1], same normalisation
# as ``persona_classifier_v2._extract_features``). Measured 2026-09-06 by
# calling ``persona_analytics._norm_log`` directly:
#   holding  _norm_log(days, 1, 180):     3d 0.21 · 21d 0.59 · 90d 0.87 · 365d 1.0
#   turnover _norm_log(per_day, .02, 1):  1/mo 0.13 · 3/mo 0.41 · 15/mo 0.82 · 40/mo 1.0
#   tickers  _norm_log(n, 1, 25):         2 → 0.22 · 6 → 0.56 · 12 → 0.77 · 20 → 0.93
# Values below sit at the bucket midpoints of those curves.
DECLARED_VECTOR_MAP: dict[str, dict[str, float]] = {
    "declared_holding": {
        "intraday": 0.0, "days": 0.25, "weeks": 0.60, "months": 0.85, "years": 1.0,
    },
    "declared_frequency": {
        "rare": 0.05, "few": 0.45, "moderate": 0.70, "frequent": 0.92, "daily": 1.0,
    },
    "declared_positions": {
        "ultra_focused": 0.20, "focused": 0.55, "moderate": 0.75, "diversified": 0.90, "broad": 1.0,
    },
    # declared_risk is stored as risk_tolerance 1..10 and projected with the
    # classifier's own formula ``(rt - 1) / 9`` — see calculate_profile_v3.
}

# Q4 answer → risk_tolerance (1..10). Same scale V2's C1 used, so
# ``persona_classifier_v2`` D7 and ``persona_analytics._declared_score``
# keep reading the column unchanged.
V3_DRAWDOWN_TO_RISK: dict[str, int] = {
    "sell_all": 1, "sell_half": 3, "hold": 6, "buy_some": 8, "buy_heavy": 10,
}

V3_HOLDING_TO_HORIZON: dict[str, str] = {
    "intraday": "short", "days": "short", "weeks": "short",
    "months": "medium", "years": "long",
}


def is_v3_answers(answers: dict | None) -> bool:
    """True when the payload carries any V3 question id."""
    if not isinstance(answers, dict) or not answers:
        return False
    return any(k in V3_QUESTION_IDS for k in answers)


def _v3_option_label(question_id: str, value: Any) -> tuple[str, str]:
    for q in QUESTIONNAIRE_V3:
        if q["id"] != question_id:
            continue
        for opt in q["options"]:
            if str(opt["value"]) == str(value):
                return opt["label"], opt["label_kr"]
    return "", ""


def _classify_declared_persona_v3(holding: str | None, frequency: str | None,
                                  risk_tolerance: int | None,
                                  record_habit: str | None) -> str:
    """Readable rule table → one of the 8 canonical persona codes.

    Order matters: the first matching row wins. Every row is a sentence a
    user could be shown ("몇 달 들고, 빠지면 판다고 하셨으니 수익형") — that is
    the point of replacing centroid distance.

    ``quant`` is intentionally unreachable from a declaration; it can only
    be *observed* (high loss-cut discipline + ticker diversity).
    """
    rt = risk_tolerance if risk_tolerance is not None else 6
    if holding == "intraday":
        return "daytrader"
    if holding == "days" and frequency in ("frequent", "daily"):
        return "speculator"
    if holding in ("days", "weeks"):
        return "growth"
    if holding == "months":
        if record_habit == "never":
            return "beginner"
        return "income" if rt <= 3 else "balanced"
    if holding == "years":
        if record_habit == "never":
            return "beginner"
        return "value" if rt >= 8 else "income"
    # No holding answer (partial payload) — the neutral bucket.
    return "balanced"


def calculate_profile_v3(answers: dict) -> dict:
    """Project V3 answers onto the profile columns + the declared vector.

    Returns
    -------
    dict with keys
        questionnaire_version : 3
        investor_type         : 8-code persona (see rule table)
        risk_tolerance        : int 1..10 (from Q4; 6 = "hold" when unanswered)
        risk_score            : int 0..100 — ``risk_tolerance * 10`` for callers
                                that still read the V2 field name
        time_horizon          : short / medium / long
        record_habit          : raw Q5 value or None
        declared_vector       : {feature_key: float} — ONLY the axes the user
                                declared (never padded with 0.5, so the mirror
                                can tell "not declared" from "declared neutral")
        statements            : [{id, value, label, label_kr}] in question
                                order — the result screen renders these verbatim
        legal_confirmed       : bool
    """
    answers = answers if isinstance(answers, dict) else {}

    holding = answers.get("declared_holding")
    frequency = answers.get("declared_frequency")
    positions = answers.get("declared_positions")
    drawdown = answers.get("declared_drawdown_response")
    record_habit = answers.get("record_habit")

    risk_tolerance = V3_DRAWDOWN_TO_RISK.get(drawdown) if drawdown is not None else None

    declared_vector: dict[str, float] = {}
    if holding in DECLARED_VECTOR_MAP["declared_holding"]:
        declared_vector["holding_period"] = DECLARED_VECTOR_MAP["declared_holding"][holding]
    if frequency in DECLARED_VECTOR_MAP["declared_frequency"]:
        declared_vector["turnover"] = DECLARED_VECTOR_MAP["declared_frequency"][frequency]
    if positions in DECLARED_VECTOR_MAP["declared_positions"]:
        declared_vector["ticker_diversity"] = DECLARED_VECTOR_MAP["declared_positions"][positions]
    if risk_tolerance is not None:
        declared_vector["declared_risk"] = round((risk_tolerance - 1) / 9.0, 4)

    statements: list[dict[str, Any]] = []
    for q in QUESTIONNAIRE_V3:
        qid = q["id"]
        if qid == "legal_confirmations" or qid not in answers:
            continue
        label, label_kr = _v3_option_label(qid, answers[qid])
        if not label:
            continue
        statements.append({
            "id": qid,
            "value": str(answers[qid]),
            "question": q["question"],
            "question_kr": q["question_kr"],
            "label": label,
            "label_kr": label_kr,
        })

    legal_items = answers.get("legal_confirmations", [])
    if isinstance(legal_items, str):
        legal_items = [legal_items]
    required_legal = {"age_18", "experience_acknowledged", "risk_acknowledged",
                      "past_performance", "ai_advisory"}
    legal_confirmed = required_legal.issubset(set(legal_items or []))

    rt_effective = risk_tolerance if risk_tolerance is not None else 6
    return {
        "questionnaire_version": 3,
        "investor_type": _classify_declared_persona_v3(
            holding, frequency, risk_tolerance, record_habit,
        ),
        "risk_tolerance": rt_effective,
        "risk_score": rt_effective * 10,
        "time_horizon": V3_HOLDING_TO_HORIZON.get(holding, "medium"),
        "record_habit": record_habit if isinstance(record_habit, str) else None,
        "declared_vector": declared_vector,
        "statements": statements,
        "legal_confirmed": legal_confirmed,
    }
