"""Connect the approved HTML workspace to the existing studio services."""
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import secrets
import sqlite3
import logging
from concurrent.futures import ThreadPoolExecutor
from html import escape
from pathlib import Path

import streamlit as st
from streamlit.components.v1 import declare_component
from streamlit.errors import StreamlitSecretNotFoundError

from .constants import is_public_deployment
from .storage import ReviewStore
from .studio_accounts import _admin_config, _create, authenticate, database, list_works, load_work, save_work
from .studio import new_bundle, persist, save_edit, send_to_xray
from .studio_model import CHANNELS, StudioError, StudioModel
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


EXACT_RELEASE = 11


@st.cache_resource
def _generation_pool():
    return ThreadPoolExecutor(max_workers=4, thread_name_prefix="studio-copy")


@st.fragment(run_every=1)
def _check_generation():
    job = st.session_state.get("exact_generation")
    if not job or not job["future"].done():
        return
    st.session_state.pop("exact_generation")
    if job["facts"] is not st.session_state.get("exact_facts"):
        st.rerun()
    result = {"action": "generate", "id": job["id"]}
    try:
        items = job["future"].result()
        bundle = new_bundle(job["facts"], items, model=job["model"], audience=job["audience"],
                            tone=job["tone"], creative_brief=job["brief"])
        st.session_state["exact_bundle"] = bundle
        result.update(items=items, message="文案已生成。")
    except StudioError as error:
        result["message"] = str(error)
    except Exception as error:
        logging.getLogger(__name__).error("Studio generation failed: %s", type(error).__name__)
        result["message"] = "生成服务遇到异常，请重试。商品资料已保留。"
    st.session_state["exact_result"] = result
    st.rerun()


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


def _challenge():
    if "studio_captcha" not in st.session_state:
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
    return st.session_state["studio_captcha"]


def _account_action(action, event, result):
    if action == "logout":
        st.session_state.clear()
        result["message"] = "已退出登录。"
        return
    code, _ = _challenge()
    st.session_state.pop("studio_captcha", None)
    if str(event.get("captcha", "")).strip().upper() != code:
        raise StudioError("验证码不正确，请再试一次。")
    name = str(event.get("username", "")).strip()
    password = str(event.get("password", ""))
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


def _run_action(event, result):
    action = event.get("action")
    if action == "refresh_captcha":
        st.session_state.pop("studio_captcha", None)
        return
    if action in {"login", "register", "logout"}:
        _account_action(action, event, result)
        return
    if action == "open_review":
        st.session_state["workspace_next"] = "传播 X 光审核"
        return
    if action in {"product", "extract"}:
        product = event["product"]
        if action == "extract":
            photo = event.get("photo", "")
            if len(photo) > 14 * 1024 * 1024:
                raise StudioError("图片请控制在 10 MB 以内。")
            image = base64.b64decode(photo.split(",", 1)[1], validate=True) if photo else None
            fields = {"产品名称": "f0", "产地": "f1", "规格": "f2", "价格": "f3", "特点": "f4"}
            result["extracted"] = {
                fields[row["field"]]: row["value"]
                for row in _model().extract(product.get("intro", "")[:600], image)
                if row["field"] in fields
            }
            result["message"] = "识图完成，请核对商品资料后保存。"
        else:
            fields = ["产品名称", "产地", "规格", "价格", "特点"]
            facts = {
                f"F{index + 1}": {"field": field, "value": value, "source": "商家人工确认"}
                for index, field in enumerate(fields)
                if (value := product.get(f"f{index}", "").strip()[:100])
            }
            if "F1" not in facts:
                raise StudioError("请填写商品名称。")
            photo = event.get("photo", "")
            if photo and (len(photo) > 14 * 1024 * 1024 or not photo.startswith(
                ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")
            )):
                raise StudioError("商品图片格式或大小不符合要求。")
            previous = st.session_state.get("exact_product", {})
            previous_photo = previous.get("photo", "") if previous.get("f0") == facts["F1"]["value"] else ""
            st.session_state["exact_product"] = {**product, "photo": photo or previous_photo}
            st.session_state["exact_facts"] = facts
            st.session_state.pop("exact_bundle", None)
            result["atlas"] = _atlas_svg(facts.get("F2", {}).get("value", ""))
            result.update(resetDraft=True, productName=facts["F1"]["value"],
                          intro=product.get("intro", "")[:600], message="商品资料已确认。")
        return

    owner = (st.session_state.get("studio_account") or {}).get("username")
    if action in {"save", "restore"} and not owner:
        result["loginRequired"] = True
        raise StudioError("登录后可以保存和打开作品。")
    if action == "restore":
        saved = load_work(owner, event["work_id"])
        if not saved:
            raise StudioError("找不到这件作品。")
        product, bundle = saved["product"], saved["bundle"]
        _run_action({"action": "product", "product": product, "photo": product.get("photo", "")}, result)
        st.session_state["exact_bundle"] = bundle
        result.update(items=bundle["items"], message="作品已打开。")
        return

    facts = st.session_state.get("exact_facts")
    if not facts:
        raise StudioError("请先录入并保存商品。")
    if action == "generate":
        if st.session_state.get("exact_generation"):
            raise StudioError("上一条生成请求还在处理，请稍候。")
        model = _model()
        if model.block_reason:
            raise StudioError(model.block_reason)
        audience = event.get("audience", "家庭日常购买")[:80]
        tone = event.get("tone", "自然清楚")[:80]
        direction = str(event.get("direction", "")).strip()[:600]
        requested_focus = event.get("focus", [])
        focus = [fid for fid in ("F2", "F3", "F4", "F5")
                 if isinstance(requested_focus, list) and fid in requested_focus and fid in facts]
        future = _generation_pool().submit(model.generate, facts, audience, CHANNELS, tone,
                                           creative_direction=direction, focus_ids=focus)
        st.session_state["exact_generation"] = {
            "id": event["id"], "future": future, "facts": facts, "model": model.name,
            "audience": audience, "tone": tone,
            "brief": {"creative_direction": direction, "focus_fact_ids": focus},
        }
        result["id"] = event["id"] + "-queued"
        result["pending"] = True
    elif action in {"save", "review"}:
        bundle = st.session_state.get("exact_bundle")
        if not bundle:
            raise StudioError("请先为当前商品生成文案。")
        edits = event.get("edits", {})
        for index, item in enumerate(bundle["items"]):
            edit = edits.get(item["channel"])
            if edit and edit["title"].strip() and edit["body"].strip():
                save_edit(bundle, index, edit["title"][:6000], edit["body"][:6000])
        persist(bundle)
        result["message"] = "文稿已保存。"
        if action == "save":
            save_work(owner, st.session_state["exact_product"], bundle)
            result["message"] = "已保存到我的作品。"
        if action == "review":
            session = send_to_xray(bundle)
            ReviewStore().save_review(session, action="studio_handoff", details={"studio_id": bundle["id"]})
            st.session_state["review"] = session
            st.session_state["workspace_next"] = "传播 X 光审核"


def render_exact_studio():
    component = declare_component("approved_studio_v11", path=Path(__file__).with_name("studio_frontend"))
    state = st.session_state.get("exact_result") or {}
    product = st.session_state.get("exact_product")
    bundle = st.session_state.get("exact_bundle")
    account = st.session_state.get("studio_account")
    _, captcha_image = _challenge()
    event = component(state=state, product=product, account=account,
                      temporary_storage=is_public_deployment(),
                      captcha="data:image/png;base64," + captcha_image,
                      works=list_works(account["username"]) if account else [],
                      items=bundle["items"] if bundle else None,
                      atlas=_atlas_svg(product.get("f1", "")) if product else None,
                      key="approved-studio", default=None)
    if st.session_state.get("exact_generation"):
        _check_generation()
    if not isinstance(event, dict) or not event.get("id"):
        return
    if event["id"] == st.session_state.get("exact_last_event"):
        return
    st.session_state["exact_last_event"] = event["id"]
    result = {"id": event["id"], "action": event.get("action")}
    try:
        _run_action(event, result)
    except StudioError as error:
        result["message"] = str(error)
    except (TypeError, ValueError, KeyError, IndexError):
        result["message"] = "这次提交的资料格式有误，请检查后重试。"
    st.session_state["exact_result"] = result
    st.rerun()
