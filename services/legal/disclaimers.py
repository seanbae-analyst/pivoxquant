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

# ─────────────────────────────────────────────────────────────────────────
# AI 생성물 표시 의무 (방통위 AI 생성물 표시제) — 현재 적용 대상 없음
# ─────────────────────────────────────────────────────────────────────────
# Until 2026-08-30 every AI-written artefact carried an "AI 생성 콘텐츠 /
# AI-generated" badge via services/artifacts/templates/_disclaimer.html, and
# two test files froze that: tests/test_ai_content_label.py and
# tests/test_artifact_none_default_and_ai_badge.py.
#
# Those templates went with services/artifacts. The seven surviving email
# templates (onboarding, retention) are hand-written static copy, so nothing
# the product currently sends is AI-generated and the badge has no surface
# to sit on. The guards were removed rather than left asserting against
# deleted files.
#
# The obligation did not go away — the subject did. The moment this product
# ships AI-written user-facing text again (the reflection questions in the
# mirror flow are the likely first), the badge and a guard freezing it must
# come back with it. Recorded here rather than in a commit message because
# a commit message is not somewhere anyone looks before writing a new
# AI-backed feature.
