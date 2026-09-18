import pytest

import soramimic_yomi


def _readings(text: str, nbest: int = 16) -> list[str]:
    return [
        candidate.reading
        for candidate in soramimic_yomi.get_yomi_candidates(text, nbest=nbest)
    ]


def test_canonical_candidate_is_exactly_existing_yomi():
    for text in ("海は広いな", "1羽のうさぎ", "AI 4443", "pick it up"):
        candidates = soramimic_yomi.get_yomi_candidates(text)
        assert candidates[0].reading == soramimic_yomi.get_yomi(text)
        assert candidates[0].rank == 0
        assert candidates[0].cost == 0.0
        assert candidates[0].sources == ("canonical",)
        assert candidates[0].spans == ()


def test_nbest_one_is_backward_compatible_and_bounds_are_checked():
    candidates = soramimic_yomi.get_yomi_candidates("AI 4443", nbest=1)
    assert [candidate.reading for candidate in candidates] == [
        soramimic_yomi.get_yomi("AI 4443")
    ]
    with pytest.raises(ValueError, match="between 1 and 32"):
        soramimic_yomi.get_yomi_candidates("AI", nbest=0)
    with pytest.raises(ValueError, match="between 1 and 32"):
        soramimic_yomi.get_yomi_candidates("AI", nbest=33)


def test_multi_digit_number_gains_digitwise_and_name_variants():
    candidates = soramimic_yomi.get_yomi_candidates("4443で外れる炭酸水", nbest=16)
    readings = [candidate.reading for candidate in candidates]

    assert readings[0].startswith("ヨンセンヨンヒャクヨンジューサン")
    assert "ヨンヨンヨンサンデハズレルタンサンスイ" in readings
    digitwise = next(
        candidate
        for candidate in candidates
        if candidate.reading.startswith("ヨンヨンヨンサン")
    )
    assert digitwise.spans[0].surface == "4443"
    assert digitwise.spans[0].rule == "digit-by-digit"
    assert digitwise.sources == ("number",)
    assert any(reading.startswith("シヨンヨンサン") for reading in readings)


def test_single_digit_counter_keeps_contextual_default_without_forced_variant():
    candidates = soramimic_yomi.get_yomi_candidates("1羽のうさぎ")
    assert [candidate.reading for candidate in candidates] == ["イチワノウサギ"]


def test_acronym_gains_letter_name_reading():
    candidates = soramimic_yomi.get_yomi_candidates("AI", nbest=8)
    assert candidates[0].reading == "アイ"
    spelled = next(
        candidate for candidate in candidates if candidate.reading == "エーアイ"
    )
    assert spelled.spans[0].rule == "letter-by-letter"
    assert spelled.spans[0].start == 0
    assert spelled.spans[0].end == 2


def test_lowercase_word_can_be_spelled_but_keeps_lexical_reading_first():
    readings = _readings("reason", nbest=8)
    assert readings[0] == "リーザン"
    assert "アールイーエーエスオーエヌ" in readings


def test_connected_english_phrase_is_generated_from_phonemes():
    candidates = soramimic_yomi.get_yomi_candidates("pick it up", nbest=12)
    assert candidates[0].reading == "ピックイットアップ"
    connected = next(
        candidate for candidate in candidates if candidate.reading == "ピキタップ"
    )
    assert connected.sources == ("english-phrase",)
    assert connected.spans[0].surface == "pick it up"
    assert connected.spans[0].rule == "connected"


def test_connected_english_includes_cross_word_fusion():
    candidates = soramimic_yomi.get_yomi_candidates("did you", nbest=12)
    assert candidates[0].reading == "ディドユー"
    fused = next(candidate for candidate in candidates if candidate.reading == "ディジュー")
    assert "boundary-fusion" in fused.spans[0].rule


def test_connected_english_never_drops_an_entire_function_word():
    readings = _readings("rock and", nbest=12)
    assert "ラカンド" in readings
    assert "ラカン" in readings


def test_disjoint_variants_can_be_combined_without_cartesian_explosion():
    candidates = soramimic_yomi.get_yomi_candidates("AI 4443", nbest=16)
    combined = next(
        candidate
        for candidate in candidates
        if candidate.reading == "エーアイヨンヨンヨンサン"
    )
    assert [span.rule for span in combined.spans] == [
        "letter-by-letter",
        "digit-by-digit",
    ]
    assert combined.sources == ("latin", "number")
    assert len(candidates) <= 16


def test_candidates_are_distinct_ranked_and_serializable():
    candidates = soramimic_yomi.get_yomi_candidates("did you 4443", nbest=16)
    assert len({candidate.reading for candidate in candidates}) == len(candidates)
    assert [candidate.rank for candidate in candidates] == list(range(len(candidates)))
    payload = candidates[-1].to_dict()
    assert payload["reading"] == candidates[-1].reading
    assert isinstance(payload["sources"], list)
    assert isinstance(payload["spans"], list)
