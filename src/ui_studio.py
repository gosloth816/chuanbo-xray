"""齐鲁卖点：信息确认、分渠道创作、编辑和送审。"""
import hashlib
import json
from pathlib import Path

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from .constants import is_public_deployment
from .studio import fingerprint, new_bundle, persist, save_edit, export_markdown, audit_copy, send_to_xray
from .studio_model import CHANNELS, FIELDS, StudioModel, StudioError
from .storage import ReviewStore

ROOT = Path(__file__).resolve().parent.parent
DESCRIPTION = "演示苹果，山东产，红色果皮，5斤一箱，每箱39元。全部为合成设定。"


def _load_demo():
    data = json.loads((ROOT / "data/studio/demo.json").read_text(encoding="utf-8"))
    st.session_state["product_description"] = DESCRIPTION
    st.session_state["upload_nonce"] = st.session_state.get("upload_nonce", 0) + 1
    st.session_state["studio_signature"] = fingerprint(DESCRIPTION)
    for field in FIELDS:
        st.session_state["product_" + field] = next((v["value"] for v in data["facts"].values() if v["field"] == field), "")
    st.session_state["confirmed_facts"] = data["facts"]
    st.session_state["studio_bundle"] = new_bundle(data["facts"], data["items"], model="未调用模型", audience="家庭日常购买", tone="自然清楚", synthetic=True)
    for key in list(st.session_state):
        if key.startswith("draft_title_") or key.startswith("draft_body_"):
            del st.session_state[key]


def _model_settings():
    try:
        try:
            settings = dict(st.secrets)
        except StreamlitSecretNotFoundError:
            settings = {}
        model = StudioModel(settings=settings, public=is_public_deployment())
    except StudioError as exc:
        st.error(str(exc))
        return None
    with st.sidebar.expander("创作模型与数据去向"):
        st.write("模型：" + (model.name or "尚未配置"))
        if model.remote:
            st.caption("图片和介绍会发送到已配置的远程模型服务；调用可能产生服务费用。")
        else:
            st.caption("使用本机兼容模型服务。请确保服务已启动且模型支持图像输入。")
        st.caption("地址、模型名和密钥在服务器环境中配置，密钥不会写入创作记录。")
    if model.block_reason:
        st.info(model.block_reason + " 合成演示、手动填写及传播X光仍可使用。")
        return None
    return model


def render_studio():
    model = _model_settings()
    st.markdown("<div class='page-heading'><h1>齐鲁卖点</h1><p>从产品信息，到可编辑的宣传文案。</p></div>", unsafe_allow_html=True)
    st.button("加载合成演示", on_click=_load_demo, help="加载预写演示内容，不调用或冒充模型。")
    if is_public_deployment():
        st.info("公开网页中的上传材料会发送至托管服务器处理，请仅使用获授权的材料。")
    info, creative, drafts, check = st.tabs(["① 产品信息", "② 受众与渠道", "③ 文案工作台", "④ 发布前检查"])
    with info:
        left, right = st.columns([1, 1.1], gap="large")
        with left:
            st.markdown("### 介绍你的产品")
            photo = st.file_uploader("产品图片（可选，最多10MB）", type=["jpg", "jpeg", "png", "webp"], key=f"product_image_{st.session_state.get('upload_nonce', 0)}")
            description = st.text_area("简要介绍", key="product_description", height=130,
                placeholder="例如：产品名称、真实产地、规格、价格、包装特点。没有依据的信息可以不填。")
            synthetic_input = st.checkbox("这是合成或测试商品资料", key="synthetic_input")
            synthetic_input = synthetic_input or description == DESCRIPTION or "合成测试" in description or "合成设定" in description
            image = photo.getvalue() if photo else None
            sig = fingerprint(description, image)
            if sig != st.session_state.get("studio_signature"):
                st.session_state["studio_signature"] = sig
                st.session_state.pop("confirmed_facts", None)
                st.session_state.pop("studio_bundle", None)
                for field in FIELDS:
                    st.session_state.pop("product_" + field, None)
            permission = st.checkbox("允许将本次图片和介绍发送到配置的模型服务", value=False) if model and model.remote else True
            if st.button("AI识别产品信息", disabled=not model or not permission or not (description.strip() or image)):
                try:
                    with st.spinner("正在识别产品信息…"):
                        rows = model.extract(description, image)
                    for field in FIELDS:
                        st.session_state["product_" + field] = next((r["value"] for r in rows if r["field"] == field), "")
                    st.session_state.pop("confirmed_facts", None)
                    st.session_state.pop("studio_bundle", None)
                    st.session_state["recognition_message"] = "模型提出的信息已填入右侧，请逐项检查后保存。"
                    st.rerun()
                except StudioError as exc:
                    st.error(str(exc))
            st.caption("照片不能证明甜度、认证或健康功效。也可以跳过识别，直接手动填写右侧信息。")
            if photo:
                st.image(image, caption="本次上传图片", width="stretch")
            elif description == DESCRIPTION:
                st.image(str(ROOT / "data/studio/apple.svg"), width="stretch")
        with right:
            st.markdown("### 确认产品事实")
            if st.session_state.get("recognition_message"):
                st.info(st.session_state.pop("recognition_message"))
            current = {}
            for index, field in enumerate(FIELDS, 1):
                value = st.text_input(field, key="product_" + field, placeholder="不确定请留空")
                if value.strip():
                    current[f"F{index}"] = {"field": field, "value": value.strip(), "source": "商家人工确认"}
            confirmed = st.session_state.get("confirmed_facts")
            # 比较字段值；修改已确认事实后，旧稿仍保留但不能继续生成或送审。
            same = lambda a, b: {k: (v["field"], v["value"]) for k, v in (a or {}).items()} == {k: (v["field"], v["value"]) for k, v in (b or {}).items()}
            current_valid = bool(confirmed) and same(current, confirmed)
            if confirmed and not current_valid:
                st.warning("产品信息已变化，请重新确认；旧文案需要重新生成。")
            if st.button("确认并保存产品信息", type="primary"):
                if not current.get("F1"):
                    st.error("请至少填写产品名称。")
                else:
                    if not same(current, confirmed):
                        st.session_state.pop("studio_bundle", None)
                    st.session_state["confirmed_facts"] = current
                    st.rerun()
            if current_valid:
                st.caption("已确认。下一步打开“② 受众与渠道”。")
    with creative:
        st.markdown("### 这次，想对谁说？")
        audience = st.selectbox("目标受众", ["家庭日常购买", "年轻上班族", "节日送礼", "社区团购"])
        channels = st.multiselect("发布渠道", CHANNELS, default=CHANNELS)
        tone = st.selectbox("表达风格", ["自然清楚", "简短直接", "温暖生活化"])
        st.caption("模型只使用已确认信息。不同渠道分别创作，不自动补充价格、认证或效果承诺。")
        if model and model.remote:
            generation_permission = st.checkbox("允许将已确认信息发送到模型服务生成文案", value=False)
        else:
            generation_permission = True
        if st.button("生成多渠道文案", type="primary", disabled=not current_valid or not channels or not model or not generation_permission):
            try:
                with st.spinner("正在创作多渠道文案…"):
                    items = model.generate(st.session_state["confirmed_facts"], audience, channels, tone)
                bundle = new_bundle(st.session_state["confirmed_facts"], items, model=model.name, audience=audience, tone=tone,
                                    synthetic_input=synthetic_input)
                bundle["input_fingerprint"] = sig
                bundle["image_sha256"] = hashlib.sha256(image).hexdigest() if image else None
                st.session_state["studio_bundle"] = bundle
                persist(bundle)
                st.success("真实模型生成已完成，请打开“③ 文案工作台”。")
            except StudioError as exc:
                st.error(str(exc))
        if not current_valid:
            st.info("请先在产品信息页确认并保存事实。")
    bundle = st.session_state.get("studio_bundle")
    with drafts:
        if not bundle:
            st.info("尚无文案。可以生成文案，或加载明确标注的合成演示体验编辑流程。")
        else:
            if bundle["synthetic"]:
                st.warning("合成演示：下面的文案预先编写，未调用模型，不对应真实商品。")
            else:
                st.caption(f"模型：{bundle['model']} · 提示词：{bundle['prompt_version']} · {bundle['id']}")
                if bundle.get("synthetic_input"):
                    st.warning("当前为合成商品的真实模型测试，生成文案不代表真实商家或真实产品。")
            for index, item in enumerate(bundle["items"]):
                with st.container(border=True):
                    st.markdown("### " + item["channel"])
                    with st.form(f"draft_{bundle['id']}_{index}"):
                        title = st.text_input("标题", value=item["title"], key=f"draft_title_{bundle['id']}_{index}")
                        body = st.text_area("正文", value=item["body"], height=150, key=f"draft_body_{bundle['id']}_{index}")
                        if st.form_submit_button("保存修改"):
                            if not title.strip() or not body.strip():
                                st.error("标题和正文不能为空。")
                            else:
                                save_edit(bundle, index, title, body)
                                persist(bundle)
                                st.success("修改已保存并留痕。")
                    for warning in audit_copy(item["title"] + item["body"], bundle["facts"]):
                        st.warning(warning)
                    st.caption("依据编号：" + ", ".join(item["fact_ids"]) + "；编号由模型自报，仍需人工核对。")
            st.download_button("下载文案 Markdown", export_markdown(bundle), file_name="齐鲁卖点-创作草稿.md", mime="text/markdown")
            st.download_button("下载创作记录 JSON", json.dumps(bundle, ensure_ascii=False, indent=2), file_name="齐鲁卖点-创作记录.json", mime="application/json")
            st.caption("导出和送审使用已保存的版本。尚未点击保存的编辑不会进入报告。")
    with check:
        st.markdown("### 交给传播 X 光，再核对一遍")
        st.write("将保存后的文案与本次确认信息一起送审，逐条检查依据、修改结论并留下记录。")
        st.caption("商家确认信息不是独立证据。规则审核不等于事实认定或发布批准。")
        if bundle:
            for item in bundle["items"]:
                for warning in audit_copy(item["title"] + item["body"], bundle["facts"]):
                    st.warning(item["channel"] + "：" + warning)
        if st.button("一键送至传播 X 光", type="primary", disabled=not bundle or not current_valid):
            session = send_to_xray(bundle)
            store = ReviewStore()
            store.save_review(session, action="studio_handoff", details={"studio_id": bundle["id"]})
            st.session_state["review"] = session
            st.session_state["workspace_next"] = "传播 X 光审核"
            st.rerun()
