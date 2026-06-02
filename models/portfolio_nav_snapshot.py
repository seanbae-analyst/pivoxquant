"""PortfolioNavSnapshot — one REAL daily NAV reading per user.

Why this exists
---------------
The equity curve ("How the book moves") used to be *reconstructed* on the fly
from the user's CURRENT share count × historical prices. That is a
counterfactual — it draws the value the book *would* have had if today's
holdings were held throughout the window, i.e. months the user never actually
held that book. CEO flagged it repeatedly as fake data (and it is a 표시광고법
fabrication risk).

The only honest equity curve is one built from NAV we *actually observed and
recorded* on each day. This table is that record: one row per (user, day),
written from real positions × real prices at the time. No backfill — the curve
starts when we started recording and grows truthfully. A brand-new account
shows an empty/short curve, which is the truth.

Schema is mirrored 1:1 with ``migrations/versions/047_portfolio_nav_snapshots.py``.
"""
from __future__ import annotations

from datetime import datetime, timezone

from extensions import db


class PortfolioNavSnapshot(db.Model):
    __tablename__ = "portfolio_nav_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The trading day this NAV was observed (naive UTC date). One row per day
    # per user — re-recording the same day UPDATES the row (latest intraday
    # reading wins) via the unique constraint below.
    as_of_date = db.Column(db.Date, nullable=False, index=True)

    # NAV unified to USD — this is the value the equity curve plots (KR
    # positions converted at the FX rate observed at record time).
    nav_total_usd = db.Column(db.Numeric(20, 2), nullable=False)
    # Native-currency subtotals (for a future split KPI; the curve uses total).
    nav_us_usd = db.Column(db.Numeric(20, 2), nullable=False, default=0)
    nav_kr_krw = db.Column(db.Numeric(20, 2), nullable=False, default=0)
    # The USD/KRW rate used at record time — kept for auditability (honesty:
    # the conversion is reproducible after the fact).
    fx_rate = db.Column(db.Numeric(12, 4), nullable=True)

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=db.func.now(),
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=db.func.now(),
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "as_of_date", name="uq_nav_snapshot_user_day"),
        db.Index("idx_nav_snapshot_user_day", "user_id", "as_of_date"),
    )

    def to_point(self) -> dict:
        """Equity-curve point: {date, value} in USD-unified NAV."""
        return {
            "date": self.as_of_date.strftime("%Y-%m-%d"),
            "value": round(float(self.nav_total_usd), 2),
        }
