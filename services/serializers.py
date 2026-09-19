"""Model serialization helpers."""

from __future__ import annotations

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

    # PIPA §22 ⑥ gate state — see the two keys at the bottom of the dict.
    age_confirmed = bool(getattr(u, "age_confirmed", False))
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
        # behind ``/signup/oauth-finalize`` until the user has confirmed
        # they are 14+. True iff ``User.age_confirmed`` is False, i.e.
        # neither the self-declaration stamp (``age_confirmed_at``) nor a
        # legacy ``birthdate`` is present (new OAuth sign-up only — legacy
        # birthdate-era users never see the interstitial again).
        # The raw birthdate / timestamp values are intentionally **not**
        # returned — the frontend only needs the boolean gate.
        "age_confirmation_required": not age_confirmed,
        # Deprecated alias — same value as ``age_confirmation_required``.
        # Kept so a frontend bundle from the birthdate era keeps gating
        # correctly during the deploy window. Remove after 2026-10-19 once
        # every deployed frontend reads the new key.
        "birthdate_required": not age_confirmed,
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

    # F3-06 (2026-05-17): feedback_ticker_display recovery gate. When the
    # alert row was persisted with a raw-ticker title (resolver miss at
    # write-time — e.g. "005930.KS reached 52-week high"), but the name
    # resolver hits at read-time, substitute the readable label so the
    # API response carries "삼성전자 (005930.KS) reached 52-week high"
    # instead of leaking the bare ticker. Skip when name == ticker
    # (degenerate) or when neither the title nor the message references
    # the ticker (already correct or unrelated).
    if a.ticker and name and name.strip() and name.strip() != a.ticker.strip():
        replacement = f"{name} ({a.ticker})"
        # Only rewrite if the bare ticker actually appears AND the
        # "name (ticker)" form is NOT already present (avoid double-wrap).
        if title and a.ticker in title and replacement not in title:
            title = title.replace(a.ticker, replacement)
        if message and a.ticker in message and replacement not in message:
            message = message.replace(a.ticker, replacement)
    return {
        "id": a.id,
        "ticker": a.ticker,
        "name": name or a.ticker,
        # NotificationDropdown fields (2026-04-22)
        "kind": kind,
        "title": title,
        "body": getattr(a, "body", None),
        "link": getattr(a, "link", None),
        # F3-02 (2026-05-17): Alert.created_at / read_at are stored as
        # naive UTC (models/alert.py uses datetime.now(timezone.utc)
        # .replace(tzinfo=None)). Without an explicit timezone suffix,
        # ``new Date("2026-05-17T10:30:00")`` in the frontend parses as
        # local time → KST users saw alert times off by 9 hours. Append
        # the "Z" suffix so consumers parse UTC correctly. Defense in
        # depth lives in frontend/src/lib/relative-time.ts.
        "read_at": (a.read_at.isoformat() + "Z") if getattr(a, "read_at", None) else None,
        # Legacy fields
        "message": message,
        "signal": a.signal,
        "score": a.score,
        "rec_shares": a.rec_shares,
        "rec_investment": a.rec_investment,
        "created_at": (a.created_at.isoformat() + "Z") if a.created_at else None,
        "is_read": a.is_read,
    }
