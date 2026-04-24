"""Resolve the *actual* data sources for a user — never a hardcoded fallback.

Why this exists
---------------
Wave 4 audit (2026-04-24) found four artifact templates that carried
hardcoded `default(['Alpaca', 'KIS', ...])` lists in the "Data sources"
colophon. When a user's service failed to populate `data_sources`, the
Jinja `default(...)` would leak a stranger's data provenance into their
PDF — e.g. a Samsung-only user receiving a report that claims `'Alpaca'`
as a source. Under 표시광고법 §3 (허위표시) that is material misstatement
risk, and self-reporting to the user they're connected to Alpaca when
they never were is both legally dangerous and trust-destroying.

Fix: each of the four services now populates `data_sources` from the
user's real `BrokerConnection` rows plus the free/public system sources
(FMP v4, SEC EDGAR, FRED). The templates render `{% if data_sources %}`
and show a neutral fallback message when the list is empty, so there
is no path for a hardcoded provenance string to reach a real user.

Scope
-----
- System sources (FMP v4, SEC EDGAR, FRED) are public APIs PivoxQuant
  *always* uses to build every artifact. They are truthful to list on
  every report regardless of broker linkage.
- Broker sources (Alpaca, KIS) are listed ONLY when an active
  `BrokerConnection` row exists with a non-empty credential bundle.
  Legacy pre-2026-04-20 Alpaca rows without encrypted credentials are
  treated as disconnected — same rule as `routes/broker_oauth.py`
  `_alpaca_connected()`.
- Observation journal is listed ONLY when the service explicitly
  signals `include_journal=True` — the weekly-memo pipeline does not,
  but the self-audit pipeline (which reads the user's own trade notes)
  does.
- Manual ledger (burn_rate) is listed ONLY when explicitly requested
  (`include_manual_ledger=True`) — the burn-rate service uses it as
  its default narration ("사용자 수기 원장") but no other artifact does.

None of these helpers raise. Any DB failure falls through to a safe
subset — the template-side `{% if %}` guard then renders the neutral
"Data sources not specified" sentence, which is always legally truthful
(you can't misstate something you refuse to claim).
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ── system sources — always truthful for every PivoxQuant artifact ──────────
_SYSTEM_SOURCES: tuple[str, ...] = ("FMP v4", "SEC EDGAR", "FRED")


# ── structured lineage rows (Wave 6) ────────────────────────────────────────
# Each system source ships with a fixed description + coverage note that
# survives any user context. Broker rows are added only when the user's
# connection is present AND credential-bearing — same gating as
# `resolve_user_data_sources`.
_SYSTEM_LINEAGE: tuple[dict[str, str], ...] = (
    {
        "source":      "FMP v4",
        "description": "Financial Modeling Prep · fundamentals + quotes.",
        "coverage":    "Consensus EPS, quote snapshots, corporate actions.",
    },
    {
        "source":      "SEC EDGAR",
        "description": "Public filings · 10-K / 10-Q / 8-K.",
        "coverage":    "Historical EPS, filings calendar, issuer disclosures.",
    },
    {
        "source":      "FRED",
        "description": "Federal Reserve Economic Data.",
        "coverage":    "3-Month T-Bill (DGS3MO) for risk-free rate.",
    },
)


# ── per-broker connectivity checks ──────────────────────────────────────────

def _has_active_alpaca(user_id: int) -> bool:
    """True when the user has a real, credential-bearing Alpaca row.

    Matches the `_alpaca_connected` whitelist in routes/broker_oauth.py so
    the legal/broker layer and the artifact layer agree on "connected".
    Returns False on any exception — a broken DB session must not cause
    us to *invent* a provenance claim.
    """
    try:
        from models import BrokerConnection  # late import → test isolation
        conn = BrokerConnection.query.filter_by(
            user_id=user_id, broker="alpaca"
        ).first()
    except Exception as exc:
        logger.debug("alpaca connection check failed for user %s: %s",
                     user_id, exc)
        return False
    if not conn:
        return False
    return bool(
        conn.is_active
        and conn.encrypted_app_key
        and conn.encrypted_app_secret
    )


def _has_active_kis(user_id: int) -> bool:
    """True when the user has an active KIS connection.

    KIS is read-only (주문 disabled) — but "read-only data source" is
    still a truthful data-source claim. Parity with the broker_oauth
    `kis_status` endpoint: `is_active` alone is sufficient because KIS
    rows without credentials never reach `is_active=True` in the first
    place (see `routes/broker_oauth.py::kis_status`).
    """
    try:
        from models import BrokerConnection
        conn = BrokerConnection.query.filter_by(
            user_id=user_id, broker="kis"
        ).first()
    except Exception as exc:
        logger.debug("kis connection check failed for user %s: %s",
                     user_id, exc)
        return False
    if not conn:
        return False
    return bool(conn.is_active)


# ── public API ──────────────────────────────────────────────────────────────

def resolve_user_data_sources(
    user_id: Optional[int],
    *,
    include_system: bool = True,
    include_journal: bool = False,
    include_manual_ledger: bool = False,
) -> list[str]:
    """Return the truthful list of data sources for this user's artifact.

    Ordering is stable: [system sources] → [broker sources] → [user
    sources]. This matches the typographic hierarchy readers expect in
    the colophon (infrastructure → integrations → user input).

    Parameters
    ----------
    user_id
        The user whose artifact is being rendered. `None` means "no
        user context" — returns system sources only.
    include_system
        When True (default) prepends FMP v4 · SEC EDGAR · FRED. Set
        False only when the artifact is produced entirely from user
        input (e.g. a pure journal export) — currently no caller does.
    include_journal
        When True, adds "Observation journal" *if* the caller believes
        the artifact reflects user-entered notes. The journal is only
        truthful for the self-audit pipeline today.
    include_manual_ledger
        When True, adds "Manual ledger" *if* the artifact is built from
        the user's hand-entered entries. Only the burn_rate service
        uses this.

    Returns
    -------
    list[str]
        Possibly empty. An empty list is the explicit "we do not know"
        signal — templates must guard on `{% if data_sources %}` and
        render a neutral fallback string rather than claim any source.
    """
    sources: list[str] = []
    if include_system:
        sources.extend(_SYSTEM_SOURCES)

    if user_id is not None:
        if _has_active_alpaca(user_id):
            sources.append("Alpaca")
        if _has_active_kis(user_id):
            sources.append("KIS")

    if include_journal:
        sources.append("Observation journal")
    if include_manual_ledger:
        sources.append("Manual ledger")

    return sources


def resolve_user_data_lineage(
    user_id: Optional[int],
    *,
    include_system: bool = True,
    include_journal: bool = False,
    include_manual_ledger: bool = False,
) -> list[dict[str, str]]:
    """Return a structured lineage list for the colophon of Wave-6 templates.

    Each element is `{'source': str, 'description': str, 'coverage': str}`
    — never a bare broker-name string. The template iterates the list and
    renders the description + coverage under the ``source`` heading; when
    the list is empty the template falls back to a neutral "Data sources
    not specified" line.

    Why this exists
    ---------------
    Wave 5 fixed colophons that used ``default([bare broker strings])``.
    Wave 6 audit then found six templates with **prose-embedded** broker
    names inside richer ``{'key', 'value'|'note'}`` dict defaults (e.g.
    ``'Alpaca · Paper account statements'``). The substring escapes the
    Wave-5 quoted-literal guard and still ships Alpaca to a Samsung-only
    user whenever the service fails to populate ``data_sources``.

    Fix pattern: templates now reference structured lineage rows and
    gate rendering on ``{% if lineage %}``. The service layer populates
    these rows *only* when they are true of the user calling the
    endpoint.

    Parameters
    ----------
    user_id
        The user whose artifact is being rendered. ``None`` returns only
        system rows (or an empty list when ``include_system`` is False).
    include_system
        When True (default) prepends FMP v4 / SEC EDGAR / FRED rows —
        these are always truthful for every PivoxQuant artifact.
    include_journal
        When True, appends the observation-journal row when the artifact
        reflects the user's own notes (self-audit, quarterly_self_report).
    include_manual_ledger
        When True, appends a manual-ledger row for artifacts that derive
        from hand-entered entries (burn_rate today).

    Returns
    -------
    list[dict[str, str]]
        Possibly empty. Each row has ``source``, ``description``,
        ``coverage`` keys. The template must guard on ``{% if lineage %}``
        so an empty return never renders a fabricated provenance claim.
    """
    rows: list[dict[str, str]] = []
    if include_system:
        rows.extend({**row} for row in _SYSTEM_LINEAGE)

    if user_id is not None:
        if _has_active_alpaca(user_id):
            rows.append({
                "source":      "Alpaca",
                "description": "Your connected Alpaca paper account.",
                "coverage":    "Positions, trade history, FX observation.",
            })
        if _has_active_kis(user_id):
            rows.append({
                "source":      "KIS",
                "description": "Your connected 한국투자증권 account (read-only).",
                "coverage":    "KR positions, KRW cash balance.",
            })

    if include_journal:
        rows.append({
            "source":      "Observation journal",
            "description": "Your own trade notes and reflective entries.",
            "coverage":    "Thesis, exit reason, lessons recorded per lot.",
        })
    if include_manual_ledger:
        rows.append({
            "source":      "Manual ledger",
            "description": "Hand-entered cashflow entries.",
            "coverage":    "Burn-rate, expense, and runway inputs.",
        })

    return rows


__all__ = [
    "resolve_user_data_sources",
    "resolve_user_data_lineage",
]
