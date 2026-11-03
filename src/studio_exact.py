"""Connect the approved HTML workspace to the existing studio services."""
import base64
from html import escape
from pathlib import Path

import streamlit as st
from streamlit.components.v1 import declare_component
from streamlit.errors import StreamlitSecretNotFoundError

from .constants import is_public_deployment
from .storage import ReviewStore
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


EXACT_RELEASE = 3


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


def _run_action(event, result):
    action = event.get("action")
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

    facts = st.session_state.get("exact_facts")
    if not facts:
        raise StudioError("请先录入并保存商品。")
    if action == "generate":
        model = _model()
        audience = event.get("audience", "家庭日常购买")[:80]
        tone = event.get("tone", "自然清楚")[:80]
        items = model.generate(facts, audience, CHANNELS, tone)
        bundle = new_bundle(facts, items, model=model.name, audience=audience, tone=tone)
        persist(bundle)
        st.session_state["exact_bundle"] = bundle
        result.update(items=items, message="文案已生成。")
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
        if action == "review":
            session = send_to_xray(bundle)
            ReviewStore().save_review(session, action="studio_handoff", details={"studio_id": bundle["id"]})
            st.session_state["review"] = session
            st.session_state["workspace_next"] = "传播 X 光审核"


def render_exact_studio():
    component = declare_component("approved_studio", path=Path(__file__).with_name("studio_frontend"))
    state = st.session_state.get("exact_result") or {}
    product = st.session_state.get("exact_product")
    bundle = st.session_state.get("exact_bundle")
    event = component(state=state, product=product,
                      items=bundle["items"] if bundle else None,
                      atlas=_atlas_svg(product.get("f1", "")) if product else None,
                      key="approved-studio", default=None)
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
