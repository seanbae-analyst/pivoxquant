"""
StockPilot — AI Service (Claude Integration)
Uses Claude Haiku for cost-efficient, beginner-friendly financial insights.
"""

import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are StockPilot AI, a friendly investment advisor assistant built into a quantitative portfolio analysis app.

Your audience is beginner investors (주린이) who may not understand financial jargon.

Rules:
- Explain concepts simply. If you must use jargon, define it immediately.
- Always match the user's language (Korean → Korean, English → English).
- Keep responses concise: 2-4 sentences for summaries, up to a short paragraph for chat.
- Use the exact numbers from the provided data context.
- Be encouraging but honest about risks.
- Base your analysis on the quant scores and signals provided.
- End with a clear, actionable takeaway when possible.
- IMPORTANT: Add a disclaimer that this is algorithmic analysis, not financial advice.
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
        lines = ["## User Portfolio Context", f"Date: {datetime.utcnow().strftime('%Y-%m-%d')}"]

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
            lines.append(f"Recommendation: Buy {data['rec_shares']} shares (~${data.get('rec_investment', 0):,.0f})")
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
        """Generator that yields text chunks from Claude streaming response."""
        if not self.available:
            yield "AI 기능이 비활성화되어 있습니다. API 키를 설정해주세요."
            return
        try:
            messages = []
            for h in (history or [])[-10:]:
                messages.append({"role": h["role"], "content": h["content"]})
            messages.append({"role": "user", "content": message})

            with self.client.messages.stream(
                model=MODEL,
                max_tokens=4000,
                system=SYSTEM_PROMPT + "\n\n" + context,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield f"죄송합니다. AI 응답 중 오류가 발생했습니다: {str(e)}"

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
Focus on: what the numbers mean, whether it's a good time to buy/sell, and one key risk.

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
            return {"commentary": en, "commentary_kr": kr}
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
            return {"summary": en, "summary_kr": kr}
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
            return {"insight": en, "insight_kr": kr}
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

End with: "Bottom line: [one sentence investment thesis]"

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
            return {"swot": en, "swot_kr": kr}
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

Cover:
- How does the main stock compare to peers in terms of score and signal?
- Which peer looks like the best opportunity based on the data?
- What's the biggest risk in this sector right now?
- One actionable insight for an investor

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
            return {"analysis": en, "analysis_kr": kr}
        except Exception as e:
            logger.error(f"Competitor analysis error: {e}")
            return None

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
                    "content": f"""Create a brief trend report for the {sector} sector based on the stock data provided.

Cover:
1. Top 3 trends in this sector right now
2. One risk most investors aren't watching
3. Which stock in this sector looks best positioned based on the scores
4. Your prediction for the next 6 months

Be specific. Use the data provided.

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
            return {"trend": en, "trend_kr": kr, "sector": sector}
        except Exception as e:
            logger.error(f"Sector trend error: {e}")
            return None
