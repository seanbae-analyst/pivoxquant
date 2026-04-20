"""Position Due-Diligence Checklist — T+3 post-entry Y/N record.

Stores a user's own answers to a 5-item checklist triggered 3 days after
they added a position. No AI judgement is persisted — PivoxQuant records
only what the *user* confirmed they checked, which is deliberately
different from an investment recommendation and keeps the artefact on
the right side of 자본시장법 §6 (미등록 투자자문업).

Idempotency
-----------
`position_id` is UNIQUE so a user cannot accumulate multiple rows per
position; re-submitting updates the existing row. The FK cascade
matches `positions` so deleting a position cleans up the checklist.
"""
from datetime import datetime, timezone
from extensions import db


class PositionDDCheck(db.Model):
    __tablename__ = "position_dd_checks"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"),
                             nullable=False, index=True)
    position_id  = db.Column(db.Integer, db.ForeignKey("positions.id"),
                             nullable=False, unique=True, index=True)

    # Five Y/N answers. Default False — unchecked until the user confirms.
    financials_checked   = db.Column(db.Boolean, default=False, nullable=False)
    moat_checked         = db.Column(db.Boolean, default=False, nullable=False)
    management_checked   = db.Column(db.Boolean, default=False, nullable=False)
    valuation_checked    = db.Column(db.Boolean, default=False, nullable=False)
    risks_checked        = db.Column(db.Boolean, default=False, nullable=False)

    # Free-form note (optional; 500 char cap to stay inside DB index limits)
    note                 = db.Column(db.String(500), nullable=True)

    created_at   = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
    updated_at   = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "id":                 self.id,
            "position_id":        self.position_id,
            "financials_checked": bool(self.financials_checked),
            "moat_checked":       bool(self.moat_checked),
            "management_checked": bool(self.management_checked),
            "valuation_checked":  bool(self.valuation_checked),
            "risks_checked":      bool(self.risks_checked),
            "note":               self.note or "",
            "created_at":         self.created_at.isoformat() + "Z" if self.created_at else None,
            "updated_at":         self.updated_at.isoformat() + "Z" if self.updated_at else None,
            "score":              self.score(),
        }

    def score(self) -> int:
        """Integer 0-5 — how many boxes the user has ticked."""
        return sum(
            1 for v in (
                self.financials_checked, self.moat_checked,
                self.management_checked, self.valuation_checked,
                self.risks_checked,
            ) if bool(v)
        )

    def __repr__(self) -> str:
        return (f"<PositionDDCheck id={self.id} user={self.user_id} "
                f"pos={self.position_id} score={self.score()}/5>")
