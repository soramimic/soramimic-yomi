# soramimic-yomi

空耳アプリ([Soramimic](https://github.com/soramimic/soramimic)等)用の読み推定ライブラリ+API。
[pyopenjtalk-plus](https://github.com/tsukumijima/pyopenjtalk-plus) をベースに、
空耳用途の工夫を重ねる:

- **ユーザー辞書**(`dic/user.csv`) — 素の辞書が知らない語を補正(例: 夕焼小焼→ユウヤケコヤケ)
- **正規化ルール**(`rules/`) — 英単語→カナ(CMUdict+[arpakana](https://github.com/jiroshimaya/arpakana)、未収録語のみ[e2k](https://github.com/Patchethium/e2k) C2K)など、合成可能な前処理
- 数字・日付の読み下し(1羽→イチワ、2020年5月→ニセンニジューネンゴガツ)は pyopenjtalk-plus 自体が強い

## 3つの使い方

**① Pythonライブラリとして**(単語リストの読み付与、データパイプライン)

```python
import soramimic_yomi
soramimic_yomi.get_yomi("夕焼小焼の赤とんぼ")   # ユウヤケコヤケノアカトンボ
soramimic_yomi.get_tokens("海は広いな")          # kuromoji.js互換のトークン列
soramimic_yomi.get_yomi_candidates("AI 4443")    # 構造化された読みN-best
```

```sh
uv add "soramimic-yomi @ git+https://github.com/soramimic/soramimic-yomi"
```

**② APIとして**(ブラウザアプリからの利用。soramimicはプログレッシブエンハンスメントで利用予定)

```sh
uv sync --extra api
uv run uvicorn api.main:app --port 8080
# POST /yomi {"text": "..."}
# POST /yomi_candidates {"text": "...", "nbest": 8}
# POST /tokenize {"text": [...]}, GET /health
```

**③ テストオラクルとして** — JS側に読み処理を移植する際の期待値生成に使う

## 語彙・ルールの追加

- 読みがおかしい語を見つけたら `src/soramimic_yomi/dic/user.csv` に1行追加(OpenJTalk拡張のMeCab CSV形式)
- 英単語のカナ変換がおかしい場合は `src/soramimic_yomi/data/english_overrides.csv`(`word,kana`)に追記すると最優先で適用される
- テキスト前処理を足したいときは `src/soramimic_yomi/rules/` にモジュールを追加して `DEFAULT_RULES` に登録

## 英語→カナ変換の仕組み

`rules/english.py` は英単語（ASCII英字、および単語内部の straight apostrophe
`'` / curly apostrophe `’`）を、以下の優先順位でカナに変換する:

1. 自前の例外辞書 `data/english_overrides.csv` — 機械変換の結果が明らかにおかしい頻出語の上書き
2. [CMUdict](https://github.com/cmusphinx/cmudict) に収録されている語は、その主発音(ARPAbet音素列)を [arpakana](https://github.com/jiroshimaya/arpakana) の明示規則で決定的にカナ化。異形発音もN-best用に保持
3. CMUdict未収録語は e2k の `C2K` で綴りから直接カナ化

CMUdict は Carnegie Mellon University が配布する発音辞書で、データ本体(`data/cmudict.dict`)は
BSD類似の寛容ライセンス(著作権表示の保持のみ要求。全文: `data/cmudict.LICENSE`)。
`cmusphinx/cmudict` の `cmudict.dict` をそのまま同梱し、自前のパーサで読んでいる。
**PyPIの `cmudict` パッケージ(GPL-3.0-or-later のラッパー)は使用していない。**
arpakana は MIT License。e2k はコード自体が Unlicenseで、CMUdict未収録語の
`C2K` フォールバックにのみ使用する。

## 読み候補（N-best）

`get_yomi_candidates(text, nbest=8)` は、解析器固有の形態素経路ではなく、
空耳・歌詞照合で比較できる**異なる全文読み**を良い順に返す。第1候補は常に
`get_yomi(text)` と完全一致するため、既存の1-best利用側は変更不要。

現在は次の候補を上限付きで組み合わせる。

- 複数桁の通常読みと桁読み（`4443`: `ヨンセン…` / `ヨンヨンヨンサン`）
- 英字列の単語読みと文字名読み（`AI`: `アイ` / `エーアイ`）
- CMUdictに登録された英単語の異形発音
- 2〜3語の英語窓に対する連結、弱形、境界融合（`did you`: `ディドユー` / `デジュ`）

候補は `ReadingCandidate` で、全文の `reading`、ゼロ始まりの `rank`、生成側の
相対的な `cost`、`sources`、既定読みから変えた表層区間 `spans` を持つ。
`cost` は音響尤度ではない。音源がある利用側は候補集合を保ったままCTCなどで
再順位付けする。候補生成は直積を無制限に作らず、beamで抑制する。

```python
candidate = soramimic_yomi.get_yomi_candidates("AI", nbest=4)[1]
candidate.reading             # エーアイ
candidate.spans[0].surface    # AI
candidate.spans[0].rule       # letter-by-letter
candidate.to_dict()           # APIと同じJSON互換dict
```

`POST /yomi_candidates` は単一文字列に `{"candidates": [...]}`、文字列配列に
`{"candidates": [[...], ...]}` を返す。`nbest` は1〜32。`GET /health` の
`candidate_contract_version: 1` と `capabilities.reading_nbest: true` で判別できる。

## `/tokenize` の token 契約（version 2）

レスポンス envelope（単一入力は `{"tokens": [...]}`、配列入力は
`{"tokens": [[...], ...]}`）と既存の kuromoji.js 互換キーは維持される。
`GET /health` の `token_contract_version` が `2` で、`capabilities` の
`lossless_surface` と `english_reading` が `true` の場合、次の契約を利用できる。

- 返された全 token の `surface_form` を順番に連結すると、入力文字列と完全一致する。
  pyopenjtalk 内部の全角化は公開表層に反映しない。
- 連続する空白（半角・全角空白、タブ、改行を含む）は最大単位の1 token とし、
  `pos: "記号"`、`pos_detail_1: "空白"`、`reading: ""`、
  `pronunciation: ""`、`is_silent: true` で返す。行頭・行末・空白だけの入力も
  順序と個数を保持する。
- ASCII英単語は `pos: "名詞"`、`pos_detail_1: "一般"` とし、有効なカナ読みを返す。
  `don't` と `don’t` のような単語内 apostrophe は表層を変えず単一の lexical token
  として扱い、両表記に同じ読みを付与する。
- 読みに寄与しない記号は表層を保持し、`reading: ""`、
  `pronunciation: ""`、`is_silent: true` とする。読みを持つ token は
  `is_silent: false` である。
- `pronunciation` を順番に連結すると、空白・句読点を除いた入力全体の読みになる。
  解析器との表層対応を安全に確定できない稀な入力では、原文を1 token に保持した
  うえで集約読みを返し、表層を欠落・置換しない。

例: `I love you` は `I` / 空白 / `love` / 空白 / `you` となり、
`pronunciation` の連結は `アイラヴユー`、`surface_form` の連結は元の
`I love you` になる。

## 開発

```sh
uv sync --extra api
uv run pytest
```

## 既知の挙動

- pyopenjtalk は内部で英数字を全角に正規化するが、`get_tokens()` は原文表層へ
  対応付けて返す
- `get_tokens()` の `apply_rules` 引数は後方互換のため残している。version 2では
  引数にかかわらず表層を変えず、英語 token 自体に読みを付与する
- 読みのアクセント記号(`’`)は除去して返す

## デプロイ

`Dockerfile` あり。想定: Cloud Run(ゼロスケール)または既存VPS。
