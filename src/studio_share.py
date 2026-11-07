"""Short-lived, standalone product sharing pages."""
import json
import re
import secrets
import sqlite3
import time
from contextlib import closing
from html import escape

import streamlit as st

from .storage import default_database_path
from .studio_model import StudioError, prepare_image
from .studio_security import decode_photo

SHARE_LIFETIME = 24 * 60 * 60
MAX_ACTIVE_SHARES = 600


def _share_photo(value):
    data = decode_photo(value)
    return prepare_image(data, max_edge=1024) if data else ""


def save_share(product, title, body):
    key = secrets.token_urlsafe(18)
    fields = ("f0", "f1", "f2", "f3", "photo", "product_url", "contact_url")
    snapshot = {field: product.get(field, "") for field in fields}
    snapshot.update(title=title, body=body, photo=_share_photo(snapshot["photo"]), photo_clean=True)
    now = int(time.time())
    with closing(sqlite3.connect(default_database_path())) as db, db:
        db.execute("""CREATE TABLE IF NOT EXISTS studio_share_pages (
            key TEXT PRIMARY KEY, snapshot TEXT NOT NULL, expires_at INTEGER NOT NULL)""")
        db.execute("DELETE FROM studio_share_pages WHERE expires_at <= ?", (now,))
        if db.execute("SELECT COUNT(*) FROM studio_share_pages").fetchone()[0] >= MAX_ACTIVE_SHARES:
            raise StudioError("分享页暂时达到容量上限，请稍后再试。")
        db.execute("INSERT INTO studio_share_pages VALUES (?, ?, ?)",
                   (key, json.dumps(snapshot, ensure_ascii=False), now + SHARE_LIFETIME))
    return key


def render_share(key):
    row = None
    path = default_database_path()
    if re.fullmatch(r"[A-Za-z0-9_-]{24}", key) and path.is_file():
        with closing(sqlite3.connect(path)) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='studio_share_pages' AND type='table'").fetchone():
                row = db.execute("SELECT snapshot FROM studio_share_pages WHERE key=? AND expires_at > ?",
                                 (key, int(time.time()))).fetchone()
    if not row:
        st.info("商品分享页不存在或已失效，请向商家索取最新链接。")
        return
    snapshot = json.loads(row[0])
    if not snapshot.pop("photo_clean", False):
        try:
            snapshot["photo"] = _share_photo(snapshot["photo"])
        except StudioError:
            snapshot["photo"] = ""
    product = {field: escape(value, quote=True) for field, value in snapshot.items()}
    photo = product["photo"]
    picture = (f'<img class="share-photo" src="{photo}" alt="{product["f0"]}的商品配图">' if photo else "")
    facts = "".join(f'<div><dt>{label}</dt><dd>{product[field]}</dd></div>'
                    for field, label in (("f1", "产地"), ("f2", "规格"), ("f3", "价格")) if product[field])
    actions = "".join(f'<a href="{product[field]}" target="_blank" rel="noopener noreferrer">{label}</a>'
                      for field, label in (("product_url", "查看商品"), ("contact_url", "联系商家")) if product[field])
    st.html(f"""<style>
    [data-testid="stHeader"], [data-testid="stSidebar"] {{display:none}}
    [data-testid="stMainBlockContainer"] {{max-width:760px;padding:28px 20px 56px}}
    .share-page {{color:#1d1d1f;font-family:system-ui,sans-serif}}
    .share-brand {{display:flex;justify-content:space-between;gap:16px;border-bottom:1px solid #dedee3;padding:0 0 14px;margin-bottom:28px;font-size:14px}}
    .share-brand span,.share-name,.share-facts dt {{color:#62626a}}
    .share-page h1 {{font-size:clamp(32px,6vw,50px);line-height:1.15;letter-spacing:-.035em;padding:0;margin:0 0 12px}}
    .share-name {{font-size:16px;margin-bottom:18px}}
    .share-photo {{display:block;width:100%;max-height:420px;object-fit:contain;background:#f5f5f7;border-radius:14px;margin:20px 0}}
    .share-body {{white-space:pre-wrap;line-height:1.8;overflow-wrap:anywhere}}
    .share-facts {{display:flex;flex-wrap:wrap;gap:10px 30px;padding:14px 0;border-top:1px solid #dedee3}}
    .share-facts dt {{font-size:13px}}
    .share-facts dd {{margin:3px 0 0}}
    .share-actions {{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}}
    .share-actions a {{display:inline-flex;align-items:center;min-height:44px;padding:0 18px;border-radius:22px;background:#0066cc;color:white;text-decoration:none}}
    </style>
    <article class="share-page">
      <header class="share-brand"><strong>齐鲁卖点</strong><span>商品分享</span></header>
      <h1>{product['title'] or product['f0']}</h1>
      <p class="share-name">{product['f0']}</p>
      {picture}
      <p class="share-body">{product['body']}</p>
      {f'<dl class="share-facts">{facts}</dl>' if facts else ''}
      {f'<nav class="share-actions" aria-label="商品入口">{actions}</nav>' if actions else ''}
    </article>""")
