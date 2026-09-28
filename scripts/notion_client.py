"""notion-cli-api-skill: Notion REST APIのPythonクライアント(標準ライブラリのみ使用)。

このモジュールは**他スキルから直接importして使う公開モジュール**。
Pythonから大量のリクエストを投げる場合（数百件の投入・更新など）は、scripts配下の
シェルスクリプトをsubprocessで起動するとプロセス起動のオーバーヘッドが支配的になるため、
こちらを直接importすること。単発の呼び出しやシェルからの利用はscripts配下を使う。

    import os, sys
    _ws = os.path.dirname(os.path.abspath(__file__))
    while not os.path.isdir(os.path.join(_ws, ".claude", "skills", "notion-cli-api-skill")) and os.path.dirname(_ws) != _ws:
        _ws = os.path.dirname(_ws)
    sys.path.insert(0, os.path.join(_ws, ".claude", "skills", "notion-cli-api-skill", "scripts"))
    from notion_client import notion_request, notion_post_paginate, NotionError

このモジュールが一手に引き受けるもの（他スキルで再実装しないこと）:
  - 認証トークンの読み込みとキャッシュ
  - APIのベースURLとバージョン
  - レート制限（リクエスト間隔の調整）
  - **一時的な失敗の再試行**（429・5xx・タイムアウト・接続断）
  - HTTPエラーの検出

エラーは `sys.exit` せず **例外を送出する**。呼び出し側がリトライするか中断するかを
選べるようにするため。コマンドラインスクリプトは `NotionError` を捕まえて exit すること。
"""
import json
import os
import random
import socket
import sys
import time
import urllib.error
import urllib.request

# Windows既定のコードページ(cp932等)だと標準出力・標準エラーへの日本語書き込みで文字化けするため、
# UTF-8に固定する(3OS可搬のための吸収。Python 3.7+)。標準エラーには再試行の通知が出る。
# 注意: これはこのモジュールをimportしたプロセスにのみ効く。importしないスクリプトで
# 標準出力へJSONを書く場合は、実行時に PYTHONIOENCODING=utf-8 を渡すこと。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

NOTION_VERSION = "2025-09-03"
API_BASE = "https://api.notion.com/v1"
# Notion REST APIのレート制限(約3req/s)を踏まえた、連続リクエスト間の最小間隔(秒)。
REQUEST_INTERVAL_SEC = 0.35

# **一時的な失敗はここで再試行する。** 2,000件超の書き込みを流す使い方をするので、
# 途中の1回が落ちると「どこまで書けたか分からない」状態になる。実際に2026-08-30の
# 移行中、Notion側の 503(レンダリングのタイムアウト超過) と読み取りタイムアウトで
# 2度落ちた。
#
# **再試行してよいのは「もう一度投げれば通るかもしれない」ものだけ。**
#   429      … レート制限。Retry-After があればそれに従う
#   5xx      … サーバ側の一時障害
#   タイムアウト・接続断 … ネットワークの揺れ
# 400(バリデーション)や404は投げ直しても同じなので**再試行しない**。呼び出し側の
# 誤りを再試行で覆い隠すと、原因の特定が遅れる。
RETRY_MAX_ATTEMPTS = 5
RETRY_BASE_SEC = 1.0
RETRY_MAX_SEC = 30.0
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

DEFAULT_ENV_FILE = os.path.join(
    os.path.expanduser("~"), ".claude-skills-env", "notion-cli-api-skill.env"
)


# ---------------------------------------------------------------- 例外

class NotionError(RuntimeError):
    """このモジュールが送出する例外の基底。スクリプトはこれを捕まえて exit する。"""


class NotionAuthError(NotionError):
    """トークンファイルが無い、または NOTION_TOKEN が設定されていない。"""


class NotionAPIError(NotionError):
    """Notion APIがエラーを返した。`status` にHTTPステータスが入る。"""

    def __init__(self, status, method, path, detail):
        super().__init__(f"Notion API returned HTTP {status} on {method} {path}\n{detail}")
        self.status = status
        self.method = method
        self.path = path
        self.detail = detail


# ---------------------------------------------------------------- 認証

_token_cache = None


def load_token(force_reload=False):
    """トークンを読み込む。一度読んだらプロセス内でキャッシュする。

    毎リクエストでファイルを読み直すと、数百件の投入で無駄なI/Oが積み上がるため。
    """
    global _token_cache
    if _token_cache is not None and not force_reload:
        return _token_cache

    env_file = os.environ.get("NOTION_ENV_FILE", DEFAULT_ENV_FILE)
    if not os.path.isfile(env_file):
        raise NotionAuthError(
            f"Notion token file not found: {env_file}\n"
            "See the セットアップ section of notion-cli-api-skill/README.md to create it."
        )
    token = None
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() == "NOTION_TOKEN":
                token = value.strip().strip('"').strip("'")
    if not token:
        raise NotionAuthError(f"NOTION_TOKEN is not set in {env_file}")

    _token_cache = token
    return token


# ---------------------------------------------------------------- リクエスト

_last_request_at = 0.0


def _throttle():
    """前回のリクエストから REQUEST_INTERVAL_SEC 以上あくように待つ。

    呼び出し側が個別に sleep すると、実際の処理時間を無視して常に待つことになり
    無駄が出る。ここで前回時刻からの経過を見て、足りない分だけ待つ。
    """
    global _last_request_at
    wait = REQUEST_INTERVAL_SEC - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _retry_wait(attempt, retry_after=None):
    """次の再試行まで待つ秒数。指数バックオフ＋ゆらぎ。

    ゆらぎを入れるのは、同時に走っている処理があったときに再試行が同じ瞬間に
    重ならないようにするため。`Retry-After` が来ていればサーバの指示を優先する。
    """
    if retry_after:
        try:
            return min(float(retry_after), RETRY_MAX_SEC)
        except (TypeError, ValueError):
            pass
    return min(RETRY_BASE_SEC * (2 ** attempt), RETRY_MAX_SEC) * (0.5 + random.random())


def notion_request(method, path, body=None, timeout=60):
    """Notion REST APIを1回呼び出し、レスポンスをdictで返す。

    レート制限と**一時的な失敗の再試行**はこの関数が面倒を見るので、呼び出し側で
    sleepもリトライもしないこと。再試行しても駄目だった場合と、再試行しても意味が
    ない失敗(400・404など)は `NotionAPIError` を送出する。
    """
    token = load_token()
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    last = None
    for attempt in range(RETRY_MAX_ATTEMPTS):
        _throttle()
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Notion-Version", NOTION_VERSION)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            last = NotionAPIError(e.code, method, path, detail)
            if e.code not in RETRYABLE_STATUS:
                raise last from None
            wait = _retry_wait(attempt, e.headers.get("Retry-After"))
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
            # 接続できない・応答が来ない。投げ直せば通ることが多い
            last = NotionError(f"{method} {path} に接続できませんでした: {e}")
            wait = _retry_wait(attempt)
        if attempt == RETRY_MAX_ATTEMPTS - 1:
            break
        print(f"    [retry {attempt + 1}/{RETRY_MAX_ATTEMPTS - 1}] "
              f"{method} {path} … {wait:.1f}秒待って再試行", file=sys.stderr, flush=True)
        time.sleep(wait)
    raise last


def notion_post_paginate(path, body=None, results_key="results"):
    """POST系エンドポイント(data_sourcesクエリ等)のページネーションを解決し、
    全結果を1つのlistで返す。"""
    all_results = []
    cursor = None
    first = True
    while first or cursor:
        first = False
        page_body = dict(body) if body else {}
        if cursor:
            page_body["start_cursor"] = cursor
        page = notion_request("POST", path, page_body)
        all_results.extend(page.get(results_key, []))
        cursor = page.get("next_cursor")
        if not page.get("has_more"):
            break
    return all_results


def notion_get_paginate(path, results_key="results"):
    """GET系エンドポイント(block children等)のページネーションをクエリパラメータで
    解決し、全結果を1つのlistで返す。"""
    all_results = []
    cursor = None
    first = True
    while first or cursor:
        first = False
        page_path = path
        if cursor:
            sep = "&" if "?" in path else "?"
            page_path = f"{path}{sep}start_cursor={cursor}"
        page = notion_request("GET", page_path)
        all_results.extend(page.get(results_key, []))
        cursor = page.get("next_cursor")
        if not page.get("has_more"):
            break
    return all_results


# ---------------------------------------------------------------- 操作別のAPI
#
# 呼び出し側スキルが各自でsubprocessラッパー(_notion_client.py)を持つと、同じ関数が
# スキルの数だけ増え、APIバージョン・エラー処理・レート制限がそこに散らばる。
# 操作単位の入口はここに1つだけ置き、各スキルはこれをimportする。

# Notion APIの1リクエストあたりchildren上限。分割の仕方(何件ずつ・間に何を挟むか)は
# 呼び出し側の判断なので、ここでは超過を検出して知らせるだけにする。
CHILDREN_LIMIT = 100


def get_page(page_id):
    """GET /pages/{id}。ページオブジェクト(プロパティ・親情報)を返す。"""
    return notion_request("GET", f"/pages/{page_id}")


def create_page(body):
    """POST /pages。bodyはparent/properties/children等、APIがそのまま受け付ける形式。"""
    return notion_request("POST", "/pages", body)


def update_page(page_id, body):
    """PATCH /pages/{id}。プロパティの部分更新やアーカイブに使う(本文は変更できない)。"""
    return notion_request("PATCH", f"/pages/{page_id}", body)


def query_data_source(data_source_id, body=None):
    """POST /data_sources/{id}/query。ページネーションを解決した全件のlistを返す。"""
    return notion_post_paginate(f"/data_sources/{data_source_id}/query", body or {})


def get_data_source(data_source_id):
    """GET /data_sources/{id}。スキーマ(プロパティ定義)の取得に使う。"""
    return notion_request("GET", f"/data_sources/{data_source_id}")


def select_options(data_source_id, property_name):
    """select/multi_selectプロパティの選択肢名リストを返す。該当しなければ空リスト。

    「既存の選択肢に無いタグを新規作成してよいか」の判断は呼び出し側の責務で、
    ここは実在する選択肢を読み出すだけ。
    """
    prop = get_data_source(data_source_id).get("properties", {}).get(property_name, {})
    ptype = prop.get("type")
    if ptype not in ("select", "multi_select"):
        return []
    return [o["name"] for o in prop[ptype].get("options", [])]


def get_block_children(block_id, recursive=True):
    """GET /blocks/{id}/children。ページネーションを解決したlistを返す。

    recursive=Trueなら has_children のブロックを再帰的に辿り、各ブロックに
    "children" キー(配列)を埋め込む。ページ本文全体が欲しい場合はpage_idを渡す。
    """
    children = notion_get_paginate(f"/blocks/{block_id}/children")
    if recursive:
        for block in children:
            if block.get("has_children"):
                block["children"] = get_block_children(block["id"], recursive=True)
    return children


def append_block_children(block_id, children):
    """PATCH /blocks/{id}/children。既存ページの末尾に本文ブロックを追記する。

    childrenは CHILDREN_LIMIT 件以内で渡すこと。超過は分割せず ValueError にする
    (何件ずつ・どこで区切るかは呼び出し側の判断のため、ここで勝手に決めない)。
    """
    if len(children) > CHILDREN_LIMIT:
        raise ValueError(
            f"children must be <= {CHILDREN_LIMIT} per request (got {len(children)}). "
            "Split on the caller side."
        )
    return notion_request("PATCH", f"/blocks/{block_id}/children", {"children": children})


def update_block(block_id, body):
    """PATCH /blocks/{id}。bodyはブロックタイプをキーにしたdict
    ({"paragraph": {"rich_text": [...]}} 等)。本文の既存行の書き換えに使う。"""
    return notion_request("PATCH", f"/blocks/{block_id}", body)


def get_comments(block_id, recursive=False):
    """GET /comments?block_id=。そのブロック(またはページ)に付いた未解決のコメントをlistで返す。

    ページIDを渡すとページ自体へのコメントだけが返り、本文へのインラインコメントは含まれない。
    recursive=Trueなら本文の全ブロックを辿り、ブロックごとに問い合わせてまとめる
    (ブロック数ぶんのリクエストになる。子ページは別のページなので辿らない)。
    解決済みのコメントはAPIの仕様で返らない。
    """
    comments = notion_get_paginate(f"/comments?block_id={block_id}")
    if recursive:
        for block in get_block_children(block_id, recursive=False):
            deeper = block.get("has_children") and block.get("type") != "child_page"
            comments.extend(get_comments(block["id"], recursive=deeper))
    return comments


def create_comment(body):
    """POST /comments。既存スレッドへの返信は {"discussion_id": ..., "rich_text": [...]}。

    parent.page_id / parent.block_id を渡せばページ・ブロックへのコメントになる。
    テキスト範囲に新しいスレッドを立てることはAPIではできず、解決もできない。
    投稿者はIntegrationのbotで、display_nameを付けても表示名が変わるだけ。
    """
    return notion_request("POST", "/comments", body)


# ---------------------------------------------------------------- 器のURL → 識別子(2026-09-22)
# 器(DB)と文書のURLは固有の値なので、文書にもスキルにも書かず環境ファイルが持つ。
# URLから保存先固有の識別子(data source ID)への
# 解決は横断スキルの機構なのでここに置く。
import re as _re
from collections.abc import Mapping as _Mapping

_ENV_FILES = {}
_DS_BY_DB = {}


def load_env_file(name, force_reload=False):
    """`~/.claude-skills-env/<name>.env` を KEY=VALUE の dict で返す。無ければ空の dict。"""
    if force_reload or name not in _ENV_FILES:
        path = os.path.join(os.path.expanduser("~"), ".claude-skills-env", f"{name}.env")
        values = {}
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        values[k.strip()] = v.strip()
        _ENV_FILES[name] = values
    return _ENV_FILES[name]


def page_id_from_url(url):
    """NotionのページURL(DBのページも同じ)からIDをダッシュ付きで取る。
    `.../p/<32hex>`・`.../Title-<32hex>`・`collection://<uuid>` のどれでもよい。"""
    seg = url.split("?")[0].split("#")[0].rstrip("/").split("/")[-1].replace("-", "")
    h = seg[-32:]
    if len(h) != 32 or not _re.fullmatch(r"[0-9a-f]{32}", h):
        raise NotionError(f"URLからNotionのIDを取れない: {url}")
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


def data_source_id_from_url(url, force_reload=False):
    """DBのページURL → data source ID(`GET /databases/{id}` の data_sources[0])。
    1つのDBが複数の data source を持つ構成は使っていないので最初のものを採る。プロセス内でキャッシュする。"""
    dbid = page_id_from_url(url)
    if force_reload or dbid not in _DS_BY_DB:
        db = notion_request("GET", f"/databases/{dbid}")
        sources = db.get("data_sources") or []
        if not sources:
            raise NotionError(f"database {dbid} に data source が無い")
        _DS_BY_DB[dbid] = sources[0]["id"]
    return _DS_BY_DB[dbid]


class EnvDataSources(_Mapping):
    """器のURL変数 `<PREFIX>_DB_<KEY>_URL` を環境ファイルから読み、data source ID に解決する遅延辞書。
    Domain層の `DS[entity]` はこれ。キーの一覧は呼び出し側が渡す。"""

    def __init__(self, env_name, prefix, keys):
        self.env_name, self.prefix, self._keys = env_name, prefix, tuple(keys)
        self._ids = {}

    def var(self, key):
        return f"{self.prefix}_DB_{key.upper()}_URL"

    def url(self, key):
        url = load_env_file(self.env_name).get(self.var(key))
        if not url:
            raise NotionError(f"~/.claude-skills-env/{self.env_name}.env に {self.var(key)} が無い"
                              "(器のURLは環境ファイルが持つ)")
        return url

    def __getitem__(self, key):
        if key not in self._keys:
            raise KeyError(key)
        if key not in self._ids:
            self._ids[key] = data_source_id_from_url(self.url(key))
        return self._ids[key]

    def __iter__(self):
        return iter(self._keys)

    def __len__(self):
        return len(self._keys)
