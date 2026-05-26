"""Support chatbot — answers ONLY customer-support questions.

Legal posture (SHIP-BLOCKER)
============================
PivoxQuant runs on the 자본시장법 §101 면제 트랙. The support chatbot must
NEVER surface investment advice / 권유 / 추천 / 매수·매도 지시 / 목표가 /
전망 / 수익률 예측. A single leak collapses the exemption track.

Three defense layers, in order:

1. **Pre-filter (`_is_investment_question`)** — runs BEFORE any model call.
   Conservative regex + forbidden-term assist. If it fires we return a
   fixed deflection string and spend ZERO Anthropic tokens.
2. **System prompt** — instructs the model to refuse investment questions
   and answer ``can_answer=false``.
3. **★ Post-filter (the core fix)** — after the model replies, the RAW
   answer (pre-scrub) is checked against ``is_compliant`` +
   ``contains_forbidden_term`` + ``_has_advice_vocab``. If ANY fires we
   **discard** the answer and force ``can_answer=False`` (→ human
   escalation). We do NOT "scrub-then-return" — scrubbing a tainted answer
   would launder an investment-advice leak into plausible-looking copy.
   ``safe_scrub`` here is only a final no-op safety net on an
   already-clean string.

Cost: existing ANTHROPIC_API_KEY, existing Haiku model. No new spend.

Zero-cost FAQ (``_faq_match``)
==============================
Common questions are answered from a curated, compliant FAQ table with NO
model call, so the bot stays useful even when the Anthropic balance is empty
(every model call would otherwise fail → escalate). The model is only a
fallback for questions the FAQ table can't match. Individual-handling topics
(환불 처리 / 청구 오류 / 계정 삭제 처리) are intentionally absent from the table
so they fall through to human escalation.

The Claude fallback is gated behind ``SUPPORT_CHAT_LLM_ENABLED`` (default OFF,
because the Anthropic balance is unfunded). With it off the bot is fully
deterministic — FAQ match → answer, otherwise → human escalation, zero API
calls. Flip the env var to ``1`` once credits are funded to enable the model
fallback for FAQ-missed questions; no code change required.
"""
from __future__ import annotations

import json
import logging
import os
import re

from services.ai.service import MODEL
from services.container import ai
from services.legal_filter import is_compliant, safe_scrub
from services.legal.forbidden_terms import contains_forbidden_term

logger = logging.getLogger(__name__)


# ── Knowledge base (FAQ + service facts) ────────────────────────────────────
# IMPORTANT: this text is fed to the model AND is surfaced verbatim in FAQ
# copy, so it must itself be compliant. Do NOT use 매수/매도/권유/사라/팔아/
# 전망/목표가 tokens here — otherwise legitimate answers grounded in the KB
# would trip the post-filter. Use information-only phrasing instead.
SUPPORT_KB = """\
[서비스 성격 / 면책]
PivoxQuant는 미국·한국 주식의 퀀트 지표와 시장 데이터를 정보 목적으로
제공하는 분석 도구입니다. 개별 투자 자문을 제공하지 않으며, 특정 매매
행동을 지시하거나 권하지 않습니다. 특정 가격이나 시세 예측도 제공하지
않습니다. 모든 판단과 책임은 이용자 본인에게 있습니다.

[요금제]
- Free: 기본 지표 열람, 포트폴리오 기록.
- Pro (월 ₩9,900): 확장 분석, 정기 리포트(이메일/PDF) 등.
- Premium (월 ₩19,900): Pro 기능 전체 + 고급 분석.
요금제 변경/해지는 설정 > 구독에서 가능합니다.

[결제 / 환불 / 구독]
결제 수단 변경, 영수증, 청구 오류, 환불 같은 개별 사안은 담당자가
직접 확인해 처리합니다. 문의를 남겨 주시면 순차적으로 회신드립니다.

[계정 / 로그인]
로그인은 Google 또는 Kakao 계정으로 진행합니다. 별도의 이메일/비밀번호
가입은 없습니다. 로그인이 안 되면 브라우저 캐시 삭제 후 재시도해 주세요.

[회원 탈퇴 / 개인정보(PIPA)]
설정 > 계정에서 탈퇴를 신청할 수 있습니다. 신청 후 30일의 유예 기간이
있으며, 그 안에 다시 로그인하면 탈퇴가 취소됩니다. 유예 기간이 지나면
개인정보가 파기됩니다.

[데이터 출처]
가격·재무·공시 데이터는 공식 라이선스를 받은 제공처에서만 가져옵니다.
비공식 스크래핑 데이터는 사용하지 않습니다.

[PWA 설치]
PivoxQuant는 PWA입니다. 모바일/데스크톱 브라우저의 "홈 화면에 추가"
또는 "앱 설치"로 설치할 수 있습니다.

[시그널 라벨 의미]
시그널은 POSITIVE / NEGATIVE / NEUTRAL 세 가지 정보성 라벨로 표시됩니다.
이는 과거·현재 지표의 방향을 중립적으로 설명하는 표시일 뿐, 특정 매매
행동을 지시하거나 권하는 신호가 아닙니다.

[문의 방법]
앱 내 고객지원 > 문의하기에서 문의를 남기시면 담당자가 확인 후
회신드립니다. 결제·계정·기술 문제 모두 이곳에서 접수됩니다.
"""


SUPPORT_SYSTEM_PROMPT = (
    "너는 PivoxQuant 고객지원 챗봇이야. 아래 [지식베이스] 범위 안에서만 "
    "한국어로 친절하고 간결하게 답해. 결제/계정/로그인/회원탈퇴/사용법/요금제/"
    "데이터 출처/PWA 설치/시그널 라벨 의미에 대해서만 답한다. "
    "투자 자문/권유/추천/매수·매도/목표가/전망/수익률 예측/'오를까 내릴까'/"
    "'사야 하나' 류의 질문에는 절대 답하지 말고 can_answer=false 로 응답해. "
    "지식베이스로 풀 수 없거나, 환불 처리·계정 삭제·결제 오류처럼 사람이 직접 "
    "처리해야 하는 문의도 can_answer=false 로 응답해. "
    "반드시 JSON 하나로만 응답해: {\"answer\":\"...\",\"can_answer\":true|false}. "
    "can_answer=false 이면 answer 는 \"\" (빈 문자열) 로 둬."
)


MAX_TOKENS = 600


def _llm_enabled() -> bool:
    """Whether the Claude fallback is allowed to run.

    Default OFF. The Anthropic balance is not funded, so attempting a model
    call would only 400 ("credit balance too low") after wasting a round-trip
    and spamming error logs. With the flag off the bot is fully deterministic:
    FAQ match → answer, otherwise → human escalation, ZERO API calls.

    When credits are funded, set ``SUPPORT_CHAT_LLM_ENABLED=1`` to turn the
    Claude fallback on for FAQ-missed questions. No code change needed.
    """
    return os.environ.get("SUPPORT_CHAT_LLM_ENABLED", "0").strip().lower() in (
        "1", "true", "yes", "on",
    )


# ── Layer 1: pre-filter (no model call) ─────────────────────────────────────
_INVESTMENT_PATTERNS = [
    re.compile(p) for p in (
        r"(?<!과)매수",
        r"(?<!과)매도",
        r"사도\s*(되|돼|될까|괜찮)",
        r"살까",
        r"팔까",
        r"팔아",
        r"사야\s*(하|할|돼|되)",
        r"팔아야\s*(하|할|돼|되)",
        r"사라\b",
        r"사세요",
        r"파세요",
        r"손절",
        r"익절",
        r"오를까",
        r"내릴까",
        r"오를\s*것",
        r"내릴\s*것",
        r"전망",
        r"목표가",
        r"적정가",
        r"수익률\s*(전망|예측|예상)",
        r"얼마나\s*(오르|내리|떨어)",
        r"투자할까",
        r"투자해도\s*(되|돼|될까)",
        r"추천\s*종목",
        r"종목\s*추천",
        r"뭐\s*(사|살|투자)",
        r"어떤\s*(종목|주식).*(사|살|좋)",
        r"상승할까",
        r"하락할까",
        r"반등할까",
        r"떨어질까",
        r"급등|급락",
    )
]
_INVESTMENT_PATTERNS_I = [
    re.compile(p, re.IGNORECASE) for p in (
        r"\bshould\s+i\s+(buy|sell|invest|hold)\b",
        r"\bbuy\s+or\s+sell\b",
        r"\b(target\s*price|price\s*target)\b",
        r"\bwill\s+\w+\s+(go\s+up|go\s+down|rise|fall|drop|moon)\b",
        r"\bgood\s+(buy|investment|stock\s+to\s+buy)\b",
        r"\b(worth\s+(buying|investing)|good\s+time\s+to\s+(buy|sell))\b",
    )
]


# ── Advice vocabulary (question + answer side; low false-positive) ──────────
# These target "investment-action urging" idioms that do NOT appear in the
# (compliant) disclaimer/KB copy, so checking them against an *answer* won't
# nuke a legitimate support reply.
_ADVICE_PATTERNS = [
    re.compile(p) for p in (
        r"물타기",
        r"불타기",
        r"추격\s*매수",
        r"추매",
        r"존버",
        r"평단",
        r"손익\s*분기",
        r"롱\s*포지션",
        r"숏\s*포지션",
        r"포지션\s*(을|를)?\s*(잡|늘|줄|정리|진입|청산|유지)",
        r"비중\s*(을|를)?\s*(늘|줄|확대|축소|조절|조정)",
        r"매입\s*(기회|타이밍|시점|적기)",
        r"매입하",
        r"들어가도\s*(좋|괜찮|될|됩|돼|되)",
        r"들어가야\s*(좋|할|하|됩|돼|되)",
        r"(매수|매도|진입|매매|투자)\s*타이밍",
        r"타이밍\s*(이|은|는|을|를)?\s*(좋|괜찮|적절|어때|언제|놓치)",
        r"지금\s*(이|가)?\s*(매수|매도|진입|투자|매입)?\s*(기회|찬스|적기|타이밍)",
        r"유망\s*(종목|주식|주\b|기업)",
        r"저평가|고평가",
        r"사면\s*(어때|될|좋|괜찮|돼|이득)",
        r"지금\s*(매수|매도|진입|들어가|투자)",
        # "지금 사" but NOT 사용/사이트/사진/사업/사례/사연/사항/사유/사회/사무/사과
        r"지금\s*사(?!용|이트|진|업|례|연|항|유|회|무|과)",
    )
]

# forbidden_terms hits that we IGNORE for blocking — bare buy/sell/매수/매도
# are too noisy ("buy the Pro plan", "과매수"). Only the others (추천/조언/
# recommend/advice/...) are trusted deny signals here.
_FORBIDDEN_IGNORE = {"매수", "매도", "buy", "sell", "hold"}


def _has_advice_vocab(text: str) -> bool:
    if not text or not isinstance(text, str):
        return False
    return any(p.search(text) for p in _ADVICE_PATTERNS)


def _is_investment_question(msg: str) -> bool:
    """True when *msg* looks like an investment question. Conservative —
    runs before any model call to spend zero tokens on advice questions."""
    if not msg or not isinstance(msg, str):
        return False
    for p in _INVESTMENT_PATTERNS:
        if p.search(msg):
            return True
    for p in _INVESTMENT_PATTERNS_I:
        if p.search(msg):
            return True
    if _has_advice_vocab(msg):
        return True
    # forbidden-term assist: only trust non-bare-buy/sell hits.
    hit = contains_forbidden_term(msg)
    if hit is not None and hit not in _FORBIDDEN_IGNORE:
        return True
    return False


# ── Layer 0: zero-cost FAQ retrieval (no model call) ───────────────────────
# Curated, COMPLIANT answers for common questions. Matched deterministically by
# keyword overlap so the bot answers even with an empty Anthropic balance.
# Answers must stay free of 매수/매도/추천/권유/사라/팔아/전망/목표가 tokens
# (they are surfaced verbatim to users and re-checked by the post-filter).
# Individual-handling topics (환불 처리/청구 오류/계정 삭제 처리) are absent on
# purpose → those questions match nothing → human escalation.
_FAQ_ENTRIES: tuple[dict, ...] = (
    {
        "keywords": ("요금", "요금제", "구독료", "플랜", "pro", "프로", "premium",
                     "프리미엄", "유료", "월 9", "9,900", "19,900"),
        "answer": (
            "요금제는 Free(무료), Pro(월 ₩9,900), Premium(월 ₩19,900) 세 가지예요. "
            "Pro는 확장 분석과 정기 리포트, Premium은 Pro 기능 전체에 고급 분석이 "
            "더해집니다. 요금제 변경·해지는 설정 > 구독에서 하실 수 있어요."
        ),
    },
    {
        "keywords": ("구독 변경", "구독 해지", "구독 취소", "해지", "플랜 변경",
                     "플랜 바꾸", "구독 바꾸", "구독 끊"),
        "answer": "구독 변경과 해지는 설정 > 구독 메뉴에서 직접 하실 수 있어요.",
    },
    {
        "keywords": ("로그인", "로그아웃", "접속이 안", "구글", "카카오", "google",
                     "kakao", "비밀번호", "계정 연결", "로그인이 안"),
        "answer": (
            "로그인은 Google 또는 Kakao 계정으로 진행돼요. 별도 이메일/비밀번호 가입은 "
            "없습니다. 로그인이 안 되면 브라우저 캐시를 삭제하고 다시 시도해 주세요. "
            "그래도 안 되면 문의를 남겨 주시면 확인해 드릴게요."
        ),
    },
    {
        "keywords": ("탈퇴", "회원탈퇴", "계정 삭제", "데이터 삭제", "개인정보 삭제",
                     "그만 쓰", "그만 사용"),
        "answer": (
            "회원 탈퇴는 설정 > 계정에서 신청하실 수 있어요. 신청 후 30일의 유예 기간이 "
            "있고, 그 안에 다시 로그인하면 탈퇴가 취소됩니다. 유예 기간이 지나면 "
            "개인정보가 파기돼요."
        ),
    },
    {
        "keywords": ("데이터 출처", "데이터 어디", "출처", "어디서 가져", "어떤 데이터",
                     "데이터 신뢰", "데이터는 정확"),
        "answer": (
            "가격·재무·공시 데이터는 공식 라이선스를 받은 제공처에서만 가져와요. "
            "비공식 스크래핑 데이터는 사용하지 않습니다."
        ),
    },
    {
        "keywords": ("설치", "pwa", "홈 화면", "홈화면", "앱 설치", "앱으로",
                     "바탕화면", "아이콘", "앱처럼"),
        "answer": (
            "PivoxQuant는 PWA라서 앱처럼 설치할 수 있어요. 모바일/데스크톱 브라우저의 "
            "\"홈 화면에 추가\" 또는 \"앱 설치\"를 사용하시면 됩니다."
        ),
    },
    {
        "keywords": ("시그널", "라벨", "positive", "negative", "neutral",
                     "신호 의미", "신호가 무슨", "표시가 무슨", "무슨 뜻"),
        "answer": (
            "시그널은 POSITIVE / NEGATIVE / NEUTRAL 세 가지 정보성 라벨이에요. "
            "지표의 방향을 중립적으로 설명하는 표시일 뿐, 특정 매매 행동을 지시하거나 "
            "권하는 신호는 아닙니다."
        ),
    },
    {
        "keywords": ("문의", "고객센터", "고객지원", "어디로 연락", "어떻게 연락",
                     "상담", "물어보려면"),
        "answer": (
            "앱 내 고객지원 > 문의하기에서 문의를 남기시면 담당자가 확인 후 회신드려요. "
            "결제·계정·기술 문제 모두 이곳에서 접수됩니다."
        ),
    },
)


def _faq_match(message: str) -> str | None:
    """Return a curated FAQ answer for *message*, or None when there is no
    confident single match. Pure python — no model call (works at zero API
    balance). Conservative: ambiguous ties return None → escalation."""
    if not message or not isinstance(message, str):
        return None
    m = message.lower()
    best_score = 0
    best_answer: str | None = None
    tie = False
    for entry in _FAQ_ENTRIES:
        score = sum(1 for kw in entry["keywords"] if kw.lower() in m)
        if score > best_score:
            best_score, best_answer, tie = score, entry["answer"], False
        elif score == best_score and score > 0:
            tie = True
    if best_score >= 1 and not tie:
        return best_answer
    return None


# ── History sanitisation ────────────────────────────────────────────────────
def _sanitize_history(history) -> list[dict]:
    if not isinstance(history, list):
        return []
    out: list[dict] = []
    for turn in history:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role")
        content = turn.get("content")
        if role not in ("user", "assistant"):
            continue
        if not isinstance(content, str) or not content:
            continue
        out.append({"role": role, "content": content[:1000]})
    return out[-10:]


# ── Response parsing ─────────────────────────────────────────────────────────
def _extract_text(resp) -> str:
    """Concatenate text from an Anthropic Messages API response."""
    parts: list[str] = []
    content = getattr(resp, "content", None)
    if content is None and isinstance(resp, dict):
        content = resp.get("content")
    if not content:
        return ""
    for block in content:
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts).strip()


def _parse_json_obj(raw_text: str) -> dict:
    """Robustly pull a JSON object out of model text (strips code fences,
    falls back to first '{' .. last '}')."""
    if not raw_text:
        return {}
    text = raw_text.strip()
    # Strip ```json ... ``` / ``` ... ``` fences.
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start:end + 1])
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return {}


def answer_support_question(message, history=None) -> dict:
    """Answer a support question. Returns ``{"answer": str, "can_answer": bool}``.

    ``can_answer=False`` means: route to a human (escalate). Never returns a
    laundered investment-advice answer — tainted answers are discarded.
    """
    deny = {"answer": "", "can_answer": False}

    if not message or not isinstance(message, str) or not message.strip():
        return deny

    # Defense-in-depth: never answer an investment question even if the route
    # guard was bypassed (the route normally deflects these before calling us).
    if _is_investment_question(message):
        return deny

    # Layer 0: zero-cost FAQ retrieval — answers common questions with NO model
    # call, so the bot stays useful when the Anthropic balance is empty. The
    # curated answer is still run through the post-filter as insurance.
    faq = _faq_match(message)
    if (
        faq is not None
        and is_compliant(faq)
        and contains_forbidden_term(faq) is None
        and not _has_advice_vocab(faq)
    ):
        return {"answer": faq, "can_answer": True}

    # Model fallback (only for questions the FAQ table can't match).
    # Gated behind SUPPORT_CHAT_LLM_ENABLED — default OFF because the Anthropic
    # balance is unfunded (a call would 400 then escalate anyway). Off ⇒ FAQ
    # miss escalates immediately with zero API calls (deterministic).
    if not _llm_enabled() or not ai.available or ai.client is None:
        return deny

    messages = _sanitize_history(history)
    messages.append({"role": "user", "content": message[:2000]})
    system = SUPPORT_SYSTEM_PROMPT + "\n\n[지식베이스]\n" + SUPPORT_KB

    try:
        resp = ai.client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
        )
    except Exception as exc:  # pragma: no cover — network/SDK failure path
        logger.warning("support chatbot model call failed: %s", exc)
        return deny

    raw_text = _extract_text(resp)
    obj = _parse_json_obj(raw_text)

    answer = obj.get("answer", "")
    can_answer = obj.get("can_answer", False)
    if not isinstance(answer, str):
        answer = ""
    can_answer = bool(can_answer) and bool(answer.strip())
    if not can_answer:
        return deny

    raw = answer  # raw model answer, BEFORE any scrub

    # ★ Post-filter (SHIP-BLOCKER core): discard tainted answers outright.
    if (
        not is_compliant(raw)
        or contains_forbidden_term(raw) is not None
        or _has_advice_vocab(raw)
    ):
        logger.warning(
            "support chatbot answer blocked by post-filter; escalating to human."
        )
        return deny  # discard + escalate. NEVER scrub-then-return.

    # scrub is a final no-op safety net on already-clean text.
    scrubbed = safe_scrub(raw, context="support_chat")
    final = scrubbed if scrubbed else raw

    if not final or not final.strip():
        return deny

    return {"answer": final, "can_answer": True}


__all__ = [
    "SUPPORT_KB",
    "SUPPORT_SYSTEM_PROMPT",
    "answer_support_question",
    "_is_investment_question",
]
