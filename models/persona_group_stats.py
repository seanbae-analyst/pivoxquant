"""PersonaGroupStats — anonymized, aggregated stats per persona × window.

Part of PivoxQuant Group Benchmark (see
reports/product/GROUP_BENCHMARK_SPEC_2026-04-24.md).

Privacy posture (개인정보보호법 + 신용정보법 준수)
--------------------------------------------------
- Individual user IDs MUST NEVER appear in any row here.
- Individual tickers MUST NEVER appear. Only sector-level buckets are
  stored (portmanteau categories like "Technology", "Healthcare") — these
  are not sufficient to identify a user.
- Minimum group size enforced at **20 unique users** (``MIN_GROUP_SIZE``).
  When ``n_users < 20`` we either (a) skip the snapshot entirely, or (b)
  persist the row with ``suppressed=True`` and a null ``metrics`` JSON so
  the API layer can distinguish "not yet computed" from "legally
  suppressed".
- One row per (persona, window_days) pair. The most recent ``computed_at``
  wins on the read path. Historic rows are kept for an audit trail.

Read path:  ``services.profile.group_benchmark.get_persona_stats(...)``
Write path: ``services.profile.group_benchmark.compute_persona_stats(...)``
            or the standalone ``scripts/compute_group_stats.py`` cron.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from extensions import db


# Legal floor — see reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §group-stats.
# Below this threshold we cannot publish aggregated metrics without risk of
# re-identification (PIPA Art.26-2 / 신용정보법 Art.32).
MIN_GROUP_SIZE = 20

# The canonical 8 persona codes — must stay in sync with
# services/profile/persona_analytics.PERSONA_CODES. Duplicated here as a
# tuple constant so the DB layer can validate writes without importing
# the analytics module (avoids an import cycle).
VALID_PERSONAS = (
    "growth", "value", "balanced", "income",
    "quant", "speculator", "daytrader", "beginner",
)

# Window-day presets. Tests + cron both write only these; the API layer
# rejects anything else with HTTP 400.
VALID_WINDOWS = (30, 90, 365)


class PersonaGroupStats(db.Model):
    __tablename__ = "persona_group_stats"

    id = db.Column(db.Integer, primary_key=True)
    # 8-persona code (see VALID_PERSONAS). NOT a user identifier.
    persona = db.Column(db.String(20), nullable=False, index=True)
    # 30 / 90 / 365 day lookback.
    window_days = db.Column(db.Integer, nullable=False, index=True)
    # UTC, naive (matches the rest of the codebase).
    computed_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        index=True,
    )
    # Group size — the legal gate key. Never expose individual counts below
    # MIN_GROUP_SIZE outside this table.
    n_users = db.Column(db.Integer, nullable=False, default=0)
    # True iff n_users < MIN_GROUP_SIZE at compute time. When suppressed,
    # metrics is stored as null so a later legal audit can prove we never
    # materialized the underlying numbers.
    suppressed = db.Column(db.Boolean, nullable=False, default=False)
    # JSON blob — see group_benchmark.py for the schema. Stored as TEXT so
    # SQLite + Postgres stay portable.
    metrics = db.Column(db.Text, nullable=True, default=None)

    __table_args__ = (
        db.Index(
            "idx_persona_group_stats_persona_window_computed",
            "persona", "window_days", "computed_at",
        ),
    )

    # ── Helpers ───────────────────────────────────────────────────────

    def metrics_dict(self) -> dict:
        """Safely decode the metrics JSON column.

        Returns an empty dict if suppressed / null / malformed — the API
        layer uses ``suppressed`` as the source of truth for "not
        publishable", not the presence of this payload.
        """
        if not self.metrics:
            return {}
        try:
            val = json.loads(self.metrics)
            return val if isinstance(val, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def to_dict(self) -> dict:
        return {
            "persona": self.persona,
            "window_days": int(self.window_days or 0),
            "computed_at": self.computed_at.isoformat() if self.computed_at else None,
            "n_users": int(self.n_users or 0),
            "suppressed": bool(self.suppressed),
            "metrics": self.metrics_dict() if not self.suppressed else None,
        }
