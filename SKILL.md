---
name: notion-cli-api-skill
description: Notion REST APIへの生アクセス(ページ/ブロック取得・データソースクエリ・ページ作成・ページ更新・コメントの取得と返信)と、Markdown⇄Notionブロック変換・プロパティ組み立てのヘルパーだけを提供する、判断を一切含まないInfrastructure層のスキル。特定のドメインに依存しない共有カーネルで、どのDBに何を書くべきかという判断は持たない。列の追加・改名・型変更といったスキーマ変更でNotionが黙って値を壊す条件（DDLの落とし穴・型変更でビュー設定が落ちること・API経由では作れない数式）もここに集約する。新規DBを作るときに必ず付ける既定列(ID・Created time・Last edited time)と、date型の書式(Year/Month/Day・24 hour)がAPIでは設定できず画面での手作業が残ることもここが持つ。公式MCPでページ本文を書く前にも参照する(CLAUDE.md等のドメインに見える語が勝手にリンクになる落とし穴)。ページに付いた未解決コメントを全部取って返信する一連の手順もここが持つ(手順は references/comments.md。取得は既定でREST、公式MCPは効率を重視するよう頼まれたときなどの例外。何と答えるかは呼び出し側の判断)。「Notionのコメントを拾って」「コメントを拾っておいて」「ページのコメントを見て」「コメントに答えて」「指摘を拾って」のように言われたときは、ユーザーから直接このスキルを使い、自分宛てのスレッド全件へ返信するところまで行う(この文脈の「拾う」は取得だけを指さず、返信までを含む)。コメント対応以外でユーザーから直接呼ばれることは想定しない。Notionへの読み書きが必要な他のスキルが、Pythonからは scripts配下のモジュールを直接import、シェルからは scripts を起動して使う。
license: MIT
metadata:
  version: "1.0.0"
  repository: "https://github.com/junyatakechi/notion-cli-api-skill"
---

# notion-cli-api-skill

Notion REST API(`https://api.notion.com/v1/...`)への薄いアクセスだけを提供するスキル。
どのデータを取得するか・取得結果をどう解釈するかの判断は一切行わない(それは呼び出し元の
スキルの責務)。

## コメントの取得と返信 → `references/comments.md`

**コメントに関わる作業を頼まれたら、手を付ける前に `references/comments.md` を読む。**
次のどれかに当たるときが対象。

- 「コメントを拾って」「コメントを見て」「コメントに答えて」「指摘を拾って」「読むだけ」と言われた
- 他のスキルから、ページのコメントの取得・返信を頼まれた
- コメントの付いたページを書き換える（表の行・列を変えると、そこに付いたスレッドが消える）

中身は、取得の経路（既定はREST。公式MCPを使うのは効率を重視するよう頼まれたときなどの例外だけ）・
返信する相手の絞り方・返信の経路（常にREST。MCPの `notion-create-comment` は使わない）・
コメントが消える操作・APIではできないこと。

## 設定が無いとき → README の「セットアップ」

Integrationの作成・ページへの接続・トークンの保存は人の手作業で、手順は README の「セットアップ」だけが持つ。
次の合図が出たら先へ進まず、README の「セットアップ」をユーザーに案内する。

| 合図 | 足りないもの |
|---|---|
| `NotionAuthError`（scripts では `Notion token file not found` / `NOTION_TOKEN is not set`） | `~/.claude-skills-env/notion-cli-api-skill.env`、またはその中の `NOTION_TOKEN` |
| あるはずのページ・データソースで `NotionAPIError`（`.status` が404） | そのページへのIntegrationの接続 |
| コメントの取得・返信で403、または中身の無い結果 | Integrationのコメント権限（→ `references/comments.md`） |

## 2つの使い方：直接import か scripts起動か

用途によって使い分ける。**Pythonから使うなら常にimport、シェル・他言語からならscripts。**

| 使い方 | 向いている場面 | 呼び方 |
|---|---|---|
| **モジュールを直接import** | Pythonから呼ぶすべての場面 | `sys.path` に `scripts/` を足して import |
| **`scripts/` を起動** | シェルからの単発の取得、他言語から | `bash scripts/get_page.sh <id>` 等 |

数百件をsubprocessで回すと、`bash`/`uv` のプロセス起動と一時ファイル生成が件数分積み上がり、
純オーバーヘッドだけで数分かかる。数百件を一度に投入する用途のために、直接importの経路を
用意してある。

**呼び出し側スキルが独自の薄いラッパー（`_notion_client.py` 等）を持たないこと。**
同じ関数がスキルの数だけ増え、認証・APIバージョン・レート制限・エラー処理がそこに散らばる。
操作単位の入口はこのモジュールに1つだけ置く。

```python
import os, sys
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "notion-cli-api-skill", "scripts")))
from notion_client import NotionError, query_data_source, create_page

pages = query_data_source(ds_id, {"filter": {...}})
create_page({"parent": {"data_source_id": ds_id}, "properties": {...}})
```

### 提供するモジュール

<table header-row="true">
<tr><td>モジュール</td><td>役割</td></tr>
<tr><td><code>notion_client.py</code></td><td>API通信。認証・レート制限・ページネーション・エラー</td></tr>
<tr><td><code>notion_blocks.py</code></td><td>Markdown→Notionブロック / Notionブロック→テキスト の機械的な変換</td></tr>
<tr><td><code>notion_props.py</code></td><td>Notionプロパティ値の組み立て(<code>title_prop</code>・<code>date_prop</code>等)</td></tr>
</table>

`notion_blocks.py` / `notion_props.py` は**どんな本文・どんな値を書くべきかの判断を持たない**。
Notionのデータ形式へ機械的に詰め替えるだけなので、Infrastructure層に置いている。

#### `notion_client.py` の操作別API

| 関数 | エンドポイント |
|---|---|
| `get_page(page_id)` | `GET /pages/{id}` |
| `create_page(body)` | `POST /pages` |
| `update_page(page_id, body)` | `PATCH /pages/{id}` |
| `query_data_source(ds_id, body=None)` | `POST /data_sources/{id}/query`（ページネーション解決済み） |
| `get_data_source(ds_id)` | `GET /data_sources/{id}`（スキーマ取得） |
| `select_options(ds_id, prop_name)` | select/multi_selectの選択肢名リスト |
| `get_block_children(block_id, recursive=True)` | `GET /blocks/{id}/children`（再帰で`children`を埋め込む） |
| `append_block_children(block_id, children)` | `PATCH /blocks/{id}/children`（100件以内） |
| `update_block(block_id, body)` | `PATCH /blocks/{id}` |
| `get_comments(block_id, recursive=False)` | `GET /comments?block_id=`（未解決のみ。`recursive=True`で本文の全ブロックを辿る） |
| `create_comment(body)` | `POST /comments`（スレッドへの返信・ページ/ブロックへのコメント） |

低レベルの `notion_request(method, path, body)` / `notion_post_paginate` /
`notion_get_paginate` も公開しているので、上記に無いエンドポイントはこれで叩く
（**`_common.sh` の `notion_curl` をsubprocessで呼ぶ回避策はもう不要**）。

**このモジュールが一手に引き受けるもの。呼び出し側で再実装しないこと。**

- 認証トークンの読み込みと**プロセス内キャッシュ**（毎リクエストでファイルを読み直さない）
- APIのベースURLとバージョン（`2025-09-03`）
- **レート制限**。`notion_request` が前回リクエストからの経過を見て足りない分だけ待つ。
  **呼び出し側で `time.sleep` しないこと**（二重に待つことになる）
- HTTPエラーの検出

エラーは `sys.exit` せず **例外**（`NotionError` とその派生）を送出する。呼び出し側が
リトライするか中断するかを選べるようにするため。コマンドラインスクリプトは
`NotionError` を捕まえて `sys.exit` すること。

| 例外 | 意味 |
|---|---|
| `NotionError` | 基底。スクリプトはこれを捕まえる |
| `NotionAuthError` | トークンファイルが無い / `NOTION_TOKEN` 未設定 |
| `NotionAPIError` | APIがエラーを返した。`.status` にHTTPステータス |

`append_block_children` に101件以上渡した場合は `ValueError`（APIに投げる前に検出する）。
**何件ずつどこで区切るかは呼び出し側の判断**なので、ここでは自動分割しない。

## 提供するスクリプト

いずれも `$HOME/.claude-skills-env/notion-cli-api-skill.env` から `NOTION_TOKEN` を読み込み、
`Notion-Version: 2025-09-03` を付けてリクエストする。認証エラー・存在しないID等の
HTTPエラー時はstderrにエラー内容を出し、非zero終了コードで終了する。

読み込み先を一時的に差し替えたい場合(別トークンでの検証など)は、環境変数
`NOTION_ENV_FILE` に絶対パスを渡せば既定パスより優先される。

### 1. ページ取得: `scripts/get_page.sh <page_id>`

`GET /v1/pages/{page_id}` を叩き、レスポンスJSONをそのまま標準出力する。

```bash
scripts/get_page.sh <page ID>
```

### 2. ブロック子取得(再帰): `uv run scripts/get_block_children.py <block_id>`

`GET /v1/blocks/{block_id}/children` を叩く。`has_children: true` の子ブロックは
再帰的に辿り、各ブロックオブジェクトに `children` キー(配列)として埋め込む。
ページネーションもこのスクリプト内で解決済みの、フラットではなくネストしたJSON配列を
標準出力する。ページ本文全体を取得したい場合は `page_id` をそのまま `block_id` として渡す。

```bash
uv run scripts/get_block_children.py <page ID>
```

### 3. データソースクエリ: `uv run scripts/query_data_source.py <data_source_id> [request_body.json]`

`POST /v1/data_sources/{data_source_id}/query` を叩く。`request_body.json` に
`filter`/`sorts`/`page_size` 等を入れたJSONファイルを渡す(省略時はフィルタなしで全件)。
ページネーションを解決した上で、全結果をマージした1つのJSON配列を標準出力する。

```bash
cat <<'EOF' > /tmp/filter.json
{"filter": {"property": "形式", "select": {"equals": "Evaluation"}}, "sorts": [{"property": "Executed time", "direction": "descending"}]}
EOF
uv run scripts/query_data_source.py <data source ID> /tmp/filter.json
```

### 4. ページ作成: `scripts/create_page.sh <request_body.json>`

`POST /v1/pages` を叩く。`request_body.json` に `parent`/`properties`/`children` 等、
Notion APIがそのまま受け付ける形式のJSONファイルを渡す。作成されたページオブジェクトの
JSONを標準出力する。

```bash
cat <<'EOF' > /tmp/new_page.json
{"parent": {"data_source_id": "<data source ID>"}, "properties": {"Name": {"title": [{"text": {"content": "テストページ"}}]}}}
EOF
scripts/create_page.sh /tmp/new_page.json
```

### 5. ページ更新: `scripts/update_page.sh <page_id> <request_body.json>`

`PATCH /v1/pages/{page_id}` を叩く。`request_body.json` に `properties`/`archived` 等、
Notion APIがそのまま受け付ける形式のJSONファイルを渡す。プロパティの一部上書き更新や、
ページのアーカイブ(`{"archived": true}`)に使う。更新後のページオブジェクトのJSONを
標準出力する。

```bash
cat <<'EOF' > /tmp/update.json
{"properties": {"点数": {"number": 80}}}
EOF
scripts/update_page.sh <page ID> /tmp/update.json
```

### 6. ブロック更新: `scripts/update_block.sh <block_id> <request_body.json>`

`PATCH /v1/blocks/{block_id}` を叩く。`request_body.json` にブロックタイプをキーにした
JSON(`{"paragraph": {"rich_text": [...]}}` 等)を渡す。ページ本文の既存行を書き換えるのに使う
(`update_page.sh` はプロパティ専用で、本文は書き換えられない)。更新後のブロックオブジェクトの
JSONを標準出力する。対象の`block_id`は`get_block_children.py`の出力から得る。

```bash
cat <<'EOF' > /tmp/update_block.json
{"numbered_list_item": {"rich_text": [{"type": "text", "text": {"content": "完了タスク: 3件 => 5件 (現在)"}}]}}
EOF
scripts/update_block.sh <block ID> /tmp/update_block.json
```

## 語彙DBを引く関数は、必ずセッション内でキャッシュする

**Notionのクエリは1回2〜3秒かかる。** 「1レコードごとに引く」形を書くと、件数ぶんの
API往復になって実用にならない。**このスキルを使う側で3回踏んでいる**ので、ここに残す。

| どこ | 症状 |
|---|---|
| ルール表の読み込み | 処理の種類ごとに、同じ数百行のルール表を引き直していた |
| 表示名の辞書 | 取り込みが1レコードごとに辞書を引いていた |
| **語彙の検査** | 1行ごとに語彙DBを引き、百行ほどで**タイムアウト**（exit 143） |

形はどれも同じで、**モジュール変数に1つ持ち、`force_reload=True` でだけ引き直す**。

```python
_cache = None

def load(force_reload=False):
    global _cache
    if not force_reload and _cache is not None:
        return _cache
    _cache = _fetch()      # ← Notionを引くのはここだけ
    return _cache
```

- **書き込みの直後は `force_reload=True`。** 足した行を読み直さないと、同じセッションの
  次の判定が古い語彙で動く
- **キャッシュはセッション内だけ。** ファイルに落とさない（Notion側で人が直した値と
  食い違い、どちらが正か分からなくなる）
- 遅さは「待たされる」だけでなく**失敗として現れる**。上の3例目はタイムアウトで
  異常終了しており、キャッシュ漏れは性能の問題ではなく**動かない原因**になる

## 新規DBを作るときの既定

**呼ばれてDBを新しく作るときは、頼まれていなくても次の3列を必ず付ける。**
どのDBでも同じ名前で辿れるようにするための決めごとなので、**列名はこの英語表記で固定する**
（既存のDBと揃う）。

| 列名 | 型 | RESTでの書き方 |
|---|---|---|
| `ID` | unique_id | `{"unique_id": {}}`（prefixは付けない） |
| `Created time` | created_time | `{"created_time": {}}` |
| `Last edited time` | last_edited_time | `{"last_edited_time": {}}` |

**3つともRESTの `POST /databases` でそのまま作れる**（2026-09-18に実測）。
公式ドキュメントはこの3つを "read-only" と書くが、**それは「ページの値を書き換えられない」
という意味**で、**列を作ること自体は通る**（ドキュメントの文言だけ見て諦めない）。

```python
notion_request("POST", "/databases", {
    "parent": {"type": "page_id", "page_id": PARENT_PAGE_ID},
    "title": [{"type": "text", "text": {"content": "<DB名>"}}],
    "initial_data_source": {"properties": {
        "Name": {"title": {}},
        "<日付列>": {"date": {}},
        "ID": {"unique_id": {}},
        "Created time": {"created_time": {}},
        "Last edited time": {"last_edited_time": {}},
    }},
})
```

MCPの `notion-create-database` で作るなら、DDLに
`"ID" UNIQUE_ID, "Created time" CREATED_TIME, "Last edited time" LAST_EDITED_TIME` を入れる。
**既存DBへ後から足すなら** `ADD COLUMN` か `PATCH /data_sources/{id}` で同じ3列を足す。

### date列の書式（Year/Month/Day・24 hour）はAPIでは設定できない

**date型の列は Date format を「Year/Month/Day」、Time format を「24 hour」にする。
ただしこれはAPIからは設定できないので、作ったあとに画面で変える。**

2026-09-18に、書けそうな経路を全部試して全滅を確認した。

| 試したこと | 結果 |
|---|---|
| REST `PATCH /data_sources/{id}` に `date.date_format` / `date.time_format` | **400** `date_format should be not present` |
| 同 `date.dateFormat` / `date.timeFormat` | **400** 同上 |
| 同 `date.format` | **400** 同上 |
| MCP DDL `ALTER COLUMN "Date" SET DATE FORMAT 'YYYY/MM/DD'` | **400** `Expected ADD, DROP, RENAME, or ALTER keyword, got "FORMAT"` |

**黙って無視されるのではなく400で弾かれる。** 書式はAPIのスキーマに無い。
`GET /data_sources/{id}` が返すdate列も常に `{"date": {}}` で、**読み取りもできない**ので、
**設定済みかどうかをAPIから確かめる術がない**（他の落とし穴のように「成功したのに
変わっていない」で気づく形にすらならない）。

## スキーマを変えるとき（DDLの落とし穴）

列の追加・改名・型変更は、公式MCPサーバーの `notion-update-data-source` にDDLを渡して行う。
**ここは失敗が例外にならず、成功レスポンスを返したまま値が消える経路がある。**
2026-08-30に実際に2,311件のプロパティ値を消したので、その形を残す。

### `RENAME COLUMN` は括弧付きの名前を黙って捨てる

```
RENAME COLUMN "カテゴリ" TO "カテゴリ(旧)"; ADD COLUMN "カテゴリ" RELATION(...)
```

これを1回で流すと、**RENAMEだけが無視され、続く ADD COLUMN が同名の既存プロパティを
relationに変換する。** エラーは出ない。結果として元の列の値が全件消える。

- 括弧を外した `"カテゴリ旧"` なら RENAME は通る（同じワークスペースの別DBで対照実験して確認）
- **`ADD COLUMN` は既存プロパティ名に対しても通り、型を差し替える。** 「既にある」という
  エラーにはならないので、名前の打ち間違いが破壊的操作になりうる

### だから守ること

1. **DDLは1文ずつ流し、都度スキーマを読み直して効いたか確かめる。**
   複数文をまとめると、効かなかった文があっても後続が走ってしまう。
2. **スキーマを変える前に、値を「ページIDつきで」ローカルへ吸い出す。**
   ページIDを入れ忘れると、他の列の組み合わせで突き合わせる羽目になる
   （実際にそうなり、他の列がすべて同じ行は一意に定まらず、
   グループ内で候補を配り切って集計だけ合わせる、という復旧になった）。
3. **列名に括弧・記号を使わない。** 通ったように見えて捨てられる。

### 型を変えると、その列を使っていたビューの設定が黙って落ちる

selectをrelationに変えたとき、**テーブルビューのフィルタは2つとも消えた**が、
**チャートのスタック指定はNotion側が `propertyType` を relation に自動追従させ、
そのまま動いていた。** 挙動が一貫しないので、**型を変えたら全ビューを開いて確かめる**。

- 貼り直すときのフィルタ値は、**リレーションはページ名では書けない**。
  ページURLかUUIDで指定する（`FILTER "カテゴリ" = "https://app.notion.com/p/<id>"`）

### select/multi_selectの選択肢を消すと、その値を持つレコードの値が黙って消える

`ALTER COLUMN "X" SET SELECT(...)` は**渡した一覧で選択肢を置き換える**。一覧から外した
選択肢は削除され、その値を持っていたレコードは**エラーも警告もなく空になる**。

**語彙を入れ替えるときは、必ずこの順で行う。**

1. 新しい選択肢を**足すだけ**のDDLを流す（古い選択肢は一覧に残したまま）
2. レコードを新しい選択肢へ振り直す
3. **古い選択肢が0件になったことをクエリで確かめる**
4. 0件を確認してから、古い選択肢を外したDDLを流す

2026-09-13に、あるDBの選択肢の再編で、この順序により数十件を無傷で移行した。
逆順だと、外した選択肢を持っていた行が空になる。

### 既存の選択肢の色は変更できない

`ALTER COLUMN ... SET SELECT(...)` で既存の選択肢に今と違う色を指定すると、
`Cannot update color of select with name: <名前>` で400になる。**一覧に載せ直す既存分は、
現在の色をそのまま書くこと**（色を変えたいなら画面で変える）。色の重複指定は通るので、
移行の途中で新旧の選択肢が同じ色を持っていても問題ない。

### データソースの改名は、独自アイコン（アップロード画像）を既定アイコンに戻す

`notion-update-data-source` に `title` を渡して改名すると、**そのDBに設定してあった
アップロード画像のアイコンが灰色の既定アイコンにリセットされる**（2026-09-13に発生）。

- 改名の**前に** `notion-fetch` でアイコンの値（`attachment:<uuid>:<filename>` 形式）を控える
- 改名後に確認し、消えていたら `notion-update-page` に `page_id`=データベースID と
  `icon`=控えた文字列を渡して戻す。このとき `command: "update_properties"` には
  `properties: {}` を**必ず添える**（省くと `requires a "properties" parameter` で400）
- なお `notion-update-data-source` のレスポンスとデータソースの `fetch` 結果は、
  復元後も `/icons/emoji-neutral_gray.svg` を返し続ける。**実際の表示を確かめるなら、
  親ページを `fetch` して `<database ... icon="...">` を見る**

### リンクドDBブロックの表示名（別名）はAPIで変えられない

親ページ上でDBに別名を付けている場合（`<database ...>別名</database>`）、
`notion-update-page` の `update_content` はその別名への置換を受け付けて
**成功レスポンス（page_id）を返すが、実際には何も変わらない**。DBの改名に追随させるには
**画面で手で直すしかない**。2026-09-13に2度試して2度とも無変更を確認。

### 列の説明（description）はDDLでは書けない。RESTのPATCHを使う

`notion-update-data-source` のDDLに列の説明を書く構文は無い（`ALTER COLUMN ... SET` に
`description` を渡しても、**列ではなくデータソース自体の説明**になる）。列に書くには
REST の `PATCH /data_sources/{id}` を使う。2026-09-03に3列へ書き込んで確認した手順:

```python
from notion_client import notion_request, get_data_source
body = {"properties": {"訪問件数": {
    "number": {"format": "number"},          # ← 型オブジェクトの同送が必須
    "description": "その週に…",              # ← 文字列。rich text配列だと400
}}}
notion_request("PATCH", f"/data_sources/{ds_id}", body)
```

踏んだ落とし穴は3つ。

| 症状 | 原因 |
|---|---|
| `body.properties.X.number should be defined` | **その列の型オブジェクトを同送していない。** descriptionだけでは通らない |
| `description should be a string` | rich text配列で渡した。**プレーンな文字列**で渡す |
| `description.length should be ≤ 280` | **280字上限。** 長い設計メモは入らないので、要点だけ書いてスキル側へ逃がす |

**型オブジェクトは、書き換えるつもりが無くても `get_data_source` で現在値を読んでそのまま
返す。** 手で書くと `number_format` などを取りこぼし、気づかないまま表示形式が変わる。

### 改名も同じPATCHで行う。ただし`description`は明示しないと消える

DDLの`RENAME COLUMN`は**括弧付きの名前へは黙って効かない**（上記）ので、`(h)`→`(h/回)`のような
改名はこのPATCHの`name`で行う。**プロパティIDは変わらないので、全行の値は保持される。**

```python
{"properties": {"平均滞在時間(h)": {"name": "平均滞在時間(h/回)",
                                   "number": {"format": "number"},
                                   "description": "…"}}}   # ← 省くと説明が消える
```

**`name`だけ渡すと、その列の`description`が空になる**（2026-09-03に実際に消して書き直した）。
PATCHは列定義の差分更新ではなく**指定した列の再定義**として効くので、
**残したい属性は毎回すべて同送する。** 迷ったら `get_data_source` の現在値をそのまま返す。

**改名したら、列名を持っているコードを同時に直す。** 列名は、書き込みの対応表を持つコード・
取り込みのマッピング・判定の設定JSON・Notionの定義書・各SKILL.mdのように、何箇所にも
散りやすい。**Notion側だけ直すと、
読み取りが旧名を引いて静かに`None`になる**（値は無事なので気づきにくい）。

### selectの選択肢は「改名できない」が「削除はできる」。この非対称が危ない

**列の改名は通るのに、選択肢の改名は通らない。** `PATCH /data_sources/{id}` に
`select.options` を `id` 付きで渡しても、**名前の変更だけが黙って捨てられる。**
2026-09-14に、あるDBのselect列で測った。

| 送ったもの | 結果 |
|---|---|
| `{"id": 既存, "name": "新しい名前"}` | **無反応**（成功レスポンス・名前は変わらない） |
| `{"id": 既存, "color": "別の色"}` | **400** `Cannot update color of select with id: <id>` |
| 一覧から選択肢を**省く** | **その選択肢が消える** |
| 選択肢に無い値を**ページへ書く** | **選択肢が自動で生える** |

**「配列ごと無視されている」のではない。** 色を変えようとすると400を返すので、
Notionは配列を読んで検証している。**それでも名前の変更だけはエラーにもならず消える。**
だから「成功したのに変わっていない」という形でしか気づけない。

**`options` は差分ではなく「送った集合がすべて」。省いた選択肢は消え、
その選択肢を使っていた行の値は黙って空になる。** 1行だけ使われている選択肢を
一覧から外して実測したところ、その行の値は `None` になった。
**2026-08-30に2,311件のカテゴリを壊した事故と同じ挙動**で、DDLに限った話ではない。

- **1つの選択肢を直すつもりで、その1件だけを配列に入れて送らない。** 他の選択肢が
  全部消え、それらを使っていた全行の値が空になる
- **`description` も同時に消える。** `select` だけを送ると説明が空になるので、
  列の再定義として毎回すべて同送する（この節の上の「改名も同じPATCHで行う」と同じ話）
- **色は消した選択肢を作り直すと変わる。** 自動で割り当てられ、APIからは指定できない
  （`purple` だったものが `brown` になった）。直したければ画面で

**改名したいときの手順は「値を書き換える」。** 選択肢は書けば自動で生えるので、
新しい名前を全行へ書いてから、古い選択肢を一覧から外す。**この順番を逆にしない**
（先に古い選択肢を消すと、その値が空になってから書き直すことになり、
途中で止まったとき何が入っていたか分からなくなる）。

```python
# 1. 全行の値を新しい名前で書き直す(選択肢は自動で生える)
for page in query_data_source(ds, {"page_size": 100}):
    ...
    update_page(page["id"], {"properties": {"対象": {"select": {"name": NEW[old]}}}})
# 2. 使用件数が0になったのを確かめてから、古い選択肢を一覧から外す
```

**`ALTER COLUMN "X" SET SELECT(...)` は使わない。** 選択肢の再定義になるので、
上と同じ「省いたものは消える」が効く。DDLは名前でしか指定できないぶん、
**書き落とした選択肢の値が黙って消える**危険がPATCHより高い。

### リレーション列には説明を付けられない

`description` を付けるPATCHは、**rich_text・title・number・selectでは効くが
リレーション列では黙って無視される**（型オブジェクトを同送しても成功レスポンスが
返り、読み直すと `None` のまま）。`description` だけを送ると型オブジェクトが無いので
400になり、**どちらの経路でも書けない**。2026-09-07に、2つのリレーション列で確認した。

**リレーション列の説明はNotionの画面で書く。** 列の意味をデータ側に残す設計を
採っているなら、ここだけ手作業になることを見込んでおく。

### dual relationの相手側プロパティ名は、DDLの`RENAME COLUMN`でしか直せない

`ADD COLUMN "X" RELATION('<ds>', DUAL)` で作ると、相手側に
`Related to <DB名> (<列名>)` という名前の列ができる。これを直す経路は1つだけ。

| 経路 | 結果 |
|---|---|
| 相手側DSへ `PATCH {"<旧名>": {"name": "<新名>", ...}}` | **400** `<新名> is not a valid property schema` |
| 自DSの `dual_property.synced_property_name` を書き換えてPATCH | **無反応**（成功レスポンス・値は変わらない） |
| 相手側DSへ DDL `RENAME COLUMN "Related to A (B)" TO "A"` | **通る** |

**`RENAME COLUMN` が括弧付きの名前を捨てるのは「新しい名前」に括弧があるときで、
「元の名前」に括弧があるのは問題ない。** 上の既定名は括弧を含むが、括弧なしの
名前へ改名する分には効く（2026-09-07に確認）。

### API経由では作れない・できないもの

| やりたいこと | 可否 |
|---|---|
| リレーション先のプロパティを辿る数式列を作る | **不可**。`prop("R").map(current.prop("X"))` 系はどう書いても `Type error with formula` で弾かれる。Notionの画面の数式エディタなら書ける |
| 単純な数式列を作る | 可（`FORMULA('1 + 1')` は通る） |
| ロールアップ列を作る | 可（`ROLLUP('リレーション列', '相手の列', 'sum')`） |
| ロールアップでグループ化する | **不可**（Notionの仕様）。リレーションでのグループ化は可 |
| 日付グループ化の粒度（日/週/月）を指定する | **不可**。ビューDSLに粒度の指定が無く、既定は「日」になる（`GROUP BY "日付" BY month` は `Unknown directive` で弾かれる）。月次の推移グラフを作るなら、画面でX軸のグループ化を「月」に切り替える |
| date列のDate format / Time formatを指定する | **不可**。400で弾かれ、読み取りもできない（常に`{"date": {}}`）。画面で設定する → 「新規DBを作るときの既定」 |
| unique_id(ID)・created_time・last_edited_timeの**列**を作る | 可（REST `POST /databases`・DDLのどちらでも通る。"read-only" なのは値であって列の作成ではない） |

親子構造の集計をしたい場合、**子を持つ側（行数の少ないマスタDB）にロールアップを置き、
そのDBを親の属性でグループ化する**ほうが、レコード側に数式列を作るより素直に収まる。

## MCPで本文を書くとき — ファイル名やドメインに見える語が勝手にリンクになる

公式MCPの `notion-update-page`（`update_content` 等）や `notion-create-pages` で本文をMarkdownとして
書くと、**ドメイン名に見える語が、頼んでいないリンクに変わる。** エラーも警告も出ず、
レスポンスは成功のまま。2026-09-23に、あるページへ節を書き足したときに発生した。

- **`.md`（モルドバ）・`.ai`（アンギラ）は実在する国別ドメイン**なので、`CLAUDE.md`・`SKILL.md`・
  `claude.ai` がWebアドレスとして扱われる
- **日本語は語の間にスペースが無いので、直前の日本語までリンクに飲み込まれる**
- 段落・見出し・表のセルのどこでも起きる。クリックすると存在しないサイトを開こうとする

| 書いたもの | 保存されたもの |
|---|---|
| 組織向けCLAUDE.md | `[組織向けCLAUDE.md](http://組織向けCLAUDE.md)` |
| 6〜8のCLAUDE.md同士 | `6〜[8のCLAUDE.md](http://8のCLAUDE.md)同士` |
| auto memory（MEMORY.md） | `auto memory（[MEMORY.md](http://MEMORY.md)）` |
| `` `CLAUDE.md` ``（コード表記） | **そのまま。リンクにならない**（同じ書き込みの中での対照） |

既存ページにも `またはclaude.ai` が丸ごと `http://またはclaude.ai` へのリンクになった例があった。

### だから守ること

1. **ファイル名・パス・ドメインは、段落でも見出しでも表のセルでも、必ずコード表記（`` ` `` で囲む）で書く。**
   拡張子が国別ドメインと同じものは特に注意する（`.md`・`.ai` は実測。`.py`＝パラグアイ・
   `.sh`＝セントヘレナ・`.io` なども同じ形だが未実測）
2. **リンクにしたい実在のドメインは `[claude.ai](https://claude.ai)` と明示して書き、前後の日本語とは
   半角スペースで区切る。** 明示したリンクは書いたとおりに保存された（2026-09-23に確認）
3. **書いたら `notion-fetch` で読み直し、`](http://` を探す。** 意図しないリンクがあれば、
   `update_content` の `old_str` に**fetchで見えるリンク込みの文字列**をそのまま渡し、コード表記へ
   置き換える。同じ文字列が複数あるなら `replace_all_matches: true`

- Notion-flavored Markdownの仕様（`notion://docs/enhanced-markdown-spec`）にこの挙動の記載は無く、
  エスケープ対象の文字にも `.` は無い。**防げると確かめたのはコード表記だけ**
- **RESTの経路（`notion_blocks.py` → `append_block_children` 等）では起きない見込み。** RESTのrich textは
  `text.link` を明示したものだけがリンクになり、`notion_blocks.py` はリンクを付けない（RESTでは未実測）。
  ただし `notion_blocks.py` は `` ` `` をコード表記に変換しない（`**太字**` 以外は素通し）ので、
  REST経由で書くと `` ` `` がそのまま文字として残る

## 注意点

- **date型プロパティの書式**: ページ作成(`create_page.sh`)でdate型プロパティを設定する際は、
  Notion公式の標準形式 `{"プロパティ名": {"date": {"start": "2026-07-20", "end": null}}}` を
  使うこと。Notion公式MCPサーバー(`notion-update-page`等)が独自に使う疑似キー記法
  `"date:プロパティ名:start"` は生のREST APIでは通用せず、送るとバリデーションエラーに
  なる(2026-07-22の動作確認で実際に発生・特定済み)。
- このスキル自体はデータソースの選定・取得範囲の判断・取得データの構造化や意味づけを
  一切行わない。それらは呼び出し元のスキル(Collection/Evaluation層)の責務。
  Notion以外の外部API(Googleカレンダー等)もこのスキルの対象外。
- 認証情報(`NOTION_TOKEN`)はこのスキルディレクトリ内に絶対に含めない。常に
  `~/.claude-skills-env/notion-cli-api-skill.env` を都度読み込むだけにする。
- Notion REST APIのレート制限(約3req/s)は`notion_client.py`が全リクエストで一括して面倒を
  見る(前回リクエストからの経過を見て0.35秒に足りない分だけ待つ)。scripts経由でもimport経由でも
  同じ経路を通るので、**呼び出し側で`time.sleep`を入れない**。
- **一時的な失敗は `notion_client.py` が再試行する**（429・500・502・503・504・
  タイムアウト・接続断）。指数バックオフにゆらぎを足し、`Retry-After` があれば
  サーバの指示を優先する。最大5回。**呼び出し側でリトライを書かない。**
  - **400・404などは再試行しない。** 投げ直しても同じで、再試行で覆い隠すと
    呼び出し側の誤りの発見が遅れる。即座に例外が上がる
  - 2026-08-30の移行中に、Notion側の503（`Public API object rendering exceeded
    the response time budget`）と読み取りタイムアウトで2度落ちた。2,000件超の
    書き込みの最中に起きると「どこまで書けたか分からない」状態になるため入れた
  - 再試行しても駄目だった場合は例外を送出する。コマンドラインスクリプトは
    `NotionError` を捕まえて exit すること
