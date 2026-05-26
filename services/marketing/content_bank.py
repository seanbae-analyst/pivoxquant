"""Content bank loader — cron 이 읽는 *미리 작성된* 마케팅 콘텐츠.

왜 파일 기반인가
================
cron 에서 LLM 을 호출해 캡션을 생성하면 Anthropic 토큰 비용이 매일 발생한다
(메모리 feedback_no_extra_cost — 추가 비용 0원 원칙). 따라서 캡션·해시태그는
사람이 별도 세션에서 미리 작성해 ``docs/marketing/content-bank.json`` 에
적재하고, cron 은 *오늘 날짜에 해당하는 항목을 읽어 발행*만 한다. 창작 0건.

스키마 (JSON 배열 of 항목)
==========================
::

    {
      "id":             "d8-weekly-memo",     # 고유 식별자 (status 갱신 키)
      "scheduled_date": "2026-05-27",         # ISO date — 이 날짜에 디스패치
      "channel":        ["instagram", "threads", "bluesky"],
      "caption":        "...",                # 사람이 미리 쓴 본문 (§101 게이트 대상)
      "hashtags":       ["#투자", "#퀀트"],   # 채널에 따라 caption 뒤 append
      "image_path":     "docs/marketing/week1-cards/d1_cfo_card.png",  # repo-relative, nullable
      "status":         "pending",            # "pending" | "published"
      "ai_label":       true                  # AI 생성물 표시제 (콘텐츠진흥법) 라벨 필요 여부
    }

``status`` 는 디스패처가 발행 성공 후 "published" 로 갱신해 다음 cron 틱에서
중복 발행을 막는다 (멱등성). 부분 발행(채널 일부 성공)은 ``published_channels``
로 추적한다.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Repo root — ``services/marketing/content_bank.py`` 에서 부모 2단계 위.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_BANK_PATH = REPO_ROOT / "docs" / "marketing" / "content-bank.json"

VALID_CHANNELS = frozenset({"instagram", "threads", "bluesky"})
STATUS_PENDING = "pending"
STATUS_PUBLISHED = "published"


@dataclass
class ContentItem:
    """A single scheduled marketing post."""

    id: str
    scheduled_date: str
    channel: list[str]
    caption: str
    hashtags: list[str] = field(default_factory=list)
    image_path: str | None = None
    status: str = STATUS_PENDING
    ai_label: bool = True
    # 부분 발행 추적 — 채널별로 성공한 것만 기록 (재시도 시 중복 방지).
    published_channels: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ContentItem":
        channels = d.get("channel") or []
        if isinstance(channels, str):
            channels = [channels]
        # Drop unknown channels defensively so a typo can't crash dispatch.
        channels = [c for c in channels if c in VALID_CHANNELS]
        return cls(
            id=str(d["id"]),
            scheduled_date=str(d["scheduled_date"]),
            channel=channels,
            caption=str(d.get("caption") or ""),
            hashtags=list(d.get("hashtags") or []),
            image_path=d.get("image_path") or None,
            status=str(d.get("status") or STATUS_PENDING),
            ai_label=bool(d.get("ai_label", True)),
            published_channels=list(d.get("published_channels") or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scheduled_date": self.scheduled_date,
            "channel": self.channel,
            "caption": self.caption,
            "hashtags": self.hashtags,
            "image_path": self.image_path,
            "status": self.status,
            "ai_label": self.ai_label,
            "published_channels": self.published_channels,
        }

    def full_caption(self) -> str:
        """Caption + AI label + hashtags, ready to post.

        AI 생성물 표시제(콘텐츠진흥법 / 정보통신망법 개정 흐름) 대응 — ``ai_label``
        이 true 면 본문 끝에 명시 라벨을 붙인다.
        """
        parts = [self.caption.strip()]
        if self.ai_label:
            parts.append("\n※ 일부 콘텐츠는 AI로 생성되었습니다.")
        if self.hashtags:
            parts.append("\n" + " ".join(self.hashtags))
        return "\n".join(p for p in parts if p).strip()


def load_content_bank(path: Path | str | None = None) -> list[ContentItem]:
    """Load and parse the content bank.

    누락/손상 파일은 빈 리스트로 graceful degrade — cron 이 안 죽는다.
    """
    bank_path = Path(path) if path else DEFAULT_BANK_PATH
    if not bank_path.exists():
        logger.warning("[marketing] content-bank not found: %s — empty", bank_path)
        return []
    try:
        raw = json.loads(bank_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("[marketing] content-bank parse failed: %s", exc)
        return []
    if not isinstance(raw, list):
        logger.error("[marketing] content-bank root must be a JSON array")
        return []
    items: list[ContentItem] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            items.append(ContentItem.from_dict(entry))
        except (KeyError, TypeError) as exc:
            logger.warning("[marketing] skipping malformed item: %s", exc)
    return items


def items_for_date(
    items: list[ContentItem],
    on: date | str,
    include_published: bool = False,
) -> list[ContentItem]:
    """Filter items scheduled for ``on`` that still need dispatch.

    ``include_published=False`` (default) 는 이미 ``status=="published"`` 인
    항목을 제외 — cron 멱등성 보장.
    """
    on_str = on.isoformat() if isinstance(on, date) else str(on)
    out = []
    for it in items:
        if it.scheduled_date != on_str:
            continue
        if not include_published and it.status == STATUS_PUBLISHED:
            continue
        out.append(it)
    return out


def save_content_bank(items: list[ContentItem], path: Path | str | None = None) -> bool:
    """Persist items back to disk (status 갱신용). Best-effort."""
    bank_path = Path(path) if path else DEFAULT_BANK_PATH
    try:
        bank_path.parent.mkdir(parents=True, exist_ok=True)
        bank_path.write_text(
            json.dumps([it.to_dict() for it in items], ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        return True
    except OSError as exc:
        logger.error("[marketing] content-bank save failed: %s", exc)
        return False


__all__ = [
    "ContentItem",
    "load_content_bank",
    "items_for_date",
    "save_content_bank",
    "DEFAULT_BANK_PATH",
    "VALID_CHANNELS",
    "STATUS_PENDING",
    "STATUS_PUBLISHED",
]
