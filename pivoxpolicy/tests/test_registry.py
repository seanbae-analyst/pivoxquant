"""레지스트리 실데이터가 스키마를 지키는지."""

import pytest

from pivoxpolicy.registry import load_codings, load_controls, load_documents, load_sources
from pivoxpolicy.schema import SchemaError, Document, validate_coding


def test_controls_are_seven_in_order():
    controls = load_controls()
    assert [c.num for c in controls] == [1, 2, 3, 4, 5, 6, 7]
    assert [c.id for c in controls] == [
        "inventory", "vendors", "unique_id", "least_privilege", "human_approval", "audit_trail", "kill_switch",
    ]


def test_documents_load_and_have_url_or_note():
    docs = load_documents()
    assert len(docs) >= 25
    for d in docs.values():
        assert d.url or d.url_note, d.id


def test_every_binding_document_is_in_seed_coding():
    """binding ≥ 1 문서는 전부 1차 코딩에 있어야 한다 (null 이어도 좋다 — 빠지면 매트릭스에서 사라진다)."""
    docs = load_documents()
    codings = load_codings()
    seed = codings["deck_2026-11-01"]["items"]
    missing = [d.id for d in docs.values() if d.binding >= 1 and d.id not in seed]
    assert not missing, missing


def test_seed_coding_validates():
    controls = load_controls()
    docs = load_documents()
    for coder, coding in load_codings().items():
        assert validate_coding(coding, docs, controls) == [], coder


def test_sources_have_id_url_issuer():
    for s in load_sources():
        assert s["id"] and s["url"].startswith("http") and s["issuer"]


def test_document_rejects_binding_two_guideline():
    with pytest.raises(SchemaError):
        Document.from_dict({
            "id": "x", "title": "t", "issuer": "i", "jurisdiction": "KR",
            "doc_type": "guideline", "status": "final", "binding": 2, "url": "http://x",
        })


def test_document_requires_url_note_when_no_url():
    with pytest.raises(SchemaError):
        Document.from_dict({
            "id": "x", "title": "t", "issuer": "i", "jurisdiction": "KR",
            "doc_type": "report", "status": "final", "binding": 0,
        })
