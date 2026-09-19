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


@pytest.mark.parametrize("text", ["shout it out", "ＳＨＯＵＴ　ＩＴ　ＯＵＴ"])
def test_short_connected_reading_survives_default_nbest(text):
    candidates = soramimic_yomi.get_yomi_candidates(text)
    assert candidates[0].reading == soramimic_yomi.get_yomi(text)
    compact = next(candidate for candidate in candidates if candidate.reading == "シャティタ")
    assert compact.sources == ("english-phrase",)
    assert compact.spans[0].surface == text
    assert compact.spans[0].start == 0
    assert compact.spans[0].end == len(text)
    assert compact.spans[0].rule == "connected+compact-diphthongs+final-coda-elision"


@pytest.mark.parametrize("text,compact", [
    ("take it", "テキ"),
    ("ride it", "ラディ"),
    ("hold it", "ホルディ"),
    ("join us", "ジョナ"),
    ("pick it up", "ピキタ"),
])
def test_compaction_generalizes_to_other_words(text, compact):
    assert compact in _readings(text, nbest=8)


def test_individual_reductions_remain_available():
    readings = _readings("shout it out", nbest=32)
    assert {"シャウティタウト", "シャティタト", "シャウティタウ", "シャティタ"} <= set(readings)


def test_compact_rules_preserve_clusters_missing_phones_and_japanese(monkeypatch):
    from soramimic_yomi.candidates import _english_phrase_readings
    from soramimic_yomi.rules import english

    # Final /nt/ is not a single coda. No word or vowel nucleus is deleted.
    variants = _english_phrase_readings("shout it aunt")
    assert variants
    assert not any("coda-elision" in rule for _, rule, _ in variants)
    assert _readings("シャウトイットアウト") == ["シャウトイットアウト"]
    assert _readings("海は広いな") == [soramimic_yomi.get_yomi("海は広いな")]
    monkeypatch.setattr(english, "_pronunciations", lambda word: ())
    assert _english_phrase_readings("shout it out") == []


def test_compact_candidates_keep_surrounding_text_and_bounded_deterministic_ranks():
    text = "海 shout it out 空"
    candidates = soramimic_yomi.get_yomi_candidates(text)
    assert "ウミシャティタソラ" in [candidate.reading for candidate in candidates]
    assert candidates == soramimic_yomi.get_yomi_candidates(text)
    assert len(candidates) <= 8
    assert len({candidate.reading for candidate in candidates}) == len(candidates)
    assert [candidate.rank for candidate in candidates] == list(range(len(candidates)))


@pytest.mark.parametrize("text,reading", [
    ("Shout it out! Shout it out!", "シャティタシャティタ"),
    ("Shout it out! shout it out! SHOUT IT OUT!", "シャティタシャティタシャティタ"),
    ("Ｓｈｏｕｔ　ｉｔ　ｏｕｔ! shout  it\tout!", "シャティタシャティタ"),
    ("pick it up, PICK IT UP", "ピキタピキタ"),
    ("take it! take it!", "テキテキ"),
    ("send it! send it!", "センディセンディ"),
    ("Shout it out! 海でShout it out!", "シャティタウミデシャティタ"),
])
def test_consistent_repeated_readings_survive_default_nbest(text, reading):
    candidates = soramimic_yomi.get_yomi_candidates(text)
    assert candidates[0].reading == soramimic_yomi.get_yomi(text)
    compact = next(candidate for candidate in candidates if candidate.reading == reading)
    assert len(compact.spans) >= 2
    assert all(span.surface == text[span.start:span.end] for span in compact.spans)
    assert all(left.end <= right.start for left, right in zip(compact.spans, compact.spans[1:]))
    assert compact.sources == ("english-phrase",)
    assert candidates == soramimic_yomi.get_yomi_candidates(text)
    assert [candidate.cost for candidate in candidates] == sorted(candidate.cost for candidate in candidates)


def test_repeated_readings_keep_partial_realizations_and_candidate_bounds():
    text = "Shout it out! Shout it out!"
    candidates = soramimic_yomi.get_yomi_candidates(text, nbest=32)
    assert "シャティタシャウトイットアウト" in [candidate.reading for candidate in candidates]
    assert "シャウトイットアウトシャティタ" in [candidate.reading for candidate in candidates]
    for nbest in (1, 8, 32):
        candidates = soramimic_yomi.get_yomi_candidates("Shout it out! " * 5, nbest=nbest)
        assert len(candidates) <= nbest
        assert len({candidate.reading for candidate in candidates}) == len(candidates)
        assert [candidate.rank for candidate in candidates] == list(range(len(candidates)))
        if nbest > 1:
            assert "シャティタ" * 5 in [candidate.reading for candidate in candidates]


def test_repeated_overlapping_windows_never_duplicate_surface_spans():
    candidates = soramimic_yomi.get_yomi_candidates("at at at at", nbest=32)
    for candidate in candidates:
        assert all(left.end <= right.start for left, right in zip(candidate.spans, candidate.spans[1:]))


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


@pytest.mark.parametrize("text,connected,compact", [
    ("shout it out", "シャウティタウト", "シャティタ"),
    ("Shout it out! Shout it out!", "シャウティタウトシャウティタウト", "シャティタシャティタ"),
    ("Shout it out! Pick it up!", "シャウティタウトピキタップ", "シャティタピキタ"),
])
def test_spoken_profiles_have_no_shortening_or_repetition_penalty(text, connected, compact):
    candidates = soramimic_yomi.get_yomi_candidates(text)
    by_reading = {candidate.reading: candidate for candidate in candidates}
    assert by_reading[connected].cost == by_reading[compact].cost == candidates[0].cost == 0
    assert all(candidate.cost == 0 for candidate in candidates if candidate.sources == ("english-phrase",))
