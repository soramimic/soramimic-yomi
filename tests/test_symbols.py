import soramimic_yomi as yomi


def readings(text, nbest=8):
    return {candidate.reading for candidate in yomi.get_yomi_candidates(text, nbest=nbest)}


def test_symbol_names_are_candidates_without_changing_canonical_reading():
    for text in ("♡が届いた", "答えは○か×か", "＋－を選ぶ", "100％の力"):
        candidates = yomi.get_yomi_candidates(text)
        assert candidates[0].reading == yomi.get_yomi(text)
        assert candidates == yomi.get_yomi_candidates(text)
        assert len(candidates) <= 8
    assert {"ガトドイタ", "ハートガトドイタ"} <= readings("♡が届いた")
    assert "コタエワマルカバツカ" in readings("答えは○か×か")
    assert "プラスマイナスヲエラブ" in readings("＋－を選ぶ")


def test_multiple_symbol_names_and_silence_are_available():
    assert {"コタエワダッタ", "コタエワバツダッタ", "コタエワカケルダッタ"} <= readings("答えは×だった")
    assert {"", "ムゲン", "ムゲンダイ", "インフィニティ"} <= readings("∞")


def test_repeated_symbols_keep_a_complete_spoken_candidate():
    text = "♡と♡と♡と♡"
    assert "ハートトハートトハートトハート" in readings(text)


def test_unknown_symbols_and_original_offsets_survive():
    text = "空 🧭と❤️と♡←HEARTBEAT"
    spans = yomi.get_symbol_spans(text)
    assert [span.surface for span in spans] == ["🧭", "❤️", "♡←"]
    assert all(span.surface == text[span.start:span.end] for span in spans)
    assert spans[0].readings == ("",)
    assert spans[1].readings == ("", "ハート")
    assert spans[2].readings == ("", "ハート")


def test_normal_punctuation_and_word_apostrophes_do_not_gain_names():
    assert yomi.get_symbol_spans("今日は、晴れ。Don't stop!") == ()
    assert readings("晴れ。") == {yomi.get_yomi("晴れ。")}


def test_symbol_candidate_provenance_uses_unchanged_surface():
    candidates = yomi.get_yomi_candidates("空に♡")
    candidate = next(c for c in candidates if c.reading == "ソラニハート")
    assert candidate.sources == ("symbol",)
    assert candidate.spans[0].surface == "♡"
    assert candidate.spans[0].start == 2
    assert candidate.spans[0].end == 3
