"""Bounded reading-candidate generation.

The default reading remains :func:`soramimic_yomi.get_yomi`.  This module adds
plausible alternatives for structured text and English phrases without exposing
an analyzer-specific lattice as part of the public API.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, replace
from itertools import pairwise

from .core import get_yomi
from .rules import english

MAX_NBEST = 32

_DIGITS = re.compile(r"[0-9０-９]+")
_LATIN_WORD = re.compile(
    r"[A-Za-zＡ-Ｚａ-ｚ]+"
    r"(?:['\u2019][A-Za-zＡ-Ｚａ-ｚ]+)*"
)
_ENGLISH_PHRASE = re.compile(rf"{_LATIN_WORD.pattern}(?:\s+{_LATIN_WORD.pattern})+")

_DIGIT_READINGS = {
    "0": "ゼロ",
    "1": "イチ",
    "2": "ニ",
    "3": "サン",
    "4": "ヨン",
    "5": "ゴ",
    "6": "ロク",
    "7": "ナナ",
    "8": "ハチ",
    "9": "キュー",
}
_DIGIT_ALTERNATES = {
    "0": "レイ",
    "4": "シ",
    "7": "シチ",
    "9": "ク",
}
_LETTER_READINGS = {
    "A": "エー",
    "B": "ビー",
    "C": "シー",
    "D": "ディー",
    "E": "イー",
    "F": "エフ",
    "G": "ジー",
    "H": "エイチ",
    "I": "アイ",
    "J": "ジェー",
    "K": "ケー",
    "L": "エル",
    "M": "エム",
    "N": "エヌ",
    "O": "オー",
    "P": "ピー",
    "Q": "キュー",
    "R": "アール",
    "S": "エス",
    "T": "ティー",
    "U": "ユー",
    "V": "ブイ",
    "W": "ダブリュー",
    "X": "エックス",
    "Y": "ワイ",
    "Z": "ゼット",
}
_WEAK_FORMS = {
    "and": ("AH0", "N"),
    "can": ("K", "AH0", "N"),
    "for": ("F", "ER0"),
    "of": ("AH0", "V"),
    "to": ("T", "AH0"),
}
_BOUNDARY_FUSIONS = {
    ("T", "Y"): "CH",
    ("D", "Y"): "JH",
    ("S", "Y"): "SH",
    ("Z", "Y"): "ZH",
}
_VOWEL_PHONES = {
    "AA",
    "AE",
    "AH",
    "AO",
    "AW",
    "AY",
    "EH",
    "ER",
    "EY",
    "IH",
    "IY",
    "OW",
    "OY",
    "UH",
    "UW",
}


@dataclass(frozen=True)
class ReadingSpan:
    """A surface interval changed from the canonical reading."""

    start: int
    end: int
    surface: str
    reading: str
    source: str
    rule: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ReadingCandidate:
    """One complete reading, ordered by a generator-side linguistic prior."""

    reading: str
    rank: int
    cost: float
    sources: tuple[str, ...]
    spans: tuple[ReadingSpan, ...] = ()

    def to_dict(self) -> dict:
        return {
            "reading": self.reading,
            "rank": self.rank,
            "cost": self.cost,
            "sources": list(self.sources),
            "spans": [span.to_dict() for span in self.spans],
        }


@dataclass(frozen=True)
class _Edit:
    span: ReadingSpan
    cost: float


def _nfkc_ascii(surface: str) -> str:
    return unicodedata.normalize("NFKC", surface)


def _digitwise_reading(surface: str) -> str:
    return "".join(_DIGIT_READINGS[digit] for digit in _nfkc_ascii(surface))


def _digit_alternate_readings(surface: str) -> list[str]:
    digits = _nfkc_ascii(surface)
    default = [_DIGIT_READINGS[digit] for digit in digits]
    readings: list[str] = []
    for index, digit in enumerate(digits):
        alternate = _DIGIT_ALTERNATES.get(digit)
        if alternate is None:
            continue
        parts = default.copy()
        parts[index] = alternate
        readings.append("".join(parts))
    return readings


def _letterwise_reading(surface: str) -> str:
    normalized = _nfkc_ascii(surface).replace("'", "").replace("\u2019", "")
    return "".join(_LETTER_READINGS[letter] for letter in normalized.upper())


def _base_phone(phone: str) -> str:
    return phone.rstrip("0123456789")


def _fuse_boundaries(words: list[list[str]]) -> tuple[list[list[str]], bool]:
    fused = [phones.copy() for phones in words]
    changed = False
    for left, right in pairwise(fused):
        if not left or not right:
            continue
        pair = (_base_phone(left[-1]), _base_phone(right[0]))
        replacement = _BOUNDARY_FUSIONS.get(pair)
        if replacement is not None:
            left[-1] = replacement
            del right[0]
            changed = True
    return fused, changed


def _phones_to_kana(words: list[list[str]]) -> str:
    return english._p2k()([phone for word in words for phone in word])


def _english_phrase_readings(surface: str) -> list[tuple[str, str, float]]:
    words = [
        _nfkc_ascii(match.group()).lower().replace("\u2019", "'")
        for match in _LATIN_WORD.finditer(surface)
    ]
    pronunciations = [english._pronunciations(word) for word in words]
    if not words or any(not variants for variants in pronunciations):
        return []

    primary = [list(variants[0]) for variants in pronunciations]
    generated: list[tuple[str, str, float]] = []

    def linkable(left: list[str], right: list[str]) -> bool:
        return bool(
            left
            and right
            and _base_phone(left[-1]) not in _VOWEL_PHONES
            and _base_phone(right[0]) in {*_VOWEL_PHONES, "W", "Y"}
        )

    # P2K is word-oriented, so only ask it to resyllabify a short window when
    # every boundary has a concrete consonant-to-vowel/glide connection.
    if all(linkable(left, right) for left, right in pairwise(primary)):
        generated.append((_phones_to_kana(primary), "connected", 0.25))

    weak = [phones.copy() for phones in primary]
    weak_changed = False
    for index, word in enumerate(words):
        replacement = _WEAK_FORMS.get(word)
        if replacement is not None and tuple(weak[index]) != replacement:
            weak[index] = list(replacement)
            weak_changed = True
    if weak_changed and len(words) == 2:
        generated.append((_phones_to_kana(weak), "weak-forms", 0.4))

    fused, fused_changed = _fuse_boundaries(primary)
    if fused_changed and len(words) == 2:
        generated.append((_phones_to_kana(fused), "boundary-fusion", 0.35))
    if weak_changed and len(words) == 2:
        weak_fused, weak_fused_changed = _fuse_boundaries(weak)
        if weak_fused_changed:
            generated.append(
                (_phones_to_kana(weak_fused), "weak-forms+boundary-fusion", 0.5)
            )

    unique: list[tuple[str, str, float]] = []
    seen: set[str] = set()
    for reading, rule, cost in generated:
        if reading and reading not in seen:
            seen.add(reading)
            unique.append((reading, rule, cost))
    return unique


def _edit(
    text: str,
    start: int,
    end: int,
    reading: str,
    *,
    source: str,
    rule: str,
    cost: float,
) -> _Edit:
    return _Edit(
        ReadingSpan(start, end, text[start:end], reading, source, rule),
        cost,
    )


def _candidate_edits(text: str) -> list[_Edit]:
    edits: list[_Edit] = []

    for match in _DIGITS.finditer(text):
        surface = match.group()
        if len(_nfkc_ascii(surface)) < 2:
            continue
        edits.append(
            _edit(
                text,
                match.start(),
                match.end(),
                _digitwise_reading(surface),
                source="number",
                rule="digit-by-digit",
                cost=0.3,
            )
        )
        for index, reading in enumerate(_digit_alternate_readings(surface)):
            edits.append(
                _edit(
                    text,
                    match.start(),
                    match.end(),
                    reading,
                    source="number",
                    rule="digit-name-variant",
                    cost=0.55 + index * 0.02,
                )
            )

    for match in _LATIN_WORD.finditer(text):
        surface = match.group()
        normalized = _nfkc_ascii(surface)
        letterwise = _letterwise_reading(surface)
        if letterwise:
            acronym_like = len(normalized) > 1 and normalized.isupper()
            edits.append(
                _edit(
                    text,
                    match.start(),
                    match.end(),
                    letterwise,
                    source="latin",
                    rule="letter-by-letter",
                    cost=0.35 if acronym_like else 0.9,
                )
            )

        pronunciations = english._pronunciations(normalized)
        for variant_index, phones in enumerate(pronunciations[1:3], start=2):
            edits.append(
                _edit(
                    text,
                    match.start(),
                    match.end(),
                    english._p2k()(list(phones)),
                    source="english",
                    rule=f"cmudict-pronunciation-{variant_index}",
                    cost=0.4 + 0.05 * (variant_index - 2),
                )
            )

    for phrase_match in _ENGLISH_PHRASE.finditer(text):
        words = list(_LATIN_WORD.finditer(phrase_match.group()))
        # e2k.P2K is a word-oriented converter.  Short windows capture useful
        # cross-word realizations without letting it re-syllabify a long line.
        window_sizes = (2, 3)
        for size in window_sizes:
            for first in range(len(words) - size + 1):
                window = words[first : first + size]
                start = phrase_match.start() + window[0].start()
                end = phrase_match.start() + window[-1].end()
                surface = text[start:end]
                for reading, rule, cost in _english_phrase_readings(surface):
                    edits.append(
                        _edit(
                            text,
                            start,
                            end,
                            reading,
                            source="english-phrase",
                            rule=rule,
                            cost=cost,
                        )
                    )

    return edits


def _overlaps(left: ReadingSpan, right: ReadingSpan) -> bool:
    return left.start < right.end and right.start < left.end


def _render(text: str, edits: tuple[_Edit, ...]) -> str:
    parts: list[str] = []
    offset = 0
    for edit in sorted(edits, key=lambda item: item.span.start):
        parts.append(get_yomi(text[offset : edit.span.start]))
        parts.append(edit.span.reading)
        offset = edit.span.end
    parts.append(get_yomi(text[offset:]))
    return "".join(parts)


def _states(edits: list[_Edit], *, beam_size: int) -> list[tuple[_Edit, ...]]:
    states: list[tuple[_Edit, ...]] = [()]
    for edit in edits:
        additions = [
            (*state, edit)
            for state in states
            if all(not _overlaps(existing.span, edit.span) for existing in state)
        ]
        states.extend(additions)
        states.sort(
            key=lambda state: (
                round(sum(item.cost for item in state), 8),
                len(state),
                tuple(
                    (item.span.start, item.span.end, item.span.rule) for item in state
                ),
            )
        )
        states = states[:beam_size]
    return states


def get_yomi_candidates(text: str, *, nbest: int = 8) -> list[ReadingCandidate]:
    """Return distinct complete readings ordered by a linguistic prior.

    The first result is always exactly :func:`get_yomi`.  Later candidates may
    contain digit-name, letter-name, CMUdict alternative, or connected-English
    realizations.  Acoustic evidence is intentionally left to callers.
    """
    if not 1 <= nbest <= MAX_NBEST:
        raise ValueError(f"nbest must be between 1 and {MAX_NBEST}")

    canonical = get_yomi(text)
    candidates = [ReadingCandidate(canonical, 0, 0.0, ("canonical",))]
    if nbest == 1:
        return candidates

    edits = _candidate_edits(text)
    states = _states(edits, beam_size=max(64, nbest * 12))
    seen = {canonical}
    for state in states:
        if not state:
            continue
        reading = _render(text, state)
        if not reading or reading in seen:
            continue
        seen.add(reading)
        ordered_state = tuple(sorted(state, key=lambda item: item.span.start))
        sources = tuple(dict.fromkeys(edit.span.source for edit in ordered_state))
        candidate = ReadingCandidate(
            reading=reading,
            rank=0,
            cost=round(sum(edit.cost for edit in state), 6),
            sources=sources,
            spans=tuple(edit.span for edit in ordered_state),
        )
        candidates.append(candidate)
        if len(candidates) >= nbest:
            break

    return [replace(candidate, rank=rank) for rank, candidate in enumerate(candidates)]
