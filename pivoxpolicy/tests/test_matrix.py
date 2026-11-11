from pivoxpolicy.matrix import build_matrix, gaps, render_csv, render_markdown
from pivoxpolicy.schema import Control, Document, cell_score

CONTROLS = [
    Control("inventory", 1, "before", "인벤토리", "Inventory", "", ""),
    Control("kill_switch", 7, "after", "즉시 중단", "Kill switch", "", ""),
]


def _doc(id, j, binding, names_agents, doc_type="regulation"):
    if binding == 1 and doc_type == "regulation":
        doc_type = "guideline"
    if binding == 0:
        doc_type = "report"
    return Document.from_dict({
        "id": id, "title": id, "issuer": "x", "jurisdiction": j, "doc_type": doc_type,
        "status": "final", "binding": binding, "names_agents": names_agents, "url": "http://x",
    })


def test_cell_score_scale():
    assert cell_score(_doc("a", "KR", 2, True), True) == 3
    assert cell_score(_doc("a", "KR", 2, False), True) == 2
    assert cell_score(_doc("a", "KR", 2, None), True) == 2
    assert cell_score(_doc("a", "KR", 1, True), True) == 1
    assert cell_score(_doc("a", "KR", 2, True), False) == 0
    assert cell_score(_doc("a", "KR", 2, True), None) is None
    assert cell_score(_doc("a", "KR", 0, True), True) is None  # 규범 아님


def test_matrix_takes_max_and_tracks_flags():
    docs = {
        "reg": _doc("reg", "KR", 2, False),        # 구속력, 에이전트 미명시
        "guide": _doc("guide", "KR", 1, True),     # 자율, 에이전트 명시
        "press": _doc("press", "KR", 0, True),     # 규범 아님
        "us": _doc("us", "US", 1, False),
    }
    coding = {"coder": "t", "coded_at": "2026-01-01", "items": {
        "reg":   {"inventory": {"covered": True, "evidence": "a"}, "kill_switch": {"covered": False}},
        "guide": {"inventory": {"covered": True, "evidence": "b"}, "kill_switch": {"covered": True, "evidence": "c"}},
        "press": {"inventory": {"covered": True, "evidence": "d"}},
        "us":    {"inventory": {"covered": None}},
    }}
    m = build_matrix(docs, CONTROLS, coding)
    kr_inv = m["KR"]["inventory"]
    assert kr_inv.score == 2 and kr_inv.top_docs == ["reg"]
    assert kr_inv.agent_specific_voluntary == ["guide"]
    assert kr_inv.n_coded == 2
    kr_ks = m["KR"]["kill_switch"]
    assert kr_ks.score == 1 and kr_ks.top_docs == ["guide"] and kr_ks.names_agents is True
    us_inv = m["US"]["inventory"]
    assert us_inv.score is None and us_inv.n_uncoded == 1
    assert m["EU"]["inventory"].score is None and m["EU"]["inventory"].n_uncoded == 0

    g = {(j, c) for j, c, _ in gaps(m, CONTROLS)}
    assert ("KR", "inventory") not in g          # 2 는 공백 아님
    assert ("KR", "kill_switch") in g
    assert ("US", "inventory") in g

    md = render_markdown(m, CONTROLS, "t", docs)
    assert "| 1 | 인벤토리 (Inventory) | 2† | ? (1 코딩 필요) | – | – |" in md
    assert "| 7 | 즉시 중단 (Kill switch) | 1* | – | – | – |" in md
    csv = render_csv(m, CONTROLS)
    assert csv.splitlines()[1] == "1,inventory,2,,,"
