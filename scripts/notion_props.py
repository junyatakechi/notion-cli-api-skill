"""notion-cli-api-skill: Notionプロパティ組み立てヘルパー(標準ライブラリのみ)。

Notionのプロパティ値の形へ機械的に詰め替えるだけで、どんな値を入れるべきかの判断は
持たない。通信は notion_client.py の担当。
"""


def title_prop(text):
    return {"title": [{"text": {"content": str(text)[:2000]}}]}


def rich_text_prop(text):
    if text is None:
        text = ""
    text = str(text)
    # Notionのrich_textは1ブロックあたり2000文字まで。超える場合は複数ブロックに分割する。
    chunks = [text[i:i + 2000] for i in range(0, len(text), 2000)] or [""]
    return {"rich_text": [{"text": {"content": c}} for c in chunks[:100]]}


def number_prop(value):
    return {"number": value if isinstance(value, (int, float)) else None}


def select_prop(name):
    if name is None:
        return {"select": None}
    return {"select": {"name": str(name)}}


def multi_select_prop(names):
    names = [n for n in (names or []) if n]
    return {"multi_select": [{"name": str(n)} for n in names]}


def date_prop(start_iso, end_iso=None):
    if start_iso is None:
        return {"date": None}
    d = {"start": start_iso}
    if end_iso:
        d["end"] = end_iso
    return {"date": d}


def relation_prop(page_ids):
    ids = [str(i) for i in (page_ids or []) if i]
    return {"relation": [{"id": i} for i in ids]}
