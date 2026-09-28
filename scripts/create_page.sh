#!/bin/sh
# notion-cli-api-skill: ページ作成 (POST /v1/pages)
#
# Usage: create_page.sh <request_body.json>
# request_body.json は Notion API の POST /v1/pages がそのまま受け付ける形式
# (parent/properties/children等)のJSONファイル。標準出力に作成されたページ
# オブジェクトJSONをそのまま出力する。
set -eu
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/_common.sh"

body_file="${1:?Usage: create_page.sh <request_body.json>}"
if [ ! -f "$body_file" ]; then
  echo "Error: request body file not found: $body_file" >&2
  exit 1
fi

notion_curl POST "/pages" "$body_file"
