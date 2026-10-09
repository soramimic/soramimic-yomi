"""Conventional symbol readings and lossless intervals for acoustic callers.

These are alternatives, not instructions to pronounce punctuation.  In
particular, an empty reading is a valid alternative, and an unknown symbol is
kept even when this small lexicon cannot propose a spoken reading.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import islice, product
import unicodedata


_READINGS = {
    "○": ("マル",), "◯": ("マル",), "〇": ("マル", "レイ"),
    "×": ("バツ", "カケル"), "÷": ("ワル",),
    "+": ("プラス",), "-": ("マイナス",), "−": ("マイナス",),
    "±": ("プラスマイナス",), "=": ("イコール",),
    "%": ("パーセント",), "&": ("アンド",), "@": ("アット",),
    "#": ("シャープ", "ハッシュ"), "?": ("ハテナ",),
    "♡": ("ハート",), "♥": ("ハート",), "❤": ("ハート",),
    "∞": ("ムゲン", "ムゲンダイ", "インフィニティ"),
}


@dataclass(frozen=True)
class SymbolSpan:
    """A possibly spoken symbol interval; offsets refer to the unchanged text."""

    start: int
    end: int
    surface: str
    readings: tuple[str, ...]
    source: str = "symbol-lexicon"

    def to_dict(self) -> dict:
        return asdict(self)


def _symbol(character: str) -> bool:
    normalized = unicodedata.normalize("NFKC", character)
    return normalized in _READINGS or unicodedata.category(character).startswith("S")


def _extension(character: str) -> bool:
    return character in "\ufe0e\ufe0f\u200d" or "\U0001f3fb" <= character <= "\U0001f3ff"


def get_symbol_spans(text: str) -> tuple[SymbolSpan, ...]:
    """Retain contiguous symbol groups, including groups without a known name.

    The first alternative is always no pronunciation.  Adjacent symbols are
    grouped so a caller can recover a contextual reading for the whole group.
    Variation selectors and emoji joiners remain inside their original span.
    """
    result = []
    offset = 0
    while offset < len(text):
        if not _symbol(text[offset]):
            offset += 1
            continue
        start = offset
        choices = []
        while offset < len(text) and (_symbol(text[offset]) or _extension(text[offset])):
            character = text[offset]
            if not _extension(character):
                choices.append(_READINGS.get(unicodedata.normalize("NFKC", character), ("",)))
            offset += 1
        # Whole-group names first; no unbounded Cartesian expansion.
        readings = tuple(dict.fromkeys(["", *("".join(row) for row in
                          islice(product(*choices), 16))]))
        result.append(SymbolSpan(start, offset, text[start:offset], readings))
    return tuple(result)
