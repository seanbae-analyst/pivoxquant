"""Model serialization helpers."""

from services.name_resolver import (
    lookup_name_from_signal_cache,
    resolve_stock_name,
)


def _resolve_display_name(ticker: str) -> str | None:
    """Prefer the live SignalCache name (broker-provided), then static
    registries. Returns None when nothing resolves — callers fall back
    to the ticker itself to preserve legacy behaviour.
    """
    if not ticker:
        return None
    name = lookup_name_from_signal_cache(ticker) or resolve_stock_name(ticker)
    return name


def serialize_user(u) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "available_capital": u.available_capital,
        "available_capital_krw": getattr(u, "available_capital_krw", 0.0) or 0.0,
        "risk_profile": getattr(u, "risk_profile", "balanced"),
        "profile_changes_left": getattr(u, "profile_changes_left", 3),
        # effective_tier applies the DEV_PREMIUM_EMAILS override; falls back
        # to the stored column for users not in the allowlist.
        "subscription_tier": getattr(u, "effective_tier", None) or getattr(u, "subscription_tier", "free"),
        "subscription_status": getattr(u, "subscription_status", "inactive") or "inactive",
        "onboarding_completed": getattr(u, "onboarding_completed", False),
        "avatar_url": getattr(u, "avatar_url", None),
        "oauth_provider": getattr(u, "oauth_provider", None),
    }


def serialize_trade(t) -> dict:
    return {
        "id": t.id,
        "ticker": t.ticker,
        "name": t.name,
        "action": t.action,
        "shares": t.shares,
        "price_per_share": t.price_per_share,
        "total_value": t.total_value,
        "pnl": t.pnl,
        "pnl_pct": t.pnl_pct,
        "currency": t.currency,
        "traded_at": t.traded_at.isoformat(),
    }


def serialize_alert(a) -> dict:
    # Resolve once per alert. Cache-backed via services.name_resolver so
    # a list render costs ~O(unique tickers) DB hits at worst.
    name = _resolve_display_name(a.ticker) if a.ticker else None
    return {
        "id": a.id,
        "ticker": a.ticker,
        "name": name or a.ticker,
        "message": a.message,
        "signal": a.signal,
        "score": a.score,
        "rec_shares": a.rec_shares,
        "rec_investment": a.rec_investment,
        "created_at": a.created_at.isoformat(),
        "is_read": a.is_read,
    }
