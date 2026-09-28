#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""モデル文書の「値の表」を読み出す機構。

Notionページの本文を歩き、**直前の見出し**をキーにして表を返す。判断は一切持たない
(どの表がどのモデルの写しになるか・値の型は、Domain層の一覧と生成器が決める)。

    from notion_tables import read_page_tables, page_title, page_version
    info = read_page_tables(page_id)
    info["title"], info["version"], info["tables"][i]["heading"|"columns"|"rows"]
"""
import re

from notion_blocks import rich_text_to_plain
from notion_client import get_block_children, get_page

HEADING_TYPES = ("heading_1", "heading_2", "heading_3")
_VERSION_RE = re.compile(r"_v(\d+\.\d+\.\d+)\s*$")


def page_title(page):
    for prop in (page.get("properties") or {}).values():
        if prop.get("type") == "title":
            return rich_text_to_plain(prop.get("title")).strip()
    return ""


def page_version(title):
    """題名末尾の `_vX.Y.Z` を返す。無ければ None(版が読めないことを黙って埋めない)。"""
    m = _VERSION_RE.search(title or "")
    return m.group(1) if m else None


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").replace("　", " ")).strip()


def tables_from_blocks(blocks):
    """取得済みのブロック列から表を集める。見出しは表の直前(同じ深さでなくてもよい)のもの。"""
    tables = []
    state = {"heading": None}

    def walk(items):
        for b in items:
            t = b.get("type")
            if t in HEADING_TYPES:
                state["heading"] = _norm(rich_text_to_plain(b[t].get("rich_text")))
                continue
            if t == "table":
                rows = [[_norm(rich_text_to_plain(c)) for c in r["table_row"]["cells"]]
                        for r in b.get("children", []) if r.get("type") == "table_row"]
                if rows:
                    tables.append({"heading": state["heading"], "block_id": b.get("id"),
                                   "columns": rows[0], "rows": rows[1:]})
                continue
            if b.get("children"):
                walk(b["children"])

    walk(blocks)
    return tables


def read_page_tables(page_id):
    page = get_page(page_id)
    title = page_title(page)
    blocks = get_block_children(page_id, recursive=True)
    return {"page_id": page_id, "title": title, "version": page_version(title),
            "last_edited": page.get("last_edited_time"), "tables": tables_from_blocks(blocks)}
