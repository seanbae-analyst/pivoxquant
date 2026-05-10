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
    # Resolve tier once. ``effective_tier`` is the property that applies the
    # DEV_FOUNDING_EMAILS / DEV_PREMIUM_EMAILS env-var overrides (see
    # models/user.py) and otherwise returns the stored ``subscription_tier``
    # column. The DB ``subscription_status`` column only flips to "active"
    # via Stripe webhooks (routes/billing.py), so an env-override user shows
    # up here with tier="founding_lifetime" / "premium" but status="inactive"
    # — which the frontend (ui/profile-dropdown.tsx) treats as a downgrade
    # back to FREE. Surface the env-derived entitlement explicitly:
    #   * ``effective_tier``    — same value as ``subscription_tier`` for
    #                             back-compat with existing consumers.
    #   * ``effective_status``  — "active" when the env override grants a
    #                             paid tier, else the raw DB status. The
    #                             frontend can read whichever it prefers;
    #                             ``subscription_status`` keeps its raw
    #                             column meaning.
    raw_tier = getattr(u, "subscription_tier", "free") or "free"
    eff_tier = getattr(u, "effective_tier", None) or raw_tier
    raw_status = getattr(u, "subscription_status", "inactive") or "inactive"
    # An env-override grant promoted ``raw_tier`` to ``eff_tier``. Treat the
    # entitlement as active so downstream gates don't fall back to FREE.
    promoted_by_env = (eff_tier != raw_tier) and eff_tier in (
        "pro", "premium", "premium_plus", "founding_lifetime",
    )
    eff_status = "active" if promoted_by_env else raw_status

    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "available_capital": u.available_capital,
        "available_capital_krw": getattr(u, "available_capital_krw", 0.0) or 0.0,
        "risk_profile": getattr(u, "risk_profile", "balanced"),
        "profile_changes_left": getattr(u, "profile_changes_left", 3),
        # ``subscription_tier`` continues to expose ``effective_tier`` so
        # existing tier-gate logic (frontend/src/components/ui/tier-gate.tsx)
        # keeps working with no client change.
        "subscription_tier": eff_tier,
        # New, additive field — explicit alias of the same value. Lets the
        # frontend pick whichever name it prefers without ambiguity.
        "effective_tier": eff_tier,
        # ``subscription_status`` here is the *effective* status: env-override
        # users now report "active" instead of the stored "inactive". Raw DB
        # value remains accessible via ``raw_subscription_status`` below for
        # callers that need it (e.g. billing reconciliation).
        "subscription_status": eff_status,
        "raw_subscription_status": raw_status,
        "onboarding_completed": getattr(u, "onboarding_completed", False),
        "avatar_url": getattr(u, "avatar_url", None),
        "oauth_provider": getattr(u, "oauth_provider", None),
        # PIPA §22 ⑥ — frontend uses this to gate authenticated routes
        # behind ``/signup/oauth-finalize`` until the user supplies a
        # valid birthdate. ``birthdate_required`` is True iff the column
        # is NULL (new OAuth sign-up *or* legacy pre-migration-031 row).
        # The raw birthdate value itself is intentionally **not** returned —
        # the frontend never needs the value, only the boolean gate.
        "birthdate_required": getattr(u, "birthdate", None) is None,
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


def _strip_signal_bracket_prefix(text: str | None) -> str | None:
    """Defensive scrub: drop the legacy ``[POSITIVE]`` / ``[NEGATIVE]`` /
    ``[NEUTRAL]`` bracket prefix that older alert_service rows persisted
    into ``Alert.message`` / ``Alert.title``.

    The structured ``signal`` field is what the UI badges off, so the
    in-string enum was always redundant. Older rows still carry it; this
    serializer strip keeps the API response clean during the rollout
    window without touching the DB.
    """
    if not text:
        return text
    for prefix in ("[POSITIVE] ", "[NEGATIVE] ", "[NEUTRAL] "):
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


def serialize_alert(a) -> dict:
    # Resolve once per alert. Cache-backed via services.name_resolver so
    # a list render costs ~O(unique tickers) DB hits at worst.
    name = _resolve_display_name(a.ticker) if a.ticker else None
    kind = getattr(a, "kind", None)
    raw_msg = a.message or ""
    raw_title = getattr(a, "title", None) or raw_msg
    title = _strip_signal_bracket_prefix(raw_title)
    message = _strip_signal_bracket_prefix(raw_msg)
    return {
        "id": a.id,
        "ticker": a.ticker,
        "name": name or a.ticker,
        # NotificationDropdown fields (2026-04-22)
        "kind": kind,
        "title": title,
        "body": getattr(a, "body", None),
        "link": getattr(a, "link", None),
        "read_at": a.read_at.isoformat() if getattr(a, "read_at", None) else None,
        # Legacy fields
        "message": message,
        "signal": a.signal,
        "score": a.score,
        "rec_shares": a.rec_shares,
        "rec_investment": a.rec_investment,
        "created_at": a.created_at.isoformat(),
        "is_read": a.is_read,
    }
