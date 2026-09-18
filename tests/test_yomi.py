import soramimic_yomi
from soramimic_yomi.rules import english as english_rules


def test_basic_yomi():
    assert soramimic_yomi.get_yomi("海は広いな") == "ウミワヒロイナ"


def test_userdic_compound():
    # 素のnaist-jdicでは 夕/焼/小/焼 に分割され「ユーヤキショーショー」になる。
    # 同梱ユーザー辞書(dic/user.csv)で補正されることを確認
    assert soramimic_yomi.get_yomi("夕焼小焼の赤とんぼ") == "ユウヤケコヤケノアカトンボ"


def test_numbers():
    # pyopenjtalk-plus の数字読みが効いていること(kuromojiでは不可能な芸当)
    assert soramimic_yomi.get_yomi("1羽のうさぎ") == "イチワノウサギ"
    assert soramimic_yomi.get_yomi("2020年5月") == "ニセンニジューネンゴガツ"


def test_english_rule():
    # CMUdict+e2kによる英語→カナ(素のpyopenjtalkはスペル読みしてしまう)
    yomi = soramimic_yomi.get_yomi("Hello, nice to meet you")
    assert "エヌ" not in yomi  # スペル読みになっていない
    assert yomi.startswith("ハロー")


def test_english_rule_override_path():
    # (a) 自前例外辞書(data/english_overrides.csv)が最優先で引かれる
    assert english_rules._convert_word("worried") == "ワーリド"


def test_english_rule_cmudict_arpakana_path():
    # (b) CMUdict収録語は発音(ARPAbet)を決定的規則で変換する
    assert "nice" in english_rules._cmudict()
    assert english_rules._convert_word("nice") == "ナイス"


def test_english_rule_c2k_fallback_path():
    # (c) CMUdict未収録語は綴りベースのe2k.C2Kにフォールバックする
    word = "anthropic"
    assert word not in english_rules._cmudict()
    kana = english_rules._convert_word(word)
    assert kana  # 何らかのカナに変換される
    assert "エー" not in kana and "エヌ" not in kana  # スペル読みになっていない


def test_accent_marks_stripped():
    # NJDのアクセント記号(’)が読みに混入しないこと
    assert "’" not in soramimic_yomi.get_yomi("うさぎ追いしかの山")


def test_tokens_kuromoji_compatible():
    tokens = soramimic_yomi.get_tokens("海は広いな")
    assert tokens[0]["surface_form"] == "海"
    assert tokens[0]["pronunciation"] == "ウミ"
    assert tokens[0]["pos"] == "名詞"
    for key in (
        "surface_form", "basic_form", "reading", "pronunciation",
        "pos", "pos_detail_1", "conjugated_type", "conjugated_form",
        "word_position", "chain_flag",
    ):
        assert key in tokens[0]


def test_tokens_keep_surface():
    # /tokenize は pyopenjtalk の全角化を公開せず、入力表層を保つ。
    tokens = soramimic_yomi.get_tokens("Hello world")
    assert "".join(t["surface_form"] for t in tokens) == "Hello world"
    normalized_tokens = soramimic_yomi.get_tokens("Hello world", apply_rules=True)
    assert "".join(t["surface_form"] for t in normalized_tokens) == "Hello world"


def test_tokens_preserve_all_whitespace_and_silence_it():
    text = "  Hello\tworld  "
    tokens = soramimic_yomi.get_tokens(text)

    assert "".join(t["surface_form"] for t in tokens) == text
    assert [t["surface_form"] for t in tokens if t["pos_detail_1"] == "空白"] == [
        "  ", "\t", "  "
    ]
    for token in (t for t in tokens if t["pos_detail_1"] == "空白"):
        assert token["reading"] == ""
        assert token["pronunciation"] == ""
        assert token["is_silent"] is True


def test_english_tokens_have_readings_regardless_of_part_of_speech_heuristics():
    tokens = soramimic_yomi.get_tokens("I love you")
    spoken = [t for t in tokens if not t["is_silent"]]

    assert [t["surface_form"] for t in spoken] == ["I", "love", "you"]
    assert [t["pronunciation"] for t in spoken] == ["アイ", "ラヴ", "ユー"]
    assert all(t["pos"] == "名詞" and t["pos_detail_1"] == "一般" for t in spoken)
    assert "".join(t["pronunciation"] for t in tokens) == "アイラヴユー"


def test_apostrophe_contraction_is_one_token_for_both_forms():
    straight = soramimic_yomi.get_tokens("don't stop")
    curly = soramimic_yomi.get_tokens("don’t stop")

    assert [t["surface_form"] for t in straight] == ["don't", " ", "stop"]
    assert [t["surface_form"] for t in curly] == ["don’t", " ", "stop"]
    assert straight[0]["pronunciation"] == curly[0]["pronunciation"] == "ドーント"
    assert "".join(t["pronunciation"] for t in straight) == "ドーントスタップ"
    assert soramimic_yomi.get_yomi("don't stop") == soramimic_yomi.get_yomi(
        "don’t stop"
    )


def test_mixed_japanese_punctuation_and_ruby_like_surface_are_lossless():
    for text, yomi in (
        ("Iとyou、love!", "アイトユーラヴ"),
        ("ルビ｜漢字《かんじ》", "ルビカンジカンジ"),
    ):
        tokens = soramimic_yomi.get_tokens(text)
        assert "".join(t["surface_form"] for t in tokens) == text
        assert "".join(t["pronunciation"] for t in tokens) == yomi

    punctuation = soramimic_yomi.get_tokens("、。!?｜《》")
    assert "".join(t["surface_form"] for t in punctuation) == "、。!?｜《》"
    assert all(t["is_silent"] and t["pronunciation"] == "" for t in punctuation)


def test_empty_and_whitespace_only_inputs_are_lossless():
    assert soramimic_yomi.get_tokens("") == []
    tokens = soramimic_yomi.get_tokens(" \t  ")
    assert len(tokens) == 1
    assert tokens[0]["surface_form"] == " \t  "
    assert tokens[0]["is_silent"] is True
