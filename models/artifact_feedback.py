"""ArtifactFeedback — section-level votes on rendered CFO artifacts.

Part of Living CFO Layer 2 (see reports/product/PERSONA_SPEC_2026-04-23.md
§6 and frontend/src/lib/cfo/hooks.ts).

One row per vote. Duplicates on ``(user_id, artifact_id, section)`` are
*allowed* — the aggregation layer treats the latest ``created_at`` as
authoritative so users can change their mind without a DELETE. The
read path in services/profile/persona_analytics picks MAX(created_at)
per (user, artifact, section) tuple.

Vote vocabulary is fixed to the frontend contract:
    ``useful`` — section moved the needle.
    ``meh``    — section was noise.
    ``skip``   — section should be suppressed next run.
"""
from datetime import datetime, timezone

from extensions import db


VOTE_CHOICES = ("useful", "meh", "skip")


class ArtifactFeedback(db.Model):
    __tablename__ = "artifact_feedback"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Artifact IDs are strings on the frontend (UUIDs / hash). Keep as
    # opaque string — this table deliberately does NOT foreign-key to
    # artifacts.id so cross-artifact feedback history survives artifact
    # deletion for aggregate-only analytics.
    artifact_id = db.Column(db.String(64), nullable=False, index=True)
    section = db.Column(db.String(80), nullable=False)
    vote = db.Column(db.String(16), nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        db.Index(
            "idx_artifact_feedback_user_artifact_section",
            "user_id",
            "artifact_id",
            "section",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "artifact_id": self.artifact_id,
            "section": self.section,
            "vote": self.vote,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
