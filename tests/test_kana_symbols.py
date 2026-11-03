"""Literal kana must retain their reading even when tagged as symbols."""

import pytest

from soramimic_yomi import get_tokens, get_yomi, get_yomi_candidates


@pytest.mark.parametrize("text", ["ノ", "ﾉ", "の", "ノ。"])
def test_standalone_kana_is_audible(text):
    assert get_yomi(text) == "ノ"
    assert get_yomi(text, apply_rules=False) == "ノ"
    tokens = get_tokens(text)
    assert "".join(t["surface_form"] for t in tokens) == text
    assert "".join(t["pronunciation"] for t in tokens) == "ノ"
    assert any(not t["is_silent"] for t in tokens)
    assert get_yomi_candidates(text)[0].reading == "ノ"


@pytest.mark.parametrize("text", ["。", "、", "❤", "???"])
def test_nonlexical_symbols_stay_silent(text):
    assert get_yomi(text) == ""
    assert all(t["is_silent"] for t in get_tokens(text))
