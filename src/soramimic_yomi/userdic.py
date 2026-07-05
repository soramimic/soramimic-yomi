"""同梱ユーザー辞書(dic/user.csv)の管理。

pyopenjtalk-plus の素の辞書が知らない語(唱歌の複合語など)をここで補う。
CSVはOpenJTalk拡張のMeCab形式。行の追加は dic/user.csv を編集するだけでよく、
コンパイル結果はキャッシュされCSVが新しいときだけ再生成される。
"""

from __future__ import annotations

import os
from pathlib import Path

import pyopenjtalk

_PACKAGE_DIR = Path(__file__).parent
USER_CSV = _PACKAGE_DIR / "dic" / "user.csv"
# 環境変数名は稼働中Cloud Runの設定(deploy.yaml)と揃えて維持する
_CACHE_DIR = Path(
    os.environ.get("SORAMIMI_YOMI_CACHE", Path.home() / ".cache" / "soramimic-yomi")
)

_loaded = False


def ensure_user_dict() -> None:
    """ユーザー辞書をコンパイル(必要時のみ)して適用する。プロセス内で1回だけ。"""
    global _loaded
    if _loaded:
        return
    if USER_CSV.exists() and USER_CSV.read_text(encoding="utf-8").strip():
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        compiled = _CACHE_DIR / "user.dic"
        if not compiled.exists() or compiled.stat().st_mtime < USER_CSV.stat().st_mtime:
            pyopenjtalk.mecab_dict_index(str(USER_CSV), str(compiled))
        pyopenjtalk.update_global_jtalk_with_user_dict(str(compiled))
    _loaded = True
