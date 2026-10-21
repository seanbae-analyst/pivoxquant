"""tests/test_year_recap.py — 올해의 기록 (services/year_recap · routes/year_recap.py).

Pins: the KST calendar year (a fill at 12-31 23:30 KST = 14:30 UTC belongs to
that year, 01-01 00:30 KST to the next); registration rows never count as
fills; a cancelled pause is "never bought" only while no later buy exists;
quotes come only from that year and only from the user's own rows, picked by
the documented deterministic rules; the rules block exists only after the
user adopted the lines; the route is session-only, validates ``year``, keeps
the quote text verbatim through the legal scrub and never returns another
user's rows. No scores, no grades.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from extensions import db
from models import InvestmentProfile, ObservationNote, PreTradeReflection, ResearchNote, TradeHistory
from services.year_recap import available_years, compute_year_recap, kst_year
from services.year_recap.recap import QUOTE_MAX_CHARS

# 2026-10-15 03:00 UTC = 2026-10-15 12:00 KST.
NOW = datetime(2026, 10, 15, 3, 0, 0)


def _trade(ticker, action, at, *, shares=1.0, price=100.0, source=None, tid=None, reflection_id=None):
    return TradeHistory(
        id=tid, user_id=1, ticker=ticker, action=action, shares=shares,
        price_per_share=price, total_value=shares * price, currency="USD",
        traded_at=at, source=source, reflection_id=reflection_id,
    )


def _refl(ticker, created, *, rid=None, cancelled=None, proceeded=None, side="BUY", rationale="이유를 적었다 열 글자 이상"):
    return PreTradeReflection(
        id=rid, user_id=1, intended_ticker=ticker, intended_side=side, rationale=rationale,
        created_at=created, cooldown_started_at=created, cooldown_ends_at=created,
        cancelled_at=cancelled, proceeded_at=proceeded,
    )


def _note(ticker, created, *, nid=None, theses=("매출이 늘어난다",), verdicts=None, reviewed=None):
    return ResearchNote(
        id=nid, user_id=1, ticker=ticker, business="번다", theses_json=json.dumps(list(theses)),
        review_on=created.date(), verdicts_json=json.dumps(verdicts) if verdicts else None,
        reviewed_at=reviewed, created_at=created,
    )


def _recap(year=2026, **kw):
    kw.setdefault("trades", [])
    kw.setdefault("reflections", [])
    return compute_year_recap(year, now=kw.pop("now", NOW), **kw)


# ── 한 해의 경계 (KST) ──────────────────────────────────────────────────

def test_kst_year_boundaries():
    # 2026-12-31 23:30 KST = 14:30 UTC → 2026. 2027-01-01 00:30 KST = 2026-12-31 15:30 UTC → 2027.
    assert kst_year(datetime(2026, 12, 31, 14, 30)) == 2026
    assert kst_year(datetime(2026, 12, 31, 15, 30)) == 2027
    # 2026-01-01 00:30 KST = 2025-12-31 15:30 UTC → 2026.
    assert kst_year(datetime(2025, 12, 31, 15, 30)) == 2026


def test_fill_at_dec_31_2330_kst_is_in_that_year():
    later = datetime(2027, 3, 1)
    trades = [
        _trade("AAA", "BUY", datetime(2026, 12, 31, 14, 30)),   # 2026-12-31 23:30 KST
        _trade("AAA", "BUY", datetime(2026, 12, 31, 15, 30)),   # 2027-01-01 00:30 KST
        _trade("BBB", "BUY", datetime(2025, 12, 31, 15, 30)),   # 2026-01-01 00:30 KST
        _trade("CCC", "BUY", datetime(2025, 12, 31, 14, 59)),   # 2025-12-31 23:59 KST
    ]
    out = _recap(trades=trades, now=later)
    assert out["fills"]["total"] == 2
    assert out["range"] == {"start": "2026-01-01", "end": "2026-12-31", "partial": False}
    by_month = {m["month"]: m["count"] for m in out["fills"]["by_month"]}
    assert len(by_month) == 12 and by_month["2026-01"] == 1 and by_month["2026-12"] == 1
    assert _recap(2027, trades=trades, now=later)["fills"]["total"] == 1


def test_current_year_stops_at_now():
    out = _recap(trades=[_trade("AAA", "BUY", NOW + timedelta(days=1))])
    assert out["fills"]["total"] == 0
    assert out["range"]["partial"] is True and out["range"]["end"] == "2026-10-15"
    assert [m["month"] for m in out["fills"]["by_month"]][-1] == "2026-10"


# ── 체결 ────────────────────────────────────────────────────────────────

def test_registration_rows_are_not_fills():
    at = datetime(2026, 3, 2)
    trades = [
        _trade("AAA", "BUY", at, source="holding_seed"),
        _trade("AAA", "SELL", at, source="holding_adjust"),
        _trade("AAA", "BUY", at),
        _trade("BBB.KS", "SELL", at + timedelta(days=40)),
        _trade("BBB.KQ", "BUY", at + timedelta(days=1)),
    ]
    f = _recap(trades=trades)["fills"]
    assert (f["total"], f["buys"], f["sells"]) == (3, 2, 1)
    assert f["tickers"] == 2  # BBB.KS / BBB.KQ 는 같은 종목 (friction_outcome.ticker_key)
    assert f["months_active"] == 2


def test_holding_median_over_sells_closed_this_year_skips_seed_lots():
    trades = [
        _trade("AAA", "BUY", datetime(2025, 11, 1)),
        _trade("AAA", "SELL", datetime(2026, 1, 1)),   # 61일, 올해 닫힘
        _trade("BBB", "BUY", datetime(2026, 2, 1)),
        _trade("BBB", "SELL", datetime(2026, 2, 11)),  # 10일
        _trade("CCC", "BUY", datetime(2026, 3, 1)),
        _trade("CCC", "SELL", datetime(2026, 3, 5)),   # 4일
        _trade("DDD", "BUY", datetime(2026, 1, 1), source="holding_seed"),
        _trade("DDD", "SELL", datetime(2026, 5, 1)),   # 시드 로트 — 매수일 없음
    ]
    h = _recap(trades=trades)["holding"]
    assert h == {"sells": 3, "median_days": 10.0}
    assert _recap(trades=[])["holding"] == {"sells": 0, "median_days": None}


# ── 멈춤 · 일어나지 않은 거래 ────────────────────────────────────────────

def test_cancelled_then_bought_vs_never():
    c1 = datetime(2026, 2, 1)
    c2 = datetime(2026, 4, 1)
    refls = [
        _refl("AAA", c1, rid=1, cancelled=c1 + timedelta(hours=1), rationale="AAA 를 사려다 멈췄다"),
        _refl("BBB", c2, rid=2, cancelled=c2 + timedelta(hours=1), rationale="BBB 는 결국 샀다"),
        _refl("CCC", c2, rid=3, proceeded=c2 + timedelta(hours=1)),
        _refl("DDD", c2, rid=4),
        _refl("EEE", c1, rid=5, cancelled=c1 + timedelta(hours=1), side="SELL"),  # // legal-ok — stored enum
        _refl("ZZZ", datetime(2025, 6, 1), rid=6, cancelled=datetime(2025, 6, 2)),  # 지난해
    ]
    trades = [_trade("BBB", "BUY", c2 + timedelta(days=3))]
    p = _recap(trades=trades, reflections=refls)["pauses"]
    assert (p["started"], p["proceeded"], p["cancelled"], p["open"]) == (5, 1, 3, 1)
    assert (p["cancelled_buy"], p["bought_later_anyway"], p["never_bought"]) == (2, 1, 1)


def test_not_taken_quote_is_the_oldest_cancelled_never_bought():
    refls = [
        _refl("AAA", datetime(2026, 2, 1), rid=1, cancelled=datetime(2026, 2, 2), rationale="먼저 멈춘 AAA"),
        _refl("BBB", datetime(2026, 1, 5), rid=2, cancelled=datetime(2026, 3, 1), rationale="나중에 취소한 BBB"),
        _refl("CCC", datetime(2026, 1, 1), rid=3, cancelled=datetime(2026, 1, 2), rationale="결국 산 CCC"),
    ]
    trades = [_trade("CCC", "BUY", datetime(2026, 5, 1))]
    quotes = {q["kind"]: q for q in _recap(trades=trades, reflections=refls)["quotes"]}
    nt = quotes["not_taken"]
    assert (nt["text"], nt["ticker"], nt["source"], nt["date"]) == ("먼저 멈춘 AAA", "AAA", "pause", "2026-02-01")
    # first_reason = 그해 가장 이른 이유, not_taken 에 쓴 멈춤은 빼고.
    assert quotes["first_reason"]["text"] == "결국 산 CCC"


def test_cancelled_pause_bought_next_year_is_not_never_bought():
    refls = [_refl("AAA", datetime(2026, 11, 1), rid=1, cancelled=datetime(2026, 11, 2))]
    trades = [_trade("AAA", "BUY", datetime(2027, 2, 1))]
    out = _recap(trades=trades, reflections=refls, now=datetime(2027, 3, 1))
    assert out["pauses"]["never_bought"] == 0
    assert all(q["kind"] != "not_taken" for q in out["quotes"])


# ── 기록 · 내 말 ────────────────────────────────────────────────────────

def test_reasoned_fills_and_research_counts():
    at = datetime(2026, 3, 2)
    trades = [
        _trade("AAA", "BUY", at, tid=10),
        _trade("BBB", "BUY", at, tid=11, reflection_id=7),
        _trade("CCC", "BUY", at, tid=12),
        _trade("DDD", "BUY", datetime(2025, 3, 2), tid=13),
    ]
    approved = [
        SimpleNamespace(id=1, approved_trade_id=10, approved_thesis="실적 발표 뒤 산다", approved_at=at, ticker="AAA"),
        SimpleNamespace(id=2, approved_trade_id=12, approved_thesis="  ", approved_at=at, ticker="CCC"),
        SimpleNamespace(id=3, approved_trade_id=13, approved_thesis="지난해 이유", approved_at=datetime(2025, 3, 2), ticker="DDD"),
    ]
    notes = [
        _note("AAA", datetime(2026, 2, 1), nid=1, theses=("a", "b"), verdicts=["right", "wrong"], reviewed=datetime(2026, 5, 1)),
        _note("BBB", datetime(2025, 12, 1), nid=2, verdicts=["unknown"], reviewed=datetime(2026, 3, 1)),
        _note("CCC", datetime(2026, 6, 1), nid=3),
    ]
    r = _recap(trades=trades, approved_pending=approved, research_notes=notes,
               observation_times=[at, datetime(2025, 1, 1)])["records"]
    assert r["reasoned_fills"] == 2
    assert (r["research_written"], r["research_reviewed"]) == (2, 2)
    assert r["verdicts"] == {"right": 1, "wrong": 1, "unknown": 1}
    assert r["observation_notes"] == 1


def test_quotes_come_only_from_that_year_and_are_trimmed():
    long = "가" * (QUOTE_MAX_CHARS + 30) + "\n둘째 줄"
    approved = [
        SimpleNamespace(id=1, approved_trade_id=None, approved_thesis="지난해 이유", approved_at=datetime(2025, 12, 31, 14), ticker="OLD"),
        SimpleNamespace(id=2, approved_trade_id=None, approved_thesis=long, approved_at=datetime(2026, 1, 3), ticker="AAA"),
    ]
    notes = [
        _note("OLD", datetime(2025, 5, 1), nid=1, reviewed=datetime(2026, 1, 1), verdicts=["right"]),
        _note("BBB", datetime(2026, 4, 1), nid=2, theses=("둘째로 쓴 리서치",), reviewed=datetime(2026, 9, 1), verdicts=["wrong"]),
        _note("CCC", datetime(2026, 3, 1), nid=3, theses=("먼저 쓴 리서치",), reviewed=datetime(2026, 9, 2), verdicts=["unknown"]),
        _note("DDD", datetime(2026, 1, 1), nid=4, theses=("채점 안 한 리서치",)),
    ]
    quotes = {q["kind"]: q for q in _recap(approved_pending=approved, research_notes=notes)["quotes"]}
    first = quotes["first_reason"]
    assert first["ticker"] == "AAA" and first["source"] == "fill"
    assert len(first["text"]) == QUOTE_MAX_CHARS and first["text"].endswith("…")
    assert "둘째 줄" not in first["text"]
    scored = quotes["scored_thesis"]
    assert (scored["text"], scored["verdict"], scored["date"]) == ("먼저 쓴 리서치", "unknown", "2026-03-01")
    assert "not_taken" not in quotes


def test_empty_year_is_flagged_and_has_no_quotes():
    out = _recap()
    assert out["empty"] is True and out["quotes"] == [] and out["rules"] is None
    assert out["doorway"] is None


def test_payload_carries_no_score_words():
    blob = json.dumps(_recap(trades=[_trade("AAA", "BUY", datetime(2026, 3, 2))]), ensure_ascii=False)
    for word in ("score", "grade", "streak", "rank", "점수", "등급", "잘했", "개선"):
        assert word not in blob


# ── 내 규칙 ─────────────────────────────────────────────────────────────

ANSWERS = {"declared_frequency": "rare", "declared_holding": "weeks"}  # ≤2번/월, 7일 이상


def test_rules_absent_when_not_adopted():
    trades = [_trade("AAA", "BUY", datetime(2026, 3, 2))]
    assert _recap(trades=trades, rules_answers=ANSWERS, rules_confirmed_at=None)["rules"] is None
    # 이듬해에 채택했으면 그해에는 규칙이 없었다.
    out = _recap(2025, trades=trades, rules_answers=ANSWERS, rules_confirmed_at=datetime(2026, 1, 5))
    assert out["rules"] is None


def test_rules_count_only_months_after_adoption():
    adopted = datetime(2026, 8, 10)
    trades = [_trade("AAA", "BUY", datetime(2026, 8, d)) for d in (1, 2, 3, 4, 5)]  # 채택 전 — 세지 않음
    trades += [_trade("AAA", "BUY", datetime(2026, 8, 20)), _trade("AAA", "BUY", datetime(2026, 8, 21))]
    trades += [_trade("BBB", "BUY", datetime(2026, 9, d)) for d in (1, 2, 3)]  # 3 > 2
    trades += [_trade("BBB", "SELL", datetime(2026, 9, 5)), _trade("AAA", "SELL", datetime(2026, 9, 30))]
    rules = _recap(trades=trades, rules_answers=ANSWERS, rules_confirmed_at=adopted)["rules"]
    assert rules["confirmed_on"] == "2026-08-10"
    freq = rules["frequency"]
    assert [m["month"] for m in freq["months"]] == ["2026-08", "2026-09", "2026-10"]
    aug, sep, octo = freq["months"]
    assert (aug["count"], aug["over"], aug["partial"]) == (2, False, True)
    assert (sep["count"], sep["over"], sep["partial"]) == (5, True, False)
    assert octo["partial"] is True
    assert (freq["within"], freq["outside"]) == (2, 1)
    # 매도 2번 — BBB 는 4일 만에(7일 전), AAA 는 8월 1일 로트부터.
    assert rules["holding"] == {"min_days": 7.0, "sells": 2, "sooner": 1, "sooner_label": "7일 전에 판 것"}


def test_rules_use_the_same_day_rules_as_the_my_rules_card():
    """2026-10-21 — the year page counted holds in 24-hour blocks and date-only
    fills by UTC instant, so it contradicted /mirror 내 규칙 on the same rows."""
    from services.profile.my_rules import compute_my_rules

    answers = {"declared_frequency": "rare", "declared_holding": "days"}
    # 14:00 KST buy, 10:00 KST sell the next morning — held into the next day.
    buy = _trade("AAA", "BUY", datetime(2026, 9, 1, 5, 0, 0, 1))
    sell = _trade("AAA", "SELL", datetime(2026, 9, 2, 1, 0, 0, 1))
    # Adopted 9/10 14:00 KST; three date-only fills that same day (KST).
    adopted = datetime(2026, 9, 10, 5, 0)
    same_day = [_trade("BBB", "BUY", datetime(2026, 9, 10)) for _ in range(3)]
    trades = [buy, sell, *same_day]

    def card(confirmed_at):
        out = compute_my_rules(answers, trades, open_positions=0,
                               now=datetime(2026, 9, 20), confirmed_at=confirmed_at)
        return {i["id"]: i for i in out["items"]}

    rules = _recap(trades=trades, rules_answers=answers, rules_confirmed_at=datetime(2026, 8, 1))["rules"]
    assert rules["holding"]["sooner"] == 0 == card(datetime(2026, 8, 1))["holding"]["sooner"]
    assert rules["holding"]["sooner_label"] == "산 날 판 것"

    rules = _recap(trades=trades, rules_answers=answers, rules_confirmed_at=adopted)["rules"]
    sep = rules["frequency"]["months"][0]
    assert sep["month"] == "2026-09" and sep["count"] == 3 and sep["over"] is True
    assert card(adopted)["frequency"]["status"] == "outside"


def test_a_date_only_fill_today_shows_before_09_kst():
    """A fill entered for today with no time is stored at today 00:00 — later
    than ``now`` (UTC) until 09:00 KST. It is today's, so it counts."""
    now = datetime(2026, 10, 20, 20, 0)          # 2026-10-21 05:00 KST
    today = _trade("AAA", "BUY", datetime(2026, 10, 21))
    out = _recap(trades=[today], now=now)
    assert out["fills"]["total"] == 1 and out["empty"] is False
    assert available_years([today.traded_at], now) == [2026]


# ── 해 목록 ─────────────────────────────────────────────────────────────

def test_available_years_newest_first_ignores_future():
    ts = [datetime(2025, 12, 31, 15, 0), datetime(2024, 5, 1), None, NOW + timedelta(days=400)]
    assert available_years(ts, NOW) == [2026, 2024]


# ── 라우트 ──────────────────────────────────────────────────────────────

def _seed(uid: int, *, ticker="AAA", rationale="내가 쓴 이유: 매수 추천 받음") -> None:
    at = datetime(2026, 3, 2, 1, 0)
    db.session.add(PreTradeReflection(
        user_id=uid, intended_ticker=ticker, intended_side="BUY", rationale=rationale,
        created_at=at, cooldown_started_at=at, cooldown_ends_at=at, cancelled_at=at + timedelta(hours=1),
    ))
    db.session.add(TradeHistory(user_id=uid, ticker="ZZZ", action="BUY", shares=1.0,
                                price_per_share=10.0, total_value=10.0, traded_at=at))
    db.session.add(ObservationNote(user_id=uid, body="관찰", created_at=at))
    db.session.commit()


def test_route_requires_auth(client):
    assert client.get("/api/mirror-home/year").status_code in (401, 403)


def test_route_validates_year(client, auth_user):
    for bad in ("abc", "26", "1999", "2019", "3000", "2026.5", "-2026", "²⁰²⁶"):
        resp = client.get(f"/api/mirror-home/year?year={bad}")
        assert resp.status_code == 400, bad
        assert resp.get_json()["code"] == "YEAR_RECAP_BAD_YEAR"


def test_route_returns_own_year_and_keeps_quote_text(client, app, make_user, auth_user):
    other = make_user(email="year-other@test.com")
    with app.app_context():
        _seed(auth_user["id"])
        _seed(other["id"], ticker="OTH", rationale="남의 이유는 보이면 안 된다")
        db.session.add(TradeHistory(user_id=other["id"], ticker="OTH", action="BUY", shares=1.0,
                                    price_per_share=1.0, total_value=1.0, traded_at=datetime(2024, 1, 5)))
        db.session.commit()
    body = client.get("/api/mirror-home/year?year=2026").get_json()
    assert body["ok"] is True and body["year"] == 2026
    assert body["disclaimer"] and body["share_disclaimer"]
    assert body["years"] == [2026]  # 남의 2024 체결은 해 목록에도 없다
    assert body["fills"]["total"] == 1 and body["pauses"]["never_bought"] == 1
    assert body["records"]["observation_notes"] == 1
    texts = [q["text"] for q in body["quotes"]]
    # 본인 문장은 스크럽 없이 원문 그대로 (skip_keys=("text",)).
    assert "내가 쓴 이유: 매수 추천 받음" in texts  # // legal-ok — user's own words fixture
    assert all("남의" not in t for t in texts)
    assert all(q["ticker"] != "OTH" for q in body["quotes"])
    assert body["doorway"] is None


def test_route_defaults_to_this_year_and_reads_rules(client, app, auth_user):
    with app.app_context():
        db.session.add(InvestmentProfile(
            user_id=auth_user["id"],
            onboarding_answers_json=json.dumps({"declared_frequency": "rare"}),
            rules_confirmed_at=datetime(2020, 1, 1),
        ))
        db.session.commit()
    body = client.get("/api/mirror-home/year").get_json()
    assert body["year"] == kst_year(datetime.now(timezone.utc).replace(tzinfo=None))
    assert body["empty"] is True and body["years"] == []
    assert body["rules"]["frequency"]["ceiling"] == 2
