"""Single source of truth for duplicated user-facing disclaimer text.

Several legal notices were copy-pasted **byte-identically** across many surfaces
(artifact builders, behaviour mirrors). Divergent copies of legally load-bearing
text are a real hazard: a lawyer-mandated wording change must hit every copy or
the product ships inconsistent disclaimers, and an audit cannot assert a single
canonical string. This module holds those shared strings ONCE.

Every constant below is the EXACT text its surfaces already shipped — adopting
this module changes ZERO wording (locked by tests/test_disclaimer_sot.py).

Context-specific disclaimers that legitimately DIFFER (tax vs investment vs
sector vs paper-twin vs persona-drift, the present-holdings "concentration"
mirror, and the frozen services/quant/* notices) intentionally keep their own
text and are NOT merged here.
"""

# ── Artifact investment-advice disclaimer (KR) ──────────────────────────────
# Shipped by: sample_data, risk_board, self_audit, dd_checklist, kpi_dashboard,
# portfolio_segment, year_end_letter, quarterly_self_report.
DISCLAIMER_ARTIFACT_KR = (
    "정보 제공 목적이며 투자 권유가 아닙니다. 투자 판단은 본인 책임입니다."
)

# Bilingual variant (KR + EN). Shipped by: earnings_prebrief, weekly_memo.
DISCLAIMER_ARTIFACT_BILINGUAL = (
    "정보 제공 목적이며 투자 권유가 아닙니다. 투자 판단은 본인 책임입니다. / "
    "Information only, not investment advice. Decisions are your own."
)

# Shorter bilingual variant. Shipped by: brag_card, monthly_brag.
DISCLAIMER_BRAG_BILINGUAL = (
    "정보 제공 목적이며 투자 권유가 아닙니다. / "
    "Information only, not investment advice."
)

# Retrospective "mirror" disclaimer — past-trade factual observation, not advice.
# Shipped by behaviour mirrors (holding / profit-loss / turnover / averaging-down)
# and the profile activity mirror. NOTE: the *present-holdings* concentration
# mirror ("현재 보유 종목") is deliberately DIFFERENT and stays separate.
DISCLAIMER_MIRROR_RETROSPECTIVE_KR = (
    "본 정보는 지난 거래의 회고적 사실 관찰이며 미래 예측이나 거래 권유가 아닙니다."
)
