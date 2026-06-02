from datetime import datetime, timezone
from extensions import db
from services.crypto_service import EncryptedText


class Position(db.Model):
    __tablename__ = "positions"
    # NEW-D (2026-05-09): UniqueConstraint(user_id, ticker) closes a race
    # window in routes/portfolio.py add_position / create_position_alias /
    # buy_new_position where two concurrent POSTs both pass the
    # ``Position.query.filter_by(user_id, ticker).first()`` lookup and
    # then both insert — producing duplicate rows that double-count in
    # /api/portfolio summary aggregations. The Python-level check stays
    # (so the merge path runs on legitimate retries) but the DB-level
    # constraint guarantees correctness even under concurrency.
    __table_args__ = (
        db.UniqueConstraint("user_id", "ticker", name="uq_positions_user_ticker"),
    )

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    ticker     = db.Column(db.String(20),  nullable=False)
    shares     = db.Column(db.Float,       nullable=False)
    avg_cost   = db.Column(db.Float,       nullable=False)
    buy_fx_rate = db.Column(db.Float,      default=0.0)
    added_at   = db.Column(db.DateTime,    default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Thesis Tracker — 매수 이유 + 주간 AI 유효성 체크.
    # thesis / thesis_reason are user/AI free-text ("매수 이유") → encrypted at
    # rest (EncryptedText, server-held key). DB type becomes TEXT; not used in
    # any SQL filter/order so encryption is transparent. thesis_status stays a
    # plaintext enum because it IS filtered on.
    thesis              = db.Column(EncryptedText,  nullable=True)
    thesis_created_at   = db.Column(db.DateTime,    nullable=True)
    thesis_last_checked = db.Column(db.DateTime,    nullable=True)
    thesis_status       = db.Column(db.String(20),  default="pending")  # pending/valid/warning/invalidated
    thesis_reason       = db.Column(EncryptedText,  nullable=True)       # AI check 결과 이유
