"""첫 화면(out/index.html) — 숫자는 레지스트리에서 계산, 자리표시자·스크립트·금지어 없음, 링크가 실제 페이지를 가리킨다."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from pivoxpolicy import landing


def test_landing_builds_from_registry(tmp_path):
    f = landing.facts()
    p = landing.build(out_dir=tmp_path, now=datetime(2026, 11, 12, tzinfo=timezone.utc))
    assert p.name == "index.html"
    page = p.read_text(encoding="utf-8")
    assert "{{" not in page and "<script" not in page                 # CSP script-src 'self' — 첫 화면은 스크립트가 없다
    for w in ("추천", "조언", "안전합니다", "적정합니다", "보장합니다"):
        assert w not in page, w
    for href in ('href="sim.html"', 'href="dashboard.html"', 'href="dashboard.html#matrix"', 'href="dashboard.html#method"'):
        assert href in page, href
    # 손으로 적은 숫자가 아니라 계산한 값이 실린다
    assert f"{f['n_inc']}</span><span class=\"k\">AI 에이전트 실제 사건" in page
    assert f"{f['n_docs']}</span><span class=\"k\">규제·가이드라인 문서" in page
    assert f["cells3"] == 21 and f["a2"] > f["g2"] >= f["g3"]                # 사람·계정 층이 AI 층보다 구속력 칸이 많다(조정본 기준)
    assert sum(f["gaps"][j] for j in ("KR", "US", "EU")) == int(re.search(r"<b>간극 (\d+)칸</b>", page).group(1))
    assert page.count('class="flow"') == 2 and 'class="flow pipe"' in page   # 미리보기 두 줄 + 만드는 법


def test_site_pages_link_each_other(tmp_path):
    """대시보드는 dashboard.html, 첫 화면은 index.html — 모의 테스트의 메뉴가 둘을 가리킨다."""
    from pivoxpolicy import sim
    names = {q.name for q in sim.build(out_dir=tmp_path, history_path=tmp_path / "h.jsonl")}
    html = (tmp_path / "sim.html").read_text(encoding="utf-8")
    assert "sim.html" in names and 'href="dashboard.html">대시보드' in html and '<a class="brand" href="./"' in html
