#!/bin/sh
# notion-cli-api-skill: bashスクリプト共通処理(トークン読み込み・curl呼び出し)
set -eu

# 秘密情報は起動フォルダ(作業ディレクトリ)の .env に置く規約。プロジェクトのスキルはこの1つを共有する。
# 環境変数 NOTION_TOKEN があればそれを使い、無ければ .env から NOTION_TOKEN の行だけを読む
# (.env には他のスキルの値も入るので、丸ごと source しない)。
NOTION_VERSION="2025-09-03"
NOTION_API_BASE="https://api.notion.com/v1"

if [ -z "${NOTION_TOKEN:-}" ] && [ -f .env ]; then
  NOTION_TOKEN="$(sed -n 's/^[[:space:]]*NOTION_TOKEN[[:space:]]*=[[:space:]]*//p' .env | tail -n 1 | tr -d '\r' | sed -e 's/[[:space:]]*$//' -e "s/^[\"']//" -e "s/[\"']\$//")"
fi

if [ -z "${NOTION_TOKEN:-}" ]; then
  echo "Error: NOTION_TOKEN is not set (neither in the environment nor in $(pwd)/.env)" >&2
  echo "See the セットアップ section of ../README.md." >&2
  exit 1
fi

# notion_curl <method> <path> [body_file]
# 標準出力にレスポンスJSON、失敗時はstderrにエラーを出し非zero終了する。
notion_curl() {
  method="$1"
  path="$2"
  body_file="${3:-}"
  tmp_body="$(mktemp)"
  trap 'rm -f "$tmp_body"' EXIT

  if [ -n "$body_file" ]; then
    http_status=$(curl -sS -o "$tmp_body" -w '%{http_code}' -X "$method" "$NOTION_API_BASE$path" \
      -H "Authorization: Bearer $NOTION_TOKEN" \
      -H "Notion-Version: $NOTION_VERSION" \
      -H "Content-Type: application/json" \
      --data @"$body_file")
  else
    http_status=$(curl -sS -o "$tmp_body" -w '%{http_code}' -X "$method" "$NOTION_API_BASE$path" \
      -H "Authorization: Bearer $NOTION_TOKEN" \
      -H "Notion-Version: $NOTION_VERSION")
  fi

  if [ "$http_status" -ge 200 ] && [ "$http_status" -lt 300 ]; then
    cat "$tmp_body"
  else
    echo "Error: Notion API returned HTTP $http_status" >&2
    cat "$tmp_body" >&2
    rm -f "$tmp_body"
    exit 1
  fi
}
