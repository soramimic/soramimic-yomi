"""soramimic-yomi: 空耳アプリ用の読み推定ライブラリ。

pyopenjtalk-plus をベースに、ユーザー辞書と空耳用の正規化ルール
(英語→カナ等)を重ねて日本語テキストの読みを推定する。
"""

from .candidates import ReadingCandidate, ReadingSpan, get_yomi_candidates
from .core import get_tokens, get_yomi
from .rules import normalize
from .symbols import SymbolSpan, get_symbol_spans

__all__ = [
    "ReadingCandidate",
    "ReadingSpan",
    "SymbolSpan",
    "get_symbol_spans",
    "get_tokens",
    "get_yomi",
    "get_yomi_candidates",
    "normalize",
]
