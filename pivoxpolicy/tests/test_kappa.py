import math

from pivoxpolicy.kappa import cohen_kappa, compare_coders
from pivoxpolicy.schema import Control, Document

CONTROLS = [Control("inventory", 1, "before", "인벤토리", "Inventory", "", "")]


def test_kappa_hand_computed_binary():
    # 2x2: a=yes/b=yes 20, yes/no 5, no/yes 10, no/no 15  (n=50)
    a = [True] * 25 + [False] * 25
    b = [True] * 20 + [False] * 5 + [True] * 10 + [False] * 15
    r = cohen_kappa(a, b)
    po = 35 / 50
    pe = (25 / 50) * (30 / 50) + (25 / 50) * (20 / 50)
    assert math.isclose(r.observed_agreement, po)
    assert math.isclose(r.kappa, (po - pe) / (1 - pe))
    assert r.landis_koch() == "fair"  # 0.4


def test_kappa_perfect_and_empty():
    assert cohen_kappa([1, 2, 3], [1, 2, 3]).kappa == 1.0
    r = cohen_kappa([], [])
    assert r.n == 0 and r.kappa is None


def test_weighted_kappa_penalises_distance_less_for_near_misses():
    a = [0, 1, 2, 3, 0, 1, 2, 3]
    near = [0, 1, 2, 2, 0, 1, 2, 2]   # 3→2 두 번
    far = [0, 1, 2, 0, 0, 1, 2, 0]    # 3→0 두 번
    rn, rf = cohen_kappa(a, near), cohen_kappa(a, far)
    assert rn.kappa == rf.kappa                 # 비가중은 똑같이 2개 불일치
    assert rn.weighted_kappa > rf.weighted_kappa  # 가중은 가까운 불일치를 덜 벌한다


def test_compare_coders_uses_only_shared_non_null_cells():
    doc = Document.from_dict({
        "id": "d", "title": "d", "issuer": "x", "jurisdiction": "KR", "doc_type": "regulation",
        "status": "in_force", "binding": 2, "names_agents": False, "url": "http://x",
    })
    doc0 = Document.from_dict({
        "id": "p", "title": "p", "issuer": "x", "jurisdiction": "KR", "doc_type": "report",
        "status": "final", "binding": 0, "url": "http://x",
    })
    docs = {"d": doc, "p": doc0}
    a = {"coder": "a", "coded_at": "2026-01-01", "items": {
        "d": {"inventory": {"covered": True, "evidence": "e"}},
        "p": {"inventory": {"covered": True, "evidence": "e"}},
    }}
    b = {"coder": "b", "coded_at": "2026-01-01", "items": {
        "d": {"inventory": {"covered": False}},
        "p": {"inventory": {"covered": True, "evidence": "e"}},
    }}
    r = compare_coders(a, b, docs, CONTROLS)
    assert r["n_cells"] == 1                     # binding 0 문서는 제외
    assert r["disagreements"] == [("d", "inventory")]
    b["items"]["d"]["inventory"]["covered"] = None
    assert compare_coders(a, b, docs, CONTROLS)["n_cells"] == 0
