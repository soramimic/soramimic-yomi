import soramimi_yomi
from soramimi_yomi.rules import english as english_rules


def test_basic_yomi():
    assert soramimi_yomi.get_yomi("海は広いな") == "ウミワヒロイナ"


def test_userdic_compound():
    # 素のnaist-jdicでは 夕/焼/小/焼 に分割され「ユーヤキショーショー」になる。
    # 同梱ユーザー辞書(dic/user.csv)で補正されることを確認
    assert soramimi_yomi.get_yomi("夕焼小焼の赤とんぼ") == "ユウヤケコヤケノアカトンボ"


def test_numbers():
    # pyopenjtalk-plus の数字読みが効いていること(kuromojiでは不可能な芸当)
    assert soramimi_yomi.get_yomi("1羽のうさぎ") == "イチワノウサギ"
    assert soramimi_yomi.get_yomi("2020年5月") == "ニセンニジューネンゴガツ"


def test_english_rule():
    # CMUdict+e2kによる英語→カナ(素のpyopenjtalkはスペル読みしてしまう)
    yomi = soramimi_yomi.get_yomi("Hello, nice to meet you")
    assert "エヌ" not in yomi  # スペル読みになっていない
    assert yomi.startswith("ハロー")


def test_english_rule_override_path():
    # (a) 自前例外辞書(data/english_overrides.csv)が最優先で引かれる
    assert english_rules._convert_word("worried") == "ワーリド"


def test_english_rule_cmudict_p2k_path():
    # (b) CMUdict収録語は発音(ARPAbet)ベースのe2k.P2Kで変換される
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
    assert "’" not in soramimi_yomi.get_yomi("うさぎ追いしかの山")


def test_tokens_kuromoji_compatible():
    tokens = soramimi_yomi.get_tokens("海は広いな")
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
    # /tokenize は表層を保つ(英語正規化を適用しない)。
    # ただし pyopenjtalk は英字を全角に正規化する点に注意
    tokens = soramimi_yomi.get_tokens("Hello world")
    assert any("Ｈｅｌｌｏ" in t["surface_form"] for t in tokens)
