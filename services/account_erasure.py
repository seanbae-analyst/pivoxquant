"""계정 파기 — 유저 소유 행 지우기의 한 벌 (PIPA §21).

두 호출자가 이것을 쓴다:
  * ``routes/auth.py:delete_account``      — "지금 삭제"
  * ``scripts/nightly/pipa_purge.py``       — 30일 유예 후 자동 파기

예전에는 두 곳이 같은 목록을 따로 들고 있었고, 야간 파기 쪽은 SAVEPOINT 가
없어 표 하나가 실패하면 그 유저의 파기 전체가 롤백·skip 됐다. 여기서는 모든
단계가 표마다 SAVEPOINT 안에서 돌고, 실패는 모아서 돌려준다.

단계 (순서 유지):
  1. 모델이 있는 유저 소유 테이블을 명시적으로 DELETE (FK CASCADE 위의
     이중 안전장치 — prod FK drift 에 파기가 막히지 않게). FK 순서가
     중요한 곳은 목록 순서로 지킨다. companion_waitlist 는 user_id 로
     연결된 행과 같은 이메일 해시의 행을 함께 지운다 (email_plaintext ·
     email_hash 가 남으면 파기가 아니다).
  2. 동적 FK 스윕 — 라이브 DB 를 introspect 해서 users.id 를 참조하는 남은
     행을 모두 지운다 (모델 없는 migration-only 테이블, 예: morning_briefs).
     funnel_events 는 FK 가 없어 건드리지 않는다 (의도된 익명 분석 스냅숏).
  3. 모델도 FK 도 없는 user_id 테이블 — 허용 목록만 (anthropic_usage_log).
  4. auth_events 는 email 키라 위 어디에도 안 걸린다 — 지우지 않고 email 을
     솔트 SHA256 으로 바꿔 익명화한다 (§29 감사 집계는 남고 사람은 사라진다).

커밋하지 않는다 — users 행 삭제·커밋·Stripe·메일은 호출자 몫이다.
"""
from __future__ import annotations

import hashlib
import logging
import os

logger = logging.getLogger(__name__)

# 모델도 users FK 도 없는 user_id 테이블 허용 목록. 모든 user_id 테이블을
# 지우면 funnel_events(의도적으로 남기는 익명 분석 스냅숏)까지 날아간다.
MODELLESS_USER_ID_TABLES = ("anthropic_usage_log",)


def _purge_salt() -> str:
    return (
        os.environ.get("PIPA_PURGE_SALT")
        or os.environ.get("SECRET_KEY")
        or "pivoxquant-purge-fallback-salt-do-not-use-in-prod"
    )


def hash_email(email: str) -> str:
    """Return ``sha256(salt + email)`` hex digest (length 64)."""
    salt = _purge_salt().encode("utf-8")
    return hashlib.sha256(salt + (email or "").encode("utf-8")).hexdigest()


def _purge_companion_waitlist(user_id: int, email: str | None) -> int:
    """대기자 명단 행을 지운다 — user_id 로 연결된 행 + 같은 이메일 해시 행.

    예전엔 user_id 만 NULL 로 떼어 내 ``email_plaintext``(원문 이메일)와
    ``email_hash``(무솔트 SHA256 — 사전 대입으로 되돌릴 수 있다)가 남았다.
    로그인 전에 랜딩에서 등록한 행은 user_id 가 없으니 이메일 해시로 찾는다.
    해시는 ``CompanionWaitlist.hash_email`` 을 그대로 쓴다 (키 규칙 한 벌).
    ``CompanionWaitlist.purge_by_email`` 은 커밋하므로 여기선 못 쓴다 —
    이 모듈은 커밋하지 않고, 표마다 SAVEPOINT 안에서 돈다.
    """
    from sqlalchemy import or_
    from models import CompanionWaitlist

    match = [CompanionWaitlist.user_id == user_id]
    if email and email.strip():
        match.append(
            CompanionWaitlist.email_hash == CompanionWaitlist.hash_email(email)
        )
    return CompanionWaitlist.query.filter(or_(*match)).delete(
        synchronize_session=False,
    )


def _explicit_ops(user_id: int, email: str | None = None):
    """(테이블 이름, 실행 함수) 목록 — 순서가 곧 FK 순서다.

    새 유저 소유 모델을 추가하면 여기 한 곳에만 넣으면 된다.
    SignalCache 는 전역(ticker 키, user_id 없음)이라 없다.
    """
    from models import (
        Position, TradeHistory, Alert, Watchlist,
        InvestmentProfile, BrokerConnection, PushSubscription,
        PortfolioShare,
        Artifact, UserReferral,
        ArtifactFeedback, BehavioralScore,
        AITwinPortfolio, AITwinWeeklyReport,
        PreTradeReflection, PersonaSnapshot, WeeklyPulse,
        PositionDDCheck, Inquiry, ObservationNote,
        ScheduledEmail, NpsFeedback,
        CheckoutExpiration, PortfolioNavSnapshot, UserAgentAudit,
        ImportBatch, ImportToken, PendingTrade,
    )

    def _d(model):
        return lambda: model.query.filter_by(user_id=user_id).delete(
            synchronize_session=False,
        )

    return [
        ("positions", _d(Position)),
        ("trade_history", _d(TradeHistory)),
        ("alerts", _d(Alert)),
        ("watchlist", _d(Watchlist)),
        ("investment_profiles", _d(InvestmentProfile)),
        ("broker_connections", _d(BrokerConnection)),
        ("push_subscriptions", _d(PushSubscription)),
        ("portfolio_shares", _d(PortfolioShare)),
        ("artifacts", _d(Artifact)),
        ("user_referrals", _d(UserReferral)),
        ("artifact_feedback", _d(ArtifactFeedback)),
        ("behavioral_scores", _d(BehavioralScore)),
        ("ai_twin_portfolios", _d(AITwinPortfolio)),
        ("ai_twin_weekly_reports", _d(AITwinWeeklyReport)),
        # Import Inbox (2026-09-29) — 승인 이유(암호화 자유 텍스트)를 담은
        # 대기 체결부터. FK 순서: pending_trades → import_batches →
        # import_tokens. pending_trades 가 pre_trade_reflections 를
        # 참조하므로 멈춤 기록보다 먼저 지운다.
        ("pending_trades", _d(PendingTrade)),
        ("import_batches", _d(ImportBatch)),
        ("import_tokens", _d(ImportToken)),
        ("pre_trade_reflections", _d(PreTradeReflection)),
        # 관찰 노트 — 유저 본인의 암호화된 자유 텍스트 (2026-09-22).
        ("observation_notes", _d(ObservationNote)),
        ("persona_snapshots", _d(PersonaSnapshot)),
        ("weekly_pulse", _d(WeeklyPulse)),
        ("scheduled_emails", _d(ScheduledEmail)),
        ("nps_feedback", _d(NpsFeedback)),
        # 암호화된 자유 텍스트. 보통 positions cascade 로 이미 사라져 0 건.
        ("position_dd_checks", _d(PositionDDCheck)),
        ("inquiries", _d(Inquiry)),
        # 2026-06-07 — users FK 가 있는데 명시 목록에서 빠져 있던 표들 (prod
        # 500 의 원인 부류). 모델 ondelete 는 CASCADE 지만 prod FK drift 에
        # 파기가 막히지 않도록 명시적으로 지운다.
        ("checkout_expirations", _d(CheckoutExpiration)),
        ("portfolio_nav_snapshots", _d(PortfolioNavSnapshot)),
        # user_agent_audit: 모델 FK 가 CASCADE — 2년 보존을 하려면 nullable
        # user_id + SET NULL + 변호사 확인이 먼저다 (legal_question_queue).
        ("user_agent_audit", _d(UserAgentAudit)),
        # companion_waitlist: 행째 지운다 — 이메일 원문·해시가 남으면 안 된다.
        ("companion_waitlist",
         lambda: _purge_companion_waitlist(user_id, email)),
    ]


def purge_user_rows(user_id: int, email: str | None = None) -> tuple[dict, list]:
    """유저 소유 행을 전부 지운다. ``(counts, failures)`` 를 돌려준다.

    ``counts``  — 테이블 이름 → 지운 행 수. auth_events 익명화는
                  ``auth_events_anonymized`` 키로 센다.
    ``failures`` — 실패한 테이블 이름 목록. 실패한 표는 그 SAVEPOINT 만
                  롤백되고 나머지는 계속된다 (예외를 던지지 않는다).

    커밋하지 않는다.
    """
    from extensions import db
    from sqlalchemy import inspect as sa_inspect, text as sa_text

    counts: dict[str, int] = {}
    failures: list[str] = []

    # 1. 명시 목록 — 표마다 SAVEPOINT.
    for label, op in _explicit_ops(user_id, email):
        try:
            with db.session.begin_nested():
                n = int(op() or 0)
            counts[label] = n
        except Exception as exc:  # noqa: BLE001 — 표 단위 실패 격리
            failures.append(label)
            logger.warning(
                "account_erasure: purge of %s failed (continuing): %s", label, exc,
            )

    # 2. 동적 FK 스윕 — 위에서 처리된 표는 0 건이라 no-op.
    try:
        insp = sa_inspect(db.engine)
        for tbl in insp.get_table_names():
            if tbl == "users":
                continue
            for fk in insp.get_foreign_keys(tbl):
                if fk.get("referred_table") != "users":
                    continue
                if "id" not in (fk.get("referred_columns") or []):
                    continue
                cols = fk.get("constrained_columns") or []
                if not cols:
                    continue
                col = cols[0]
                try:
                    with db.session.begin_nested():
                        db.session.execute(
                            sa_text(f'DELETE FROM "{tbl}" WHERE "{col}" = :uid'),
                            {"uid": user_id},
                        )
                except Exception as exc:  # noqa: BLE001
                    failures.append(tbl)
                    logger.warning(
                        "account_erasure: dynamic purge of %s.%s failed: %s",
                        tbl, col, exc,
                    )
    except Exception:
        logger.exception("account_erasure: dynamic FK sweep init failed (continuing)")

    # 3. 모델·FK 없는 user_id 테이블 — 허용 목록만.
    try:
        insp = sa_inspect(db.engine)
        existing = set(insp.get_table_names())
        for tbl in MODELLESS_USER_ID_TABLES:
            if tbl not in existing:
                continue
            if "user_id" not in {c["name"] for c in insp.get_columns(tbl)}:
                continue
            try:
                with db.session.begin_nested():
                    n = db.session.execute(
                        sa_text(f'DELETE FROM "{tbl}" WHERE "user_id" = :uid'),
                        {"uid": user_id},
                    ).rowcount
                counts[tbl] = int(n or 0)
            except Exception as exc:  # noqa: BLE001
                failures.append(tbl)
                logger.warning(
                    "account_erasure: model-less purge of %s failed: %s", tbl, exc,
                )
    except Exception:
        logger.exception(
            "account_erasure: model-less user_id sweep init failed (continuing)"
        )

    # 4. auth_events — 지우지 않고 email 을 해시로 바꾼다.
    if email:
        try:
            from models import AuthEvent
            with db.session.begin_nested():
                n = (
                    AuthEvent.query.filter(AuthEvent.email == email)
                    .update({AuthEvent.email: hash_email(email)},
                            synchronize_session=False)
                )
            counts["auth_events_anonymized"] = int(n or 0)
        except Exception as exc:  # noqa: BLE001
            failures.append("auth_events")
            logger.warning("account_erasure: auth_events anonymize failed: %s", exc)

    return counts, failures
