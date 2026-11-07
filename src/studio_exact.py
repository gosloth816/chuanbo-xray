"""Connect the approved HTML workspace to the existing studio services."""
import base64
import secrets
import sqlite3
import re
from io import BytesIO
from copy import deepcopy
from uuid import uuid4
from html import escape
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit

import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from streamlit.components.v1 import declare_component
from streamlit.errors import StreamlitSecretNotFoundError

from .constants import is_public_deployment
from .storage import ReviewStore
from .studio import new_bundle, persist, save_edit, send_to_xray
from .studio_accounts import _admin_config, _create, authenticate, database, list_works, load_work, save_work
from .studio_model import CHANNELS, StudioError, StudioModel
from .studio_security import bounded_text, decode_photo, reserve_request
from .studio_share import save_share
from .studio_workspace import _match_origin, _origin_atlas


def _atlas_svg(origin):
    atlases = _origin_atlas()
    province, city = _match_origin(origin, atlases)
    if not province:
        return ""
    atlas = atlases[province]
    region = escape(city or province, quote=True)
    svg = atlas["svg"].replace(f'class="city" data-region="{region}"',
                               f'class="city selected" data-region="{region}"')
    x, y = atlas["cities"].get(city, (125, 85))
    label = escape(city.removesuffix("市") if city else province)
    return svg.replace('<text id="atlas-city-label"></text>',
                       f'<text x="{x}" y="{y}">{label}</text>')


EXACT_RELEASE = 15


class _StudioWithSafeTitles(StudioModel):
    def call(self, instruction, data, image=None, **options):
        result = super().call(instruction, data, image, **options)
        facts = data.get("confirmed_facts")
        items = result.get("items")
        if facts and isinstance(items, list):
            product_name = next((row["value"] for row in facts.values()
                                 if row["field"] == "产品名称"), "")
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = item.get("title")
                if product_name and (not isinstance(title, str) or not title.strip()):
                    item["title"] = product_name
        return result


def _model():
    try:
        settings = dict(st.secrets)
    except StreamlitSecretNotFoundError:
        settings = {}
    return _StudioWithSafeTitles(settings=settings, public=is_public_deployment())


def _product_links(product):
    links = {}
    for key, label in (("product_url", "商品链接"), ("contact_url", "客服链接")):
        value = product.get(key, "")
        if not isinstance(value, str):
            raise StudioError(f"请填写完整有效的 HTTPS{label}。")
        value = value.strip()
        if value:
            try:
                parsed = urlsplit(value)
                port = parsed.port
                valid = (parsed.scheme == "https" and parsed.hostname and parsed.username is None
                         and "\\" not in value and not any(char.isspace() or ord(char) < 32 for char in value)
                         and len(value) <= 2048 and (port is None or port > 0))
            except ValueError:
                valid = False
            if not valid:
                raise StudioError(f"请填写完整有效的 HTTPS{label}。")
        links[key] = value
    return links


def _challenge():
    if ("studio_captcha" not in st.session_state
            or monotonic() - st.session_state.get("studio_captcha_at", 0) >= 300):
        alphabet = "ACDEFGHJKLMNPRTUVWXY2346789"
        code = "".join(secrets.choice(alphabet) for _ in range(5))
        image = Image.new("RGB", (160, 50), "#edf3fa")
        draw = ImageDraw.Draw(image)
        for _ in range(42):
            x, y = secrets.randbelow(160), secrets.randbelow(50)
            draw.ellipse((x, y, x + 2, y + 2), fill="#b8cbe0")
        font = ImageFont.load_default(size=29)
        for index, character in enumerate(code):
            draw.text((16 + index * 27, 7 + secrets.randbelow(7)),
                      character, font=font, fill="#244466")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        st.session_state["studio_captcha"] = (code, base64.b64encode(buffer.getvalue()).decode())
        st.session_state["studio_captcha_at"] = monotonic()
    return st.session_state["studio_captcha"]


def _account_action(action, event, result):
    if action == "logout":
        for key in ("studio_account", "studio_captcha", "studio_captcha_at", "exact_product", "exact_facts",
                    "exact_bundle", "review", "review_desk_response", "review_desk_last"):
            st.session_state.pop(key, None)
        result["message"] = "已退出登录。"
        return
    if st.session_state.get("studio_account"):
        raise StudioError("请先退出当前账号，再切换账号。")
    reserve_request("account")
    code, _ = _challenge()
    st.session_state.pop("studio_captcha", None)
    captcha = bounded_text(event.get("captcha", ""), 6).upper()
    if not secrets.compare_digest(captcha.encode(), code.encode()):
        raise StudioError("验证码不正确，请再试一次。")
    name = bounded_text(event.get("username", ""), 33)
    password = event.get("password", "")
    if not isinstance(password, str) or len(password) > 128:
        raise StudioError("请检查账号和密码格式。")
    admin_name, admin_password = _admin_config()
    if action == "register":
        if name.casefold() in {"admin", admin_name.casefold()}:
            raise StudioError("该用户名不可用于注册。")
        try:
            with database() as db:
                _create(db, name, password, "merchant")
        except sqlite3.IntegrityError as exc:
            raise StudioError("该用户名已存在。") from exc
        except ValueError as exc:
            raise StudioError(str(exc)) from exc
        result["registered"] = True
        result["message"] = "账号已创建，可以登录了。"
        return
    if admin_password and name == admin_name:
        with database() as db:
            if not db.execute("SELECT 1 FROM studio_users WHERE username=?", (name,)).fetchone():
                try:
                    _create(db, name, admin_password, "admin")
                except sqlite3.IntegrityError:
                    pass
    account = authenticate(name, password)
    if not account:
        raise StudioError("账号或密码有误，或尝试过多，请稍后再试。")
    st.session_state["studio_account"] = account
    result["signedIn"] = True
    result["message"] = "登录成功。"


def _restored_draft(restored, facts):
    items = restored.get("items") if isinstance(restored, dict) else None
    if (not isinstance(items, list) or len(items) != len(CHANNELS)
            or any(not isinstance(item, dict) or item.get("channel") not in CHANNELS for item in items)
            or {item["channel"] for item in items} != set(CHANNELS)):
        raise StudioError("这份历史文案格式有误，请重新录入商品。")
    clean = []
    for item in items:
        ids = item.get("fact_ids")
        clean.append({"channel": item["channel"], "title": bounded_text(item.get("title"), 6000),
                      "body": bounded_text(item.get("body"), 6000),
                      "fact_ids": [key for key in facts if isinstance(ids, list) and key in ids[:20]]})
    brief = restored.get("creative_brief")
    brief = brief if isinstance(brief, dict) else {}
    ids = brief.get("focus_fact_ids")
    bundle = new_bundle(facts, clean, model=bounded_text(restored.get("model", ""), 120),
                        audience=bounded_text(restored.get("audience", ""), 80),
                        tone=bounded_text(restored.get("tone", ""), 80),
                        creative_brief={"creative_direction": bounded_text(brief.get("creative_direction", ""), 600),
                                        "focus_fact_ids": [key for key in facts if isinstance(ids, list) and key in ids[:20]]})
    bundle["origin"] = "从当前浏览器恢复的历史文稿"
    return bundle


def _run_action(event, result):
    action = event.get("action")
    if action == "preview_share":
        if event.get("confirmed") is not True:
            raise StudioError("请先确认公开这份商品内容。")
        product = st.session_state.get("exact_product")
        title, body = (bounded_text(event.get(key), 6000) for key in ("title", "body"))
        if not product or not (title or body):
            raise StudioError("请先保存商品，并填写朋友圈文案。")
        reserve_request("share")
        result["share_key"] = save_share(product, title, body)
        return
    if action == "refresh_captcha":
        reserve_request("captcha")
        st.session_state.pop("studio_captcha", None)
        return
    if action in {"login", "register", "logout"}:
        _account_action(action, event, result)
        return
    owner = (st.session_state.get("studio_account") or {}).get("username")
    saved_work = None
    if action == "restore_account_product":
        work_id = bounded_text(event.get("work_id"), 65)
        saved_work = load_work(owner, work_id) if owner and len(work_id) <= 64 else None
        if not saved_work:
            raise StudioError("没有找到这件账号作品。")
        product = saved_work["product"]
        event = {"product": product, "photo": product.get("photo", ""), "history_id": work_id}
        action = "restore_product"
    if action == "open_review":
        st.session_state["workspace_next"] = "传播 X 光审核"
        return
    if action in {"product", "restore_product", "extract"}:
        product = event["product"]
        if not isinstance(product, dict):
            raise StudioError("请检查商品资料格式。")
        if action == "extract":
            if event.get("consent") is not True:
                raise StudioError("请先确认允许发送图片和介绍给模型。")
            reserve_request("model")
            image = decode_photo(event.get("photo", ""))
            fields = {"产品名称": "f0", "产地": "f1", "规格": "f2", "价格": "f3", "特点": "f4"}
            result["extracted"] = {
                fields[row["field"]]: row["value"]
                for row in _model().extract(bounded_text(product.get("intro", ""), 600), image)
                if row["field"] in fields
            }
            result["message"] = "识图完成，请核对商品资料后保存。"
        else:
            reserve_request("product")
            fields = ["产品名称", "产地", "规格", "价格", "特点"]
            values = {f"f{index}": bounded_text(product.get(f"f{index}", ""), 100)
                      for index in range(len(fields))}
            facts = {
                f"F{index + 1}": {"field": field, "value": value, "source": "商家人工确认"}
                for index, field in enumerate(fields)
                if (value := values[f"f{index}"])
            }
            if "F1" not in facts:
                raise StudioError("请填写商品名称。")
            photo = event.get("photo", "")
            decode_photo(photo)
            history_id = event.get("history_id") if action == "restore_product" else None
            history_id = history_id or uuid4().hex
            if not isinstance(history_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", history_id):
                raise StudioError("这份商品记录编号无效。")
            previous = st.session_state.get("exact_product", {})
            same_product = (previous.get("history_id") == history_id if history_id
                            else previous.get("f0") == facts["F1"]["value"])
            previous_photo = previous.get("photo", "") if same_product else ""
            restored = event.get("draft") if action == "restore_product" else None
            bundle = saved_work["bundle"] if saved_work else None
            if restored:
                bundle = _restored_draft(restored, facts)
            confirmed = {**values, **_product_links(product), "photo": photo or previous_photo,
                         "history_id": history_id, "intro": bounded_text(product.get("intro", ""), 600)}
            if owner and action == "product":
                save_work(owner, confirmed, None)
            st.session_state["exact_product"] = confirmed
            st.session_state["exact_facts"] = facts
            st.session_state.pop("exact_bundle", None)
            result["atlas"] = _atlas_svg(facts.get("F2", {}).get("value", ""))
            result.update(resetDraft=True, productName=facts["F1"]["value"],
                          intro=confirmed["intro"], message="商品资料已确认。")
            if bundle:
                st.session_state["exact_bundle"] = bundle
                result.update(items=bundle["items"], message="已打开历史商品和文案。")
        return

    facts = st.session_state.get("exact_facts")
    if not facts:
        raise StudioError("请先录入并保存商品。")
    if action == "generate":
        if event.get("consent") is not True:
            raise StudioError("请先确认允许发送商品资料给模型。")
        reserve_request("model")
        model = _model()
        audience = bounded_text(event.get("audience", "家庭日常购买"), 80)
        tone = bounded_text(event.get("tone", "自然清楚"), 80)
        direction = bounded_text(event.get("direction", ""), 600)
        requested_focus = event.get("focus", [])
        focus = [fid for fid in ("F2", "F3", "F4", "F5")
                 if isinstance(requested_focus, list) and fid in requested_focus[:20] and fid in facts]
        items = model.generate(facts, audience, CHANNELS, tone,
                               creative_direction=direction, focus_ids=focus)
        bundle = new_bundle(facts, items, model=model.name, audience=audience, tone=tone,
                            creative_brief={"creative_direction": direction, "focus_fact_ids": focus})
        if owner:
            save_work(owner, st.session_state["exact_product"], bundle)
        else:
            persist(bundle)
        st.session_state["exact_bundle"] = bundle
        result.update(items=items, message="文案已生成。")
    elif action in {"save", "review"}:
        reserve_request("review")
        bundle = st.session_state.get("exact_bundle")
        if not bundle:
            raise StudioError("请先为当前商品生成文案。")
        bundle = deepcopy(bundle)
        edits = event.get("edits", {})
        if not isinstance(edits, dict):
            raise StudioError("请检查文稿格式后重试。")
        for index, item in enumerate(bundle["items"]):
            edit = edits.get(item["channel"])
            if isinstance(edit, dict):
                title, body = (bounded_text(edit.get(key, ""), 6000) for key in ("title", "body"))
                if title and body and (title, body) != (item["title"], item["body"]):
                    save_edit(bundle, index, title, body)
        if owner:
            save_work(owner, st.session_state["exact_product"], bundle)
        else:
            persist(bundle)
        st.session_state["exact_bundle"] = bundle
        result["message"] = "文稿已保存。"
        result["saved"] = action == "save"
        if action == "review":
            session = send_to_xray(bundle)
            ReviewStore().save_review(session, action="studio_handoff", details={"studio_id": bundle["id"]})
            st.session_state["review"] = session
            st.session_state["workspace_next"] = "传播 X 光审核"


def render_exact_studio():
    component = declare_component("approved_studio_v15", path=Path(__file__).with_name("studio_frontend"))
    state = st.session_state.get("exact_result") or {}
    product = st.session_state.get("exact_product")
    bundle = st.session_state.get("exact_bundle")
    account = st.session_state.get("studio_account")
    event = component(state=state, product=product, account=account,
                      captcha="" if account else "data:image/png;base64," + _challenge()[1],
                      account_works=list_works(account["username"]) if account else [],
                      temporary_accounts=is_public_deployment(),
                      items=bundle["items"] if bundle else None,
                      draft={key: bundle[key] for key in ("items", "model", "audience", "tone", "creative_brief")} if bundle else None,
                      atlas=_atlas_svg(product.get("f1", "")) if product else None,
                      key="approved-studio", default=None)
    if not isinstance(event, dict) or not isinstance(event.get("id"), str) or not 0 < len(event["id"]) <= 64:
        return
    if event["id"] == st.session_state.get("exact_last_event"):
        return
    st.session_state["exact_last_event"] = event["id"]
    result = {"id": event["id"], "action": event.get("action")}
    try:
        _run_action(event, result)
    except StudioError as error:
        result["message"] = str(error)
    except sqlite3.Error:
        result["message"] = "暂时无法访问作品或账号存储，请稍后重试。"
    except (TypeError, ValueError, KeyError, IndexError):
        result["message"] = "这次提交的资料格式有误，请检查后重试。"
    st.session_state["exact_result"] = result
    st.rerun()
