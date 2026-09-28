#!/bin/sh
# notion-cli-api-skill: ページ取得 (GET /v1/pages/{page_id})
#
# Usage: get_page.sh <page_id>
# 標準出力にNotionのページオブジェクトJSONをそのまま出力する。
set -eu
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/_common.sh"

page_id="${1:?Usage: get_page.sh <page_id>}"

notion_curl GET "/pages/$page_id"
