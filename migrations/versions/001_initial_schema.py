"""Initial schema — baseline from existing SQLAlchemy models.

Revision ID: 001_initial
Revises:
Create Date: 2026-04-10

This migration represents the existing schema as of the SQLite -> PostgreSQL
migration. It does NOT create tables (db.create_all() handles that).
Instead, it serves as the baseline revision so that future migrations
can be tracked properly.

For existing databases, run:
    flask db stamp 001_initial

For new databases, db.create_all() creates the schema, then stamp this.
"""
from alembic import op
import sqlalchemy as sa

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Schema already created by db.create_all() or the migration script.
    # This revision exists only as a baseline marker.
    #
    # Tables at this point:
    #   - users (id, email, password_hash, name, oauth_provider, google_id,
    #            kakao_id, avatar_url, available_capital, available_capital_krw,
    #            risk_profile, profile_changes_left, subscription_tier,
    #            stripe_customer_id, stripe_subscription_id, subscription_status,
    #            onboarding_completed, created_at)
    #   - positions (id, user_id, ticker, shares, avg_cost, buy_fx_rate, added_at)
    #   - alerts (id, user_id, ticker, message, signal, score, rec_shares,
    #             rec_investment, created_at, is_read)
    #   - signal_cache (ticker, data_json, updated_at)
    #   - trade_history (id, user_id, ticker, name, action, shares,
    #                     price_per_share, total_value, pnl, pnl_pct,
    #                     currency, traded_at)
    #   - watchlist (id, user_id, ticker, added_at)
    #   - investment_profiles (id, user_id, experience_level, investment_goal,
    #                          risk_tolerance, time_horizon, preferred_markets,
    #                          preferred_sectors, auto_trade_preference, daily_time,
    #                          profile_type, tech_weight, fund_weight, news_weight,
    #                          tp_min, tp_max, sl_min, sl_max, max_positions,
    #                          buy_threshold, sell_threshold, ai_coaching_style,
    #                          alert_frequency, created_at, updated_at)
    #   - broker_connections (id, user_id, broker, access_token, refresh_token,
    #                         account_id, is_paper, is_active, last_synced_at,
    #                         created_at)
    #   - push_subscriptions (id, user_id, endpoint, p256dh, auth, created_at)
    pass


def downgrade():
    # Cannot safely drop all tables as a downgrade — this is the baseline.
    # The upgrade() did not create tables (db.create_all() did), so there is
    # no reversible DDL to undo.  Dropping all tables would destroy user data
    # and is never the correct action for a baseline stamp.
    raise NotImplementedError(
        "Migration 001_initial is the baseline schema stamp and cannot be "
        "downgraded.  To start fresh, drop the database and re-run "
        "db.create_all() followed by 'flask db stamp 001_initial'."
    )
