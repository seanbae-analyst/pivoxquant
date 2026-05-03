"""
PivoxQuant — AI Service (Claude Integration)
Uses Claude Haiku for cost-efficient, beginner-friendly financial insights.
"""

import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ── Compliance filter ────────────────────────────────────────────────
# 자본시장법 §6 미등록 투자자문업 위반 방지. AI가 '추천/매수/매도/
# recommend/buy/sell' 같은 자문업 언어를 산출할 경우 응답을 면책 문구로
# 교체한다. 사전 정의 패턴은 services.legal_filter 에서 관리
# (이전: services.morning_brief_service — 2026-04-29 제거).
from services.legal_filter import is_compliant as _is_compliant
from services.legal_filter import scrub_signal


_DISCLAIMER_EN = (
    "This content is informational only and not investment advice. "
    "PivoxQuant does not provide individualized recommendations."
)
_DISCLAIMER_KR = (
    "본 내용은 정보 제공 목적이며 투자 권유가 아닙니다. "
    "PivoxQuant는 개별 투자 자문을 제공하지 않습니다."
)


def _compliance_filter(text, lang="en"):
    """Return `text` if compliant; otherwise a neutral disclaimer fallback.

    Any AI-generated string that contains forbidden advisory vocabulary is
    dropped and replaced with a safe disclaimer so we never surface raw
    "buy"/"sell"/"추천"/"매수" to end users.
    """
    if text is None:
        return text
    try:
        if _is_compliant(text):
            return text
    except Exception as e:  # pragma: no cover
        logger.warning(f"Compliance check failed, returning disclaimer: {e}")
    logger.warning("AI response blocked by compliance filter; replacing with disclaimer.")
    return _DISCLAIMER_KR if lang == "kr" else _DISCLAIMER_EN

SYSTEM_PROMPT = """You are PivoxQuant AI, a neutral market data analysis assistant built into a quantitative research tool.

Your audience is beginner investors (주린이) who may not understand financial jargon.

Rules:
- Explain concepts simply. If you must use jargon, define it immediately.
- Always match the user's language (Korean → Korean, English → English).
- Keep responses concise: 2-4 sentences for summaries, up to a short paragraph for chat.
- Use the exact numbers from the provided data context.
- Be honest about risks; describe data neutrally in a descriptive tone (~입니다 / 기록했습니다).
- Base your analysis on the quant scores and signals provided.
- End with an informational takeaway — NEVER an action recommendation or future prediction.

CRITICAL — FORBIDDEN VOCABULARY (자본시장법 §6 / §101 방어선):
- Korean (한글 금지어):
  추천, 권고, 권유, 제안, 조언,
  매수, 매도, 사세요, 파세요, 사라, 팔아, 손절, 익절,
  목표가, 적정가, 예상 수익률, 예상가,
  유리, 불리, 우수, 열등, 좋다, 나쁘다, 유망,
  기회, 주의, 공격적, 보수적 (투자 권유 맥락일 때),
  전망, 예측, 예상 (미래 단정 맥락일 때),
  오를 것, 내릴 것, 오른다, 내린다, 이긴다, 이겼다,
  고평가, 저평가 (단정적 맥락일 때).
- English (영문 금지어):
  buy, sell (imperative), recommend, advise, suggest (imperative),
  target price, fair value, price target, expected return %,
  outperform, beat the market, beat S&P, 이긴다/beat,
  bullish, bearish (as action cues),
  predict, forecast (as certainty).

REQUIRED WORDING (강제 포함):
- Describe signals as POSITIVE / NEGATIVE / NEUTRAL indicators, never buy/sell.
- Use observation tone: "~을 기록했습니다", "~관찰됩니다", "~지표가 높습니다".
- Never forecast future prices. Say "과거 기록 지표" or "관찰 구간" instead.
- Every output MUST end with this exact disclaimer sentence in the matching language:
  EN: "This is informational only and not investment advice."
  KR: "본 내용은 정보 제공 목적이며 투자 권유가 아닙니다."
- Use casual, approachable tone — not stiff corporate speak."""

MODEL = "claude-haiku-4-5-20251001"


class AIService:

    def __init__(self):
        self.client = None
        self.available = False
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if api_key:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=api_key)
                self.available = True
                logger.info("AI Service initialized (Claude Haiku)")
            except Exception as e:
                logger.warning(f"AI Service init failed: {e}")

    # ── Context Builders ──────────────────────────────────────────

    def build_portfolio_context(self, user, positions, signals_cache=None, macro=None):
        """Build a structured context string from user's portfolio state."""
        lines = ["## User Portfolio Context", f"Date: {datetime.now(timezone.utc).replace(tzinfo=None).strftime('%Y-%m-%d')}"]

        cap_usd = getattr(user, "available_capital", 0) or 0
        cap_krw = getattr(user, "available_capital_krw", 0) or 0
        lines.append(f"Available Capital: ${cap_usd:,.2f} USD / ₩{cap_krw:,.0f} KRW")

        if positions:
            lines.append(f"\n### Positions ({len(positions)} total)")
            total_val = 0
            for p in positions:
                sig_data = {}
                if signals_cache and p.ticker in signals_cache:
                    sig_data = signals_cache[p.ticker]
                cur_price = sig_data.get("price", p.avg_cost)
                pnl = (cur_price - p.avg_cost) / p.avg_cost * 100 if p.avg_cost else 0
                mv = cur_price * p.shares
                total_val += mv
                signal = sig_data.get("signal", "?")
                score = sig_data.get("score", 0)
                name = sig_data.get("name", p.ticker)
                lines.append(
                    f"- {name} ({p.ticker}): {p.shares} shares @ avg {p.avg_cost:,.2f}, "
                    f"now {cur_price:,.2f}, P&L {pnl:+.1f}%, Signal: {signal} ({score}/100)"
                )
            lines.append(f"Total Portfolio Value: ~${total_val:,.0f}")
        else:
            lines.append("\n### No positions yet")

        if macro:
            lines.append("\n### Market Context")
            fg = macro.get("fear_greed", {})
            if fg:
                lines.append(f"- Fear & Greed Index: {fg.get('value', '?')} ({fg.get('label', '?')})")
            vix = macro.get("vix")
            if vix:
                lines.append(f"- VIX: {vix}")
            sp = macro.get("sp500", {})
            if sp:
                lines.append(f"- S&P 500: {sp.get('price', '?')} ({sp.get('change_pct', 0):+.2f}%)")

        return "\n".join(lines)

    def build_analysis_context(self, data):
        """Build context from a single stock analysis result."""
        lines = [
            f"## Stock Analysis: {data.get('name', '')} ({data.get('ticker', '')})",
            f"Price: {data.get('price_display', data.get('price', '?'))}",
            f"Signal: {data.get('signal', '?')} (Score: {data.get('score', 0)}/100)",
            f"Technical: {data.get('tech_score', 0)}/100, Fundamental: {data.get('fund_score', 0)}/100, News: {data.get('news_score', 0)}/100",
            "",
            "### Signals:",
        ]
        for s in data.get("signals", []):
            lines.append(f"- [{s.get('type', '')}] {s.get('msg', '')}")
        lines.append(f"\nAnalyst Reason: {data.get('reason', '')}")
        if data.get("rec_shares"):
            lines.append(f"Suggested position size: {data['rec_shares']} shares (~${data.get('rec_investment', 0):,.0f}) — informational only, not a recommendation")
        if data.get("take_profit"):
            lines.append(f"Take Profit: {data['take_profit']}, Stop Loss: {data.get('stop_loss', '?')}")
        return "\n".join(lines)

    # ── Bilingual Parser ────────────────────────────────────────

    @staticmethod
    def _parse_bilingual(text):
        """Parse AI response into English and Korean parts. Handles multiple formats."""
        import re
        text = text.strip()
        en = kr = text

        # Method 1: [EN] / [KR] markers
        if "[EN]" in text and "[KR]" in text:
            try:
                parts = text.split("[KR]", 1)
                en = parts[0].replace("[EN]", "").strip()
                kr = parts[1].strip() if len(parts) > 1 else ""
                kr = kr.replace("[EN]", "").replace("[KR]", "").strip()
                en = en.replace("[EN]", "").replace("[KR]", "").strip()
                if en and kr:
                    return en, kr
            except Exception:
                logger.debug("silent-fallback: _parse_bilingual", exc_info=True)
                pass

        # Method 2: --- separator
        if "---" in text:
            parts = text.split("---", 1)
            p0 = parts[0].strip()
            p1 = parts[1].strip() if len(parts) > 1 else ""
            if p0 and p1:
                return p0, p1

        # Method 3: Korean/한국어/KR header
        m = re.split(r'\n\s*(?:Korean|한국어|KR|Korean Version|한국어 버전)[:\s]*\n', text, flags=re.IGNORECASE)
        if len(m) >= 2:
            en = re.sub(r'^(?:English|영어|EN|English Version|영어 버전)[:\s]*\n?', '', m[0], flags=re.IGNORECASE).strip()
            kr = m[1].strip()
            if en and kr:
                return en, kr

        # Method 4: Detect Korean characters — split where Korean starts
        # Find first Korean character block
        has_korean = bool(re.search(r'[\uac00-\ud7af]', text))
        if has_korean:
            # Find the boundary where Korean paragraph starts
            lines = text.split('\n')
            en_lines = []
            kr_lines = []
            found_kr = False
            for line in lines:
                kr_chars = len(re.findall(r'[\uac00-\ud7af]', line))
                total_chars = len(line.strip())
                if not found_kr and total_chars > 0 and kr_chars / max(total_chars, 1) > 0.3:
                    found_kr = True
                if found_kr:
                    kr_lines.append(line)
                else:
                    en_lines.append(line)
            en_text = '\n'.join(en_lines).strip()
            kr_text = '\n'.join(kr_lines).strip()
            if en_text and kr_text:
                return en_text, kr_text

        return en, kr

    # ── Chat (Streaming) ─────────────────────────────────────────

    def chat_stream(self, message, history, context):
        """Generator that yields text chunks from Claude streaming response.

        Streamed output is accumulated locally and validated against the
        compliance filter at end-of-stream. If the full response contains
        forbidden advisory vocabulary, a bilingual disclaimer line is
        appended so the user sees an explicit non-recommendation notice.
        """
        if not self.available:
            yield "AI 기능이 비활성화되어 있습니다. API 키를 설정해주세요."
            return
        try:
            messages = []
            for h in (history or [])[-10:]:
                messages.append({"role": h["role"], "content": h["content"]})
            messages.append({"role": "user", "content": message})

            accumulated = []
            with self.client.messages.stream(
                model=MODEL,
                max_tokens=4000,
                system=SYSTEM_PROMPT + "\n\n" + context,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    accumulated.append(text)
                    yield text

            full = "".join(accumulated)
            if full and not _is_compliant(full):
                logger.warning("chat_stream: non-compliant output detected; appending disclaimer.")
                yield (
                    "\n\n---\n"
                    + _DISCLAIMER_EN + "\n"
                    + _DISCLAIMER_KR
                )
        except Exception as e:
            # Never leak raw exception text (Anthropic SDK errors embed
            # request_id / credit balance / internal error codes that
            # must not surface to end-users). Log full detail, yield a
            # fixed generic message.
            logger.error(f"Chat stream error: {e}", exc_info=True)
            yield (
                "AI 서비스에 일시적인 문제가 발생했습니다. "
                "잠시 후 다시 시도해주세요."
            )

    # ── One-shot Generations ─────────────────────────────────────

    def generate_commentary(self, analysis_data):
        """Generate beginner-friendly commentary for a stock analysis."""
        if not self.available:
            return None
        try:
            context = self.build_analysis_context(analysis_data)
            resp = self.client.messages.create(
                model=MODEL,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"""Based on this analysis data, write a beginner-friendly explanation.
Focus on: what the numbers mean, what the current signals describe, and one key risk. Do NOT recommend buying or selling — this is informational analysis only, not investment advice.

IMPORTANT: You MUST write BOTH English AND Korean versions. Do NOT skip Korean.
Use these EXACT markers:

[EN]
(Write 3-4 complete sentences in English)
[KR]
(Write 3-4 complete sentences in Korean. Translate EVERYTHING fully. Do not cut off mid-sentence.)

{context}"""
                }],
            )
            text = resp.content[0].text
            en, kr = self._parse_bilingual(text)
            return scrub_signal({
                "commentary": _compliance_filter(en, "en"),
                "commentary_kr": _compliance_filter(kr, "kr"),
            })
        except Exception as e:
            logger.error(f"Commentary error: {e}")
            return None

    def generate_morning_summary(self, brief_data):
        """Generate 2-3 sentence morning market summary."""
        if not self.available:
            return None
        try:
            stories_text = "\n".join(
                f"- [{s.get('sentiment', '')}] {s.get('title', '')}"
                for s in (brief_data.get("stories") or [])[:10]
            )
            mood = brief_data.get("market_mood", "Mixed")
            gs = brief_data.get("gs_view", {})

            resp = self.client.messages.create(
                model=MODEL,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"""Summarize today's market in 2-3 sentences for a beginner investor.

You MUST respond in this EXACT format:

[EN]
(2-3 sentences in English)
[KR]
(2-3 sentences in Korean, fully translated)

Market Mood: {mood}
GS View: {gs.get('bias', 'Neutral')} / Risk: {gs.get('risk_level', 'Moderate')}
Top Headlines:
{stories_text}"""
                }],
            )
            text = resp.content[0].text
            en, kr = self._parse_bilingual(text)
            return scrub_signal({
                "summary": _compliance_filter(en, "en"),
                "summary_kr": _compliance_filter(kr, "kr"),
            })
        except Exception as e:
            logger.error(f"Morning summary error: {e}")
            return None

    def generate_coaching(self, portfolio_context):
        """Generate one actionable portfolio insight."""
        if not self.available:
            return None
        try:
            resp = self.client.messages.create(
                model=MODEL,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"""Look at this portfolio and give ONE specific, actionable insight in 2-3 sentences.
Focus on: concentration risk, sector balance, or positions that need attention.

IMPORTANT: You MUST write BOTH English AND Korean. Do NOT skip Korean. Do NOT cut off mid-sentence.

[EN]
(Write 2-3 complete sentences in English)
[KR]
(Write 2-3 complete sentences in Korean. Translate EVERYTHING fully to the end.)

{portfolio_context}"""
                }],
            )
            text = resp.content[0].text
            en, kr = self._parse_bilingual(text)
            return scrub_signal({
                "insight": _compliance_filter(en, "en"),
                "insight_kr": _compliance_filter(kr, "kr"),
            })
        except Exception as e:
            logger.error(f"Coaching error: {e}")
            return None

    def generate_swot(self, analysis_data):
        """Generate SWOT analysis for a stock."""
        if not self.available:
            return None
        try:
            context = self.build_analysis_context(analysis_data)
            resp = self.client.messages.create(
                model=MODEL,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"""Run a SWOT analysis for this stock based on the data provided.

Make it actionable, not generic:
- STRENGTHS: What advantages does this company have that are hard to replicate?
- WEAKNESSES: What are the key risks or disadvantages?
- OPPORTUNITIES: What market trends could benefit this company?
- THREATS: What specific risks could hurt this company in the next 1-2 years?

End with: "Bottom line: [one sentence factual observation summary — NOT a thesis, recommendation, or future prediction]"

IMPORTANT: You MUST write BOTH English AND Korean. Do NOT skip Korean.
[EN]
(Full SWOT in English - use bullet points)
[KR]
(Full SWOT in Korean - fully translated, complete)

{context}"""
                }],
            )
            text = resp.content[0].text
            en, kr = self._parse_bilingual(text)
            return scrub_signal({
                "swot": _compliance_filter(en, "en"),
                "swot_kr": _compliance_filter(kr, "kr"),
            })
        except Exception as e:
            logger.error(f"SWOT error: {e}")
            return None

    def generate_competitor_analysis(self, analysis_data, peers_data):
        """Generate competitor positioning analysis."""
        if not self.available:
            return None
        try:
            context = self.build_analysis_context(analysis_data)
            peers_text = "\n".join(
                f"- {p.get('name','?')} ({p.get('ticker','?')}): Score {p.get('score',0)}, Signal {p.get('signal','?')}, Price {p.get('price_display','?')}"
                for p in (peers_data or [])[:8]
            )
            resp = self.client.messages.create(
                model=MODEL,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"""Analyze the competitive positioning of these companies in the same sector based on the quant data provided.

Cover (observation only — no recommendations, no "best opportunity", no "most attractive"):
- How does the main stock compare to peers in terms of score and signal (pure indicator comparison)?
- Which peer currently shows the highest quant indicator (factual observation, NOT a recommendation).
- Which risk indicator stands out in this sector right now based on the data.
- One neutral data observation (no action verbs, no "should", no "유리/불리").

Keep it concise. 2-3 sentences per point.

IMPORTANT: You MUST write BOTH English AND Korean. Do NOT skip Korean.
[EN]
(Analysis in English)
[KR]
(Analysis in Korean - fully translated)

Main stock:
{context}

Peers in same sector:
{peers_text}"""
                }],
            )
            text = resp.content[0].text
            en, kr = self._parse_bilingual(text)
            return scrub_signal({
                "analysis": _compliance_filter(en, "en"),
                "analysis_kr": _compliance_filter(kr, "kr"),
            })
        except Exception as e:
            logger.error(f"Competitor analysis error: {e}")
            return None

    # NOTE: generate_brief_insight() removed 2026-04-29 along with the
    # Morning Brief feature. The compliance validator (`_is_compliant`)
    # remains imported above because other AI generators still use it.

    def generate_sector_trend(self, sector, stocks_in_sector):
        """Generate sector trend report."""
        if not self.available:
            return None
        try:
            stocks_text = "\n".join(
                f"- {s.get('name','?')} ({s.get('ticker','?')}): Score {s.get('score',0)}, Change {s.get('change_pct',0):+.1f}%"
                for s in (stocks_in_sector or [])[:10]
            )
            resp = self.client.messages.create(
                model=MODEL,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"""Create a brief, descriptive trend report for the {sector} sector based ONLY on the stock data provided.

Cover (observation only, no forecasts, no recommendations):
1. Top 3 observed trends in this sector right now (based on the provided scores).
2. One risk indicator worth noting from the data.
3. Which stock currently shows the highest quant score in this sector (pure indicator observation, NOT a recommendation).
4. Summary of the current observation window (past + present indicators ONLY; do NOT predict or forecast future months).

Use descriptive, past/present tense. Do NOT use words like "predict", "forecast", "will", "expected to", "전망", "예측", "예상", "오를 것", "내릴 것".

IMPORTANT: You MUST write BOTH English AND Korean. Do NOT skip Korean.
[EN]
(Report in English)
[KR]
(Report in Korean - fully translated)

Stocks in {sector}:
{stocks_text}"""
                }],
            )
            text = resp.content[0].text
            en, kr = self._parse_bilingual(text)
            return scrub_signal({
                "trend": _compliance_filter(en, "en"),
                "trend_kr": _compliance_filter(kr, "kr"),
                "sector": sector,
            })
        except Exception as e:
            logger.error(f"Sector trend error: {e}")
            return None
