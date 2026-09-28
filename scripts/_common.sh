#!/bin/sh
# notion-cli-api-skill: bashスクリプト共通処理(トークン読み込み・curl呼び出し)
set -eu

# 秘密情報はスキル外の $HOME/.claude-skills-env/<skill_name>.env に置く規約。
# このスキルのskill_nameは notion-cli-api-skill なので notion-cli-api-skill.env が正。
NOTION_ENV_FILE="${NOTION_ENV_FILE:-$HOME/.claude-skills-env/notion-cli-api-skill.env}"
NOTION_VERSION="2025-09-03"
NOTION_API_BASE="https://api.notion.com/v1"

if [ ! -f "$NOTION_ENV_FILE" ]; then
  echo "Error: Notion token file not found: $NOTION_ENV_FILE" >&2
  echo "See the セットアップ section of ../README.md to create it." >&2
  exit 1
fi

# shellcheck disable=SC1090
. "$NOTION_ENV_FILE"

if [ -z "${NOTION_TOKEN:-}" ]; then
  echo "Error: NOTION_TOKEN is not set in $NOTION_ENV_FILE" >&2
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
