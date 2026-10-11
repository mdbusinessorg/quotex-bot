from app import calib


def _res(n, wins, cls="forex", voters=("ai_turbo", "bible_sr")):
    out = []
    for i in range(n):
        out.append({"result": "win" if i < wins else "loss",
                    "cls": cls, "voters": list(voters)})
    return out


def test_no_data_is_50_and_sem_dados():
    t = calib.build([])
    p, n = calib.estimate(t, "forex", ["ai_turbo"])
    assert abs(p - 0.5) < 1e-9 and n == 0
    assert calib.grade(p, n) == "sem_dados"


def test_void_ignored():
    rows = _res(10, 10) + [{"result": "void", "cls": "forex", "voters": ["ai_turbo"]}] * 50
    t = calib.build(rows)
    assert t["global"][0] == 10


def test_shrinks_small_samples():
    t = calib.build(_res(10, 10))            # 10/10 wins
    p, _ = calib.estimate(t, "forex", ["ai_turbo", "bible_sr"])
    assert 0.5 < p < 0.75                    # longe de 100%


def test_large_sample_converges_and_grades():
    t = calib.build(_res(300, 200))          # 66,7%
    p, n = calib.estimate(t, "forex", ["ai_turbo", "bible_sr"])
    assert 0.62 < p < 0.67 and n == 300
    assert calib.grade(p, n) == "forte"


def test_no_trade_when_history_against():
    t = calib.build(_res(100, 30))           # 30%
    p, n = calib.estimate(t, "forex", ["ai_turbo", "bible_sr"])
    assert calib.grade(p, n) == "no_trade"


def test_other_class_barely_affected():
    t = calib.build(_res(300, 300, cls="crypto"))
    p, n = calib.estimate(t, "forex", ["ai_turbo"])
    assert p < 0.9 and n == 0 and calib.grade(p, n) == "sem_dados"


def test_no_trade_exact_needs_strong_evidence():
    t = calib.build(_res(50, 15))            # 30% mas só 50 amostras
    assert calib.no_trade_exact(t, "forex", ["ai_turbo", "bible_sr"]) is False
    t = calib.build(_res(100, 25))           # 25% com 100 do MESMO conjunto
    assert calib.no_trade_exact(t, "forex", ["ai_turbo", "bible_sr"]) is True
    # um votante fraco não pode contaminar sinais com mais votantes
    t = calib.build(_res(100, 25, voters=["ai_turbo"]) +
                    _res(10, 5, voters=["ai_turbo", "bible_sr"]))
    assert calib.no_trade_exact(t, "forex", ["ai_turbo", "bible_sr"]) is False


def test_no_trade_exact_never_on_few_voters():
    t = calib.build(_res(200, 20, voters=["ai_turbo"]))
    assert calib.no_trade_exact(t, "forex", ["ai_turbo"]) is False
    assert calib.no_trade_exact(t, "forex", []) is False
