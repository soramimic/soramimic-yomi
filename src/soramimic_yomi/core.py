"""pyopenjtalk-plus ベースの読み推定コア。

- 読み(発音カタカナ)の取得: get_yomi()
- kuromoji互換のトークン列の取得: get_tokens()

初回呼び出し時に同梱のユーザー辞書(dic/user.csv)をコンパイルして適用する。
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

import pyopenjtalk

from .rules.english import _word_pronunciation
from .userdic import ensure_user_dict

# NJDのpronに含まれるアクセント核などの記号(読みとしては不要)
_PRON_MARKS = re.compile(r"[’]")
# 読みに寄与しない発音(句読点・ポーズ)
_NON_YOMI_PRON = {"", "、", "。", "・", "?", "!"}
_LOSSLESS_PART = re.compile(r"\s+|[A-Za-z]+(?:['\u2019][A-Za-z]+)*")
_KANJI_NUMBER = frozenset("〇零一二三四五六七八九十百千万億兆京")


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


def _align_number_surfaces(
    source: str, nodes: list[dict],
) -> list[tuple[str, list[dict]]] | None:
    """Map numeric NJD rewrites while retaining the surrounding lexical nodes.

    Only decimal-digit to kanji-number replacements are accepted. Boundaries
    inside an expansion have no exact source position, so e.g. the NJD nodes
    二/千/二/十/六 share the original surface 2026 instead of inventing cuts.
    """
    normalized = unicodedata.normalize("NFKC", source)
    strings = [unicodedata.normalize("NFKC", node["string"]) for node in nodes]
    target = "".join(strings)
    positions: dict[int, int] = {}
    changed = False
    matcher = SequenceMatcher(None, normalized, target, autojunk=False)
    for tag, a, b, c, d in matcher.get_opcodes():
        if tag == "equal":
            positions.update((c + i, a + i) for i in range(b - a + 1))
        elif (tag == "replace" and normalized[a:b].isascii()
              and normalized[a:b].isdecimal() and set(target[c:d]) <= _KANJI_NUMBER):
            positions[c], positions[d] = a, b
            changed = True
        else:
            return None
    if not changed:
        return None

    # NFKC can combine half-width kana or expand compatibility characters.
    # Retain only boundaries that also exist in the exact original surface.
    originals = {}
    for end in range(len(source) + 1):
        prefix = unicodedata.normalize("NFKC", source[:end])
        if normalized.startswith(prefix):
            originals[len(prefix)] = end

    result = []
    start = cursor = first = 0
    for i, text in enumerate(strings):
        cursor += len(text)
        position = positions.get(cursor)
        end = originals.get(position) if position is not None else None
        if end is not None and end > start:
            result.append((source[start:end], nodes[first:i + 1]))
            start, first = end, i + 1
    return result if start == len(source) and first == len(nodes) else None


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
    aligned = (list(zip(surfaces, ([node] for node in nodes), strict=True))
               if surfaces is not None else _align_number_surfaces(text, nodes))
    if aligned is None:
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
    for surface, group in aligned:
        node = group[0]
        is_silent = all(_node_is_silent(item) for item in group)
        pronunciation = "".join(_clean_pron(item["pron"]) for item in group
                                if not _node_is_silent(item))
        reading = "".join(_clean_pron(item["read"]) for item in group
                          if not _node_is_silent(item))
        result.append(
            _token(
                surface,
                basic_form="".join(item["orig"] for item in group) or "*",
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
            pronunciation, pronunciation_source = _word_pronunciation(surface)
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
            tokens[-1]["pronunciation_source"] = pronunciation_source
        offset = match.end()

    if offset < len(text):
        tokens.extend(_tokens_from_japanese_segment(text[offset:]))

    for i, token in enumerate(tokens, start=1):
        token["word_position"] = i
    return tokens
