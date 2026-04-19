"""Model serialization helpers."""


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
    return {
        "id": a.id,
        "ticker": a.ticker,
        "message": a.message,
        "signal": a.signal,
        "score": a.score,
        "rec_shares": a.rec_shares,
        "rec_investment": a.rec_investment,
        "created_at": a.created_at.isoformat(),
        "is_read": a.is_read,
    }
