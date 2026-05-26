"""Marketing autopost pipeline (2026-05-26).

매주 마케팅 콘텐츠를 *미리 작성된* content-bank 에서 읽어 §101 게이트를
통과시킨 뒤 Slack 리마인더(인스타) + (토큰 있으면) Threads/Bluesky 자동
발행으로 디스패치한다.

핵심 설계 제약 (메모리 feedback_no_extra_cost):
- cron 에서 LLM/Anthropic API 호출 **금지**. 캡션은 사람이 미리 쓴
  ``docs/marketing/content-bank.json`` 에서 읽는다 — 창작은 cron 이 안 함.
- 새 기능은 ``PIVOX_MARKETING_AUTOPOST_ENABLED`` (기본 false) 뒤에 둔다.
- Threads/Bluesky 는 토큰 없으면 graceful no-op — 추가 유료 SaaS 0건.
"""
from __future__ import annotations

from services.marketing.content_bank import (
    ContentItem,
    load_content_bank,
    items_for_date,
    save_content_bank,
)

__all__ = [
    "ContentItem",
    "load_content_bank",
    "items_for_date",
    "save_content_bank",
]
