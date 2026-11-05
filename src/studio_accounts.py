"""Account login and private works storage."""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
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
                PRIMARY KEY(owner, work_id))""")
            yield db
    finally:
        db.close()


def _digest(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)


def _create(db, username, password, role):
    if not re.fullmatch(r"[\w.-]{3,32}", username) or not 10 <= len(password) <= 128:
        raise ValueError("用户名需为 3–32 个字母、数字或下划线等字符，密码需为 10–128 个字符。")
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


def render_login():
    username, password = _admin_config()
    with database() as db:
        if password and not db.execute("SELECT 1 FROM studio_users WHERE username=?", (username,)).fetchone():
            try:
                _create(db, username, password, "admin")
            except (ValueError, sqlite3.IntegrityError):
                st.warning("管理员初始化未完成，请检查服务器配置。")
    st.title("齐鲁卖点")
    login, register = st.tabs(["登录", "新建用户"])
    with login, st.form("studio_login"):
        name = st.text_input("用户名", max_chars=32)
        password = st.text_input("密码", type="password", max_chars=128)
        if st.form_submit_button("登录", type="primary"):
            account = authenticate(name.strip(), password)
            if account:
                st.session_state["studio_account"] = account
                st.rerun()
            st.error("用户名或密码有误，或尝试过多，请稍后再试。")
    with register, st.form("studio_register", clear_on_submit=True):
        name = st.text_input("新用户名", max_chars=32)
        password = st.text_input("新密码", type="password", max_chars=128)
        confirm = st.text_input("确认新密码", type="password", max_chars=128)
        if st.form_submit_button("创建用户"):
            try:
                if password != confirm:
                    raise ValueError("两次密码输入不一致。")
                if name.strip().casefold() in {"admin", username.casefold()}:
                    raise ValueError("该用户名不可用于注册。")
                with database() as db:
                    _create(db, name.strip(), password, "merchant")
                st.success("账号已创建，请切换到登录。")
            except ValueError as error:
                st.error(str(error))
            except sqlite3.IntegrityError:
                st.error("这个用户名已被使用。")


def save_work(owner, product, bundle):
    with database() as db:
        db.execute("""INSERT INTO private_works VALUES (?,?,?,?,?)
                   ON CONFLICT(owner,work_id) DO UPDATE SET
                   name=excluded.name,updated=excluded.updated,payload=excluded.payload""",
                   (owner, bundle["id"], product["f0"], int(time.time()),
                    json.dumps({"product": product, "bundle": bundle}, ensure_ascii=False)))


def list_works(owner):
    with database() as db:
        return [dict(row) for row in db.execute(
            "SELECT work_id,name,updated FROM private_works WHERE owner=? ORDER BY updated DESC", (owner,))]


def load_work(owner, work_id):
    with database() as db:
        row = db.execute("SELECT payload FROM private_works WHERE owner=? AND work_id=?",
                         (owner, work_id)).fetchone()
        return json.loads(row["payload"]) if row else None


def admin_totals():
    with database() as db:
        return (db.execute("SELECT count(*) FROM studio_users").fetchone()[0],
                db.execute("SELECT count(*) FROM private_works").fetchone()[0])
