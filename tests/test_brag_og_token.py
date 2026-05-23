"""Regression — monthly-brag OG image enumeration block (2026-05-23 fix).

The public ``/api/artifacts/monthly-brag/og-image/<id>`` endpoint embeds
the user's real name + monthly return in the PNG. It used to serve on a
bare integer ``brag_id`` (anyone could enumerate 1, 2, 3, … and pull every
user's card — PIPA §29). It now requires an HMAC-signed ``?sig=`` token
bound to that ``brag_id``.
"""
from __future__ import annotations


def test_token_roundtrip(app):
    from services.brag_og_token import make_og_token, verify_og_token
    with app.app_context():
        tok = make_og_token(42)
        assert verify_og_token(tok, 42) is True
        # Token minted for a different id must not validate.
        assert verify_og_token(tok, 43) is False
        # Empty / garbage / tampered tokens are rejected.
        assert verify_og_token("", 42) is False
        assert verify_og_token("not-a-token", 42) is False
        assert verify_og_token(tok + "x", 42) is False


def test_og_image_blocks_enumeration_without_sig(raw_client):
    # No ?sig= → 403 BEFORE any DB lookup. This is the enumeration block.
    resp = raw_client.get("/api/artifacts/monthly-brag/og-image/42")
    assert resp.status_code == 403
    assert resp.get_json().get("code") == "BRAG_SIG_INVALID"


def test_og_image_rejects_forged_sig(raw_client):
    resp = raw_client.get(
        "/api/artifacts/monthly-brag/og-image/42?sig=forged.signature.here"
    )
    assert resp.status_code == 403


def test_og_image_valid_sig_passes_signature_gate(app, raw_client):
    # A valid sig for a non-existent row must get PAST the 403 gate and
    # hit the 404 (row not found) — proving the signature check accepts
    # legitimately minted tokens.
    from services.brag_og_token import make_og_token
    with app.app_context():
        tok = make_og_token(999999)
    resp = raw_client.get(
        f"/api/artifacts/monthly-brag/og-image/999999?sig={tok}"
    )
    assert resp.status_code == 404
    assert resp.get_json().get("code") == "BRAG_NOT_FOUND"
