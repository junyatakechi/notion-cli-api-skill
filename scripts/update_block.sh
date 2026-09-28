#!/bin/sh
# notion-cli-api-skill: ブロック更新 (PATCH /v1/blocks/{block_id})
#
# Usage: update_block.sh <block_id> <request_body.json>
# request_body.json は Notion API の PATCH /v1/blocks/{id} がそのまま受け付ける形式
# (ブロックタイプをキーにした {"paragraph": {"rich_text": [...]}} 等)のJSONファイル。
# 標準出力に更新後のブロックオブジェクトJSONをそのまま出力する。
set -eu
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/_common.sh"

block_id="${1:?Usage: update_block.sh <block_id> <request_body.json>}"
body_file="${2:?Usage: update_block.sh <block_id> <request_body.json>}"
if [ ! -f "$body_file" ]; then
  echo "Error: request body file not found: $body_file" >&2
  exit 1
fi

notion_curl PATCH "/blocks/$block_id" "$body_file"
