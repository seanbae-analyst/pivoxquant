"""MonthlyReportSend — 월간 거울 리포트를 그 달 몫으로 이미 보냈다는 기록.

services/reports_delivery.py. 서버(Render Free)가 1일 08:30 KST 에 자고 있으면
인프로세스 크론이 그 발송을 통째로 건너뛴다(.github/workflows/keep-warm.yml §0-c).
그래서 1일 08:30–23:30 매시 다시 시도하고, 이 행으로 같은 달을 두 번 보내지
않는다. 리포트 내용은 담지 않는다 — 누구에게 어느 달 몫을 언제 보냈는지뿐.

스키마는 ``migrations/versions/068_monthly_report_sends.py`` 와 1:1. 탈퇴 시
``services/account_erasure`` 가 지운다(FK CASCADE 와 함께).
"""
from __future__ import annotations

from datetime import datetime, timezone

from extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MonthlyReportSend(db.Model):
    __tablename__ = "monthly_report_sends"
    __table_args__ = (
        db.UniqueConstraint("user_id", "period", name="uq_monthly_report_sends_user_period"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    # 리포트가 덮는 달 (KST, "YYYY-MM").
    period = db.Column(db.String(7), nullable=False)
    sent_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
