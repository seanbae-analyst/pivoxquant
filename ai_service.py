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
                max_tokens=800,
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
                max_tokens=300,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"""Based on this analysis data, write a beginner-friendly explanation in 3-4 sentences.
First write in English, then write the Korean version after "---".
Focus on: what the numbers mean, whether it's a good time to buy/sell, and one key risk.

{context}"""
                }],
            )
            text = resp.content[0].text
            parts = text.split("---")
            en = parts[0].strip()
            kr = parts[1].strip() if len(parts) > 1 else en
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
                max_tokens=200,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"""Summarize today's market in 2-3 sentences for a beginner investor.
First English, then Korean after "---".

Market Mood: {mood}
GS View: {gs.get('bias', 'Neutral')} / Risk: {gs.get('risk_level', 'Moderate')}
Top Headlines:
{stories_text}"""
                }],
            )
            text = resp.content[0].text
            parts = text.split("---")
            en = parts[0].strip()
            kr = parts[1].strip() if len(parts) > 1 else en
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
                max_tokens=200,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"""Look at this portfolio and give ONE specific, actionable insight in 2-3 sentences.
Focus on: concentration risk, sector balance, or positions that need attention.
First English, then Korean after "---".

{portfolio_context}"""
                }],
            )
            text = resp.content[0].text
            parts = text.split("---")
            en = parts[0].strip()
            kr = parts[1].strip() if len(parts) > 1 else en
            return {"insight": en, "insight_kr": kr}
        except Exception as e:
            logger.error(f"Coaching error: {e}")
            return None
