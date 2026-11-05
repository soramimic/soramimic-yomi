"""Normalization of supplied kana pronunciations, without text inference."""

from __future__ import annotations

import re
import unicodedata

_KANA = re.compile(r"[ァ-ヺーヽヾ]+")
_SEPARATORS = re.compile(r"[\s・、。,.=:;/!?()\[\]{}「」『』【】〈〉《》<>\-'’\"]+")
_EXPANDABLE = re.compile(r"[A-Za-z0-9\u3400-\u9fff々〆〇]+")
_SMALL = str.maketrans("ァィゥェォャュョヮヵヶ", "アイウエオヤユヨワカケ")
_PAIRS = re.compile(
    r"(?:[ウクグスズツヌフブプヴ][ァィェォ]"
    r"|[キギシジチヂニヒビピミリ][ャュョェ]"
    r"|[テデ][ィャュョ]|[トド]ゥ|イ[ェュ]|[クグ]ヮ|[フヴ][ャュョ])"
)
_VOWELS = {
    char: vowel
    for vowel, row in {
        "ア": "アカサタナハマヤラワガザダバパァャヮヵヷ",
        "イ": "イキシチニヒミリギジヂビピィヰヸ",
        "ウ": "ウクスツヌフムユルグズヅブプヴゥュ",
        "エ": "エケセテネヘメレゲゼデベペェヶヱヹ",
        "オ": "オコソトノホモヨロヲゴゾドボポォョヺ",
    }.items()
    for char in row
}


def normalize_reading(text: str, *, expand_non_kana: bool = False) -> str:
    """Validate and normalize a supplied reading without inferring its words.

    Width and hiragana are unified, iteration marks expanded, and small kana
    outside a compound mora opened. Repeated long marks become explicit vowels
    after the first mark, preserving their number. Literal vowel sequences
    (including オウ and エイ), ハ/ヘ/ヲ, and valid compound moras are preserved.
    Name separators are silent and keep neighboring moras separate during
    normalization. Other non-kana input is rejected by default. Opting into
    expand_non_kana resolves only non-kana spans using get_yomi; supplied kana
    never passes through the text frontend, even in a mixed reading.
    """
    kana = unicodedata.normalize("NFKC", text).strip()
    kana = "".join(
        chr(ord(char) + 0x60) if "ぁ" <= char <= "ゖ" or char in "ゝゞ" else char
        for char in kana
    )
    out: list[str] = []
    for chunk in re.split(r"([ァ-ヺーヽヾ]+)", kana):
        if not chunk:
            continue
        if _KANA.fullmatch(chunk):
            out.append(_normalize_kana(chunk, text))
            continue
        lexical = _SEPARATORS.sub("", chunk)
        if not lexical:
            continue
        if expand_non_kana and _EXPANDABLE.fullmatch(lexical):
            from .core import get_yomi

            inferred = get_yomi(chunk)
            if inferred:
                out.append(normalize_reading(inferred))
                continue
        invalid = "".join(dict.fromkeys(lexical))
        raise ValueError(
            f"指定した読み「{text}」に使えない文字「{invalid}」があります。"
            "読みをカナで指定してください。"
        )
    if not out:
        raise ValueError(f"指定した読み「{text}」: 読みが空です。読みをカナで指定してください。")
    return "".join(out)


def _normalize_kana(kana: str, text: str) -> str:
    """Normalize one uninterrupted kana span, preserving explicit vowel count."""

    expanded: list[str] = []
    for char in kana:
        if char in "ヽヾ":
            if not expanded or expanded[-1] in "ーンッ":
                raise ValueError(f"指定した読み「{text}」の繰り返し記号の位置を確認してください。")
            base = unicodedata.normalize("NFD", expanded[-1])[0]
            char = unicodedata.normalize("NFC", base + ("\u3099" if char == "ヾ" else ""))
            if len(char) != 1 or not _KANA.fullmatch(char):
                raise ValueError(f"指定した読み「{text}」の濁音の繰り返しをカナで指定してください。")
        expanded.append(char)

    out: list[str] = []
    vowel = ""
    previous = ""
    for char in expanded:
        if char == "ー":
            if not out:
                raise ValueError(f"指定した読み「{text}」の先頭に長音は指定できません。")
            out.append(vowel if previous == "ー" and vowel else char)
        else:
            if out and _PAIRS.fullmatch(out[-1] + char):
                normalized = char
            else:
                normalized = char.translate(_SMALL)
            out.append(normalized)
            vowel = _VOWELS.get(normalized, "")
        previous = char
    return "".join(out)
