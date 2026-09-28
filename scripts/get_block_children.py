#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
"""notion-cli-api-skill: ブロック子取得 (GET /v1/blocks/{block_id}/children、再帰対応)

Usage: uv run get_block_children.py <block_id>

標準出力に、指定ブロック配下の子ブロックをJSON配列で出力する。
has_children=true のブロックは再帰的に子ブロックを取得し、各ブロックオブジェクトに
"children" キーとして埋め込む(子が無い場合はキー自体を付けない)。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notion_client import NotionError, get_block_children  # noqa: E402


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: get_block_children.py <block_id>")
    try:
        result = get_block_children(sys.argv[1])
    except NotionError as e:
        sys.exit(f"Error: {e}")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
