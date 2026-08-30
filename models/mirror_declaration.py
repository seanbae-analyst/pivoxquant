"""What a user said about themselves, and when.

Stored as an append-only series rather than a mutable row on ``users``.
The product's claim is the distance between a belief and a record, and
that only means something if the belief is fixed in time — if answering
again overwrote the first answer, a user could quietly restate their
belief after seeing the mirror, and the gap would close without anything
about their trading having changed.

So the row is never updated. Re-answering writes a new row, the newest is
what the current screen compares against, and the older ones stay as the
record of what was believed before. That series is also the only way to
show movement later: a chat session cannot tell you what you thought in
March, and this is the table that can.
"""
from datetime import datetime, timezone

from extensions import db


class MirrorDeclaration(db.Model):
    __tablename__ = "mirror_declarations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # All three nullable: partial answers are allowed on purpose. Forcing a
    # complete set would push users to guess at a question they have no
    # feel for, and a guessed belief makes a meaningless gap.
    hold_days = db.Column(db.Float)
    trades_per_month = db.Column(db.Float)
    hold_longer = db.Column(db.String(10))  # profit | loss | same | unsure

    declared_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        index=True,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "hold_days": self.hold_days,
            "trades_per_month": self.trades_per_month,
            "hold_longer": self.hold_longer,
            "declared_at": self.declared_at.isoformat() + "Z" if self.declared_at else None,
        }

    @classmethod
    def latest_for(cls, user_id: int) -> "MirrorDeclaration | None":
        return (
            cls.query
            .filter_by(user_id=int(user_id))
            .order_by(cls.declared_at.desc(), cls.id.desc())
            .first()
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<MirrorDeclaration user={self.user_id} at={self.declared_at}>"
