"""Monthly Brag Card — 1080×1920 PNG, emailed 1st of each month 09:00 KST.

Entry points
------------
    MonthlyBragService().generate_for_user(user_id, month=None) -> dict
    MonthlyBragService().render_png(data)                       -> bytes
    MonthlyBragService().render_email_html(data, png_url)       -> str
    MonthlyBragService().send_email(user, png_bytes, html_body) -> bool
    MonthlyBragService().run_monthly(target_month=None)         -> summary dict

Design principles
-----------------
1. **Everyone gets a card.** Unlike the Pro+ weekly memo, the monthly
   brag card is the viral loop input — it goes to Free users too.
   Empty-portfolio users still get a "welcome" card so new signups
   aren't excluded from the habit.
2. **Idempotent.** `(user_id, "monthly_brag", title)` is UNIQUE at the
   DB level (same composite as Weekly Memo). Re-running on the same
   month UPSERTs into the existing row.
3. **Graceful degradation.** Pillow is a hard dep for the PNG render
   but the rest of the pipeline tolerates partial failures — missing
   font, missing position history, missing fx rate etc. each short-
   circuit to a safe fallback.
4. **Compliance.** No "buy/sell/추천" prose. Numbers and tickers only.
   Anonymous mode hides ticker names for users who enable it.
5. **No modifications to engine.py / weekly_memo_service.py.** This
   service imports them read-only or not at all.
6. **Font fallback.** We try to load Pretendard from
   `services/artifacts/fonts/` (SIL OFL — Korean-friendly sans).
   If the files aren't there we drop to `ImageFont.load_default()`
   so CI can still render a (less pretty) card.

Storage
-------
PNGs are written to `<PROJECT_ROOT>/artifacts/monthly_brag/
<user_id>/<title>.png`. Override with `MONTHLY_BRAG_STORAGE_DIR`.

Font bundle (manual placement)
------------------------------
Download from https://github.com/orioncactus/pretendard/releases
and https://fonts.google.com/specimen/Source+Serif+4, then drop:

    services/artifacts/fonts/Pretendard-Bold.otf
    services/artifacts/fonts/Pretendard-Regular.otf
    services/artifacts/fonts/SourceSerif-Regular.otf

Pretendard is SIL OFL; Source Serif is SIL OFL. Both are free for
commercial use — no runtime download needed.
"""
from __future__ import annotations

import io
import logging
import os
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from extensions import db
from models import Artifact, Position, TradeHistory, User, UserReferral
from services.legal_filter import is_compliant, safe_scrub

logger = logging.getLogger(__name__)


# ── paths / config ───────────────────────────────────────────────────────────

_FONT_DIR = Path(__file__).parent / "fonts"
_DEFAULT_STORAGE_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "monthly_brag"

# Card canvas — Instagram Story aspect ratio.
CARD_WIDTH  = 1080
CARD_HEIGHT = 1920

# Design system — Vantablack backdrop + Warm Gold hero + green/red deltas.
COLOR_BG         = "#0B0D12"
COLOR_FG         = "#F6F3EC"
COLOR_FG_DIM     = "#8C8B87"
COLOR_GOLD       = "#E2B96F"
COLOR_UP         = "#F04744"   # KR convention: red = up
COLOR_DOWN       = "#3E8EDE"   # KR convention: blue = down
COLOR_DIVIDER    = "#1B1E25"

_SHARE_DOMAIN = os.environ.get("MONTHLY_BRAG_SHARE_DOMAIN", "pivoxquant.com")


def _storage_dir() -> Path:
    override = os.environ.get("MONTHLY_BRAG_STORAGE_DIR")
    d = Path(override) if override else _DEFAULT_STORAGE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── optional deps ────────────────────────────────────────────────────────────

def _try_import_pillow():
    """Return (Image, ImageDraw, ImageFont) or (None, None, None)."""
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
        return Image, ImageDraw, ImageFont
    except Exception as exc:  # pragma: no cover — depends on env
        logger.error("Pillow unavailable (%s); PNG render will be skipped.", exc)
        return None, None, None


def _load_font(ImageFont, *candidates: str, size: int):
    """Load the first usable font from a list of candidate filenames.

    Falls back to PIL's default bitmap font if none are available.
    Default font ignores the `size` parameter but at least keeps the
    pipeline moving in CI without the font bundle.
    """
    for name in candidates:
        path = _FONT_DIR / name
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except Exception as exc:
                logger.debug("font load failed for %s: %s", path, exc)
                continue
    # Last-resort fallback — PIL's bundled bitmap. No size control.
    try:
        return ImageFont.load_default()
    except Exception:
        logger.debug("silent-fallback: Last-resort fallback — PIL's bundled bitmap. No size control | _load_font", exc_info=True)
        return None


# ── data assembly ────────────────────────────────────────────────────────────

@dataclass
class BragContext:
    """Fields required to render one user's monthly brag card."""
    user_id:          int
    user_name:        str
    referral_code:    str
    month_label:      str        # "2026년 3월" / "March 2026"
    month_start:      date
    month_end:        date
    generated_at:     datetime
    return_pct:       Optional[float]
    trade_count:      int
    hold_days_avg:    Optional[float]
    best_ticker:      Optional[str]
    best_return_pct:  Optional[float]
    worst_ticker:     Optional[str]
    worst_return_pct: Optional[float]
    anonymous:        bool
    is_empty:         bool        # True → "welcome aboard" card variant
    disclaimer:       str

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id":          self.user_id,
            "user_name":        self.user_name,
            "referral_code":    self.referral_code,
            "month_label":      self.month_label,
            "month_start":      self.month_start.isoformat(),
            "month_end":        self.month_end.isoformat(),
            "generated_at":     self.generated_at.isoformat() + "Z",
            "return_pct":       self.return_pct,
            "trade_count":      self.trade_count,
            "hold_days_avg":    self.hold_days_avg,
            "best_ticker":      self.best_ticker,
            "best_return_pct":  self.best_return_pct,
            "worst_ticker":     self.worst_ticker,
            "worst_return_pct": self.worst_return_pct,
            "anonymous":        self.anonymous,
            "is_empty":         self.is_empty,
            "disclaimer":       self.disclaimer,
        }


# ── helpers ──────────────────────────────────────────────────────────────────

def _previous_month_bounds(today: date | None = None) -> tuple[date, date]:
    """Return (first_day, last_day) of the month *before* `today`."""
    today = today or date.today()
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev, last_prev


def _month_label(d: date) -> str:
    """Human-readable month label — Korean by default."""
    return f"{d.year}년 {d.month}월"


def _month_title(d: date) -> str:
    """Title used in the Artifact table row — stable across runs for upsert."""
    return f"{d.year}-{d.month:02d} Monthly Brag"


def _compute_monthly_stats(
    user_id: int, start: date, end: date,
) -> dict[str, Any]:
    """Aggregate a user's trades for the target month.

    Returns
    -------
    {
      "return_pct":       float | None,    # PnL % on gross invested $
      "trade_count":      int,
      "hold_days_avg":    float | None,
      "best_ticker":      str  | None,
      "best_return_pct":  float| None,
      "worst_ticker":     str  | None,
      "worst_return_pct": float| None,
    }

    Math: per-ticker return% is the ratio of SELL pnl to the gross buy
    cost for that ticker within the window — a straightforward "realized
    return on invested capital" proxy. Unrealized positions opened in
    the window but not yet closed are tracked but do not contribute to
    the brag number (shows up only as trade_count > 0).
    """
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time())

    try:
        trades = (
            TradeHistory.query
            .filter(TradeHistory.user_id == user_id,
                    TradeHistory.traded_at >= start_dt,
                    TradeHistory.traded_at < end_dt)
            .order_by(TradeHistory.traded_at.asc())
            .all()
        )
    except Exception as exc:
        logger.debug("trade history fetch failed for user %s: %s", user_id, exc)
        trades = []

    if not trades:
        return {
            "return_pct":       None,
            "trade_count":      0,
            "hold_days_avg":    None,
            "best_ticker":      None,
            "best_return_pct":  None,
            "worst_ticker":     None,
            "worst_return_pct": None,
        }

    # Per-ticker tally: buy cost, sell pnl
    per_ticker: dict[str, dict[str, float]] = {}
    realized_pnl = 0.0
    realized_cost = 0.0
    hold_days: list[float] = []
    # Map of first-BUY date per ticker for hold-days proxy.
    first_buy: dict[str, datetime] = {}

    for t in trades:
        tkr = (t.ticker or "").upper()
        if not tkr:
            continue
        bucket = per_ticker.setdefault(
            tkr, {"buy_cost": 0.0, "sell_pnl": 0.0, "sell_cost": 0.0}
        )
        tv = float(t.total_value or 0)
        pnl = float(t.pnl or 0)
        action = (t.action or "").upper()
        if action == "BUY":
            bucket["buy_cost"] += tv
            first_buy.setdefault(tkr, t.traded_at or start_dt)
        elif action == "SELL":
            bucket["sell_pnl"] += pnl
            bucket["sell_cost"] += tv
            realized_pnl += pnl
            realized_cost += max(tv, 0.0)
            buy_ts = first_buy.get(tkr)
            if buy_ts and t.traded_at:
                hd = (t.traded_at - buy_ts).total_seconds() / 86400.0
                if hd >= 0:
                    hold_days.append(hd)

    # Headline return % — realized pnl over realized (sold) notional.
    return_pct: Optional[float] = None
    if realized_cost > 0:
        return_pct = round(realized_pnl / realized_cost * 100, 2)

    # Best / worst ticker by realized pnl% (only tickers with SELLs count).
    per_ticker_pct: list[tuple[str, float]] = []
    for tkr, bk in per_ticker.items():
        cost = bk["buy_cost"] or bk["sell_cost"]
        if cost <= 0 or bk["sell_cost"] <= 0:
            continue
        pct = bk["sell_pnl"] / cost * 100
        per_ticker_pct.append((tkr, round(pct, 2)))

    best_ticker = worst_ticker = None
    best_ret = worst_ret = None
    if per_ticker_pct:
        per_ticker_pct.sort(key=lambda x: x[1])
        worst_ticker, worst_ret = per_ticker_pct[0]
        best_ticker, best_ret = per_ticker_pct[-1]
        # If only one tracked ticker, avoid duplicating best==worst.
        if best_ticker == worst_ticker and len(per_ticker_pct) == 1:
            worst_ticker = None
            worst_ret = None

    return {
        "return_pct":       return_pct,
        "trade_count":      len(trades),
        "hold_days_avg":    round(sum(hold_days) / len(hold_days), 1)
                            if hold_days else None,
        "best_ticker":      best_ticker,
        "best_return_pct":  best_ret,
        "worst_ticker":     worst_ticker,
        "worst_return_pct": worst_ret,
    }


# ── The service ──────────────────────────────────────────────────────────────

class MonthlyBragService:
    """Coordinates data assembly, PNG render, email dispatch, persistence.

    This service is safe to run against the full user base (including
    Free tier) because the PNG generation has no upstream API calls and
    the email path short-circuits on `email_opt_out`.
    """

    # ── data ─────────────────────────────────────────────────────────────────

    def generate_for_user(self, user_id: int,
                          month: date | None = None,
                          *, anonymous: bool | None = None) -> dict[str, Any]:
        """Assemble the brag payload for one user.

        `month` is any date inside the *target* month (default: the month
        immediately preceding today). `anonymous` explicitly overrides the
        user's setting — leave `None` to honor the user's flag.
        """
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"user {user_id} not found")

        # Resolve target month — either the explicit month arg (anywhere
        # inside the target month) or the month preceding today.
        if month is None:
            start, end = _previous_month_bounds(date.today())
        else:
            start = month.replace(day=1)
            end = start.replace(day=monthrange(start.year, start.month)[1])

        stats = _compute_monthly_stats(user_id, start, end)

        has_positions = (
            Position.query.filter_by(user_id=user_id).count() > 0
        )
        is_empty = (stats["trade_count"] == 0) and not has_positions

        # Resolve anonymous flag — explicit arg beats the user attribute.
        if anonymous is None:
            anonymous = bool(getattr(user, "brag_anonymous", False))

        # Referral code (auto-provision on first brag — bootstraps the
        # viral loop for legacy users who registered pre-referrals).
        referral = UserReferral.get_or_create(user_id)

        user_name = (user.name or "").strip() or \
                    (user.email or "").split("@")[0] or "Investor"

        ctx = BragContext(
            user_id=user_id,
            user_name=user_name,
            referral_code=referral.referral_code,
            month_label=_month_label(start),
            month_start=start,
            month_end=end,
            generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            return_pct=stats["return_pct"],
            trade_count=stats["trade_count"],
            hold_days_avg=stats["hold_days_avg"],
            best_ticker=stats["best_ticker"],
            best_return_pct=stats["best_return_pct"],
            worst_ticker=stats["worst_ticker"],
            worst_return_pct=stats["worst_return_pct"],
            anonymous=anonymous,
            is_empty=is_empty,
            disclaimer="정보 제공 목적이며 투자 권유가 아닙니다.",
        )
        return ctx.to_dict()

    # ── render (PNG) ─────────────────────────────────────────────────────────

    def render_png(self, data: dict[str, Any]) -> Optional[bytes]:
        """Compose the 1080×1920 Instagram-Story card.

        Returns PNG bytes on success, None if Pillow is unavailable.
        Does not raise on font-missing / partial-data — any missing field
        is simply omitted from the layout.
        """
        Image, ImageDraw, ImageFont = _try_import_pillow()
        if Image is None:
            return None

        img = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), COLOR_BG)
        draw = ImageDraw.Draw(img)

        # Font loading — tolerant of missing bundle.
        f_month   = _load_font(ImageFont,
                               "SourceSerif-Regular.otf",
                               "Pretendard-Regular.otf", size=56)
        f_hero    = _load_font(ImageFont,
                               "Pretendard-Bold.otf", size=220)
        f_user    = _load_font(ImageFont,
                               "Pretendard-Regular.otf", size=36)
        f_meta    = _load_font(ImageFont,
                               "Pretendard-Regular.otf", size=32)
        f_water   = _load_font(ImageFont,
                               "Pretendard-Regular.otf", size=22)

        # Layout helpers
        def _measure(text: str, font) -> tuple[int, int]:
            """Return (width, height) — uses textbbox when available."""
            try:
                box = draw.textbbox((0, 0), text, font=font)
                return box[2] - box[0], box[3] - box[1]
            except Exception:
                # Default font on older PIL — best-effort fallback.
                return (len(text) * 10, 14)

        def _draw_centered(text: str, font, y: int, fill: str):
            w, _ = _measure(text, font)
            draw.text(((CARD_WIDTH - w) // 2, y), text, font=font, fill=fill)

        # ── Hero row: month ──────────────────────────────────────────────
        _draw_centered(data.get("month_label", ""), f_month, 240, COLOR_FG_DIM)

        # ── Hero number: return %, or greeting for empty portfolios ─────
        return_pct = data.get("return_pct")
        is_empty   = bool(data.get("is_empty"))
        anonymous  = bool(data.get("anonymous"))

        if is_empty or return_pct is None:
            # New-user / no-trade variant — keeps bragging habit alive.
            hero_text = "Welcome"
            hero_color = COLOR_GOLD
        else:
            sign = "+" if return_pct >= 0 else ""
            hero_text = f"{sign}{return_pct:.1f}%"
            hero_color = COLOR_UP if return_pct > 0 else (
                COLOR_DOWN if return_pct < 0 else COLOR_GOLD
            )

        _draw_centered(hero_text, f_hero, 560, hero_color)

        # ── Name sub-line ───────────────────────────────────────────────
        name = data.get("user_name", "Investor")
        _draw_centered(f"{name}'s month", f_user, 900, COLOR_FG)

        # ── Meta row: trade_count · best ticker · hold days ─────────────
        meta_bits: list[str] = []
        tc = int(data.get("trade_count") or 0)
        if tc > 0:
            meta_bits.append(f"{tc} trades")

        best_t = data.get("best_ticker")
        best_r = data.get("best_return_pct")
        if best_t and best_r is not None:
            # Anonymous mode hides the ticker but keeps the %.
            label = "★" if anonymous else f"${best_t}"
            sign = "+" if best_r >= 0 else ""
            meta_bits.append(f"Top {label} {sign}{best_r:.1f}%")

        hd = data.get("hold_days_avg")
        if hd is not None:
            meta_bits.append(f"avg hold {hd:.0f}d")

        if is_empty and not meta_bits:
            meta_bits.append("첫 카드를 기다립니다")

        meta_text = " · ".join(meta_bits)
        _draw_centered(meta_text, f_meta, 1040, COLOR_FG_DIM)

        # ── Divider ─────────────────────────────────────────────────────
        draw.line(
            [(CARD_WIDTH // 2 - 120, 1720),
             (CARD_WIDTH // 2 + 120, 1720)],
            fill=COLOR_DIVIDER, width=2,
        )

        # ── Watermark + referral link ──────────────────────────────────
        _draw_centered("Generated by PivoxQuant", f_water, 1760, COLOR_FG_DIM)
        referral = data.get("referral_code") or ""
        if referral:
            link = f"{_SHARE_DOMAIN}/r/{referral}"
            _draw_centered(link, f_water, 1800, COLOR_GOLD)

        # ── Disclaimer (tiny) ─────────────────────────────────────────
        disclaimer = data.get("disclaimer") or ""
        if disclaimer:
            _draw_centered(disclaimer, f_water, 1850, COLOR_FG_DIM)

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    # ── render (email) ───────────────────────────────────────────────────────

    def render_email_html(self, data: dict[str, Any],
                          png_url: str | None = None) -> str:
        """Return inline-safe email body with embedded PNG + share CTA.

        `png_url` is optional; when absent the caller is expected to
        attach the PNG as a file part instead of inlining it.
        """
        from html import escape

        ret = data.get("return_pct")
        if ret is None:
            ret_str = "—"
        else:
            sign = "+" if ret >= 0 else ""
            ret_str = f"{sign}{ret:.1f}%"

        month = escape(data.get("month_label", ""))
        name = escape(data.get("user_name", "Investor"))
        referral = escape(data.get("referral_code", ""))
        share_link = f"https://{_SHARE_DOMAIN}/r/{referral}" if referral else ""
        disclaimer = escape(data.get("disclaimer", ""))

        img_tag = ""
        if png_url:
            img_tag = (f'<img src="{escape(png_url)}" alt="Monthly brag card" '
                       f'style="max-width:100%; border-radius:12px;" />')
        else:
            # Attachment-only mode — reference via CID if the mailer
            # wires one up, but keep the body readable without it.
            img_tag = ('<div style="color:#8C8B87;">'
                       '(카드 이미지는 첨부파일로 포함되어 있습니다.)</div>')

        cta = ""
        if share_link:
            cta = (f'<p style="margin-top:24px;">'
                   f'<a href="{share_link}" '
                   f'style="display:inline-block;padding:12px 24px;'
                   f'background:#E2B96F;color:#0B0D12;text-decoration:none;'
                   f'border-radius:8px;font-weight:600;">'
                   f'공유 링크 열기</a></p>')

        html = f"""<!doctype html><html><body style="font-family:-apple-system,sans-serif;
background:#0B0D12;color:#F6F3EC;padding:32px;">
<h1 style="margin:0 0 16px;">{name}님의 {month} 수익률</h1>
<p style="font-size:48px;margin:0 0 24px;color:#E2B96F;"><strong>{ret_str}</strong></p>
{img_tag}
{cta}
<p style="margin-top:32px;color:#8C8B87;font-size:12px;"><em>{disclaimer}</em></p>
</body></html>"""
        # Legal guard: 자본시장법 §6 미등록 투자자문업 방어선.
        scrubbed = safe_scrub(html, context="monthly_brag") or html
        if not is_compliant(scrubbed):
            logger.warning("legal_filter fail: monthly_brag")
        return scrubbed

    # ── send ─────────────────────────────────────────────────────────────────

    def send_email(self, user: User,
                   png_bytes: Optional[bytes],
                   html_body: str) -> bool:
        """Deliver the brag card email. Mirrors WeeklyMemoService.send_email.

        Priority: SendGrid → SMTP → skip (dev).
        Returns True on success, False on skip/failure. Never raises.
        """
        if getattr(user, "email_opt_out", False):
            logger.info("user %s opted out of email", user.id)
            return False

        from_email = os.environ.get(
            "MONTHLY_BRAG_FROM_EMAIL",
            os.environ.get("WEEKLY_MEMO_FROM_EMAIL", "reports@pivoxquant.com"),
        )
        subject = "당신의 월간 브래그 카드가 도착했어요"
        attach_name = f"pivoxquant_brag_{user.id}.png"

        # --- SendGrid ---
        sg_key = os.environ.get("SENDGRID_API_KEY")
        if sg_key:
            try:
                import base64
                from sendgrid import SendGridAPIClient  # type: ignore
                from sendgrid.helpers.mail import (  # type: ignore
                    Mail, Attachment, FileContent, FileName, FileType, Disposition,
                )
                mail = Mail(from_email=from_email, to_emails=user.email,
                            subject=subject, html_content=html_body)
                if png_bytes:
                    enc = base64.b64encode(png_bytes).decode()
                    att = Attachment(
                        FileContent(enc),
                        FileName(attach_name),
                        FileType("image/png"),
                        Disposition("attachment"),
                    )
                    mail.attachment = att
                SendGridAPIClient(sg_key).send(mail)
                return True
            except Exception as exc:
                logger.error("SendGrid brag send failed for user %s: %s",
                             user.id, exc)
                return False

        # --- SMTP fallback ---
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
                if png_bytes:
                    msg.add_attachment(png_bytes, maintype="image",
                                       subtype="png", filename=attach_name)
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
                logger.error("SMTP brag send failed for user %s: %s",
                             user.id, exc)
                return False

        logger.info("no email provider configured — skipping brag "
                    "send for user %s", user.id)
        return False

    # ── persist + orchestrate ────────────────────────────────────────────────

    def _persist(self, user_id: int, data: dict[str, Any],
                 png_bytes: Optional[bytes], sent: bool,
                 target_month_start: date) -> Artifact:
        """UPSERT on (user_id, type='monthly_brag', title)."""
        title = _month_title(target_month_start)
        png_path: Optional[str] = None
        if png_bytes:
            try:
                base = _storage_dir() / str(user_id)
                base.mkdir(parents=True, exist_ok=True)
                path = base / f"{title.replace(' ', '_')}.png"
                path.write_bytes(png_bytes)
                png_path = str(path)
            except Exception as exc:
                logger.warning("PNG write failed for user %s: %s", user_id, exc)

        artefact = (
            Artifact.query
            .filter_by(user_id=user_id, type="monthly_brag", title=title)
            .first()
        )
        if artefact:
            artefact.data_json = data
            if png_path:
                artefact.pdf_path = png_path  # column is reused across artefact types
            if sent and not artefact.sent_at:
                artefact.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            artefact = Artifact(
                user_id=user_id,
                type="monthly_brag",
                title=title,
                data_json=data,
                pdf_path=png_path,
                sent_at=datetime.now(timezone.utc).replace(tzinfo=None) if sent else None,
            )
            db.session.add(artefact)
        db.session.commit()
        return artefact

    def run_for_user(self, user: User,
                     target_month: date | None = None,
                     *, send: bool = True) -> Optional[Artifact]:
        """End-to-end: generate → render → send → persist for one user.

        Unlike the weekly memo, empty portfolios are *not* skipped —
        they get a "Welcome" card. Returns the Artifact row.
        """
        data = self.generate_for_user(user.id, month=target_month)
        png_bytes = self.render_png(data)
        html_body = self.render_email_html(data)

        sent = False
        if send:
            try:
                sent = self.send_email(user, png_bytes, html_body)
            except Exception as exc:
                logger.error("send_email raised for user %s: %s", user.id, exc)
                sent = False

        # Key the persist row by the target month's first day so
        # re-runs within the same month UPSERT cleanly.
        if target_month is None:
            start, _ = _previous_month_bounds(date.today())
        else:
            start = target_month.replace(day=1)

        return self._persist(user.id, data, png_bytes, sent, start)

    def run_monthly(self, target_month: date | None = None) -> dict[str, Any]:
        """Cron target — 1st of each month 09:00 KST.

        Iterates over *all* users (Free + Pro + Premium) — the brag card
        is the viral loop input and needs the widest possible surface.
        """
        if target_month is None:
            start, end = _previous_month_bounds(date.today())
        else:
            start = target_month.replace(day=1)
            start.replace(day=monthrange(start.year, start.month)[1])

        users = User.query.all()

        successes = 0
        failures = 0

        for user in users:
            try:
                self.run_for_user(user, target_month=start)
                successes += 1
            except Exception as exc:
                db.session.rollback()
                failures += 1
                logger.error("monthly brag failed for user %s: %s", user.id, exc)

        summary = {
            "month":     start.isoformat(),
            "attempted": len(users),
            "success":   successes,
            "failed":    failures,
        }
        logger.info("monthly brag run: %s", summary)
        return summary
