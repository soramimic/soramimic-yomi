"""pyopenjtalk-plus ベースの読み推定コア。

- 読み(発音カタカナ)の取得: get_yomi()
- kuromoji互換のトークン列の取得: get_tokens()

初回呼び出し時に同梱のユーザー辞書(dic/user.csv)をコンパイルして適用する。
"""

from __future__ import annotations

import re
import unicodedata

import pyopenjtalk

from .rules.english import _convert_word
from .userdic import ensure_user_dict

# NJDのpronに含まれるアクセント核などの記号(読みとしては不要)
_PRON_MARKS = re.compile(r"[’]")
# 読みに寄与しない発音(句読点・ポーズ)
_NON_YOMI_PRON = {"", "、", "。", "・", "?", "!"}
_LOSSLESS_PART = re.compile(r"\s+|[A-Za-z]+(?:['\u2019][A-Za-z]+)*")


def _clean_pron(pron: str | None) -> str:
    return _PRON_MARKS.sub("", pron or "")


def _run_frontend(text: str) -> list[dict]:
    ensure_user_dict()
    return pyopenjtalk.run_frontend(text)


def _node_is_silent(node: dict) -> bool:
    # A one-letter Latin token can be classified as an alphabet symbol by
    # pyopenjtalk, but its reading is meaningful (for example I -> アイ).
    return node["pos"] == "記号" and node["pos_group1"] != "アルファベット"


def get_yomi(text: str, *, apply_rules: bool = True) -> str:
    """テキストの読み(発音カタカナ)を返す。

    apply_rules=True のとき、get_tokens() と同じ英語変換と無音表現を用いて
    pronunciationを連結する。Falseは従来どおりpyopenjtalkの直接読みを返す。
    """
    if apply_rules:
        # Use the same direct English readings as /tokenize.  Feeding converted
        # kana back through pyopenjtalk can change ヴ to ブ (love: ラヴ -> ラブ).
        return "".join(token["pronunciation"] for token in get_tokens(text))

    nodes = _run_frontend(text)
    return "".join(
        p
        for n in nodes
        if not _node_is_silent(n)
        if (p := _clean_pron(n["pron"])) not in _NON_YOMI_PRON
    )


def _token(
    surface: str,
    *,
    basic_form: str,
    reading: str,
    pronunciation: str,
    pos: str,
    pos_detail_1: str,
    pos_detail_2: str = "*",
    pos_detail_3: str = "*",
    conjugated_type: str = "*",
    conjugated_form: str = "*",
    chain_flag: int = 0,
    is_silent: bool = False,
) -> dict:
    return {
        "surface_form": surface,
        "basic_form": basic_form,
        "reading": reading,
        "pronunciation": pronunciation,
        "pos": pos,
        "pos_detail_1": pos_detail_1,
        "pos_detail_2": pos_detail_2,
        "pos_detail_3": pos_detail_3,
        "conjugated_type": conjugated_type,
        "conjugated_form": conjugated_form,
        "chain_flag": chain_flag,
        "is_silent": is_silent,
    }


def _align_surfaces(source: str, nodes: list[dict]) -> list[str] | None:
    """Map pyopenjtalk's normalized node strings back onto the original text."""
    surfaces: list[str] = []
    offset = 0
    for index, node in enumerate(nodes):
        expected = unicodedata.normalize("NFKC", node["string"])
        if index == len(nodes) - 1:
            candidate = source[offset:]
            if unicodedata.normalize("NFKC", candidate) != expected:
                return None
            surfaces.append(candidate)
            offset = len(source)
            continue

        found = None
        for end in range(offset + 1, len(source) + 1):
            candidate = source[offset:end]
            normalized = unicodedata.normalize("NFKC", candidate)
            if normalized == expected:
                found = (candidate, end)
                break
            if len(normalized) > len(expected):
                break
        if found is None:
            return None
        candidate, offset = found
        surfaces.append(candidate)

    return surfaces if offset == len(source) else None


def _tokens_from_japanese_segment(text: str) -> list[dict]:
    nodes = _run_frontend(text)
    if not nodes:
        # pyopenjtalk can drop unusual control/format characters.  They still
        # need a lossless, explicitly silent representation in the contract.
        return (
            [
                _token(
                    text,
                    basic_form=text or "*",
                    reading="",
                    pronunciation="",
                    pos="記号",
                    pos_detail_1="一般",
                    is_silent=True,
                )
            ]
            if text
            else []
        )

    surfaces = _align_surfaces(text, nodes)
    if surfaces is None:
        # Safe fallback: preserve the exact surface and the aggregate reading.
        # This is preferable to returning normalized or missing input bytes.
        pronunciation = "".join(
            p for node in nodes
            if not _node_is_silent(node)
            if (p := _clean_pron(node["pron"])) not in _NON_YOMI_PRON
        )
        return [
            _token(
                text,
                basic_form=text or "*",
                reading=pronunciation,
                pronunciation=pronunciation,
                pos="名詞" if pronunciation else "記号",
                pos_detail_1="一般",
                is_silent=not pronunciation,
                chain_flag=nodes[0]["chain_flag"],
            )
        ]

    result = []
    for surface, node in zip(surfaces, nodes, strict=True):
        is_silent = _node_is_silent(node)
        pronunciation = "" if is_silent else _clean_pron(node["pron"])
        reading = "" if is_silent else _clean_pron(node["read"])
        result.append(
            _token(
                surface,
                basic_form=node["orig"] or "*",
                reading=reading or ("" if is_silent else "*"),
                pronunciation=pronunciation or ("" if is_silent else "*"),
                pos=node["pos"],
                pos_detail_1=node["pos_group1"],
                pos_detail_2=node["pos_group2"],
                pos_detail_3=node["pos_group3"],
                conjugated_type=node["ctype"],
                conjugated_form=node["cform"],
                chain_flag=node["chain_flag"],
                is_silent=is_silent,
            )
        )
    return result


def get_tokens(text: str, *, apply_rules: bool = False) -> list[dict]:
    """kuromoji.js互換のトークン列を返す。

    surface_form / pronunciation / pos などのフィールド名は kuromoji に合わせ、
    未知の読みは "*" とする(soramimic の TextAnalyzer の未知語判定に合わせる)。
    加えて chain_flag(アクセント句の連結情報。0/-1=句頭)を付与する。
    surface_form の連結は常に入力と完全一致する。英単語(ASCII英字、単語内の
    straight/curly apostropheを含む)は1語としてカナ読みを付与し、空白と記号は
    pronunciation/readingを空文字にした is_silent token として返す。

    apply_rules は後方互換のため残しているが、表層保持契約を優先するため
    token化対象の文字列自体は正規化しない。
    """
    del apply_rules
    tokens: list[dict] = []
    offset = 0
    for match in _LOSSLESS_PART.finditer(text):
        if match.start() > offset:
            tokens.extend(_tokens_from_japanese_segment(text[offset:match.start()]))

        surface = match.group(0)
        if surface.isspace():
            tokens.append(
                _token(
                    surface,
                    basic_form=surface,
                    reading="",
                    pronunciation="",
                    pos="記号",
                    pos_detail_1="空白",
                    is_silent=True,
                )
            )
        else:
            pronunciation = _convert_word(surface)
            tokens.append(
                _token(
                    surface,
                    basic_form=surface.lower().replace("\u2019", "'"),
                    reading=pronunciation,
                    pronunciation=pronunciation,
                    pos="名詞",
                    pos_detail_1="一般",
                )
            )
        offset = match.end()

    if offset < len(text):
        tokens.extend(_tokens_from_japanese_segment(text[offset:]))

    for i, token in enumerate(tokens, start=1):
        token["word_position"] = i
    return tokens
