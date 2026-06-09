"""Lock the disclaimer SoT text (services/legal/disclaimers.py).

These constants replaced byte-identical copies across ~16 surfaces. A typo in
the SoT would now silently change LEGAL text everywhere at once, so the exact
strings are pinned here. The values below are the verbatim text those surfaces
shipped before consolidation — do NOT "fix" them without legal sign-off.
"""

from services.legal.disclaimers import (
    DISCLAIMER_ARTIFACT_BILINGUAL,
    DISCLAIMER_ARTIFACT_KR,
    DISCLAIMER_BRAG_BILINGUAL,
    DISCLAIMER_MIRROR_RETROSPECTIVE_KR,
)


def test_artifact_kr_exact():
    assert DISCLAIMER_ARTIFACT_KR == (
        "정보 제공 목적이며 투자 권유가 아닙니다. 투자 판단은 본인 책임입니다."
    )


def test_artifact_bilingual_exact():
    assert DISCLAIMER_ARTIFACT_BILINGUAL == (
        "정보 제공 목적이며 투자 권유가 아닙니다. 투자 판단은 본인 책임입니다. / "
        "Information only, not investment advice. Decisions are your own."
    )


def test_brag_bilingual_exact():
    assert DISCLAIMER_BRAG_BILINGUAL == (
        "정보 제공 목적이며 투자 권유가 아닙니다. / "
        "Information only, not investment advice."
    )


def test_mirror_retrospective_exact():
    assert DISCLAIMER_MIRROR_RETROSPECTIVE_KR == (
        "본 정보는 지난 거래의 회고적 사실 관찰이며 미래 예측이나 거래 권유가 아닙니다."
    )


def test_behavior_mirrors_resolve_to_sot():
    import routes.behavior as b

    for name in (
        "_HOLDING_MIRROR_DISCLAIMER",
        "_PROFIT_LOSS_MIRROR_DISCLAIMER",
        "_TURNOVER_MIRROR_DISCLAIMER",
        "_AVERAGING_DOWN_MIRROR_DISCLAIMER",
    ):
        assert getattr(b, name) == DISCLAIMER_MIRROR_RETROSPECTIVE_KR

    # The present-holdings concentration mirror is deliberately DIFFERENT.
    assert b._CONCENTRATION_MIRROR_DISCLAIMER != DISCLAIMER_MIRROR_RETROSPECTIVE_KR


def test_profile_activity_mirror_resolves_to_sot():
    import routes.profile as p

    assert p._ACTIVITY_MIRROR_DISCLAIMER == DISCLAIMER_MIRROR_RETROSPECTIVE_KR
