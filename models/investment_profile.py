"""Investment profile model — the user's onboarding declarations (V3) + legacy columns."""
import json
from datetime import datetime, timezone
from extensions import db

# ── Profile presets: maps profile_type → quant engine parameters ──
PROFILE_PRESETS = {
    "conservative": {
        "tech_weight": 0.40, "fund_weight": 0.40, "news_weight": 0.20,
        "tp_min": 5.0, "tp_max": 10.0, "sl_min": 3.0, "sl_max": 5.0,
        "max_positions": 10, "buy_threshold": 75.0, "sell_threshold": 30.0,
        "ai_coaching_style": "risk_warning", "alert_frequency": "daily",
    },
    "balanced": {
        "tech_weight": 0.50, "fund_weight": 0.30, "news_weight": 0.20,
        "tp_min": 8.0, "tp_max": 15.0, "sl_min": 5.0, "sl_max": 8.0,
        "max_positions": 15, "buy_threshold": 70.0, "sell_threshold": 25.0,
        "ai_coaching_style": "balanced", "alert_frequency": "daily",
    },
    "growth": {
        "tech_weight": 0.55, "fund_weight": 0.25, "news_weight": 0.20,
        "tp_min": 12.0, "tp_max": 25.0, "sl_min": 8.0, "sl_max": 12.0,
        "max_positions": 20, "buy_threshold": 65.0, "sell_threshold": 22.0,
        "ai_coaching_style": "opportunity", "alert_frequency": "realtime",
    },
    "aggressive": {
        "tech_weight": 0.60, "fund_weight": 0.20, "news_weight": 0.20,
        "tp_min": 15.0, "tp_max": 40.0, "sl_min": 10.0, "sl_max": 20.0,
        "max_positions": 30, "buy_threshold": 60.0, "sell_threshold": 20.0,
        "ai_coaching_style": "aggressive", "alert_frequency": "realtime",
    },
}


class InvestmentProfile(db.Model):
    __tablename__ = "investment_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                         unique=True, nullable=False)

    # ── Onboarding answers ──
    experience_level = db.Column(db.String(20), default="beginner")
    investment_goal = db.Column(db.String(30), default="growth")
    risk_tolerance = db.Column(db.Integer, default=5)
    time_horizon = db.Column(db.String(20), default="medium")
    preferred_markets = db.Column(db.String(10), default="both")
    preferred_sectors = db.Column(db.Text, default="[]")  # JSON array
    auto_trade_preference = db.Column(db.String(20), default="manual")
    daily_time = db.Column(db.String(20), default="moderate")

    # ── Auto-calculated quant parameters ──
    profile_type = db.Column(db.String(20), default="balanced")
    tech_weight = db.Column(db.Float, default=0.50)
    fund_weight = db.Column(db.Float, default=0.30)
    news_weight = db.Column(db.Float, default=0.20)
    tp_min = db.Column(db.Float, default=8.0)
    tp_max = db.Column(db.Float, default=15.0)
    sl_min = db.Column(db.Float, default=5.0)
    sl_max = db.Column(db.Float, default=8.0)
    max_positions = db.Column(db.Integer, default=15)
    buy_threshold = db.Column(db.Float, default=70.0)
    sell_threshold = db.Column(db.Float, default=25.0)
    ai_coaching_style = db.Column(db.String(20), default="balanced")
    alert_frequency = db.Column(db.String(20), default="daily")

    # ── Feature 1 (Quant Composer) ── per-user model selection + weight overrides.
    # Stored as TEXT JSON for SQLite/Postgres portability; serialized via
    # services.quant.composer at the boundary. Empty list/dict = "no override"
    # so the engine remains backward compatible for users who never opted in.
    enabled_quant_models = db.Column(db.Text, default="[]")
    model_weights = db.Column(db.Text, default="{}")

    # ── Questionnaire V3 (2026-09-06) ── the user's own words, kept.
    # V2 discarded raw answers after classification, so ``/mirror`` could only
    # compare observed behaviour against a persona *centroid*. V3 persists
    # the answers verbatim and their projection onto the observed feature
    # scale so the mirror compares "what you said" with "what you did".
    # NULL for skip-path users and for rows written before V3.
    questionnaire_version = db.Column(db.Integer, nullable=True)
    onboarding_answers_json = db.Column(db.Text, nullable=True)   # raw {qid: value}
    declared_vector_json = db.Column(db.Text, nullable=True)      # {feature_key: 0..1}

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def apply_preset(self):
        """Fill the legacy quant-parameter columns from ``profile_type``.

        The quant engine that read these columns was deleted 2026-08-31 and
        nothing reads them now; they are kept populated only so existing
        rows / exports keep a consistent shape. V3 persona codes that are
        not in the 4-tier map (value, income, speculator, …) take the
        ``balanced`` preset.
        """
        preset = PROFILE_PRESETS.get(self.profile_type, PROFILE_PRESETS["balanced"])
        for k, v in preset.items():
            setattr(self, k, v)

    def to_engine_params(self) -> dict:
        """Return dict for engine.analyze(profile_params=...)"""
        return {
            "tech_weight": self.tech_weight,
            "fund_weight": self.fund_weight,
            "news_weight": self.news_weight,
            "tp_min": self.tp_min,
            "tp_max": self.tp_max,
            "sl_min": self.sl_min,
            "sl_max": self.sl_max,
            "max_positions": self.max_positions,
            "buy_threshold": self.buy_threshold,
            "sell_threshold": self.sell_threshold,
        }

    def declared_vector(self) -> dict:
        """Parsed ``declared_vector_json`` — ``{}`` when absent or corrupt."""
        raw = self.declared_vector_json
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        out: dict[str, float] = {}
        for k, v in data.items():
            try:
                out[str(k)] = max(0.0, min(1.0, float(v)))
            except (TypeError, ValueError):
                continue
        return out

    def onboarding_answers(self) -> dict:
        """Parsed ``onboarding_answers_json`` — ``{}`` when absent or corrupt."""
        raw = self.onboarding_answers_json
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def to_dict(self) -> dict:
        """Serialize for API response."""
        return {
            "questionnaire_version": self.questionnaire_version,
            "declared_vector": self.declared_vector(),
            "profile_type": self.profile_type,
            "experience_level": self.experience_level,
            "investment_goal": self.investment_goal,
            "risk_tolerance": self.risk_tolerance,
            "time_horizon": self.time_horizon,
            "preferred_markets": self.preferred_markets,
            "preferred_sectors": self.preferred_sectors,
            "auto_trade_preference": self.auto_trade_preference,
            "daily_time": self.daily_time,
            "tech_weight": self.tech_weight,
            "fund_weight": self.fund_weight,
            "news_weight": self.news_weight,
            "tp_min": self.tp_min,
            "tp_max": self.tp_max,
            "sl_min": self.sl_min,
            "sl_max": self.sl_max,
            "max_positions": self.max_positions,
            "buy_threshold": self.buy_threshold,
            "sell_threshold": self.sell_threshold,
            "ai_coaching_style": self.ai_coaching_style,
            "alert_frequency": self.alert_frequency,
        }
