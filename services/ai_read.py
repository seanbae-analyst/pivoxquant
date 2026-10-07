"""AI read of a broker screen's masked OCR text — extraction only, flag-gated.

docs/product/AI_READ_EXPERIMENT_2026-10-07.md. The image never leaves the
device: the browser runs OCR, drops identity / account lines
(frontend/src/lib/fill-ocr/mask.ts) and sends only the kept text. This module
drops those lines again (the client is not trusted), asks Claude to copy the
holdings / fills it sees into a fixed JSON shape, and then **does not trust
the answer either**:

  * a number the model says it *read* must be printed in the text it was
    given — otherwise it is only a hint the user confirms;
  * shares x price is re-checked here against every amount the model reports
    seeing (매입금액 · 평가금액 − 평가손익 · (현재가 − 평단) x 수량 · 체결금액);
    a printed relation that does not hold empties the numbers;
  * a cell is filled only when it was read or derived AND a relation proves
    it. Everything else goes back as a hint.

Nothing here interprets, scores or advises — the output is the same rows the
rule parser produces, and they go through the same review table, preview and
commit validation before anything is saved. Nothing is stored or logged: not
the text, not the answer.

Off unless BOTH ``AI_READ_ENABLED`` (config) and an Anthropic credential are
present. Turning it on also needs the overseas-transfer consent copy and the
privacy-policy change reviewed (§5 of the doc) — the route asks for the
per-use consent flag, but the legal text is not this module's to approve.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from flask import current_app

log = logging.getLogger(__name__)

AI_READ_MODEL = "claude-opus-5-5"
KINDS = ("holdings", "fills")
MAX_SCREENS = 10
MAX_TEXT_CHARS = 6000  # per screen; a phone screen's kept lines are ~1-2k

# ── masking (server copy of frontend/src/lib/fill-ocr/mask.ts) ─────────

_DROP_IDENTITY = re.compile(r"계좌|위탁|고객|님")
_DROP_UNNEEDED = re.compile(r"예수금|주문가능|출금가능")
_ACCOUNT_TAG = re.compile(r"\[[^\]]*(종합|위탁|주식|CMA|ISA|연금|비대면|저축)[^\]]*\]")
_D = r"[0-9OolI|]"
_ACCOUNT = re.compile(rf"{_D}{{2,}}(?:\s?[-–]\s?{_D}{{2,}}){{1,3}}|{_D}{{8,}}")
_DATE = re.compile(r"^(19|20)\d{2}[-–]?(0[1-9]|1[0-2])[-–]?(0[1-9]|[12]\d|3[01])$")


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s.replace("O", "0").replace("o", "0").replace("l", "1").replace("I", "1").replace("|", "1"))


def _account_like(m: str) -> bool:
    return len(_digits(m)) >= 8 and "," not in m and not _DATE.match(re.sub(r"\s", "", m))


def drop_reason(line: str) -> str | None:
    """Why a line must not be sent on, or None. Same rules as mask.ts."""
    squashed = re.sub(r"\s+", "", line)
    if _DROP_IDENTITY.search(squashed):
        return "identity"
    if _DROP_UNNEEDED.search(squashed):
        return "unneeded"
    if _ACCOUNT_TAG.search(squashed):
        return "account"
    if any(_account_like(m.group(0)) for m in _ACCOUNT.finditer(line)):
        return "account"
    return None


def mask_text(text: str) -> str:
    return "\n".join(l for l in str(text or "").splitlines() if l.strip() and drop_reason(l) is None)


# ── gate ─────────────────────────────────────────────────────────────

def ai_read_enabled() -> bool:
    """Config flag AND a credential. Read here, never from os.environ in a route."""
    if not current_app.config.get("AI_READ_ENABLED", False):
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


class AiReadError(Exception):
    def __init__(self, code: str, en: str, kr: str, status: int = 502):
        super().__init__(en)
        self.code, self.en, self.kr, self.status = code, en, kr, status


# ── prompt + schema ──────────────────────────────────────────────────

_COMMON = """너는 증권사 앱 화면을 기기에서 OCR 한 텍스트에서 기록을 **옮겨 적기만 하는** 판독기다.
해석·평가·의견·권유·요약 문장은 절대 쓰지 않는다. reason 칸에는 화면 종류와, 행을 못 만들었을 때 어떤 화면을 올리면 되는지만 한 문장으로 쓴다.
텍스트는 OCR 결과라 한글이 음절 단위로 띄어져 있고 오독이 섞여 있다. 개인정보 줄은 기기에서 이미 지워졌다. 광고 문구·기기 테두리 글자는 무시한다.

칸마다 상태를 적는다: read(화면의 라벨·열로 직접 읽음) / derived(화면 숫자로 계산) / guessed(오독 보정·추정 — 유저 확인 필요) / blank(모름, 값은 null).
- 종목: 화면 표기가 그대로 읽히면 **고치지 않는다**(정식명 변환은 서버가 한다). OCR 이 깨졌거나 화면이 일부를 가린 것만 보정하고 guessed.
- 오독 복원(`%`·`&`·`2` 로 읽힌 `주`·`원`, 잘린 앞자리)은 아래 검산이 맞을 때만 하고 guessed 로 둔다.
- 화면에 없는 숫자를 만들지 않는다. 화면 위·아래로 잘려 숫자 줄이 없는 종목은 truncated=true, 숫자 null.
- evidence 칸에는 그 행에서 **화면에 찍힌 그대로** 읽은 금액만 적는다(없으면 null). 서버가 이 숫자로 다시 검산한다.
"""

_HOLDINGS = _COMMON + """
화면 종류(screen_type): holdings(보유·잔고 목록) · position_detail(한 종목 화면의 "내 주식/보유" 블록) · fills(체결·거래내역) · order(주문) · watchlist(관심종목) · account_summary(계좌 합계만) · quote(시세·차트·종목 정보) · other.
행은 holdings / position_detail 에서만 만든다.

꼭 읽혀야 하는 것: 종목 · 보유수량 · 평균단가(1주 평균 매입단가, 그 종목 통화). 평균단가는 라벨(평균·평균가·평단·매입가·매입단가·1주 평균금액)로 읽거나,
매입금액÷수량 / (평가금액−평가손익)÷수량으로 유도하되 **나누어떨어질 때만**(원 단위, 달러는 센트) derived.
검산 관계: 수량×평단≈매입금액 · 수량×평단≈평가금액−평가손익 · (현재가−평단)×수량≈평가손익 · 수량×현재가≈평가금액. 관계가 있는데 어떤 판독으로도 안 맞으면 수량·평단을 null.
절대 금지: 현재가·시가·체결가·주문가·52주가·다른 투자자 통계를 평단으로 · 주문·체결·매도가능 수량을 보유수량으로 · 원화 환산 평단을 USD 평단으로.
통화: `$`·`달러` → USD, `원`·`₩` → KRW, 판단 못 하면 unknown.
"""

_FILLS = _COMMON + """
fills 텍스트는 체결 화면 OCR 이거나, 유저가 붙여넣은 증권사 체결 알림 문자일 수 있다(문자 한 건이 체결 한 건). 문자면 screen_type 은 fills.
화면 종류(screen_type): fills(체결·거래내역 — 체결된 매수/매도) · holdings(보유·잔고) · order(주문·미체결) · watchlist · account_summary · quote · other.
행은 fills 에서만, **체결된** 것만 만든다. 미체결·취소·정정·주문접수는 행으로 만들지 않는다.

꼭 읽혀야 하는 것: 종목 · 매수/매도 · 체결수량 · 체결단가 · 체결일. 시각·통화는 있으면 읽는다.
검산 관계: 수량×단가≈체결금액(evidence.amount). 관계가 있는데 안 맞으면 수량·단가를 null.
절대 금지: 주문가·현재가를 체결단가로 · 주문수량·미체결수량을 체결수량으로 · 화면에 없는 날짜 만들기(연도가 안 보이면 date 는 null, date_hint 에 화면 표기).
날짜 YYYY-MM-DD, 시각 HH:MM(초가 보이면 HH:MM:SS). 통화: `$`·`달러` → USD, `원`·`₩` → KRW, 판단 못 하면 unknown.
"""

_STATUS = {"type": "string", "enum": ["read", "derived", "guessed", "blank"]}
_NUM = {"type": ["number", "null"]}
_STR = {"type": ["string", "null"]}


def _obj(props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


_HOLDING_ROW = _obj({
    "stock": _STR, "stock_status": _STATUS,
    "shares": _NUM, "shares_status": _STATUS,
    "avg_cost": _NUM, "avg_cost_status": _STATUS,
    "currency": {"type": "string", "enum": ["KRW", "USD", "unknown"]},
    "evidence": _obj({"cost": _NUM, "value": _NUM, "pl": _NUM, "current": _NUM}),
    "truncated": {"type": "boolean"},
})

_FILL_ROW = _obj({
    "stock": _STR, "stock_status": _STATUS,
    "side": {"type": "string", "enum": ["buy", "sell", "unknown"]},
    "shares": _NUM, "shares_status": _STATUS,
    "price": _NUM, "price_status": _STATUS,
    "date": _STR, "date_hint": _STR, "time": _STR,
    "currency": {"type": "string", "enum": ["KRW", "USD", "unknown"]},
    "evidence": _obj({"amount": _NUM}),
})


def _schema(row: dict[str, Any], types: list[str]) -> dict[str, Any]:
    screen = _obj({
        "index": {"type": "integer"},
        "screen_type": {"type": "string", "enum": types},
        "reason": {"type": "string"},
        "rows": {"type": "array", "items": row},
    })
    return _obj({"screens": {"type": "array", "items": screen}})


_SPEC = {
    "holdings": (_HOLDINGS, _schema(_HOLDING_ROW, ["holdings", "position_detail", "fills", "order", "watchlist",
                                                   "account_summary", "quote", "other"])),
    "fills": (_FILLS, _schema(_FILL_ROW, ["fills", "holdings", "order", "watchlist", "account_summary",
                                          "quote", "other"])),
}

# ── the call ─────────────────────────────────────────────────────────


def _client():
    import anthropic
    return anthropic.Anthropic(timeout=90.0, max_retries=1)


def _call(kind: str, texts: list[str], client=None) -> dict[str, Any]:
    import anthropic

    system, schema = _SPEC[kind]
    body = "\n\n".join(f"### 화면 {i}\n{t}" for i, t in enumerate(texts))
    try:
        resp = (client or _client()).beta.messages.create(
            model=AI_READ_MODEL,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": body}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
            # Refusal fallback chosen by Anthropic per refusal category. The
            # pinned SDK (<0.101) has no `fallbacks` kwarg yet → extra_body.
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},
        )
    except anthropic.RateLimitError as exc:
        raise AiReadError("AI_READ_BUSY", "The reader is busy. Try again shortly.",
                          "판독기가 바쁩니다. 잠시 후 다시 시도해 주세요.", 503) from exc
    except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
        log.warning("ai_read upstream error: %s", type(exc).__name__)
        raise AiReadError("AI_READ_UPSTREAM", "The reader could not be reached.",
                          "판독기에 연결하지 못했습니다.", 502) from exc
    if resp.stop_reason == "refusal":
        raise AiReadError("AI_READ_DECLINED", "The reader declined this text.",
                          "판독기가 이 텍스트를 읽지 않았습니다. 직접 입력해 주세요.", 422)
    if resp.stop_reason == "max_tokens":
        raise AiReadError("AI_READ_TOO_LONG", "Too much text in one read.",
                          "한 번에 읽기엔 화면이 너무 많습니다. 나눠서 올려 주세요.", 422)
    text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
    try:
        return json.loads(text)
    except (TypeError, ValueError) as exc:
        raise AiReadError("AI_READ_UPSTREAM", "The reader returned an unreadable answer.",
                          "판독 결과를 읽지 못했습니다.", 502) from exc


# ── server-side checks ───────────────────────────────────────────────

_NUM_TOKEN = re.compile(r"[+\-−]?\$?\d[\d,]*(?:\.\d+)?")


def printed_numbers(text: str) -> set[float]:
    """Every number printed in the text, sign dropped ("+1,234원" → 1234.0)."""
    out: set[float] = set()
    for m in _NUM_TOKEN.finditer(text):
        s = re.sub(r"[+\-−$,]", "", m.group(0))
        try:
            out.add(abs(float(s)))
        except ValueError:
            continue
    return out


def _printed(v: Any, nums: set[float]) -> bool:
    return isinstance(v, (int, float)) and any(abs(abs(v) - n) < 1e-6 for n in nums)


def _close(a: float, b: float, usd: bool) -> bool:
    tol = max(0.011 if usd else 1.0, abs(b) * 0.005)
    return abs(a - b) <= tol


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _plain(v: float) -> int | float:
    return int(v) if float(v).is_integer() else v


def _cell(value: Any, status: str, ok: bool) -> dict[str, Any]:
    """Filled only when read/derived AND proven; otherwise a hint for the user."""
    if value is None or status == "blank":
        return {"value": None}
    if ok and status in ("read", "derived"):
        return {"value": _plain(value)}
    return {"value": None, "hint": str(_plain(value))}


def _stock_cells(stock: Any, status: str, usd: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    """(name, code). A code is a 6-digit KRX code, or a ticker on a USD row —
    "GS" / "NHN" on a won row are Korean names, not tickers."""
    s = str(stock or "").strip()
    if not s or status == "blank":
        return {"value": None}, {"value": None}
    is_code = bool(re.fullmatch(r"\d{6}", s)) or (usd and bool(re.fullmatch(r"[A-Z][A-Z.\-]{0,5}", s)))
    cell = {"value": s} if status == "read" else {"value": None, "hint": s}
    return ({"value": None}, cell) if is_code else (cell, {"value": None})


def check_holding(row: dict[str, Any], nums: set[float]) -> dict[str, Any]:
    cur = row.get("currency")
    usd = cur == "USD"
    q, p = _num(row.get("shares")), _num(row.get("avg_cost"))
    qs, ps = row.get("shares_status", "blank"), row.get("avg_cost_status", "blank")
    ev = {k: (_num(v) if _printed(v, nums) else None) for k, v in (row.get("evidence") or {}).items()}
    flags = ["ai_read"]
    if row.get("truncated"):
        q = p = None
    # A "read" number must be printed in the text the model was given.
    if q is not None and qs == "read" and not _printed(q, nums):
        qs = "guessed"
    if p is not None and ps == "read" and not _printed(p, nums):
        ps = "guessed"
    targets: list[float] = []
    if ev.get("cost") is not None:
        targets.append(ev["cost"])
    if ev.get("value") is not None and ev.get("pl") is not None:
        targets += [ev["value"] - ev["pl"], ev["value"] + ev["pl"]]  # P/L sign may be lost by OCR
    proven = False
    if q and p:
        if any(_close(q * p, t, usd) for t in targets):
            proven = True
        elif ev.get("current") is not None and ev.get("pl") is not None and \
                _close(abs((ev["current"] - p) * q), abs(ev["pl"]), usd):
            proven = True
    relation_printed = bool(targets) or (ev.get("current") is not None and ev.get("pl") is not None)
    if q and p and relation_printed and not proven:
        flags.append("amount_mismatch")
        q = p = None
    if ps == "derived" and not proven:
        ps = "guessed"
    if proven:
        flags.append("cross_checked")
    name, code = _stock_cells(row.get("stock"), row.get("stock_status", "blank"), usd)
    return {
        "name": name, "code": code,
        "shares": _cell(q, qs, proven), "avg_cost": _cell(p, ps, proven),
        "currency": cur if cur in ("KRW", "USD") else None,
        "truncated": bool(row.get("truncated")), "flags": flags,
    }


def check_fill(row: dict[str, Any], nums: set[float]) -> dict[str, Any]:
    cur = row.get("currency")
    usd = cur == "USD"
    q, p = _num(row.get("shares")), _num(row.get("price"))
    qs, ps = row.get("shares_status", "blank"), row.get("price_status", "blank")
    amount = _num((row.get("evidence") or {}).get("amount"))
    if amount is not None and not _printed(amount, nums):
        amount = None
    if q is not None and qs == "read" and not _printed(q, nums):
        qs = "guessed"
    if p is not None and ps == "read" and not _printed(p, nums):
        ps = "guessed"
    flags = ["ai_read"]
    proven = bool(q and p and amount is not None and _close(q * p, amount, usd))
    if q and p and amount is not None and not proven:
        flags.append("amount_mismatch")
        q = p = None
    if proven:
        flags.append("cross_checked")
    date = row.get("date")
    date_ok = isinstance(date, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", date))
    time = row.get("time")
    time_ok = isinstance(time, str) and bool(re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?", time))
    side = row.get("side")
    name, code = _stock_cells(row.get("stock"), row.get("stock_status", "blank"), usd)
    return {
        "name": name, "code": code,
        # `action` (buy/sell), like the /image payload — the route's legal
        # scrub skips that key and rewrites a trade label anywhere else.
        "action": {"value": side} if side in ("buy", "sell") else {"value": None},
        "shares": _cell(q, qs, proven), "price": _cell(p, ps, proven),
        "amount": {"value": _plain(amount)} if proven else {"value": None},
        "date": {"value": date} if date_ok else {"value": None, "hint": str(row.get("date_hint") or "") or None},
        "time": {"value": time} if time_ok else {"value": None},
        "currency": cur if cur in ("KRW", "USD") else None,
        "flags": flags,
    }


_POSITIVE = {"holdings": {"holdings", "position_detail"}, "fills": {"fills"}}


def read_screens(kind: str, texts: list[str], client=None) -> list[dict[str, Any]]:
    """Masked screen texts → per-screen {screen_type, reason, rows}, rows checked here."""
    if kind not in KINDS:
        raise AiReadError("AI_READ_INVALID", "Unknown kind.", "알 수 없는 종류입니다.", 400)
    masked = [mask_text(t) for t in texts]
    # Never cut a text: a truncated paste would silently lose rows.
    if any(len(t) > MAX_TEXT_CHARS for t in masked):
        raise AiReadError("AI_READ_TOO_LONG", "A text is too long for one read.",
                          "한 번에 읽기엔 텍스트가 너무 깁니다. 나눠서 올려 주세요.", 422)
    answer = _call(kind, masked, client=client)
    by_index = {s.get("index"): s for s in answer.get("screens") or [] if isinstance(s, dict)}
    out = []
    for i, text in enumerate(masked):
        s = by_index.get(i) or {"screen_type": "other", "reason": "", "rows": []}
        nums = printed_numbers(text)
        positive = s.get("screen_type") in _POSITIVE[kind]
        check = check_holding if kind == "holdings" else check_fill
        rows = [check(r, nums) for r in (s.get("rows") or []) if isinstance(r, dict)] if positive else []
        out.append({"screen_type": s.get("screen_type") or "other", "reason": str(s.get("reason") or "")[:200],
                    "rows": rows})
    return out
