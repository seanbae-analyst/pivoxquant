"""NpsFeedback — 1-click NPS score per user (Wave G C-AC2).

One row per submission. Score is constrained 1-10 at the DB level
(``ck_nps_score_range``) so a buggy client cannot poison the aggregates.

Classified as *transactional* (서비스 개선) under 정통망법 §50 — collected
to improve the product, not to drive marketing decisions, so no
marketing-consent gate applies.

Aggregation
-----------
The standard NPS rollup is:

    promoters - detractors = NPS    (promoters: 9-10, detractors: 1-6,
                                     passives: 7-8 are excluded)

The read path lives in services/product_analytics (separate PR) — the
model itself is intentionally minimal.

Idempotency
-----------
Duplicate submissions on the same ``(user_id, weekly_memo_id)`` tuple
are allowed at the DB level; the frontend de-duplicates via localStorage
(see ``NpsWidget``) and the read path picks ``MAX(created_at)`` per
tuple. Allowing duplicates lets a user change their score without a
DELETE round-trip.
"""
from datetime import datetime, timezone

from extensions import db


class NpsFeedback(db.Model):
    __tablename__ = "nps_feedback"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    score = db.Column(db.Integer, nullable=False)
    # weekly_memo_id is an opaque artifact slug — deliberately NOT FK'd to
    # artifacts.id (mirrors ArtifactFeedback) so NPS history survives
    # artifact deletion for aggregate-only analytics.
    weekly_memo_id = db.Column(db.String(64), nullable=True, index=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    __table_args__ = (
        db.CheckConstraint("score >= 1 AND score <= 10", name="ck_nps_score_range"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "score": self.score,
            "weekly_memo_id": self.weekly_memo_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
