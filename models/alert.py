from datetime import datetime, timezone
from extensions import db


class Alert(db.Model):
    """User-facing notification.

    New fields (2026-04-22) — `kind`, `title`, `body`, `link`, `read_at`
    support the NotificationDropdown API. Legacy fields (`message`, `signal`,
    `score`, `rec_shares`, `rec_investment`, `is_read`, `ticker`) remain
    intact so existing routes.alerts endpoints keep working.
    """
    __tablename__ = "alerts"
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ticker         = db.Column(db.String(20))

    # ── New (2026-04-22) bell-dropdown fields ───────────────────────────────
    kind           = db.Column(db.String(40))   # price_52w_high, concentration_alert, ...
    title          = db.Column(db.String(200))  # Short headline (observation tone)
    body           = db.Column(db.Text)         # Optional secondary line
    link           = db.Column(db.String(300))  # Click-through path (e.g. /reports)
    read_at        = db.Column(db.DateTime)     # When marked read

    # ── Legacy fields (kept for backwards compatibility) ────────────────────
    message        = db.Column(db.Text)         # Was: nullable=False. Relaxed so new callers can skip.
    signal         = db.Column(db.String(10))
    score          = db.Column(db.Float,   default=0)
    rec_shares     = db.Column(db.Integer, default=0)
    rec_investment = db.Column(db.Float,   default=0)
    created_at     = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    is_read        = db.Column(db.Boolean,  default=False)
