"""Account login and private works storage."""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
import unicodedata
from contextlib import contextmanager

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from .storage import default_database_path


@contextmanager
def database():
    db = sqlite3.connect(default_database_path(), timeout=10)
    db.row_factory = sqlite3.Row
    try:
        with db:
            db.execute("""CREATE TABLE IF NOT EXISTS studio_users (
                username TEXT PRIMARY KEY, salt BLOB NOT NULL, digest BLOB NOT NULL,
                role TEXT NOT NULL, failures INTEGER NOT NULL DEFAULT 0,
                retry_at INTEGER NOT NULL DEFAULT 0)""")
            db.execute("""CREATE TABLE IF NOT EXISTS private_works (
                owner TEXT NOT NULL, work_id TEXT NOT NULL, name TEXT NOT NULL,
                updated INTEGER NOT NULL, payload TEXT NOT NULL,
                origin TEXT NOT NULL DEFAULT '', has_draft INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY(owner, work_id))""")
            columns = {row["name"] for row in db.execute("PRAGMA table_info(private_works)")}
            if "origin" not in columns:
                db.execute("BEGIN IMMEDIATE")
                columns = {row["name"] for row in db.execute("PRAGMA table_info(private_works)")}
                if "origin" not in columns:
                    db.execute("ALTER TABLE private_works ADD COLUMN origin TEXT NOT NULL DEFAULT ''")
                    db.execute("ALTER TABLE private_works ADD COLUMN has_draft INTEGER NOT NULL DEFAULT 1")
                db.commit()
            yield db
    finally:
        db.close()


def _digest(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)


def _create(db, username, password, role):
    if role == "merchant":
        groups = (r"[A-Za-z]", r"[0-9]", r"_")
        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", username) or sum(
            bool(re.search(group, username)) for group in groups
        ) < 2:
            raise ValueError("账号须为 3–20 位，由字母、数字、下划线中的至少两类组成。")
        if not (8 <= len(password) <= 20 and re.search(r"[A-Za-z]", password)
                and re.search(r"[0-9]", password)
                and any(unicodedata.category(char)[0] in "PS" for char in password)
                and all(char.isprintable() and not char.isspace() for char in password)):
            raise ValueError("密码须为 8–20 位，包含字母、数字和特殊符号，且不能有空格。")
    elif not re.fullmatch(r"[\w.-]{3,32}", username) or not 10 <= len(password) <= 128:
        raise ValueError("管理员账号配置不符合要求。")
    salt = secrets.token_bytes(16)
    db.execute("INSERT INTO studio_users(username,salt,digest,role) VALUES (?,?,?,?)",
               (username, salt, _digest(password, salt), role))


def authenticate(username, password):
    if len(username) > 32 or len(password) > 128:
        return None
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        user = db.execute("SELECT * FROM studio_users WHERE username=?", (username,)).fetchone()
        now = int(time.time())
        if user and user["retry_at"] > now:
            return None
        digest = _digest(password, user["salt"] if user else bytes(16))
        if not user or not hmac.compare_digest(digest, user["digest"]):
            if user:
                failures = user["failures"] + 1
                db.execute("UPDATE studio_users SET failures=?, retry_at=? WHERE username=?",
                           (failures % 5, now + 60 if failures >= 5 else 0, username))
            return None
        db.execute("UPDATE studio_users SET failures=0,retry_at=0 WHERE username=?", (username,))
        return {"username": username, "role": user["role"]}


def _admin_config():
    try:
        return str(st.secrets.get("STUDIO_ADMIN_USERNAME", "admin")), str(st.secrets.get("STUDIO_ADMIN_PASSWORD", ""))
    except StreamlitSecretNotFoundError:
        return "admin", ""


def save_work(owner, product, bundle):
    with database() as db:
        db.execute("""INSERT INTO private_works(owner,work_id,name,updated,payload,origin,has_draft)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(owner,work_id) DO UPDATE SET
                   name=excluded.name,updated=excluded.updated,payload=excluded.payload,
                   origin=excluded.origin,has_draft=excluded.has_draft""",
                   (owner, product["history_id"], product["f0"], int(time.time()),
                    json.dumps({"product": product, "bundle": bundle}, ensure_ascii=False),
                    product.get("f1", ""), int(bundle is not None)))


def list_works(owner):
    with database() as db:
        return [dict(row) for row in db.execute(
            """SELECT work_id,name,updated,origin,has_draft FROM private_works
               WHERE owner=? ORDER BY updated DESC, rowid DESC""", (owner,))]


def load_work(owner, work_id):
    with database() as db:
        row = db.execute("SELECT payload FROM private_works WHERE owner=? AND work_id=?",
                         (owner, work_id)).fetchone()
        return json.loads(row["payload"]) if row else None
