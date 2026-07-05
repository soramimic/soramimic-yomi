"""空耳用のテキスト正規化ルール群。

読み推定の前段に適用する、合成可能な text -> text の関数を集める。
「数字・英語の読みを空耳用に工夫したい」の受け皿。ルールを増やすときは
モジュールを追加して DEFAULT_RULES に並べる(順序が適用順)。

なお数字・日付の読み下し(1羽→イチワ、2020年→ニセンニジューネン)は
pyopenjtalk-plus 自体が強いため、ここでは扱わない。
"""

from __future__ import annotations

from . import english

DEFAULT_RULES = [
    english.normalize,
]


def normalize(text: str) -> str:
    for rule in DEFAULT_RULES:
        text = rule(text)
    return text
