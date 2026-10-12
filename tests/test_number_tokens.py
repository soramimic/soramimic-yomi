import pytest

from soramimic_yomi import get_tokens, get_yomi


@pytest.mark.parametrize("number", ["1人", "2人", "２人", "12人", "１２人"])
def test_numeric_counter_keeps_surrounding_word_boundaries(number):
    text = f"晴れた日に{number}で公園へ行った"
    tokens = get_tokens(text)
    surfaces = [token["surface_form"] for token in tokens]

    assert "".join(surfaces) == text
    assert surfaces[:4] == ["晴れ", "た", "日", "に"]
    assert surfaces[-5:] == ["で", "公園", "へ", "行っ", "た"]
    assert tokens[0]["pos"] == "動詞"
    assert tokens[-5]["pos"] == "助詞"
    assert "".join(t["pronunciation"] for t in tokens) == get_yomi(
        text, apply_rules=False
    )
    assert [t["word_position"] for t in tokens] == list(range(1, len(tokens) + 1))
    if number in {"1人", "2人", "２人"}:
        counter = next(t for t in tokens if t["surface_form"] == number)
        assert counter["pronunciation"] == ("ヒトリ" if number == "1人" else "フタリ")


@pytest.mark.parametrize("middle", [
    "2026年10月12日", "２０２０年５月", "3.14倍", "1,200円", "１０分",
    "100000人", "2人と3人", "03時", "ｶﾞﾗｽを2枚",
])
def test_number_expansion_keeps_surface_reading_and_later_words(middle):
    text = f"今日は{middle}について話した"
    tokens = get_tokens(text)
    surfaces = [t["surface_form"] for t in tokens]

    assert "".join(surfaces) == text
    assert surfaces[:2] == ["今日", "は"]
    assert "話し" in surfaces
    assert surfaces[-1] == "た"
    assert "".join(t["pronunciation"] for t in tokens) == get_yomi(
        text, apply_rules=False
    )
    assert all(t["surface_form"] for t in tokens)


def test_expanded_number_is_not_split_between_invented_surface_positions():
    tokens = get_tokens("約2026人が集まる")
    number = next(t for t in tokens if t["surface_form"] == "2026")
    assert number["pronunciation"] == "ニセンニジューロク"
    assert number["pos"] == "名詞"
    assert number["pos_detail_1"] == "数"


def test_unrelated_surface_change_still_uses_lossless_fallback(monkeypatch):
    from soramimic_yomi import core

    nodes = core._run_frontend("別の表記")
    monkeypatch.setattr(core, "_run_frontend", lambda _: nodes)
    tokens = get_tokens("原文2人")
    assert len(tokens) == 1
    assert tokens[0]["surface_form"] == "原文2人"
    assert tokens[0]["pronunciation"] == "ベツノヒョーキ"
