"""英単語をカナ読みに置き換えるルール。

pyopenjtalk は未知の英単語をスペル読み(NICE→エヌアイシーイー)してしまうため、
英単語をカナに変換してから読み推定に渡す。

変換優先順位:
  1. 自前の例外辞書(data/english_overrides.csv) — 頻出語で機械変換の結果が
     明らかにおかしい場合の上書き
  2. CMUdict(data/cmudict.dict)に収録されている語は、その発音(ARPAbet音素列、
     異形("(2)"等)を除いた主発音のみ)を e2k.P2K でカナ化
  3. CMUdict未収録語は e2k.C2K で綴りから直接カナ化(小文字入力)

CMUdict は Carnegie Mellon University が配布する発音辞書で、データ本体は
BSD類似の寛容ライセンス(著作権表示の保持のみを要求)。cmusphinx/cmudict の
cmudict.dict をそのまま同梱し、自前のパーサで読む(PyPIの `cmudict` パッケージは
ラッパー自体が GPL-3.0-or-later のため使用しない)。ライセンス全文は
data/cmudict.LICENSE を参照。

e2k(コードは Unlicense)の P2K/C2K モデルは遅延ロード(初回呼び出し時の1回のみ)し、
変換結果は単語単位で lru_cache により再利用する。
"""

from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / "data"
_CMUDICT_PATH = _DATA_DIR / "cmudict.dict"
_OVERRIDES_PATH = _DATA_DIR / "english_overrides.csv"

_ENGLISH_WORD = re.compile(r"[A-Za-z][A-Za-z']*")
# CMUdict の異形エントリ("word(2)" 等)を検出する
_ALT_PRON_RE = re.compile(r"^(.*)\(\d+\)$")


@lru_cache(maxsize=1)
def _overrides() -> dict[str, str]:
    """自前の英語例外辞書(word,kana のCSV)を読み込む。キーは小文字化した単語。"""
    overrides: dict[str, str] = {}
    with _OVERRIDES_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            word = (row.get("word") or "").strip()
            kana = (row.get("kana") or "").strip()
            if word and kana:
                overrides[word.lower()] = kana
    return overrides


@lru_cache(maxsize=1)
def _cmudict() -> dict[str, tuple[str, ...]]:
    """cmudict.dict(cmusphinx/cmudict 形式)を自前パースする。

    フォーマット例: ``hello HH AH0 L OW1`` (単語 + ARPAbet音素列、ストレス数字付き)。
    ``;;;`` で始まる行はコメント。``word(2)`` のような異形(第2発音以降)は
    採用せず、無印の主発音のみを保持する。行末の ``# ...`` コメントも無視する。
    """
    d: dict[str, tuple[str, ...]] = {}
    with _CMUDICT_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith(";;;"):
                continue
            line = line.split("#", 1)[0].rstrip()
            if not line:
                continue
            parts = line.split()
            word, phonemes = parts[0], parts[1:]
            if not phonemes:
                continue
            if _ALT_PRON_RE.match(word):
                # 異形発音("aalborg(2)"等)は主発音を優先するためスキップ
                continue
            d[word.lower()] = tuple(phonemes)
    return d


@lru_cache(maxsize=1)
def _p2k():
    from e2k import P2K

    return P2K()


@lru_cache(maxsize=1)
def _c2k():
    from e2k import C2K

    return C2K()


@lru_cache(maxsize=None)
def _convert_word(word: str) -> str:
    """英単語1語をカナに変換する(語単位でキャッシュ)。"""
    lower = word.lower()

    override = _overrides().get(lower)
    if override is not None:
        return override

    phonemes = _cmudict().get(lower)
    if phonemes is not None:
        return _p2k()(list(phonemes))

    return _c2k()(lower)


def normalize(text: str) -> str:
    def repl(m: re.Match) -> str:
        return _convert_word(m.group(0))

    return _ENGLISH_WORD.sub(repl, text)
