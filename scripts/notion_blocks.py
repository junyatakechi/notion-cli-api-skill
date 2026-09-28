"""notion-cli-api-skill: Notionブロック⇄テキストの相互変換ヘルパー(標準ライブラリのみ)。

Markdown→Notionブロック / Notionブロック→テキスト の機械的な変換だけを行い、
どんな本文を書くべきかの判断は持たない。Notionを読み書きする他のスキルから使う。
"""
import json
import re


def rich_text_to_plain(rich_text_list):
    return "".join(rt.get("plain_text", "") for rt in (rich_text_list or []))


def block_to_lines(block, depth=0):
    btype = block.get("type")
    data = block.get(btype, {}) if isinstance(block.get(btype), dict) else {}
    indent = "  " * depth
    lines = []
    if btype in ("heading_1", "heading_2", "heading_3"):
        level = {"heading_1": "#", "heading_2": "##", "heading_3": "###"}[btype]
        lines.append(f"{indent}{level} {rich_text_to_plain(data.get('rich_text'))}")
    elif btype == "bulleted_list_item":
        lines.append(f"{indent}- {rich_text_to_plain(data.get('rich_text'))}")
    elif btype == "numbered_list_item":
        lines.append(f"{indent}1. {rich_text_to_plain(data.get('rich_text'))}")
    elif btype == "to_do":
        checked = "x" if data.get("checked") else " "
        lines.append(f"{indent}- [{checked}] {rich_text_to_plain(data.get('rich_text'))}")
    elif btype == "quote":
        lines.append(f"{indent}> {rich_text_to_plain(data.get('rich_text'))}")
    elif btype == "code":
        lines.append(f"{indent}```{data.get('language', '')}")
        lines.append(rich_text_to_plain(data.get("rich_text")))
        lines.append("```")
    elif btype == "table_row":
        cells = data.get("cells", [])
        lines.append(indent + " | ".join(rich_text_to_plain(c) for c in cells))
    elif btype == "paragraph":
        text = rich_text_to_plain(data.get("rich_text"))
        if text:
            lines.append(f"{indent}{text}")
    else:
        text = rich_text_to_plain(data.get("rich_text")) if isinstance(data, dict) else ""
        if text:
            lines.append(f"{indent}{text}")

    for child in block.get("children", []):
        lines.extend(block_to_lines(child, depth + 1))
    return lines


def blocks_to_text(blocks):
    lines = []
    for b in blocks:
        lines.extend(block_to_lines(b))
    return "\n".join(lines)


def extract_section(blocks, heading_prefix):
    """トップレベルのblocks配列から、テキストがheading_prefixで始まるブロックを1つ探し、
    そのブロック自身(子ブロックを含む)を返す。見出し・箇条書き等のブロック種別は問わない
    (例: 「前提:」が見出しではなく箇条書き項目として存在し、条件・制約等が子ブロックと
    してぶら下がっている場合にも対応する)。"""
    for b in blocks:
        btype = b.get("type", "")
        data = b.get(btype, {}) if isinstance(b.get(btype), dict) else {}
        text = rich_text_to_plain(data.get("rich_text")) if isinstance(data, dict) else ""
        if text.strip().startswith(heading_prefix):
            return [b]
    return []


def property_value_to_str(prop):
    ptype = prop.get("type")
    if ptype == "number":
        return "" if prop.get("number") is None else str(prop["number"])
    if ptype == "select":
        sel = prop.get("select")
        return sel["name"] if sel else ""
    if ptype == "date":
        d = prop.get("date")
        if not d:
            return ""
        return d.get("start", "") + (f"~{d['end']}" if d.get("end") else "")
    if ptype == "rich_text":
        return rich_text_to_plain(prop.get("rich_text"))
    if ptype == "title":
        return rich_text_to_plain(prop.get("title"))
    if ptype == "multi_select":
        return ",".join(o["name"] for o in prop.get("multi_select", []))
    return json.dumps(prop, ensure_ascii=False)


def pages_to_markdown_table(pages, columns):
    if not pages:
        return "(該当データなし)"
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    rows = [header, sep]
    for p in pages:
        props = p.get("properties", {})
        row = [property_value_to_str(props.get(c, {})) for c in columns]
        rows.append("| " + " | ".join(row) + " |")
    return "\n".join(rows)


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def inline_rich_text(text, max_len=1900):
    """`**太字**` を解釈してrich_text配列に変換する。太字以外の記法は素通しする。"""
    text = (text or "")[:max_len]
    out = []
    for i, part in enumerate(_BOLD_RE.split(text)):
        if not part:
            continue
        out.append({
            "type": "text",
            "text": {"content": part},
            "annotations": {"bold": i % 2 == 1},
        })
    return out or [{"type": "text", "text": {"content": ""}}]


def heading_block(text, level=3):
    btype = {1: "heading_1", 2: "heading_2", 3: "heading_3"}[level]
    return {
        "object": "block",
        "type": btype,
        btype: {"rich_text": inline_rich_text(text)},
    }


def _simple_block(btype, text):
    return {"object": "block", "type": btype, btype: {"rich_text": inline_rich_text(text)}}


def text_to_paragraph_blocks(text, max_len=1900):
    text = text or "(データなし)"
    blocks = []
    for i in range(0, len(text), max_len):
        chunk = text[i:i + max_len]
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": inline_rich_text(chunk, max_len=max_len)},
        })
    return blocks


_TABLE_SEP_RE = re.compile(r"^\|?[\s:|-]+\|?$")


def _split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _try_parse_table(lines, i):
    """lines[i]がMarkdown表のヘッダー行で、lines[i+1]が区切り行(|---|---|)なら、
    (table_block, 表が終わった直後の行インデックス) を返す。表でなければNoneを返す。"""
    if i + 1 >= len(lines):
        return None
    header_line = lines[i].strip()
    sep_line = lines[i + 1].strip()
    if not (header_line.startswith("|") and _TABLE_SEP_RE.match(sep_line)):
        return None
    header_cells = _split_row(header_line)
    body_rows = []
    j = i + 2
    while j < len(lines) and lines[j].strip().startswith("|"):
        body_rows.append(_split_row(lines[j]))
        j += 1
    return table_block(header_cells, body_rows), j


def table_block(header_cells, body_rows):
    def row_block(cells):
        return {
            "object": "block",
            "type": "table_row",
            "table_row": {"cells": [inline_rich_text(c) for c in cells]},
        }

    width = len(header_cells)
    normalized_rows = [r + [""] * (width - len(r)) if len(r) < width else r[:width] for r in body_rows]
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True,
            "has_row_header": False,
            "children": [row_block(header_cells)] + [row_block(r) for r in normalized_rows],
        },
    }


_NUMBERED_RE = re.compile(r"^\s*\d+\.\s+(.*)$")


def markdown_to_blocks(markdown_text, max_blocks=None):
    """簡易Markdown→Notionブロック変換。見出し(#/##/###)・箇条書き(`- `)・
    番号付きリスト(`1. `)・引用(`> `)・`| ... |`形式の表をそれぞれ対応する
    Notionブロックに変換し、それ以外の行は段落にまとめる。`**太字**`はinlineで解釈する。

    max_blocksは既定でNone(切り捨てなし)。100ブロックを超える場合は呼び出し側が
    create_page(最初の100)とappend_block_children(残り)に分割すること。"""
    blocks = []
    buffer = []
    lines = markdown_text.split("\n")

    def flush():
        if buffer:
            text = "\n".join(buffer).strip("\n")
            if text.strip():
                blocks.extend(text_to_paragraph_blocks(text))
            buffer.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        numbered = _NUMBERED_RE.match(line)
        if line.startswith("### "):
            flush()
            blocks.append(heading_block(line[4:], level=3))
            i += 1
        elif line.startswith("## "):
            flush()
            blocks.append(heading_block(line[3:], level=2))
            i += 1
        elif line.startswith("# "):
            flush()
            blocks.append(heading_block(line[2:], level=1))
            i += 1
        elif stripped.startswith("- "):
            flush()
            blocks.append(_simple_block("bulleted_list_item", stripped[2:]))
            i += 1
        elif numbered:
            flush()
            blocks.append(_simple_block("numbered_list_item", numbered.group(1)))
            i += 1
        elif stripped.startswith("> "):
            flush()
            blocks.append(_simple_block("quote", stripped[2:]))
            i += 1
        elif stripped.startswith("|"):
            parsed = _try_parse_table(lines, i)
            if parsed:
                flush()
                block, next_i = parsed
                blocks.append(block)
                i = next_i
            else:
                buffer.append(line)
                i += 1
        else:
            buffer.append(line)
            i += 1
    flush()

    if max_blocks is not None and len(blocks) > max_blocks:
        blocks = blocks[:max_blocks]
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{
                "type": "text",
                "text": {"content": "(文字数上限のため以下省略)"},
            }]},
        })
    return blocks
