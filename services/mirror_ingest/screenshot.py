"""Extract trade rows from a screenshot of a broker's 거래내역 screen.

The behavioural mirrors are pure functions over ``TradeHistory``, so the
only job here is to turn an image into rows shaped like that model:
ticker, name, action, shares, price_per_share, traded_at, currency.

Why a screenshot at all — Korean broker APIs are closed to us. KIS states
partnership is unavailable to non-licensed firms, and Toss's terms §5②
forbid a user handing their app key to a third party (the key is an
접근매체 under 전자금융거래법). A screenshot the user takes themselves
carries none of that, and review evidence from existing journal apps shows
그것이 이미 유저가 하고 있는 행동이다 — 손으로 옮겨 적는 대신 캡쳐해서
올린다.

**The rule this module exists to enforce: never invent a trade.**

A mirror's only claim is that it reports the user's own record back to
them. One fabricated row makes every number a guess and the user cannot
tell which. So the extraction is asked to transcribe, not to interpret:
anything it cannot read is returned in ``unreadable`` for the user to fix,
never filled in with a plausible-looking value. A run that reads nothing
is a valid result — an empty list is honest, a guessed list is not.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Vision model for the SDK path only. The CLI path — the default — runs
# whatever model the local `claude` session is configured with and ignores
# this, because pinning a model there would also pin the session's own
# config for the call. Named accordingly so the two are not confused: this
# is not a global knob.
_API_MODEL = os.environ.get("PIVOX_INGEST_API_MODEL", "claude-haiku-4-5")

_MAX_IMAGE_BYTES = 5 * 1024 * 1024  # Anthropic per-image limit
_CLI_TIMEOUT_S = int(os.environ.get("PIVOX_INGEST_TIMEOUT_S", "180"))
_SUPPORTED_MEDIA = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),
}

_SYSTEM = """\
You transcribe Korean brokerage transaction screens (거래내역 / 체결내역)
into structured rows. You are a transcriber, not an analyst.

Return ONLY a JSON object, no prose, no code fence:

{
  "trades": [
    {
      "ticker": "005930",        // code as shown; "" if only a name is visible
      "name": "삼성전자",         // as shown
      "action": "BUY",           // BUY for 매수/매집, SELL for 매도  # noqa: legal
      "shares": 10,              // number only
      "price_per_share": 71500,  // unit price (체결단가/단가). NOT the total
      "traded_at": "2026-03-14", // YYYY-MM-DD, or with time if shown
      "currency": "KRW"          // KRW or USD, inferred from the symbol shown
    }
  ],
  "unreadable": [
    {"row_hint": "3번째 줄", "reason": "체결단가가 잘려서 안 보임"}
  ],
  "source_note": "키움 거래내역 화면으로 보임"
}

Hard rules:
- Transcribe only what is legibly visible. If a field is cut off, blurred,
  or ambiguous, put the row in `unreadable` and explain which field failed.
- Never estimate, average, round, or infer a missing value from the others.
  A wrong number is far worse than a missing row.
- Do not compute totals, returns, or fees. Unit price only.
- If the image is not a transaction screen at all, return empty `trades`
  and say so in `source_note`.
- An empty `trades` list is an acceptable answer.
"""


@dataclass
class ExtractedTrade:
    """One transcribed row, shaped for ``models.TradeHistory``."""

    ticker: str
    name: str
    action: str          # TradeHistory.action value  # noqa: legal
    shares: float
    price_per_share: float
    traded_at: datetime
    currency: str = "KRW"

    @property
    def total_value(self) -> float:
        return self.shares * self.price_per_share


@dataclass
class ExtractionResult:
    trades: list[ExtractedTrade] = field(default_factory=list)
    unreadable: list[dict[str, str]] = field(default_factory=list)
    source_note: str = ""
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def needs_review(self) -> bool:
        """True when the user should look before we mirror anything back.

        Surfaced rather than hidden: a partial read is the normal case for a
        cropped screenshot, and quietly mirroring a partial record would
        misstate the very numbers the product exists to report faithfully.
        """
        return bool(self.unreadable)


def _media_type(data: bytes) -> str | None:
    for media, signatures in _SUPPORTED_MEDIA.items():
        if any(data.startswith(sig) for sig in signatures):
            return media
    return None


# Sanity bounds for a transcribed trade date. `%Y` accepts any four digits,
# so a single misread digit turns 2026 into 2096 and the row still parses —
# and a trade dated in the future silently distorts every hold-period and
# turnover figure computed from it. Korea's electronic trading predates
# neither bound by enough to matter; anything outside them is a misread,
# not a trade.
_MIN_TRADE_YEAR = 1990
_FUTURE_GRACE_DAYS = 1  # timezone skew between the screenshot and this host


def _parse_when(raw: Any, *, now: datetime | None = None) -> datetime | None:
    """Parse the date/time as transcribed. Returns None rather than guessing."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().replace("/", "-").replace(".", "-")
    text = re.sub(r"\s+", " ", text)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        reference = now or datetime.now()
        if parsed.year < _MIN_TRADE_YEAR:
            return None
        if parsed > reference + timedelta(days=_FUTURE_GRACE_DAYS):
            return None
        return parsed
    return None


def _coerce_row(raw: dict) -> tuple[ExtractedTrade | None, str | None]:
    """Validate one transcribed row. Returns (trade, rejection_reason)."""
    # The literals below are values of the TradeHistory.action column — a
    # record of what the user already did — not a signal label rendered to
    # anyone. 자본시장법 bans directing a user to trade; restating their own
    # past is the only thing this product ever does. The mirrors render
    # 매수/매도 in Korean at the surface.
    action = str(raw.get("action", "")).strip().upper()
    if action not in ("BUY", "SELL"):  # noqa: legal
        return None, f"매수/매도 구분 불명 ({raw.get('action')!r})"

    try:
        shares = float(raw.get("shares"))
        price = float(raw.get("price_per_share"))
    except (TypeError, ValueError):
        return None, "수량 또는 단가가 숫자가 아님"

    # Zero or negative would silently distort every mirror downstream —
    # hold periods, turnover counts and FIFO pairing all assume real fills.
    if shares <= 0 or price <= 0:
        return None, f"수량/단가가 0 이하 (shares={shares}, price={price})"

    when = _parse_when(raw.get("traded_at"))
    if when is None:
        return None, f"거래일시를 읽을 수 없음 ({raw.get('traded_at')!r})"

    currency = str(raw.get("currency", "KRW")).strip().upper()
    if currency not in ("KRW", "USD"):
        currency = "KRW"

    return ExtractedTrade(
        ticker=str(raw.get("ticker", "")).strip()[:20],
        name=str(raw.get("name", "")).strip()[:100],
        action=action,
        shares=shares,
        price_per_share=price,
        traded_at=when,
        currency=currency,
    ), None


def extract_trades_from_image(
    image_bytes: bytes,
    *,
    client: Any = None,
    model: str | None = None,
) -> ExtractionResult:
    """Transcribe a 거래내역 screenshot into trade rows.

    Never raises for a bad image or a failed call — the caller gets an
    ``ExtractionResult`` with ``error`` set, because a half-failed upload
    should surface as "we couldn't read this" rather than a 500.

    ``client`` is injectable so tests never touch the network.
    """
    if not image_bytes:
        return ExtractionResult(error="이미지가 비어 있습니다.")

    if len(image_bytes) > _MAX_IMAGE_BYTES:
        mb = len(image_bytes) / 1024 / 1024
        return ExtractionResult(
            error=f"이미지가 너무 큽니다 ({mb:.1f}MB). 5MB 이하로 줄여주세요."
        )

    media_type = _media_type(image_bytes)
    if media_type is None:
        return ExtractionResult(
            error="지원하지 않는 이미지 형식입니다. JPG · PNG · GIF · WebP 만 됩니다."
        )

    if client is not None:
        text = _call_api(client, image_bytes, media_type, model)
    else:
        text = _call_cli(image_bytes, media_type)

    if text is None:
        return ExtractionResult(error="이미지를 분석하지 못했습니다. 다시 시도해주세요.")

    return _parse_response(text)


def _call_api(client: Any, image_bytes: bytes, media_type: str, model: str | None) -> str | None:
    """Vision call over the Anthropic SDK. Used when a client is injected.

    Kept for tests and for any deployment that has a funded API key, but it
    is not the default — see :func:`_call_cli`.
    """
    try:
        response = client.messages.create(
            model=model or _API_MODEL,
            max_tokens=4000,
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                        },
                    },
                    {"type": "text", "text": "이 화면의 거래 내역을 그대로 옮겨 적어주세요."},
                ],
            }],
        )
        return "".join(
            block.text for block in response.content
            if getattr(block, "type", None) == "text"
        )
    except Exception:
        logger.warning("mirror_ingest: API vision call failed", exc_info=True)
        return None


def _call_cli(image_bytes: bytes, media_type: str) -> str | None:
    """Vision call through the local ``claude`` CLI. The default path.

    The Anthropic API returns 400 "credit balance is too low" on this
    account, and the project runs on a ₩0 budget, so paying per image is
    not on the table. The CLI reads the same models through the Max plan's
    OAuth session at no incremental cost — the same trade
    ``scripts/caus_auto_fix.py`` already makes for its fix loop.

    The image is written to a private temp file because the CLI reads from
    disk, and removed in a ``finally`` so an upload never lingers: these
    are screenshots of somebody's brokerage account.
    """
    ext = {"image/jpeg": ".jpg", "image/png": ".png",
           "image/gif": ".gif", "image/webp": ".webp"}[media_type]

    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix="mirror_ingest_", suffix=ext)
        with os.fdopen(fd, "wb") as fh:
            fh.write(image_bytes)
        os.chmod(tmp_path, 0o600)

        prompt = (
            f"{_SYSTEM}\n\n"
            f"Read the image at {tmp_path} and transcribe it under those rules.\n"
            f"Output ONLY the JSON object."
        )
        # The prompt carries a path the subprocess is told to read, and the
        # image it reads is supplied by a user. That makes this an injection
        # surface: text inside the screenshot can address the agent.
        #
        # `--allowedTools Read` narrows the capability but not the reach —
        # Read has no path-scoping syntax, so it can open anything the
        # process can. So the process itself is narrowed instead:
        #
        #   cwd  — a directory holding only the uploaded image, so a relative
        #          path in an injected instruction resolves nowhere useful.
        #   env  — a minimal set. The parent holds ANTHROPIC_API_KEY, the
        #          database URL and the broker encryption key; inheriting
        #          those means a successful injection reads them out of
        #          /proc/self/environ on Linux. Only what the CLI needs to
        #          find its own session is passed through.
        #
        # A model refusing an obvious injection is not a control — it is one
        # model version's judgement about one phrasing. These are.
        safe_env = {
            k: v for k, v in os.environ.items()
            if k in ("HOME", "PATH", "USER", "LANG", "LC_ALL", "TMPDIR")
        }
        proc = subprocess.run(
            ["claude", "-p", prompt, "--allowedTools", "Read"],
            capture_output=True, text=True, timeout=_CLI_TIMEOUT_S,
            cwd=os.path.dirname(tmp_path),
            env=safe_env,
        )
        if proc.returncode != 0:
            logger.warning(
                "mirror_ingest: claude CLI exited %s: %.300s",
                proc.returncode, proc.stderr,
            )
            return None
        return proc.stdout
    except FileNotFoundError:
        logger.warning("mirror_ingest: `claude` CLI not on PATH")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("mirror_ingest: claude CLI timed out after %ss", _CLI_TIMEOUT_S)
        return None
    except Exception:
        logger.warning("mirror_ingest: CLI vision call failed", exc_info=True)
        return None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                logger.debug("mirror_ingest: temp cleanup failed", exc_info=True)


def _parse_response(text: str) -> ExtractionResult:
    """Turn the model's reply into a result, rejecting anything malformed.

    Split out from the call so the validation path is testable without a
    client, and so a malformed reply can never reach the mirrors.
    """
    # Tolerate a code fence even though the prompt forbids one.
    stripped = re.sub(r"^\s*```(?:json)?|```\s*$", "", text.strip())
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        logger.warning("mirror_ingest: reply was not JSON: %.200s", text)
        return ExtractionResult(error="분석 결과를 해석하지 못했습니다.")

    if not isinstance(payload, dict):
        return ExtractionResult(error="분석 결과 형식이 올바르지 않습니다.")

    result = ExtractionResult(
        source_note=str(payload.get("source_note", ""))[:200],
    )

    for entry in payload.get("unreadable") or []:
        if isinstance(entry, dict):
            result.unreadable.append({
                "row_hint": str(entry.get("row_hint", ""))[:80],
                "reason": str(entry.get("reason", ""))[:200],
            })

    for raw in payload.get("trades") or []:
        if not isinstance(raw, dict):
            continue
        trade, rejection = _coerce_row(raw)
        if trade is not None:
            result.trades.append(trade)
        else:
            # A row we cannot validate joins `unreadable` rather than being
            # dropped — the user is told something was skipped and why.
            result.unreadable.append({
                "row_hint": str(raw.get("name") or raw.get("ticker") or "알 수 없는 행")[:80],
                "reason": rejection or "확인할 수 없는 행",
            })

    return result


def _get_client():
    """Lazy Anthropic client, mirroring services/ai/models.py."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        logger.warning("mirror_ingest: ANTHROPIC_API_KEY not set")
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key, timeout=60.0, max_retries=1)
    except Exception:
        logger.warning("mirror_ingest: client init failed", exc_info=True)
        return None
