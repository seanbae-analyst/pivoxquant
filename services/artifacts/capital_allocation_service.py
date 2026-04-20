"""Capital Allocation Calculator — Premium on-demand What-If calculator.

Legal posture (2026-04-19 redesign)
-----------------------------------
This calculator **does not recommend** any allocation. It is a pure
*what-if* computation surface:

  1. User supplies a total `cash_amount`.
  2. User supplies up to 4 scenarios, each a concrete allocation the user
     themselves is considering (diversify existing, new ticker, hold cash,
     dividend ETF).
  3. We compute, for each scenario, *historical* 5y CAGR / volatility /
     max drawdown / Sharpe — all descriptive statistics of the past.

We never rank, compare, rate, or say which is "better". The PDF renders
the four scenarios side-by-side on a single page with identical
formatting; best/worst ordering is not surfaced.

Data source
-----------
- `services.container.fetcher.get_price_history(ticker, period="5y")`
  for every ticker referenced. Failures collapse silently — the scenario
  is kept in the output with `return_cagr=None` and a short note.
- USD cash scenario uses 0 % return, 0 % vol, 0 % dd by definition.

Cadence
-------
- On-demand: `POST /api/artifacts/capital-allocation/calculate` from the
  frontend fires this synchronously for the caller (returns a `calc_id`
  that maps to the persisted Artifact row).
- Quarterly (month=1,4,7,10 day=14) 09:00 KST: sends an **email reminder
  only** with a CTA linking back to the in-app calculator. We never run
  the calculator itself on the scheduler — see `send_quarterly_reminder`.
"""
from __future__ import annotations

import logging
import math
import os
import re
import secrets
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from extensions import db
from models import Artifact, Position, User

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_STORAGE_DIR = (
    Path(__file__).resolve().parents[2] / "artifacts" / "capital_allocation"
)
_PAID_TIERS = frozenset({"premium", "elite"})

# Known dividend / income ETFs — whitelist the user can pick from.
# Suffixes `.KS` for KOSPI, plain for US.
_DIVIDEND_ETF_WHITELIST: dict[str, str] = {
    "SCHD":       "Schwab U.S. Dividend Equity ETF",
    "VYM":        "Vanguard High Dividend Yield ETF",
    "DVY":        "iShares Select Dividend ETF",
    "HDV":        "iShares Core High Dividend ETF",
    "279530.KS":  "KODEX 배당성장",
    "211560.KS":  "TIGER 배당성장",
    "325020.KS":  "KODEX 미국배당다우존스",  # SCHD 미러
}

_MAX_SCENARIOS = 4
_MAX_CASH = 10_000_000_000.0   # sanity ceiling (10 B in caller's ccy)
_MIN_CASH = 0.0
_TRADING_DAYS = 252


# ── scenario data types ──────────────────────────────────────────────────────

@dataclass
class ScenarioInput:
    """Raw user input for one of the 4 what-if scenarios.

    `type` — one of:
        - "diversify_existing"  params: {}           (spread evenly across
                                                     user's current
                                                     Positions)
        - "new_ticker"          params: {ticker}     (concentrate in one
                                                     new symbol the user
                                                     is considering)
        - "cash"                params: {}           (hold in cash)
        - "dividend_etf"        params: {ticker}     (must be in
                                                     `_DIVIDEND_ETF_WHITELIST`)
    """
    type:   str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioResult:
    label:       str        # human-readable scenario label
    type:        str
    tickers:     list[str]          # [] for cash
    weights:     list[float]        # parallel to tickers
    return_cagr: Optional[float]    # 5y CAGR % (past, never forward)
    volatility:  Optional[float]    # annualised std dev % (past)
    max_dd:      Optional[float]    # worst peak-to-trough % (past)
    sharpe:      Optional[float]    # CAGR / vol (rf=0 simplified)
    note:        str                # "past 5y window" or "insufficient data"

    def to_dict(self) -> dict[str, Any]:
        def _r(v: Optional[float]) -> Optional[float]:
            return round(v, 4) if v is not None else None
        return {
            "label":       self.label,
            "type":        self.type,
            "tickers":     self.tickers,
            "weights":     [round(w, 4) for w in self.weights],
            "return_cagr": _r(self.return_cagr),
            "volatility":  _r(self.volatility),
            "max_dd":      _r(self.max_dd),
            "sharpe":      _r(self.sharpe),
            "note":        self.note,
        }


# ── stats helpers ────────────────────────────────────────────────────────────

def _safe_history(ticker: str):
    """Return a close-price series (pandas) or None. No exceptions leak."""
    try:
        from services.container import fetcher
        df = fetcher.get_price_history(ticker, period="5y")
        if df is None or "Close" not in df or len(df["Close"]) < 60:
            return None
        return df["Close"].dropna()
    except Exception as exc:
        logger.debug("capital_allocation history failed for %s: %s", ticker, exc)
        return None


def _stats_single(closes) -> tuple[Optional[float], Optional[float],
                                   Optional[float], Optional[float]]:
    """Compute (CAGR%, vol%, max_dd%, sharpe) from a close-price series."""
    try:
        n = len(closes)
        if n < 60:
            return None, None, None, None
        first = float(closes.iloc[0])
        last  = float(closes.iloc[-1])
        if first <= 0 or last <= 0:
            return None, None, None, None
        years = max(n / _TRADING_DAYS, 1 / 12)
        cagr = ((last / first) ** (1 / years) - 1.0) * 100.0

        rets = closes.pct_change().dropna()
        vol = float(rets.std()) * math.sqrt(_TRADING_DAYS) * 100.0 if len(rets) else None

        cummax = closes.cummax()
        dd = ((closes / cummax) - 1.0).min()
        max_dd = float(dd) * 100.0 if dd is not None else None

        sharpe = None
        if vol and vol > 1e-6:
            sharpe = cagr / vol

        return cagr, vol, max_dd, sharpe
    except Exception as exc:
        logger.debug("stats_single failed: %s", exc)
        return None, None, None, None


def _stats_portfolio(tickers: list[str],
                     weights: list[float]
                     ) -> tuple[Optional[float], Optional[float],
                                Optional[float], Optional[float]]:
    """Aggregate per-ticker historical stats into weighted portfolio numbers.

    Uses simple weighted averages for CAGR / vol (conservative — ignores
    covariance, which would understate vol; overstating it is the safer
    direction for a what-if tool). Max DD is the weighted average of
    individual max DDs, a pessimistic approximation.
    """
    if not tickers or not weights or len(tickers) != len(weights):
        return None, None, None, None
    s_w = sum(weights)
    if s_w <= 0:
        return None, None, None, None
    weights = [w / s_w for w in weights]

    agg_cagr: list[tuple[float, float]] = []
    agg_vol:  list[tuple[float, float]] = []
    agg_dd:   list[tuple[float, float]] = []

    for t, w in zip(tickers, weights):
        closes = _safe_history(t)
        if closes is None:
            continue
        cagr, vol, max_dd, _ = _stats_single(closes)
        if cagr is not None:
            agg_cagr.append((w, cagr))
        if vol is not None:
            agg_vol.append((w, vol))
        if max_dd is not None:
            agg_dd.append((w, max_dd))

    def _wavg(rows: list[tuple[float, float]]) -> Optional[float]:
        if not rows:
            return None
        ws = sum(w for w, _ in rows)
        if ws <= 0:
            return None
        return sum(w * v for w, v in rows) / ws

    cagr = _wavg(agg_cagr)
    vol = _wavg(agg_vol)
    max_dd = _wavg(agg_dd)
    sharpe = None
    if cagr is not None and vol and vol > 1e-6:
        sharpe = cagr / vol
    return cagr, vol, max_dd, sharpe


# ── scenario resolution ──────────────────────────────────────────────────────

def _resolve_diversify_existing(user_id: int) -> tuple[list[str], list[float]]:
    positions = Position.query.filter_by(user_id=user_id).all()
    if not positions:
        return [], []
    # Equal-weight across the user's current holdings.
    n = len(positions)
    tickers = [p.ticker.upper() for p in positions]
    weights = [1.0 / n] * n
    return tickers, weights


def _resolve_scenario(user_id: int, s: ScenarioInput) -> ScenarioResult:
    stype = (s.type or "").strip().lower()
    params = s.params or {}

    if stype == "cash":
        return ScenarioResult(
            label="Hold Cash",
            type=stype,
            tickers=[],
            weights=[],
            return_cagr=0.0,
            volatility=0.0,
            max_dd=0.0,
            sharpe=None,
            note="현금은 과거 5년 동안 명목 가치 기준으로 변동이 없습니다.",
        )

    if stype == "diversify_existing":
        tickers, weights = _resolve_diversify_existing(user_id)
        if not tickers:
            return ScenarioResult(
                label="Diversify Existing Holdings",
                type=stype, tickers=[], weights=[],
                return_cagr=None, volatility=None,
                max_dd=None, sharpe=None,
                note="기존 보유 포지션이 없어 계산할 수 없습니다.",
            )
        cagr, vol, dd, sh = _stats_portfolio(tickers, weights)
        return ScenarioResult(
            label="Diversify Existing Holdings",
            type=stype, tickers=tickers, weights=weights,
            return_cagr=cagr, volatility=vol, max_dd=dd, sharpe=sh,
            note=f"기존 {len(tickers)}개 포지션을 균등 가중으로 분산.",
        )

    if stype == "new_ticker":
        ticker = str(params.get("ticker") or "").upper().strip()
        if not ticker or not re.match(r"^[A-Z0-9\.\-\^]{1,20}$", ticker):
            return ScenarioResult(
                label=f"New Position — {ticker or '?'}",
                type=stype, tickers=[], weights=[],
                return_cagr=None, volatility=None,
                max_dd=None, sharpe=None,
                note="티커가 비어 있거나 형식이 올바르지 않습니다.",
            )
        closes = _safe_history(ticker)
        if closes is None:
            return ScenarioResult(
                label=f"New Position — {ticker}",
                type=stype, tickers=[ticker], weights=[1.0],
                return_cagr=None, volatility=None,
                max_dd=None, sharpe=None,
                note="과거 5년 가격 데이터를 충분히 받아오지 못했습니다.",
            )
        cagr, vol, dd, sh = _stats_single(closes)
        return ScenarioResult(
            label=f"New Position — {ticker}",
            type=stype, tickers=[ticker], weights=[1.0],
            return_cagr=cagr, volatility=vol, max_dd=dd, sharpe=sh,
            note="과거 5년 단독 수익률/변동성 기준.",
        )

    if stype == "dividend_etf":
        ticker = str(params.get("ticker") or "").upper().strip()
        if ticker not in _DIVIDEND_ETF_WHITELIST:
            return ScenarioResult(
                label=f"Dividend ETF — {ticker or '?'}",
                type=stype, tickers=[], weights=[],
                return_cagr=None, volatility=None,
                max_dd=None, sharpe=None,
                note=("허용된 배당 ETF 목록에 없습니다. "
                      f"허용: {', '.join(sorted(_DIVIDEND_ETF_WHITELIST))}"),
            )
        closes = _safe_history(ticker)
        label = f"Dividend ETF — {_DIVIDEND_ETF_WHITELIST[ticker]}"
        if closes is None:
            return ScenarioResult(
                label=label, type=stype, tickers=[ticker], weights=[1.0],
                return_cagr=None, volatility=None, max_dd=None, sharpe=None,
                note="과거 5년 가격 데이터를 충분히 받아오지 못했습니다.",
            )
        cagr, vol, dd, sh = _stats_single(closes)
        return ScenarioResult(
            label=label, type=stype, tickers=[ticker], weights=[1.0],
            return_cagr=cagr, volatility=vol, max_dd=dd, sharpe=sh,
            note="과거 5년 단독 수익률/변동성 기준. 배당 재투자는 가격 데이터에 포함되지 않을 수 있습니다.",
        )

    # Unknown type → record it and move on; caller never fails.
    return ScenarioResult(
        label=f"Unknown Scenario ({stype!r})",
        type=stype or "unknown",
        tickers=[], weights=[],
        return_cagr=None, volatility=None, max_dd=None, sharpe=None,
        note=("허용되지 않은 시나리오 유형입니다. "
              "(허용: diversify_existing / new_ticker / cash / dividend_etf)"),
    )


# ── misc helpers ─────────────────────────────────────────────────────────────

def _try_import_weasyprint():
    try:
        from weasyprint import HTML  # type: ignore
        return HTML
    except Exception as exc:  # pragma: no cover
        logger.info("WeasyPrint unavailable (%s); skipping PDF.", exc)
        return None


def _try_import_jinja():
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        return Environment, FileSystemLoader, select_autoescape
    except Exception as exc:  # pragma: no cover
        logger.warning("Jinja2 unavailable (%s).", exc)
        return None, None, None


def _storage_dir() -> Path:
    override = os.environ.get("CAPITAL_ALLOCATION_STORAGE_DIR")
    d = Path(override) if override else _DEFAULT_STORAGE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _infer_ccy(cash_amount: float, scenarios: list[ScenarioResult]) -> str:
    # Heuristic: if any scenario references a KR ticker → KRW. Otherwise USD.
    for s in scenarios:
        for t in s.tickers or []:
            if t.upper().endswith((".KS", ".KQ")):
                return "KRW"
    # Cash-only or US-only → assume USD.
    return "USD" if cash_amount < 100_000 else "KRW"


# ── service ──────────────────────────────────────────────────────────────────

class CapitalAllocationService:
    """On-demand Premium what-if calculator. Synchronous by design."""

    ETF_WHITELIST = _DIVIDEND_ETF_WHITELIST  # expose for routes/UI

    # ---------- public entry point: compute for a given user ----------------

    def calculate_for_user(
        self,
        user_id: int,
        *,
        cash_amount: float,
        scenarios: list[dict[str, Any]],
    ) -> dict[str, Any]:
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"user {user_id} not found")

        # Validate cash
        try:
            cash = float(cash_amount)
        except (TypeError, ValueError) as exc:
            raise ValueError("cash_amount must be numeric") from exc
        if math.isnan(cash) or math.isinf(cash):
            raise ValueError("cash_amount must be finite")
        if cash < _MIN_CASH or cash > _MAX_CASH:
            raise ValueError(
                f"cash_amount out of range [{_MIN_CASH}, {_MAX_CASH}]"
            )

        # Validate scenarios
        if not isinstance(scenarios, list):
            raise ValueError("scenarios must be a list")
        if len(scenarios) == 0:
            raise ValueError("at least one scenario is required")
        if len(scenarios) > _MAX_SCENARIOS:
            raise ValueError(
                f"at most {_MAX_SCENARIOS} scenarios may be supplied"
            )

        parsed_inputs: list[ScenarioInput] = []
        for entry in scenarios:
            if not isinstance(entry, dict):
                raise ValueError("each scenario must be an object")
            st = str(entry.get("type") or "").strip().lower()
            if st not in {"diversify_existing", "new_ticker",
                           "cash", "dividend_etf"}:
                raise ValueError(f"unknown scenario type: {st!r}")
            params = entry.get("params") or {}
            if not isinstance(params, dict):
                raise ValueError("scenario.params must be an object")
            parsed_inputs.append(ScenarioInput(type=st, params=params))

        # Resolve every scenario — never raise, collapse to a "no data" row.
        results: list[ScenarioResult] = [
            _resolve_scenario(user_id, s) for s in parsed_inputs
        ]
        ccy = _infer_ccy(cash, results)

        generated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        calc_token = secrets.token_urlsafe(12)

        data: dict[str, Any] = {
            "calc_token":    calc_token,
            "user_id":       user_id,
            "user_name":     user.name or user.email.split("@")[0],
            "cash_amount":   round(cash, 2),
            "portfolio_ccy": ccy,
            "generated_at":  generated_at.isoformat() + "Z",
            "scenarios":     [r.to_dict() for r in results],
            "etf_whitelist": _DIVIDEND_ETF_WHITELIST,
            "disclaimer": (
                "본 결과는 과거 5년 가격 데이터에 기반한 통계적 관찰이며, "
                "향후 수익률을 보장하지 않습니다. PivoxQuant은 어떠한 "
                "배분도 권유·추천하지 않으며, 본 계산은 이용자가 직접 "
                "입력한 시나리오의 과거 사실만 요약합니다. 투자 판단과 "
                "그 결과는 전적으로 이용자 본인의 책임입니다."
            ),
        }
        return data

    # ---------- rendering ---------------------------------------------------

    def render_html(self, data: dict[str, Any]) -> str:
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data)
        try:
            tpl = env.get_template("capital_allocation.html")
            return tpl.render(**data)
        except Exception as exc:
            logger.warning("capital_allocation render failed: %s", exc)
            return self._fallback_html(data)

    def render_pdf(self, data: dict[str, Any]) -> Optional[bytes]:
        HTML = _try_import_weasyprint()
        if HTML is None:
            return None
        try:
            return HTML(string=self.render_html(data)).write_pdf()
        except Exception as exc:  # pragma: no cover
            logger.error("WeasyPrint capital_allocation failed: %s", exc)
            return None

    def _jinja_env(self):
        Environment, FileSystemLoader, select_autoescape = _try_import_jinja()
        if Environment is None:
            return None
        try:
            return Environment(
                loader=FileSystemLoader(str(_TEMPLATE_DIR)),
                autoescape=select_autoescape(["html", "xml"]),
                trim_blocks=True, lstrip_blocks=True,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Jinja env build failed: %s", exc)
            return None

    def _fallback_html(self, data: dict[str, Any]) -> str:
        from html import escape
        rows = "".join(
            f"<tr><td>{escape(s['label'])}</td>"
            f"<td>{s.get('return_cagr') or '—'}</td>"
            f"<td>{s.get('volatility')  or '—'}</td>"
            f"<td>{s.get('max_dd')      or '—'}</td></tr>"
            for s in data.get("scenarios", [])
        )
        return (
            f"<!doctype html><html><body>"
            f"<h1>Capital Allocation — {escape(str(data.get('generated_at','')))}</h1>"
            f"<table><tr><th>Scenario</th><th>CAGR</th><th>Vol</th><th>Max DD</th></tr>"
            f"{rows}</table>"
            f"<p><em>{escape(data.get('disclaimer',''))}</em></p>"
            f"</body></html>"
        )

    # ---------- persist -----------------------------------------------------

    def persist(self, user_id: int, data: dict[str, Any],
                pdf_bytes: Optional[bytes]) -> Artifact:
        token = data.get("calc_token") or secrets.token_urlsafe(12)
        title = f"Capital Allocation — {token}"

        pdf_path: Optional[str] = None
        if pdf_bytes:
            try:
                base = _storage_dir() / str(user_id)
                base.mkdir(parents=True, exist_ok=True)
                safe = re.sub(r"[^A-Za-z0-9_-]+", "_", token)
                path = base / f"{safe}.pdf"
                path.write_bytes(pdf_bytes)
                pdf_path = str(path)
            except Exception as exc:
                logger.warning("capital_allocation PDF write failed for user %s: %s",
                               user_id, exc)

        artefact = Artifact(
            user_id=user_id,
            type="capital_allocation",
            title=title,
            data_json=data,
            pdf_path=pdf_path,
            share_token=token,
        )
        db.session.add(artefact)
        db.session.commit()
        return artefact

    # ---------- quarterly email reminder (NO calculation) -------------------

    def send_quarterly_reminder(self) -> dict[str, Any]:
        """Email every Premium user a reminder to revisit the calculator.

        This does **not** run any calculation — that's deliberate.
        Regulatory: we never push allocation advice; the user must opt
        into the calculator themselves.
        """
        paid = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )
        from_email = os.environ.get(
            "WEEKLY_MEMO_FROM_EMAIL", "reports@pivoxquant.com"
        )
        subject = "PivoxQuant — 분기 Capital Allocation 체크인"
        body_html = (
            "<p>안녕하세요,</p>"
            "<p>새 현금을 어떻게 배분할지 고민 중이시라면, "
            "PivoxQuant의 <strong>What-If Capital Allocation Calculator</strong>에서 "
            "최대 4개의 시나리오를 직접 입력해 과거 5년 기준의 수익률·변동성·"
            "최대 낙폭을 병렬 비교하실 수 있습니다.</p>"
            "<p><a href=\"https://pivoxquant.com/artifacts?type=capital_allocation\">"
            "계산기 열기 →</a></p>"
            "<p style=\"color:#6b7280;font-size:12px;margin-top:24px;\">"
            "본 이메일은 Premium 가입자에게만 발송되며, PivoxQuant은 어떠한 "
            "배분도 권유하거나 추천하지 않습니다. 계산 결과는 과거 사실일 뿐이며, "
            "투자 판단은 본인 책임입니다.</p>"
        )

        ok = skipped = failed = 0
        for u in paid:
            if getattr(u, "email_opt_out", False):
                skipped += 1
                continue
            try:
                if self._send_email(u, from_email, subject, body_html):
                    ok += 1
                else:
                    skipped += 1
            except Exception as exc:
                logger.error("capital_allocation reminder send failed user %s: %s",
                             u.id, exc)
                failed += 1

        summary = {
            "attempted": len(paid),
            "sent":      ok,
            "skipped":   skipped,
            "failed":    failed,
        }
        logger.info("capital_allocation quarterly reminder: %s", summary)
        return summary

    # ---------- internal: email plumbing (mirrors sibling services) ---------

    def _send_email(self, user: User, from_email: str,
                    subject: str, html_body: str) -> bool:
        sg_key = os.environ.get("SENDGRID_API_KEY")
        if sg_key:
            try:
                from sendgrid import SendGridAPIClient  # type: ignore
                from sendgrid.helpers.mail import Mail  # type: ignore
                mail = Mail(from_email=from_email, to_emails=user.email,
                            subject=subject, html_content=html_body)
                SendGridAPIClient(sg_key).send(mail)
                return True
            except Exception as exc:
                logger.error("SendGrid capital_allocation reminder failed %s: %s",
                             user.id, exc)
                return False

        smtp_host = os.environ.get("SMTP_HOST")
        if smtp_host:
            try:
                import smtplib
                from email.message import EmailMessage
                msg = EmailMessage()
                msg["From"] = from_email
                msg["To"] = user.email
                msg["Subject"] = subject
                msg.set_content("HTML-only; view in an HTML-capable client.")
                msg.add_alternative(html_body, subtype="html")
                port = int(os.environ.get("SMTP_PORT", "587"))
                user_ = os.environ.get("SMTP_USER")
                pw = os.environ.get("SMTP_PASSWORD")
                with smtplib.SMTP(smtp_host, port, timeout=10) as s:
                    s.starttls()
                    if user_ and pw:
                        s.login(user_, pw)
                    s.send_message(msg)
                return True
            except Exception as exc:
                logger.error("SMTP capital_allocation reminder failed %s: %s",
                             user.id, exc)
                return False

        return False
