"""Supplied readings must not be reinterpreted as sentences."""

import pytest

from soramimic_yomi import get_yomi, normalize_reading


@pytest.mark.parametrize("text, expected", [
    ("はない", "ハナイ"), ("ハナイ", "ハナイ"),
    ("はへを", "ハヘヲ"), ("の", "ノ"),
    (" ｳｯｾｪﾜ ", "ウッセエワ"), ("はぁ", "ハア"),
    ("キャァ", "キャア"), ("ェ", "エ"), ("ッォ", "ッオ"),
    ("ティーファイル", "ティーファイル"), ("きゃっぷ", "キャップ"),
    ("クヮルテット", "クヮルテット"), ("フュージョン", "フュージョン"),
    ("トーキョー", "トーキョー"), ("ドーー", "ドーオ"),
    ("キャーーー", "キャーアア"), ("セーェ", "セーエ"),
    ("トウキョウ", "トウキョウ"), ("ケイ", "ケイ"),
    ("いすゞ", "イスズ"), ("さゝ", "ササ"), ("ばゝ", "バハ"),
    ("ハナイ・ティー", "ハナイティー"), ("カ ナ", "カナ"),
    ("セ・ェ", "セエ"), ("ピエール＝ジル", "ピエールジル"),
])
def test_normalize_supplied_reading_without_inference(text, expected):
    assert normalize_reading(text) == expected
    assert normalize_reading(expected) == expected


@pytest.mark.parametrize("text", ["", "  ", "メカX", "メカ２", "東京", "❤", "???",
                                 "ー", "ーハ", "ヾ", "ンヽ", "アヾ"])
def test_invalid_supplied_reading_is_rejected(text):
    with pytest.raises(ValueError, match="指定した読み"):
        normalize_reading(text)


def test_normalization_does_not_call_text_frontend(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("supplied readings must not be inferred")

    monkeypatch.setattr("soramimic_yomi.core._run_frontend", forbidden)
    assert normalize_reading("はない") == "ハナイ"
    assert normalize_reading("はない", expand_non_kana=True) == "ハナイ"


def test_sentence_reading_still_pronounces_particles():
    assert get_yomi("私は歌う") == "ワタシワウタウ"
    assert get_yomi("はない") == "ワナイ"


def test_mixed_reading_expands_only_non_kana_spans(monkeypatch):
    seen = []

    def infer(text):
        seen.append(text)
        return {"X": "エックス", "2": "ニ", "卿": "キョー"}[text]

    monkeypatch.setattr("soramimic_yomi.core.get_yomi", infer)
    assert normalize_reading("はないX", expand_non_kana=True) == "ハナイエックス"
    assert normalize_reading("ポリゴン２", expand_non_kana=True) == "ポリゴンニ"
    assert normalize_reading("ケルヴィン卿", expand_non_kana=True) == "ケルヴィンキョー"
    assert seen == ["X", "2", "卿"]


@pytest.mark.parametrize("text", ["❤", "ハナイ❤", "メカX❤", "???"])
def test_mixed_reading_does_not_discard_unreadable_symbols(text):
    with pytest.raises(ValueError, match="指定した読み"):
        normalize_reading(text, expand_non_kana=True)
