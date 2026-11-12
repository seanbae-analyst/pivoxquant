"""오프라인 사본 — 외부 스크립트 없음 · CSP 해시가 인라인 스크립트와 맞음 · 링크 · 인라인 데이터 이스케이프."""

from __future__ import annotations

import base64
import hashlib
import re

import pytest

from pivoxpolicy import bundle, sim


def test_data_cannot_close_the_script_tag():
    evil = 'window.X = {"t":"</script><script>alert(1)</script><!--"};'
    out = bundle.inline_js(evil, data=True)
    assert "</script" not in out.lower() and "<!--" not in out
    with pytest.raises(bundle.BundleError):
        bundle.inline_js("var a = '</script>';")


def test_offline_pages_are_self_contained(tmp_path):
    sim.build(out_dir=tmp_path, history_path=tmp_path / "h.jsonl")
    (tmp_path / "index.html").write_text('<!doctype html><html><head><meta charset="utf-8" /></head><body><a href="./">홈</a>'
                                         '<a href="sim.html">s</a><a href="dashboard.html#matrix">d</a><a href="offline/pivoxpolicy-sim.html" download>o</a></body></html>', encoding="utf-8")
    (tmp_path / "dashboard.html").write_text('<!doctype html><html><head><meta charset="utf-8" /></head><body></body></html>', encoding="utf-8")
    from pivoxpolicy import experiment
    (tmp_path / "experiment.html").write_text(experiment.page(experiment.run()), encoding="utf-8")
    names = {p.name for p in bundle.build(out_dir=tmp_path)}
    assert {"pivoxpolicy-home.html", "pivoxpolicy-dashboard.html", "pivoxpolicy-sim.html", "pivoxpolicy-experiment.html", "simulation.md"} <= names
    exp = (tmp_path / "offline" / "pivoxpolicy-experiment.html").read_text(encoding="utf-8")
    assert "<script" not in exp and 'href="pivoxpolicy-sim.html"' in exp and "script-src 'none'" in exp
    page = (tmp_path / "offline" / "pivoxpolicy-sim.html").read_text(encoding="utf-8")
    assert not re.search(r"<script\s+src=", page) and page.count("<script>") == 3
    csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', page).group(1)
    for code in re.findall(r"<script>(.*?)</script>", page, re.S):
        h = "'sha256-" + base64.b64encode(hashlib.sha256(code.encode("utf-8")).digest()).decode() + "'"
        assert h in csp                                       # 넣은 스크립트만 실행된다
    assert "connect-src" not in csp and "default-src 'none'" in csp
    assert 'href="pivoxpolicy-dashboard.html"' in page and 'href="pivoxpolicy-home.html"' in page and 'href="sim.html"' not in page
    home = (tmp_path / "offline" / "pivoxpolicy-home.html").read_text(encoding="utf-8")
    assert 'href="pivoxpolicy-dashboard.html#matrix"' in home and 'href="pivoxpolicy-sim.html"' in home and "offline/" not in home
