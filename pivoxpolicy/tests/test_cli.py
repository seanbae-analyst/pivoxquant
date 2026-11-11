from pivoxpolicy.cli import main


def test_check_passes(capsys):
    assert main(["check"]) == 0
    assert "✓ 통과" in capsys.readouterr().out


def test_matrix_and_gaps_render(capsys):
    assert main(["matrix"]) == 0
    out = capsys.readouterr().out
    assert "| # | 통제 | KR | US | EU | INTL |" in out
    assert main(["gaps"]) == 0
    assert main(["timeline"]) == 0
    capsys.readouterr()
    assert main(["matrix", "--csv"]) == 0
    assert capsys.readouterr().out.startswith("control_num,control_id,KR,US,EU,INTL")


def test_kappa_needs_two_coders_or_runs(capsys):
    rc = main(["kappa"])
    assert rc in (0, 2)
