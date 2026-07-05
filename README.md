# soramimic-yomi

空耳アプリ([Soramimic](https://github.com/soramimic/soramimic)等)用の読み推定ライブラリ+API。
[pyopenjtalk-plus](https://github.com/tsukumijima/pyopenjtalk-plus) をベースに、
空耳用途の工夫を重ねる:

- **ユーザー辞書**(`dic/user.csv`) — 素の辞書が知らない語を補正(例: 夕焼小焼→ユウヤケコヤケ)
- **正規化ルール**(`rules/`) — 英単語→カナ(CMUdict+[e2k](https://github.com/Patchethium/e2k)。素だとスペル読みになる)など、合成可能な前処理
- 数字・日付の読み下し(1羽→イチワ、2020年5月→ニセンニジューネンゴガツ)は pyopenjtalk-plus 自体が強い

## 3つの使い方

**① Pythonライブラリとして**(単語リストの読み付与、データパイプライン)

```python
import soramimic_yomi
soramimic_yomi.get_yomi("夕焼小焼の赤とんぼ")   # ユウヤケコヤケノアカトンボ
soramimic_yomi.get_tokens("海は広いな")          # kuromoji.js互換のトークン列
```

```sh
uv add "soramimic-yomi @ git+https://github.com/soramimic/soramimic-yomi"
```

**② APIとして**(ブラウザアプリからの利用。soramimicはプログレッシブエンハンスメントで利用予定)

```sh
uv sync --extra api
uv run uvicorn api.main:app --port 8080
# POST /yomi {"text": "..."} , POST /tokenize {"text": [...]}, GET /health
```

**③ テストオラクルとして** — JS側に読み処理を移植する際の期待値生成に使う

## 語彙・ルールの追加

- 読みがおかしい語を見つけたら `src/soramimic_yomi/dic/user.csv` に1行追加(OpenJTalk拡張のMeCab CSV形式)
- 英単語のカナ変換がおかしい場合は `src/soramimic_yomi/data/english_overrides.csv`(`word,kana`)に追記すると最優先で適用される
- テキスト前処理を足したいときは `src/soramimic_yomi/rules/` にモジュールを追加して `DEFAULT_RULES` に登録

## 英語→カナ変換の仕組み

`rules/english.py` は英単語(正規表現 `[A-Za-z][A-Za-z']*` で抽出したトークン)を、以下の優先順位でカナに変換する:

1. 自前の例外辞書 `data/english_overrides.csv` — 機械変換の結果が明らかにおかしい頻出語の上書き
2. [CMUdict](https://github.com/cmusphinx/cmudict) に収録されている語は、その発音(ARPAbet音素列、主発音のみ)を [e2k](https://github.com/Patchethium/e2k) の `P2K` でカナ化
3. CMUdict未収録語は e2k の `C2K` で綴りから直接カナ化

CMUdict は Carnegie Mellon University が配布する発音辞書で、データ本体(`data/cmudict.dict`)は
BSD類似の寛容ライセンス(著作権表示の保持のみ要求。全文: `data/cmudict.LICENSE`)。
`cmusphinx/cmudict` の `cmudict.dict` をそのまま同梱し、自前のパーサで読んでいる。
**PyPIの `cmudict` パッケージ(GPL-3.0-or-later のラッパー)は使用していない。**
e2k はコード自体が Unlicense。

## 開発

```sh
uv sync --extra api
uv run pytest
```

## 既知の挙動

- pyopenjtalk は英数字の表層を全角に正規化する(`Hello`→`Ｈｅｌｌｏ`)
- `get_tokens()` はデフォルトで正規化ルールを適用しない(表層保持。英語処理は利用側の裁量)
- 読みのアクセント記号(`’`)は除去して返す

## デプロイ

`Dockerfile` あり。想定: Cloud Run(ゼロスケール)または既存VPS。
