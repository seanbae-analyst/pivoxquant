"""
PivoxQuant — Thesis Tracker Service

유저가 매수 시 기록한 thesis(매수 이유)가 여전히 유효한지
Claude AI로 주간 체크. 가격 변화 + 최근 뉴스 + thesis 텍스트 입력.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def check_thesis(ticker: str, thesis: str, price_change_30d: float = 0.0,
                 recent_news: str = "") -> dict:
    """
    Claude AI로 thesis 유효성 판정.

    Returns:
        { "status": "valid|warning|invalidated",
          "reason": "한 줄 이유" }

    실패 시: { "status": "pending", "reason": "check failed" }
    """
    try:
        from ai_service import AIService
        ai = AIService()
    except Exception as e:
        logger.warning(f"ai_service unavailable: {e}")
        return {"status": "pending", "reason": "AI service unavailable"}

    prompt = f"""유저가 {ticker}를 다음 thesis로 매수했습니다:

Thesis: "{thesis}"

최근 30일 가격 변화: {price_change_30d:+.1f}%
최근 뉴스 요약: {recent_news[:500] if recent_news else "(없음)"}

이 thesis가 여전히 유효한가요? 다음 JSON만 반환:
{{"status": "valid" | "warning" | "invalidated", "reason": "한 줄 이유 (50자 이내)"}}

- valid: thesis 전제가 여전히 사실, 지지 요인 계속 있음
- warning: 일부 전제 약화, 추가 관찰 필요
- invalidated: thesis 전제가 깨짐, 재검토 필요

(주의: 매수/매도 권유 금지, thesis 관련 사실적 판정만)"""

    try:
        resp = ai.chat(prompt, max_tokens=200)
        # Parse JSON from response
        import json
        import re
        m = re.search(r'\{[^}]+\}', resp)
        if m:
            data = json.loads(m.group(0))
            status = data.get("status", "pending")
            reason = str(data.get("reason", ""))[:200]
            if status not in ("valid", "warning", "invalidated"):
                status = "pending"
            return {"status": status, "reason": reason}
    except Exception as e:
        logger.warning(f"thesis check parse failed: {e}")

    return {"status": "pending", "reason": "AI response unparseable"}


def check_all_positions_for_user(user_id: int) -> int:
    """
    한 유저의 모든 포지션 thesis 체크. 주간 크론에서 호출.
    Returns: 체크한 포지션 수
    """
    from models.position import Position
    from extensions import db

    positions = Position.query.filter_by(user_id=user_id).filter(
        Position.thesis.isnot(None)
    ).all()

    count = 0
    for pos in positions:
        if not pos.thesis:
            continue
        result = check_thesis(
            ticker=pos.ticker,
            thesis=pos.thesis,
            price_change_30d=0.0,  # TODO: compute from snapshot
            recent_news="",         # TODO: fetch from news service
        )
        pos.thesis_status = result["status"]
        pos.thesis_reason = result["reason"]
        pos.thesis_last_checked = datetime.now(timezone.utc).replace(tzinfo=None)
        count += 1

    try:
        db.session.commit()
    except Exception as e:
        logger.error(f"thesis batch commit failed: {e}")
        db.session.rollback()

    return count
