"""Artifact — persisted artefacts (weekly memo, brag card, etc).

One row per generated artefact. Schema intentionally generic so MVP#1
(Weekly Investor Memo), MVP#2 (Monthly Brag Card), MVP#3 (Earnings
Pre-Brief) can share the same table.

Columns
-------
- `type`      — short slug identifying the artefact class. Allowed values
                are not enforced at the DB level (so new artefact types
                never require a schema migration); the application
                layer validates against `ARTIFACT_TYPES`.
- `title`     — human-readable display title ("Week 16 Investor Memo").
- `data_json` — raw structured payload the artefact was rendered from.
                Useful for re-rendering with an updated template without
                re-fetching upstream data.
- `pdf_path`  — either a local path (dev) or an S3 URL (prod). Nullable
                because some artefacts are HTML/image-only (brag card).
- `sent_at`   — when the email/push was delivered. NULL → pending/failed.
- `opened_at` — when the recipient clicked the download link. NULL → unread.

Idempotency: the `(user_id, type, title)` triple is declared UNIQUE so a
scheduler re-run on the same week/month cannot create duplicate rows.
Re-runs should UPSERT into the existing row via `title` collision.
"""
from datetime import datetime, timezone

from extensions import db


# Known artefact types. Enforced at the service layer, not the DB, so we
# can add new types without a migration.
ARTIFACT_TYPES = {
    "weekly_memo",
    "brag_card",
    "monthly_brag",
    "earnings_pre",
    "earnings_prebrief",  # MVP #3: 30-min pre-announcement brief
    "earnings_post",
    "fomc_playbook",
    # 2026-04-19 — Three new artefact classes:
    "kpi_dashboard",     # Daily 08:00 KST KPI email (Pro+)
    "self_audit",        # Quarterly decision-quality PDF (Premium)
    "dd_checklist",      # T+3 post-entry due-diligence email (Pro+)
    # 2026-04-19 (Pro-tier expansion)
    "burn_rate",         # Monthly 1-page PDF — cost + expected tax (Pro+)
    "credit_rating",     # Monthly self-assessed portfolio grade (Pro+)
    # 2026-04-19 (Premium-tier finance reports)
    "dividend_income",   # Monthly 3-page dividend statement (Premium)
    "monthly_finance",   # Monthly 6-page Cash Runway + Cost/Tax (Premium)
    # 2026-04-19 (Premium-tier risk + segment reports)
    "risk_board",        # Monthly + VIX-spike 8-page deck (Premium)
    "portfolio_segment", # Quarterly 4-page segment breakdown (Premium)
    # 2026-04-19 (Premium — on-demand What-If + weekly event feed)
    "capital_allocation", # On-demand Capital Allocation What-If (Premium)
    "insider_mirror",    # Weekly 3-page SEC/DART insider event feed (Premium)
    # 2026-04-19 (Premium-tier retrospective artefacts — download-only,
    # no share surface per explicit legal decision)
    "year_end_letter",        # Annual 6-page Buffett-tone letter (Premium)
    "quarterly_self_report",  # Quarterly 15-page Self 10-K + Thesis check (Premium)
}


class Artifact(db.Model):
    __tablename__ = "artifacts"

    id         = db.Column(db.Integer,    primary_key=True)
    user_id    = db.Column(db.Integer,    db.ForeignKey("users.id"),
                           nullable=False, index=True)
    type       = db.Column(db.String(40), nullable=False, index=True)
    title      = db.Column(db.String(200), nullable=False)
    data_json  = db.Column(db.JSON,       nullable=True)
    pdf_path   = db.Column(db.String(500), nullable=True)
    sent_at    = db.Column(db.DateTime,   nullable=True)
    opened_at  = db.Column(db.DateTime,   nullable=True)
    # Brag Card (MVP #2) — unguessable public-share handle. Other artefact
    # types may also use this in the future; the column is shared. Kept
    # nullable because legacy rows don't have one; UNIQUE enforced via
    # the migration's explicit index.
    share_token = db.Column(db.String(32), nullable=True, index=True)
    created_at = db.Column(db.DateTime,   default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "type", "title",
                             name="uq_artifact_user_type_title"),
    )

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "type":       self.type,
            "title":      self.title,
            "pdf_path":   self.pdf_path,
            "data":       self.data_json or {},
            "sent_at":    self.sent_at.isoformat() + "Z" if self.sent_at else None,
            "opened_at":  self.opened_at.isoformat() + "Z" if self.opened_at else None,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Artifact id={self.id} user={self.user_id} type={self.type} title={self.title!r}>"
