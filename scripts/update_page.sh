#!/bin/sh
# notion-cli-api-skill: ページ更新 (PATCH /v1/pages/{page_id})
#
# Usage: update_page.sh <page_id> <request_body.json>
# request_body.json は Notion API の PATCH /v1/pages/{id} がそのまま受け付ける形式
# (properties/archived等)のJSONファイル。標準出力に更新後のページオブジェクトJSONを
# そのまま出力する。
set -eu
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/_common.sh"

page_id="${1:?Usage: update_page.sh <page_id> <request_body.json>}"
body_file="${2:?Usage: update_page.sh <page_id> <request_body.json>}"
if [ ! -f "$body_file" ]; then
  echo "Error: request body file not found: $body_file" >&2
  exit 1
fi

notion_curl PATCH "/pages/$page_id" "$body_file"
