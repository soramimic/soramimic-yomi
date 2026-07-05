"""pyopenjtalk-plus ベースの読み推定コア。

- 読み(発音カタカナ)の取得: get_yomi()
- kuromoji互換のトークン列の取得: get_tokens()

初回呼び出し時に同梱のユーザー辞書(dic/user.csv)をコンパイルして適用する。
"""

from __future__ import annotations

import re

import pyopenjtalk

from .rules import normalize
from .userdic import ensure_user_dict

# NJDのpronに含まれるアクセント核などの記号(読みとしては不要)
_PRON_MARKS = re.compile(r"[’]")
# 読みに寄与しない発音(句読点・ポーズ)
_NON_YOMI_PRON = {"", "、", "。", "・", "?", "!"}


def _clean_pron(pron: str | None) -> str:
    return _PRON_MARKS.sub("", pron or "")


def _run_frontend(text: str) -> list[dict]:
    ensure_user_dict()
    return pyopenjtalk.run_frontend(text)


def get_yomi(text: str, *, apply_rules: bool = True) -> str:
    """テキストの読み(発音カタカナ)を返す。

    apply_rules=True のとき、空耳用の正規化ルール(英語→カナ等)を
    読み推定の前に適用する。
    """
    if apply_rules:
        text = normalize(text)
    nodes = _run_frontend(text)
    return "".join(
        p for n in nodes if (p := _clean_pron(n["pron"])) not in _NON_YOMI_PRON
    )


def get_tokens(text: str, *, apply_rules: bool = False) -> list[dict]:
    """kuromoji.js互換のトークン列を返す。

    surface_form / pronunciation / pos などのフィールド名は kuromoji に合わせ、
    未知の読みは "*" とする(soramimic の TextAnalyzer の未知語判定に合わせる)。
    加えて chain_flag(アクセント句の連結情報。0/-1=句頭)を付与する。
    デフォルトでは正規化ルールを適用しない(表層を保つ。英語処理などは
    利用側が行う想定)。
    """
    if apply_rules:
        text = normalize(text)
    tokens = []
    for i, n in enumerate(_run_frontend(text)):
        pron = _clean_pron(n["pron"])
        tokens.append(
            {
                "surface_form": n["string"],
                "basic_form": n["orig"] or "*",
                "reading": n["read"] or "*",
                "pronunciation": pron or "*",
                "pos": n["pos"],
                "pos_detail_1": n["pos_group1"],
                "pos_detail_2": n["pos_group2"],
                "pos_detail_3": n["pos_group3"],
                "conjugated_type": n["ctype"],
                "conjugated_form": n["cform"],
                "word_position": i + 1,
                "chain_flag": n["chain_flag"],
            }
        )
    return tokens
