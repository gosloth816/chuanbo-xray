import base64
import json
import sqlite3
from contextlib import closing
from io import BytesIO
from threading import Lock
from collections import deque
from zipfile import ZipFile

import pytest
from PIL import Image

from src import studio_exact, studio_security, studio_share
from src.parsing import DocumentParseError, parse_document_bytes
from src.studio_accounts import load_work
from src.studio_model import StudioError


@pytest.fixture
def state(monkeypatch, tmp_path):
    monkeypatch.setenv("XRAY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(studio_exact.st, "session_state", {})
    monkeypatch.setattr(studio_security, "is_public_deployment", lambda: False)
    return studio_exact.st.session_state


def test_product_limits_and_ownership(state):
    state["studio_account"] = {"username": "alice_1"}
    studio_exact._run_action({"action": "product", "product": {"f0": "a" * 300, "unexpected": "private"},
                              "history_id": "chosen-by-client"}, {})
    product = state["exact_product"]
    assert len(product["f0"]) == 100
    assert "unexpected" not in product
    assert product["history_id"] != "chosen-by-client"
    assert load_work("alice_1", product["history_id"])["product"] == product
    assert load_work("bob_1", product["history_id"]) is None
    with pytest.raises(StudioError, match="请先退出"):
        studio_exact._run_action({"action": "login"}, {})
    studio_exact._run_action({"action": "logout"}, {})
    assert "exact_product" not in state
    with pytest.raises(StudioError, match="没有找到"):
        studio_exact._run_action({"action": "restore_account_product", "work_id": product["history_id"]}, {})


@pytest.mark.parametrize("action", ["extract", "generate"])
def test_model_requires_explicit_confirmation(state, monkeypatch, action):
    state["exact_facts"] = {"F1": {"value": "苹果"}}
    monkeypatch.setattr(studio_exact, "_model", lambda: pytest.fail("must not contact the model"))
    with pytest.raises(StudioError, match="请先确认"):
        studio_exact._run_action({"action": action, "product": {"intro": "测试"}}, {})


def test_image_format_and_public_metadata(state, monkeypatch):
    buffer = BytesIO()
    exif = Image.Exif()
    exif[0x013B] = "private-artist"
    Image.new("RGB", (8, 8)).save(buffer, "JPEG", exif=exif)
    encoded = base64.b64encode(buffer.getvalue()).decode()
    with pytest.raises(StudioError, match="无法读取"):
        studio_security.decode_photo("data:image/png;base64," + encoded)
    photo = "data:image/jpeg;base64," + encoded
    key = studio_share.save_share({"f0": "测试商品", "photo": photo}, "<img onerror=alert(1)>", "测试正文")
    with closing(sqlite3.connect(studio_share.default_database_path())) as db:
        snapshot = json.loads(db.execute("SELECT snapshot FROM studio_share_pages WHERE key=?", (key,)).fetchone()[0])
    with Image.open(BytesIO(studio_security.decode_photo(snapshot["photo"]))) as clean:
        assert not clean.getexif()
    rendered = []
    monkeypatch.setattr(studio_share.st, "html", rendered.append)
    studio_share.render_share(key)
    assert "&lt;img onerror=alert(1)&gt;" in rendered[0]
    assert "<img onerror=" not in rendered[0]


def test_rate_limit_is_shared_between_sessions(state, monkeypatch):
    site = Lock(), {"model": deque()}
    monkeypatch.setattr(studio_security, "_site_limits", lambda: site)
    monkeypatch.setattr(studio_security, "is_public_deployment", lambda: True)
    monkeypatch.setattr(studio_security, "LIMITS", {"model": (60, 1, 2)})
    monkeypatch.setattr(studio_security, "monotonic", lambda: 10)
    studio_security.reserve_request("model")
    with pytest.raises(StudioError, match="过于频繁"):
        studio_security.reserve_request("model")
    state.clear()
    studio_security.reserve_request("model")
    state.clear()
    with pytest.raises(StudioError, match="过于频繁"):
        studio_security.reserve_request("model")
    monkeypatch.setattr(studio_security, "monotonic", lambda: 71)
    studio_security.reserve_request("model")


def test_docx_rejects_excessive_number_of_zip_entries():
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for index in range(2001):
            archive.writestr(f"part{index}", b"")
    with pytest.raises(DocumentParseError, match="解包后的内容过大"):
        parse_document_bytes(name="archive.docx", role="reference", data=buffer.getvalue())
