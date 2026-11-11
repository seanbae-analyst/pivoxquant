"""정적 대시보드 생성 — 자리표시자·금지어·섹션·디자인 규칙."""

import re
from datetime import datetime, timezone

from pivoxpolicy import site
from pivoxpolicy.intel import Item


def test_build_fills_all_placeholders_and_has_no_forbidden_words(tmp_path):
    p = site.build(out_dir=tmp_path, snapshot_dir=tmp_path, now=datetime(2026, 11, 11, tzinfo=timezone.utc))
    t = p.read_text(encoding="utf-8")
    # 채우지 않은 {{...}} 없음 (주석 예시 포함 — 생성 시 주석을 제거하므로)
    assert re.findall(r"\{\{[A-Z_0-9]+\}\}", t) == []
    # 자본시장법·표시광고 금지 어휘 (프로젝트 규칙)
    for w in ("추천", "조언", "안전합니다", "적정합니다", "보장합니다"):
        assert w not in t, w
    # 섹션이 전부 있다
    for sid in ("now", "incidents", "matrix", "gaps", "profile", "timeline", "docs", "method"):
        assert f'id="{sid}"' in t
    # 디자인 토큰·heat 클래스가 인라인
    assert "--pq-ink" in t and "#050505" in t and "h-x" in t
    # 히트맵·상태에 빨강·초록(가격색 hex)을 바탕으로 쓰지 않는다 — 셀 배경은 브론즈 알파뿐
    assert "background:#d18888" not in t.lower() and "background:#7aa0c8" not in t.lower()
    assert "rgba(184, 149, 106" in t or "rgba(184,149,106" in t  # 브론즈 히트 스케일


def test_matrix_cells_carry_heat_classes(tmp_path):
    p = site.build(out_dir=tmp_path, snapshot_dir=tmp_path, now=datetime(2026, 11, 11, tzinfo=timezone.utc))
    t = p.read_text(encoding="utf-8")
    assert 'class="h-0"' in t or 'class="h-x"' in t
    assert 'class="matrix"' in t


def test_agent_relevance_and_security_filters():
    def it(title, topic="threat_intel", matched=("ai",)):
        x = Item("f", title, "https://x/" + title.replace(" ", ""), "2026-11-10", "", list(matched))
        x.topic = topic
        return x
    assert site._is_agent_relevant(it("AI agent backdoored"))
    assert not site._is_agent_relevant(it("quantum workshop", matched=("technology",)))
    assert site._is_security(it("AI agent exploited in breach"))
    assert not site._is_security(it("AI 데이터센터 동맹", matched=("ai",)))


def test_now_excludes_weak_matches_but_keeps_agent_items():
    def it(title, topic, matched, summary=""):
        x = Item("f", title, "https://x/" + str(abs(hash(title))), "2026-11-10", summary, list(matched))
        x.topic = topic
        x.issuer = "X"
        x.kind = "primary"
        return x
    items = [
        it("제439회국회 제5차 전체회의", "regulation", ["전체회의"]),            # 약함 → 제외
        it("금융 AI 에이전트 보안 가이드라인", "regulation", ["에이전트", "AI"]),  # 유지
        it("AI 데이터센터 동맹", "incident", ["AI"]),                          # 보안 신호 없음 → 사건서 제외
        it("AI agent used in bank breach", "threat_intel", ["agent", "breach"]),  # 유지
    ]
    now_html, inc_html, _, _ = site._now_and_incidents(items)
    assert "에이전트 보안 가이드라인" in now_html
    assert "전체회의" not in now_html
    assert "bank breach" in inc_html
    assert "데이터센터" not in inc_html
