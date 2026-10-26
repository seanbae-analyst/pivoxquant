"""OpenDART 인증키 — 거절문을 로그에 그대로 찍는다 (2026-10-26).

OpenDART 는 틀린 키·막힌 IP·만료 계정에도 HTTP 200 으로 ``{"status":"010",
"message":"등록되지 않은 인증키입니다."}`` 같은 거절문만 돌려준다. corpCode.xml 도
ZIP 대신 그 거절문이라 예전엔 ``BadZipFile`` 만 남았고, 화면에선 공시가 조용히
비어 키 문제인지 알 길이 없었다. 이제 부팅 때 한 번 찔러 보고(``check_key``),
회사코드·공시 요청이 거절되면 status 와 메시지를 WARNING 으로 남긴다.
"""
from __future__ import annotations

import logging

import pytest

import app as app_module
from services.filing_timeline import dart

REJECT_JSON = b'{"status":"010","message":"\xeb\x93\xb1\xeb\xa1\x9d\xeb\x90\x98\xec\xa7\x80 \xec\x95\x8a\xec\x9d\x80 \xec\x9d\xb8\xec\xa6\x9d\xed\x82\xa4\xec\x9e\x85\xeb\x8b\x88\xeb\x8b\xa4."}'
REJECT_XML = "<result><status>020</status><message>요청 제한을 초과하였습니다.</message></result>".encode()


class _Resp:
    def __init__(self, data=None, content=b""):
        self._data, self.content = data, content

    def json(self):
        if self._data is None:
            raise ValueError("not json")
        return self._data


@pytest.fixture(autouse=True)
def _fresh_corp_map(monkeypatch):
    monkeypatch.setattr(dart, "_corp_map", {})
    monkeypatch.setattr(dart, "_corp_map_at", 0.0)
    monkeypatch.setattr(dart, "_corp_map_failed_at", 0.0)


# ── 거절문 읽기 ──────────────────────────────────────────────────────────────

def test_rejection_reads_json_and_xml_bodies():
    assert dart._rejection(REJECT_JSON) == ("010", "등록되지 않은 인증키입니다.")
    assert dart._rejection(REJECT_XML) == ("020", "요청 제한을 초과하였습니다.")
    assert dart._rejection(b'{"status":"000","list":[]}') is None
    assert dart._rejection(b"PK\x03\x04 real zip bytes") is None
    assert dart._rejection(b"{not json") is None


def test_corp_code_rejection_is_logged_with_dart_message(monkeypatch, caplog):
    monkeypatch.setenv("DART_API_KEY", "k" * 40)
    monkeypatch.setattr(dart, "_get", lambda path, params, timeout: _Resp(content=REJECT_JSON))

    with caplog.at_level(logging.WARNING, logger="services.filing_timeline.dart"):
        assert dart.corp_code_for("005930") is None

    msgs = [r.getMessage() for r in caplog.records]
    assert any("corpCode.xml 거부 — status 010: 등록되지 않은 인증키입니다." in m and "DART_API_KEY" in m for m in msgs)
    assert not any("BadZipFile" in m for m in msgs)


def test_other_corp_code_failures_keep_the_exception(monkeypatch, caplog):
    monkeypatch.setenv("DART_API_KEY", "k" * 40)

    def _boom(path, params, timeout):
        raise ConnectionError("dns")

    monkeypatch.setattr(dart, "_get", _boom)
    with caplog.at_level(logging.WARNING, logger="services.filing_timeline.dart"):
        assert dart.corp_code_for("005930") is None
    assert any("corpCode.xml failed: dns" in r.getMessage() for r in caplog.records)


def test_list_rejection_names_the_key_only_for_key_statuses(monkeypatch, caplog):
    monkeypatch.setenv("DART_API_KEY", "k" * 40)
    monkeypatch.setattr(dart, "corp_code_for", lambda code: "00126380")
    answers = iter([{"status": "011", "message": "사용할 수 없는 키입니다."}])
    monkeypatch.setattr(dart, "_get", lambda path, params, timeout: _Resp(next(answers)))

    with caplog.at_level(logging.WARNING, logger="services.filing_timeline.dart"):
        assert dart.fetch("005930") is None
    line = next(r.getMessage() for r in caplog.records if "list.json" in r.getMessage())
    assert "status 011: 사용할 수 없는 키입니다." in line and "DART_API_KEY" in line

    # 020 (요청 한도) is not a key problem — no hint.
    assert dart._status_line("020", "요청 제한을 초과하였습니다.") == "status 020: 요청 제한을 초과하였습니다."


# ── check_key ────────────────────────────────────────────────────────────────

def test_check_key_without_a_key_says_so_and_never_calls_out(monkeypatch):
    monkeypatch.delenv("DART_API_KEY", raising=False)
    monkeypatch.setattr(dart, "_get", lambda *a, **k: pytest.fail("no key → no request"))
    ok, line = dart.check_key()
    assert ok is False and "DART_API_KEY 없음" in line


@pytest.mark.parametrize("status", ["000", "013"])
def test_check_key_accepts_a_working_key(monkeypatch, status):
    monkeypatch.setenv("DART_API_KEY", "k" * 40)
    seen = {}

    def _get(path, params, timeout):
        seen.update(path=path, params=params)
        return _Resp({"status": status, "message": "", "list": []})

    monkeypatch.setattr(dart, "_get", _get)
    ok, line = dart.check_key()
    assert ok is True and "OK" in line
    assert seen["path"] == "list.json" and seen["params"]["corp_code"] == "00126380" and seen["params"]["page_count"] == 1


def test_check_key_reports_the_dart_rejection(monkeypatch):
    monkeypatch.setenv("DART_API_KEY", "k" * 40)
    monkeypatch.setattr(dart, "_get", lambda *a, **k: _Resp({"status": "010", "message": "등록되지 않은 인증키입니다."}))
    ok, line = dart.check_key()
    assert ok is False
    assert line == "status 010: 등록되지 않은 인증키입니다. — Render 의 DART_API_KEY 를 확인하세요"


def test_check_key_reports_a_network_failure(monkeypatch):
    monkeypatch.setenv("DART_API_KEY", "k" * 40)

    def _boom(*a, **k):
        raise TimeoutError("read timed out")

    monkeypatch.setattr(dart, "_get", _boom)
    ok, line = dart.check_key()
    assert ok is False and line.startswith("OpenDART 에 닿지 못함: TimeoutError")


# ── 부팅 로그 ────────────────────────────────────────────────────────────────

def test_boot_logs_a_missing_key_without_a_thread(monkeypatch, caplog):
    monkeypatch.delenv("DART_API_KEY", raising=False)
    monkeypatch.setattr(app_module.threading, "Thread", lambda *a, **k: pytest.fail("no thread without a key"))
    with caplog.at_level(logging.INFO, logger="app"):
        app_module._start_dart_key_check()
    assert any("DART_API_KEY 없음" in r.getMessage() for r in caplog.records)


def test_boot_logs_the_check_result(monkeypatch, caplog):
    monkeypatch.setattr(dart, "check_key", lambda: (False, "status 010: 등록되지 않은 인증키입니다."))
    with caplog.at_level(logging.INFO, logger="app"):
        app_module._log_dart_key_check()
    rec = next(r for r in caplog.records if r.getMessage().startswith("dart: "))
    assert rec.levelno == logging.WARNING and "status 010" in rec.getMessage()

    caplog.clear()
    monkeypatch.setattr(dart, "check_key", lambda: (True, "인증키 OK"))
    with caplog.at_level(logging.INFO, logger="app"):
        app_module._log_dart_key_check()
    rec = next(r for r in caplog.records if r.getMessage().startswith("dart: "))
    assert rec.levelno == logging.INFO and "OK" in rec.getMessage()
