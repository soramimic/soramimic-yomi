# soramimi-yomi

空耳アプリ([Soramimic](https://github.com/soramimic/soramimic)等)用の読み推定ライブラリ+API。
[pyopenjtalk-plus](https://github.com/tsukumijima/pyopenjtalk-plus) をベースに、
空耳用途の工夫を重ねる:

- **ユーザー辞書**(`dic/user.csv`) — 素の辞書が知らない語を補正(例: 夕焼小焼→ユウヤケコヤケ)
- **正規化ルール**(`rules/`) — 英単語→カナ(BEP辞書4.7万語。素だとスペル読みになる)など、合成可能な前処理
- 数字・日付の読み下し(1羽→イチワ、2020年5月→ニセンニジューネンゴガツ)は pyopenjtalk-plus 自体が強い

## 3つの使い方

**① Pythonライブラリとして**(単語リストの読み付与、データパイプライン)

```python
import soramimi_yomi
soramimi_yomi.get_yomi("夕焼小焼の赤とんぼ")   # ユウヤケコヤケノアカトンボ
soramimi_yomi.get_tokens("海は広いな")          # kuromoji.js互換のトークン列
```

```sh
uv add "soramimi-yomi @ git+https://github.com/soramimic/soramimi-yomi"
```

**② APIとして**(ブラウザアプリからの利用。soramimicはプログレッシブエンハンスメントで利用予定)

```sh
uv sync --extra api
uv run uvicorn api.main:app --port 8080
# POST /yomi {"text": "..."} , POST /tokenize {"text": [...]}, GET /health
```

**③ テストオラクルとして** — JS側に読み処理を移植する際の期待値生成に使う

## 語彙・ルールの追加

- 読みがおかしい語を見つけたら `src/soramimi_yomi/dic/user.csv` に1行追加(OpenJTalk拡張のMeCab CSV形式)
- テキスト前処理を足したいときは `src/soramimi_yomi/rules/` にモジュールを追加して `DEFAULT_RULES` に登録

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
