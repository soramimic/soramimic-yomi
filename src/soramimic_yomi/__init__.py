"""soramimic-yomi: 空耳アプリ用の読み推定ライブラリ。

pyopenjtalk-plus をベースに、ユーザー辞書と空耳用の正規化ルール
(英語→カナ等)を重ねて日本語テキストの読みを推定する。
"""

from .core import get_tokens, get_yomi
from .rules import normalize

__all__ = ["get_yomi", "get_tokens", "normalize"]
