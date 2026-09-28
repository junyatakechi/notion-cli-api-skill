#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
"""notion-cli-api-skill: データソースクエリ (POST /v1/data_sources/{id}/query、ページネーション対応)

Usage: uv run query_data_source.py <data_source_id> [request_body.json]

request_body.json は filter/sorts/page_size 等を含むJSONファイル(省略可、省略時は
フィルタなしで全件取得)。標準出力に、全ページ分をマージした結果をJSON配列で出力する。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notion_client import NotionError, notion_post_paginate  # noqa: E402


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit("Usage: query_data_source.py <data_source_id> [request_body.json]")
    data_source_id = sys.argv[1]
    body = {}
    if len(sys.argv) == 3:
        with open(sys.argv[2], encoding="utf-8") as f:
            body = json.load(f)
    try:
        results = notion_post_paginate(f"/data_sources/{data_source_id}/query", body)
    except NotionError as e:
        sys.exit(f"Error: {e}")
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
