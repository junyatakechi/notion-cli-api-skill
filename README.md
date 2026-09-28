# notion-cli-api-skill

NotionをClaudeから扱うためのスキル。
Claudeに頼むと、Notionが黙って値を壊す落とし穴を避けながら編集したり、Notionのコメントを拾って返信したりする。

中身はNotion REST APIへの薄いアクセスで、どのデータを読み書きするかは決めない。
他のスキルがNotionを読み書きするときの部品としても使える。

## 必要なもの

- [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
- Notionの Internal Integration
- Python 3.11以上と [uv](https://docs.astral.sh/uv/)
- `sh` と `curl`（WindowsではGit Bash）
- Claudeに接続した公式の [Notion MCP](https://developers.notion.com/docs/mcp)（[コメントに答えてもらう](#notionのコメントに答えてもらう)ときだけ）

## インストール

スキルのフォルダでクローンする。フォルダ名はリポジトリ名のままでよい。

```bash
git clone https://github.com/junyatakechi/notion-cli-api-skill.git ~/.claude/skills/notion-cli-api-skill
```

特定のプロジェクトだけで使うなら、`<プロジェクト>/.claude/skills/` の中でクローンする。

## セットアップ

### Pythonとuvを入れる

Windowsでは、[winget](https://learn.microsoft.com/windows/package-manager/winget/)で入れる。

```bash
winget install --id Python.Python.3.14 --exact
```

```bash
winget install --id astral-sh.uv --exact
```

macOS・Linuxでは、[uvの公式インストーラー](https://docs.astral.sh/uv/getting-started/installation/)でuvを入れ、uvでPythonを入れる。

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```bash
uv python install 3.14
```

入れたらターミナルを開き直し、`uv --version` でバージョンが表示されるのを確かめる。

### Notionの準備

1. [Notionのインテグレーション画面](https://www.notion.so/profile/integrations)で Internal Integration を作り、トークン（`ntn_` で始まる。2024-09-25より前に発行したものは `secret_` で始まる）を控える。
2. 読み書きしたいページやデータベースを開き、右上の「接続」からこのIntegrationを追加する。追加していないページはAPIから見えず、404になる。
3. トークンを、スキルのフォルダの外にあるファイルへ保存する。`ntn_xxxxxxxx` は控えたトークンに置き換える。キーの名前は同梱の `.env.example` と同じ。

   ```bash
   mkdir -p "$HOME/.claude-skills-env"
   echo 'NOTION_TOKEN=ntn_xxxxxxxx' > "$HOME/.claude-skills-env/notion-cli-api-skill.env"
   ```

### コメントに答えてもらうときの準備

[Notionのコメントに答えてもらう](#notionのコメントに答えてもらう)ときだけ要る。

1. [Notionのインテグレーション画面](https://www.notion.so/profile/integrations)で、Integrationの「Read comments」と「Insert comments」を有効にする。既定はオフで、オフのままだと403になるか、中身の無い結果が返る。
2. 公式の [Notion MCP](https://developers.notion.com/docs/mcp) をClaudeに接続する。どのスレッドがあなたの発言で止まっているかを見分けるのに使う。

## 使い方

Claudeに普段の言葉で頼むと、Claudeがこのスキルを読み込んで作業する。

### Notionを編集するときの落とし穴を避けてもらう

Claudeが次の作業をするとき、このスキルにまとめた注意点に沿って進める。
確実に使わせたいときは、頼むときに「notion-cli-api-skillの注意点に沿って」と添える。

| 作業 | Claudeが守ること |
|---|---|
| データベースの列を追加・改名・型変更する | 先に値をページIDつきで書き出し、変更は1つずつ効いたか確かめる |
| selectの選択肢を入れ替える | 新しい選択肢を足す → 値を付け替える → 古い選択肢が0件なのを確かめてから消す |
| 新しいデータベースを作る | `ID`・`Created time`・`Last edited time` の3列を必ず付ける |
| 公式MCPでページ本文を書く | `CLAUDE.md` のようなファイル名をコード表記にし、勝手にリンクになるのを防ぐ |

Notionはこれらの操作で、エラーを出さずに値を消すことがある。条件と実際に起きたことは [SKILL.md](SKILL.md) にまとめている。

date列の表示形式（年/月/日・24時間表記）はAPIでは設定できないので、データベースを作ったあとにNotionの画面で直す。

Notionのコメントへの返信も頼める。公式MCPを併用する例外があるため、[後ろの節](#notionのコメントに答えてもらう)にまとめた。

## 他のスキルから使う

Notionを読み書きするスキルを作るときは、このスキルのスクリプトとモジュールを部品として使える。

| 操作 | シェルから | Pythonから |
|---|---|---|
| ページを取得する | `scripts/get_page.sh` | `get_page` |
| ページ本文を再帰で取得する | `scripts/get_block_children.py` | `get_block_children` |
| データソースをクエリする | `scripts/query_data_source.py` | `query_data_source` |
| ページを作成する | `scripts/create_page.sh` | `create_page` |
| ページのプロパティを更新する | `scripts/update_page.sh` | `update_page` |
| ブロックを更新する | `scripts/update_block.sh` | `update_block` |
| ブロックを追加する | — | `append_block_children` |
| コメントを取得する | — | `get_comments` |
| コメントに返信する | — | `create_comment` |

Pythonのモジュールは次の4つ。標準ライブラリだけで動く。

| モジュール | 役割 |
|---|---|
| `notion_client.py` | API通信。認証・レート制限・ページネーション・再試行・エラー |
| `notion_blocks.py` | Markdown→Notionブロック、Notionブロック→テキストの変換 |
| `notion_props.py` | プロパティ値の組み立て（`title_prop`・`date_prop` など） |
| `notion_tables.py` | ページ本文の表を、直前の見出しをキーにして読み出す |

シェルからは次のように呼ぶ。結果はJSONで標準出力に出る。HTTPエラーのときは標準エラーに内容を出し、0以外で終了する。

```bash
scripts/get_page.sh <page ID>
```

Pythonからはimportして使う。数百件を読み書きするときも、シェルのスクリプトを繰り返し起動せずにこちらを使う。

```python
import os, sys
sys.path.insert(0, os.path.expanduser("~/.claude/skills/notion-cli-api-skill/scripts"))
from notion_client import NotionError, query_data_source, create_page

pages = query_data_source("<data source ID>", {"filter": {...}})
create_page({"parent": {"data_source_id": "<data source ID>"}, "properties": {...}})
```

- レート制限（約3リクエスト/秒）と、一時的な失敗（429・5xx・タイムアウト）の再試行はモジュールが受け持つ。呼び出し側で `time.sleep` やリトライを書かない。
- エラーは `sys.exit` ではなく例外（`NotionError` とその派生）で返る。
- 別のトークンを一時的に使いたいときは、環境変数 `NOTION_ENV_FILE` にファイルの絶対パスを渡す。

## Notionのコメントに答えてもらう

ページに付いた未解決のコメントを取り、あなたの問いかけで止まっているスレッドにClaudeが返信する。
このスキルはREST APIで動くが、この機能だけは公式のNotion MCPも併用する。
先に、セットアップの[コメントに答えてもらうときの準備](#コメントに答えてもらうときの準備)を済ませておく。

### 頼み方

ページのURLを貼って頼む。

| 頼み方 | Claudeがすること |
|---|---|
| 「このページのコメントを拾って <URL>」 | 未解決のコメントを全部取り、あなたの問いかけで止まっているスレッドすべてに返信する |
| 「このページのコメントを見て <URL>」「指摘を拾って <URL>」 | 同上 |
| 「効率重視で、このページのコメントを拾って <URL>」 | 同上。コメントを公式MCPで一度に取る（→ [コメントの取り方](#コメントの取り方)） |
| 「このページのコメントを読むだけ <URL>」 | 内容を伝えるだけで、返信しない |

- 「拾って」は返信までを含む。返信させたくないときは「読むだけ」と伝える。
- 終わると、取得した件数と返信した件数が報告される。

### どのスレッドに返信するか

スレッドの最後のコメントを誰が書いたかで決める。

| スレッドの最後のコメント | Claudeの扱い |
|---|---|
| あなた | 返信する |
| このIntegration（bot） | 返信済みとして飛ばす |
| 他のメンバー | 飛ばす（あなた宛てとは限らないため） |

返信はIntegrationの名前（bot）で投稿される。あなたの名前では投稿されない。

### コメントの取り方

既定ではREST APIで取る。公式MCPを使うのは例外で、頼まれたときだけ。

| | 既定 | 「効率重視で」と頼んだとき |
|---|---|---|
| 使うもの | Notion REST API | 公式のNotion MCP |
| 取り方 | 本文のブロックを1つずつ問い合わせる | ページ全体を1回で取る |
| かかる時間 | ブロック数に比例する（約230ブロックで2分ほど） | 1回の呼び出しで済む |
| どの記述へのコメントか | ブロック単位まで分かる | 選択された文字列まで分かる |

- 解決済みのコメントも読みたいときは、そう伝える。REST APIでは読めないので、公式MCPで取る。
- 返信は、どちらで取ったときもREST APIで行う。公式MCPで返信するとあなたの名前で投稿されてしまうため。

### できないこと

- コメントの解決（Resolve）。返信を読んだら、Notionの画面で解決する。
- 文章の一部を選んで、新しいコメントを付けること。既存のスレッドへの返信と、ページやブロックへのコメントはできる。

表の行や列を増減させる編集をすると、その表に付いたコメントは消える。Claudeはコメントに返信してから表を直す。

手順の詳細は [references/comments.md](references/comments.md) にある。

## ライセンス

[MIT License](LICENSE)
