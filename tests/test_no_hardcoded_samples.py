"""Regression guard: no hardcoded sample tickers or money in Jinja template defaults.

Background
----------
2026-04-24 field-mapping audit flagged 99/351 Jinja `default(...)` calls as
ORPHAN+MISMATCH — the admin preview was fed from `sample_data.py` (AAPL, NVDA,
$94.9B, etc.), but when a real user's artifact pipeline failed to populate a
field, the template `default(...)` fallback leaked those same sample values
into the rendered PDF/email. A Samsung-only user could receive a Brag Card
narrating their "NVDA +$1,240 on April 3" trade.

2026-04-24 P0-1 rework — the original regex only covered the **scalar** form
(`default('AAPL')`), missing three list-embedded regressions surfaced by a
second audit pass: `brag_card.top_lots`, `dd_checklist.peer_bars`,
`weekly_memo.what_to_watch`. Full sweep uncovered ~20 additional list-embedded
defaults across 9 templates. This file now checks both forms.

This pytest mirrors `.github/workflows/legal-guard.yml` so the same check
fires in local/CI unit runs, catches regressions pre-push, and documents the
forbidden patterns for future authors.

Scope
-----
* Only scans `services/artifacts/templates/**.html` — the generated-artifact
  pipeline. Admin preview via `sample_data.py` still supplies real sample data.
* Blocks (scalar form):
    - `default('AAPL')`, `default('NVDA')`, `default('005930.KS')` — any
      2-6 uppercase tickers, optionally with `.KS`/`.KQ` suffix.
    - `default('$127,450')`, `default('$94.9B · Q4 FY25')` — any absolute
      USD fallback.
* Blocks (list-embedded form):
    - `default([{'t':'AAPL', 'v':100}, ...])` — ticker literal in a dict.
    - `default(['NVDA', 'MSFT'])` — ticker literal in a plain list.
    - `default([{'detail':'AAPL · Tue'}])` — ticker inside a longer prose
      string (the weekly_memo regression).
    - `default([{'amt':'$1,240'}])` — $money inside any literal.
* Permitted:
    - `default(none)` / `default('')` / `default(0)` / `default([])` — empty.
    - `default('Megacap Tech')` / `default('Source Serif 4 · Geist')` — style
      copy, not user data.
    - `default('April 2026')` / `default('Q1 2026')` — period labels on
      portfolio-level artifacts (risk_board, kpi_dashboard, quarterly_self_report,
      portfolio_segment). These are tracked as D-grade follow-ups, not P0.
    - Credit-rating grades (`AAA`/`BBB`/`CCC`), macro labels (`DXY`/`VIX`),
      form types (`DART`), bond categories (`TIPS`) — not equity tickers.

Aligned rule: CLAUDE.md — "기존 백엔드 서비스 파일 수정 금지" / 자본시장법 §178
허위표시 방어선.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "services" / "artifacts" / "templates"

# Jinja: `{{ field | default('AAPL') }}` — 2-6 upper letters with optional
# .KS / .KQ / .HK market suffix.  Allows single-quote OR double-quote.
TICKER_DEFAULT_RE = re.compile(
    r"""default\(\s*['"]([A-Z]{2,6}(?:\.[A-Z]{2,3})?)['"]\s*\)"""
)

# Jinja: `{{ field | default('$127,450') }}` — any absolute dollar figure.
MONEY_DEFAULT_RE = re.compile(r"""default\(\s*['"]\$[0-9]""")


def _iter_template_files() -> list[Path]:
    assert TEMPLATES_DIR.is_dir(), (
        f"templates dir missing: {TEMPLATES_DIR}"
    )
    return sorted(TEMPLATES_DIR.rglob("*.html"))


class TestNoHardcodedTickerInDefaults:
    """`{{ ticker | default('AAPL') }}` would cross-user-leak sample data."""

    def test_no_ticker_symbol_in_template_defaults(self) -> None:
        offenders: list[str] = []
        for path in _iter_template_files():
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                m = TICKER_DEFAULT_RE.search(line)
                if not m:
                    continue
                # Skip false positives: template-literal non-ticker constants
                # deliberately expressed as uppercase (e.g. CSS tokens inside
                # a string).  We scope the check to `default(...)` only, so
                # any 2-6-upper match here is genuinely a ticker fallback.
                symbol = m.group(1)
                rel = path.relative_to(REPO_ROOT)
                offenders.append(f"{rel}:{lineno}: default('{symbol}')")
        assert not offenders, (
            "Hardcoded sample ticker in template default() — real users would "
            "see a stranger's symbol in their artifact. Replace with "
            "default(none) and wrap the surrounding section in {% if field %}"
            "...{% endif %}.\n\n"
            + "\n".join(offenders)
        )


class TestNoHardcodedMoneyInDefaults:
    """`default('$127,450')` bleeds a fictitious NAV into real users' KPI pages."""

    def test_no_dollar_amount_in_template_defaults(self) -> None:
        offenders: list[str] = []
        for path in _iter_template_files():
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if MONEY_DEFAULT_RE.search(line):
                    rel = path.relative_to(REPO_ROOT)
                    offenders.append(f"{rel}:{lineno}: {line.strip()}")
        assert not offenders, (
            "Hardcoded money figure in template default() — fictitious sample "
            "would render for any real user whose field resolution fell "
            "through. Replace with default(none) and gate the surrounding "
            "block on the real value.\n\n"
            + "\n".join(offenders)
        )


class TestTemplatesDirectoryShape:
    """Defensive: ensure the check actually scanned something."""

    def test_templates_directory_populated(self) -> None:
        files = _iter_template_files()
        assert len(files) >= 10, (
            f"templates directory unexpectedly sparse: {len(files)} files "
            f"found under {TEMPLATES_DIR}"
        )


# ---------------------------------------------------------------------------
# List-embedded defaults — the P0-1 regression surface
# ---------------------------------------------------------------------------

# Equity tickers we actively guard against leaking. Pre-seeded with every
# ticker found in the pre-rework templates + common S&P index proxies.
# Credit-rating grades (AAA/BBB/CCC), macro labels (DXY/VIX/MOVE), bond
# categories (TIPS), and form names (DART) are deliberately excluded — those
# are not equity tickers and legitimately appear as style labels.
_FORBIDDEN_TICKERS: frozenset[str] = frozenset(
    {
        "AAPL", "MSFT", "GOOG", "GOOGL", "META", "NVDA", "AVGO", "TSLA",
        "AMZN", "NFLX", "BRK", "BRK.B", "HD", "UNH", "JPM", "KO", "PG",
        "COST", "LLY", "ORCL", "CRM", "MCD", "JNJ", "VZ", "XOM", "BABA",
        "INTC", "QCOM", "NKE",
        # Korean numeric tickers (KRX codes) — match both bare and suffixed.
        "005930", "005930.KS", "000660", "000660.KS",
        # Benchmark/index ETF proxies that should come from config, not a
        # template literal.
        "SPY", "QQQ", "TLT", "AGG",
    }
)

# Finds any default([...]) block and captures the full bracket-balanced body.
# We parse these manually (not via regex) because nested brackets and
# multi-line lists are common.
_LIST_DEFAULT_START_RE = re.compile(r"default\(\s*\[")

# Inside a block, look for any candidate token that could be a ticker.
# Word-boundary match — catches both quoted (`'AAPL'`) and prose-embedded
# (`'AAPL · Tue after the close'`) occurrences.
_TOKEN_RE = re.compile(r"\b([A-Z]{2,6}(?:\.[A-Z]{2,3})?)\b")

# Korean tickers start with a digit, so \b won't precede them. Match
# separately.
_KR_TICKER_RE = re.compile(r"\b(005930|000660)(\.KS|\.KQ)?\b")

# Absolute dollar figures ($1, $1,240, $127,450.00, etc.).
_EMBEDDED_MONEY_RE = re.compile(r"\$[\d,]+\.?\d*")


def _extract_list_default_blocks(text: str) -> list[tuple[int, str]]:
    """Return (line_number, block_text) for every `default([...])` in `text`.

    Walks the file character-by-character to balance nested brackets — a
    plain regex cannot match nested lists reliably across multiple lines.
    """
    blocks: list[tuple[int, str]] = []
    for match in _LIST_DEFAULT_START_RE.finditer(text):
        start = match.start()
        depth = 0
        idx = match.end() - 1  # points at the opening `[`
        while idx < len(text):
            ch = text[idx]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    break
            idx += 1
        else:
            # Unbalanced — skip rather than crash.
            continue
        line_no = text.count("\n", 0, start) + 1
        blocks.append((line_no, text[start : idx + 1]))
    return blocks


class TestNoListEmbeddedTickers:
    """`default([{'t':'AAPL', ...}])` leaks sample tickers the same way the
    scalar form does. This test catches the P0-1 regression where the original
    regex only covered the scalar form and let three list-embedded defaults
    slip through (brag_card.top_lots, dd_checklist.peer_bars,
    weekly_memo.what_to_watch).
    """

    def test_no_ticker_inside_list_default_block(self) -> None:
        offenders: list[str] = []
        for path in _iter_template_files():
            text = path.read_text(encoding="utf-8")
            for line_no, block in _extract_list_default_blocks(text):
                found_equities = {
                    tok
                    for tok in _TOKEN_RE.findall(block)
                    if tok in _FORBIDDEN_TICKERS
                }
                found_kr = _KR_TICKER_RE.findall(block)
                if found_equities or found_kr:
                    rel = path.relative_to(REPO_ROOT)
                    hits = sorted(found_equities) + [
                        "".join(t) for t in found_kr
                    ]
                    offenders.append(f"{rel}:{line_no}: tickers={hits[:6]}")
        assert not offenders, (
            "Ticker literal inside a template `default([...])` list — the "
            "same cross-user-leak hazard as a scalar default('AAPL'), just "
            "wrapped in a list. Replace with `default([])` and wrap the "
            "consumer of the variable in `{% if field %}...{% else %}"
            "<neutral fallback>{% endif %}`.\n\n"
            + "\n".join(offenders)
        )

    def test_no_money_inside_list_default_block(self) -> None:
        offenders: list[str] = []
        for path in _iter_template_files():
            text = path.read_text(encoding="utf-8")
            for line_no, block in _extract_list_default_blocks(text):
                hits = _EMBEDDED_MONEY_RE.findall(block)
                if hits:
                    rel = path.relative_to(REPO_ROOT)
                    offenders.append(f"{rel}:{line_no}: money={hits[:4]}")
        assert not offenders, (
            "Absolute dollar figure inside a template `default([...])` list. "
            "A real user would see this sample figure whenever the service "
            "fails to populate the field. Replace with `default([])` and "
            "gate rendering on the real data.\n\n"
            + "\n".join(offenders)
        )


# ---------------------------------------------------------------------------
# Wave 5 — data-source provenance in list defaults
# ---------------------------------------------------------------------------
#
# Why this exists (the legal exposure)
# ------------------------------------
# The Weekly Memo / Brag Card / Burn Rate / Self Audit colophons advertise
# the "Data sources" used to build the artifact. If the service layer fails
# to populate `data_sources` and the template's `default([...])` kicks in,
# a real user sees a stranger's broker list. A Samsung-only KR investor
# receiving a PDF that claims "Alpaca" as a data source is a material
# misrepresentation under 표시광고법 §3 (기만표시).
#
# Fix: templates now use `default([])` and the service layer populates
# `data_sources` from the user's real `BrokerConnection` rows via
# `services.artifacts.data_source_resolver.resolve_user_data_sources`.
# This test guards against the regression path — anyone re-introducing a
# hardcoded broker/provider name inside `default([...])` fails CI.
#
# Why these labels are intentionally allowed (D-grade retained)
# -------------------------------------------------------------
# The audit also flagged several `default([...])` lists on D-grade:
#   * `months_labels` / `hold_bins` — chart axis labels ("May", "Jun",
#     "< 1w", "1-4w") that are not user-provided data.
#   * `segment_corr_labels` — correlation bucket labels ("Low", "Mid",
#     "High") that are rendering tokens, not claims.
#   * `hero_headline` carry-variants — literary UI copy, not a data
#     claim. Strings like "Q1 Review" or "March check-in" do not
#     mis-state the user's broker connections.
# Those are explicitly not in `_FORBIDDEN_SOURCE_LABELS` below because
# they are never mistaken for a data-source claim in context.

_FORBIDDEN_SOURCE_LABELS: frozenset[str] = frozenset(
    {
        # Brokers — explicit Capital-Markets-Act exposure if falsely claimed.
        "Alpaca",
        "KIS",
        "Kiwoom",
        # Generic provenance labels that imply a connection PivoxQuant does
        # not actually have with every user's account.
        "Broker statements",
        "Bank statements",
        "Credit card statements",
        "Manual ledger",
        "Budget app export",
        "Observation journal",
        "Rebalance log",
    }
)

# Wave 6 — template-wide broker-name blocklist. Catches both quoted
# string literals *and* raw HTML text that name a broker/data provider.
# A prose-embedded `<div>Alpaca Broker API</div>` is the same legal
# exposure as a dict literal `{'broker': 'Alpaca'}` — both ship to a
# user who is not actually connected.
#
# Intentionally *excludes* public aggregators that are not user
# credentials — FMP v4, SEC EDGAR, FRED, NASDAQ, CME, FactSet, MSCI,
# Bloomberg, ECB, BOJ. Those are always-true facts about the analysis
# pipeline, not claims about the user's account.
_FORBIDDEN_BROKER_TOKENS: frozenset[str] = frozenset(
    {
        "Alpaca",
        "KIS",
        "Kiwoom",
        "키움",
        "알파카",
        "Polygon",
        "E-TRADE",
        "Charles Schwab",
    }
)

# Strip Jinja comments `{# ... #}` before scanning so audit-note
# comments that *document* the removed strings don't retrigger the
# guard. re.DOTALL lets `.` match newlines for multi-line comments.
_JINJA_COMMENT_RE = re.compile(r"\{#.*?#\}", flags=re.DOTALL)

# Any single- or double-quoted string literal (same-line). We don't
# attempt multi-line strings because template literals are one line.
_ANY_QUOTED_LITERAL_RE = re.compile(r"""(['"])([^'"]*?)\1""")

# Any HTML raw-text run between two tags on the same line.
_ANY_RAW_TEXT_RE = re.compile(r">([^<>]+)<")

# Captures the inner content of a quoted string inside a default([...]).
# We extract literals explicitly (rather than substring-matching the
# whole block) so style labels like "AlpacaSans" in a font stack —
# should anyone ever add one — don't produce a false positive.
_QUOTED_LITERAL_RE = re.compile(r"'([^']+)'")


class TestNoHardcodedDataSources:
    """`default(['Alpaca', 'KIS', ...])` claims broker/data provenance
    for every user whose service layer fails to populate `data_sources`.

    A real user connected only to Samsung (KIS) must never receive a PDF
    that names "Alpaca" in the colophon — that is a §3 표시광고법
    misrepresentation. Templates must use `default([])` and rely on the
    service layer's `resolve_user_data_sources(user_id)` call.

    Wave 6 upgrade — this test now uses *substring* matching. The Wave-5
    version required the literal to be the entire quoted string, which
    let `'Alpaca · Paper account statements'` and `'CBOE via Alpaca.'`
    slip through as "prose-embedded" regressions. Substring match closes
    that blind spot.
    """

    def test_no_broker_or_provider_inside_list_default_block(self) -> None:
        offenders: list[str] = []
        for path in _iter_template_files():
            text = path.read_text(encoding="utf-8")
            for line_no, block in _extract_list_default_blocks(text):
                quoted = _QUOTED_LITERAL_RE.findall(block)
                hits: list[str] = []
                for q in quoted:
                    # Wave 6 — substring match. Any broker/provider label
                    # appearing *anywhere* inside a quoted literal counts
                    # as a provenance claim, even when wrapped in prose.
                    for label in _FORBIDDEN_SOURCE_LABELS:
                        if label in q:
                            hits.append(f"{label} (in '{q}')")
                            break
                if hits:
                    rel = path.relative_to(REPO_ROOT)
                    offenders.append(
                        f"{rel}:{line_no}: data_source_labels={hits[:6]}"
                    )
        assert not offenders, (
            "Broker / data-source provenance literal inside a template "
            "`default([...])` list — including prose-embedded forms. If "
            "the service layer fails to populate `data_sources`, this "
            "fallback would ship to a real user — claiming a data source "
            "that user isn't actually connected to. That's 표시광고법 §3 "
            "misrepresentation. Replace with `default([])` and populate "
            "`data_sources` at the service layer via "
            "`resolve_user_data_sources(user_id)` or "
            "`resolve_user_data_lineage(user_id)`.\n\n"
            + "\n".join(offenders)
        )


# ---------------------------------------------------------------------------
# Wave 6 — template-wide broker-name scan (beyond `default([...])` blocks)
# ---------------------------------------------------------------------------
#
# The Wave-5 guards only scan inside `default([...])` blocks. Wave-6 audit
# found six additional regressions where the broker name was hardcoded as
# raw HTML text *outside* any default() call — e.g. `<div>Alpaca Broker
# API (read-only).</div>` in the monthly_finance colophon. Those strings
# always render, regardless of whether the service populates a context
# variable. This test scans every quoted string literal and every
# between-tags raw text run across all templates for a broker name.

def _strip_jinja_comments(text: str) -> str:
    """Replace `{# ... #}` spans with newlines so line numbers are preserved.

    The Wave-6 fix added a handful of comments documenting the removed
    strings. Those comments legitimately mention broker names; the test
    must scan the rendered output only.
    """
    def replace(m: re.Match[str]) -> str:
        # Preserve newlines so downstream line numbering stays accurate.
        return "\n" * m.group(0).count("\n")
    return _JINJA_COMMENT_RE.sub(replace, text)


class TestNoBrokerNameInTemplates:
    """Broker-name substring guard — quoted literals + raw HTML text.

    This is the Wave-6 blind-spot closure. The Wave-5 test only checked
    the contents of `default([...])` blocks via equality match. Six
    templates had broker names hardcoded *outside* any default call
    (direct `<div>Alpaca …</div>`) or *inside* a longer prose string
    (`'Alpaca · Paper account statements'`). Both forms ship the string
    to every real user. Substring match over the full template catches
    both.

    Allowed (whitelisted by construction):
    * Public aggregators — FMP v4, SEC EDGAR, FRED, NASDAQ, CME,
      FactSet, MSCI, Bloomberg, ECB, BOJ — are always-true facts about
      the analysis pipeline, not claims about user credentials.
    * `CBOE` — the public exchange name. CBOE appears as an index
      reference (`CBOE Put-Call Ratio`) in persona macros; it's not a
      broker the user may or may not be connected to. When `CBOE` was
      coupled with a broker name (`CBOE via Alpaca`) the Alpaca half
      triggers the guard, which is the correct behaviour.
    * `IEX` — data-feed infrastructure label. Historically written as
      "IEX consolidated tape" for methodology disclosure. Substring
      guard does NOT include IEX because it would flag every mention
      of the consolidated tape. Wave 6 rewrites did remove every prior
      use that paired IEX with Alpaca; if IEX returns alone in a
      methodology paragraph, that is not a broker-connection claim.
    """

    def test_no_broker_name_in_template_quoted_literals(self) -> None:
        offenders: list[str] = []
        for path in _iter_template_files():
            text = _strip_jinja_comments(path.read_text(encoding="utf-8"))
            for lineno, line in enumerate(text.splitlines(), start=1):
                for match in _ANY_QUOTED_LITERAL_RE.finditer(line):
                    literal = match.group(2)
                    for token in _FORBIDDEN_BROKER_TOKENS:
                        if token in literal:
                            rel = path.relative_to(REPO_ROOT)
                            offenders.append(
                                f"{rel}:{lineno}: broker={token!r} in {literal!r}"
                            )
                            break
        assert not offenders, (
            "Broker-name substring inside a template quoted string — a "
            "service-layer resolution failure would ship this literal to a "
            "real user, claiming a provider they are not actually connected "
            "to (표시광고법 §3 기만표시). Rewrite to inject the value from "
            "`resolve_user_data_lineage(user_id)` at the service layer and "
            "gate the surrounding section on `{% if lineage %}`.\n\n"
            + "\n".join(offenders)
        )

    def test_no_broker_name_in_template_raw_text(self) -> None:
        offenders: list[str] = []
        for path in _iter_template_files():
            text = _strip_jinja_comments(path.read_text(encoding="utf-8"))
            for lineno, line in enumerate(text.splitlines(), start=1):
                for match in _ANY_RAW_TEXT_RE.finditer(line):
                    segment = match.group(1)
                    for token in _FORBIDDEN_BROKER_TOKENS:
                        if token in segment:
                            rel = path.relative_to(REPO_ROOT)
                            offenders.append(
                                f"{rel}:{lineno}: broker={token!r} in <…>{segment!r}<…>"
                            )
                            break
        assert not offenders, (
            "Broker-name substring inside HTML raw text between template "
            "tags — this renders unconditionally for every user regardless "
            "of service-layer population, falsely claiming a broker "
            "connection (표시광고법 §3 기만표시). Move the string into a "
            "Jinja conditional gated on a service-provided scalar (e.g. "
            "`{% if positions_source %}{{ positions_source }}{% endif %}`) "
            "and populate it only when the user has a real connection.\n\n"
            + "\n".join(offenders)
        )
