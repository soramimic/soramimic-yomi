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
])
def test_normalize_supplied_reading_without_inference(text, expected):
    assert normalize_reading(text) == expected
    assert normalize_reading(expected) == expected


@pytest.mark.parametrize("text", ["", "  ", "メカX", "メカ２", "東京", "❤", "???",
                                 "カ ナ", "ハナイ・ティー", "セ・ェ", "ピエール＝ジル",
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


@pytest.mark.parametrize("text, expected", [
    ("はない", "ハナイ"), ("ハナイ", "ハナイ"), ("はへを", "ハヘヲ"),
    (" ｳｯｾｪﾜ ", "ウッセエワ"), ("ドーー", "ドーオ"),
    ("ティーファイル", "ティーファイル"), ("キャァ", "キャア"),
    ("トウキョウ", "トウキョウ"), ("フュージョン", "フュージョン"),
    ("いすゞ", "イスズ"),
])
def test_word_reading_normalizes_kana_without_frontend(monkeypatch, text, expected):
    from soramimic_yomi import get_word_reading

    def forbidden(*args, **kwargs):
        raise AssertionError("kana-only readings must not be inferred")

    monkeypatch.setattr("soramimic_yomi.core._run_frontend", forbidden)
    assert get_word_reading(text) == expected


@pytest.mark.parametrize("text, prepared", [
    ("はないX", "はないX"), (" メカＸ ", "メカX"),
    ("ポリゴン２", "ポリゴン2"), ("ケルヴィン卿", "ケルヴィン卿"),
    ("カ ナ", "カ ナ"), ("ハナイ・ティー", "ハナイ・ティー"),
])
def test_word_reading_infers_whole_mixed_input(monkeypatch, text, prepared):
    from soramimic_yomi import get_word_reading

    seen = []

    def infer(value):
        seen.append(value)
        return "わないエクス"

    monkeypatch.setattr("soramimic_yomi.core.get_yomi", infer)
    assert get_word_reading(text) == "ワナイエクス"
    assert seen == [prepared]


@pytest.mark.parametrize("inferred", ["", "  ", "X", "ー"])
def test_word_reading_rejects_invalid_inferred_result(monkeypatch, inferred):
    from soramimic_yomi import get_word_reading

    monkeypatch.setattr("soramimic_yomi.core.get_yomi", lambda text: inferred)
    with pytest.raises(ValueError, match="指定した読み「対象X」"):
        get_word_reading("対象X")


@pytest.mark.parametrize("text", ["", " ", "❤", "???", "ー", "ヾ"])
def test_word_reading_rejects_unreadable_input(text):
    from soramimic_yomi import get_word_reading

    with pytest.raises(ValueError, match="指定した読み"):
        get_word_reading(text)
