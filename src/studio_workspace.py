"""齐鲁卖点：信息确认、分渠道创作、编辑和送审。"""
from html import escape
import gzip
import hashlib
import json
from pathlib import Path

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from .constants import is_public_deployment
from .studio import fingerprint, new_bundle, persist, save_edit, export_markdown, audit_copy, send_to_xray
from .studio_model import CHANNELS, FIELDS, GOALS, LENGTHS, PROMPT_VERSION, StudioModel, StudioError
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
        st.caption("创作规范：" + PROMPT_VERSION)
        if model.remote:
            st.caption("图片和介绍会发送到已配置的远程模型服务；调用可能产生服务费用。")
        else:
            st.caption("使用本机兼容模型服务。请确保服务已启动且模型支持图像输入。")
        st.caption("地址、模型名和密钥在服务器环境中配置，密钥不会写入创作记录。")
    if model.block_reason:
        st.info(model.block_reason + " 合成演示、手动填写及传播X光仍可使用。")
        return None
    return model


@st.cache_data
def _origin_atlas():
    with gzip.open(ROOT / "data/studio/origin_atlas.json.gz", "rt", encoding="utf-8") as file:
        return json.load(file)


def _match_origin(origin, atlases):
    text = "".join(origin.split()).replace("中国", "", 1)
    autonomous = {
        "内蒙古自治区": "内蒙古", "广西壮族自治区": "广西",
        "西藏自治区": "西藏", "宁夏回族自治区": "宁夏",
        "新疆维吾尔自治区": "新疆",
    }
    for province, atlas in atlases.items():
        short = autonomous.get(province, province.removesuffix("特别行政区").removesuffix("省").removesuffix("市"))
        prefix = next((name for name in (province, short) if text.startswith(name)), None)
        if prefix:
            rest = text[len(prefix):].lstrip("，,、/·")
            city = next((name for name in sorted(atlas["cities"], key=len, reverse=True)
                         if rest.startswith(name.removesuffix("市"))), None)
            return province, city
    matches = [(province, city) for province, atlas in atlases.items() for city in atlas["cities"]
               if text in (city, city.removesuffix("市"))]
    return matches[0] if len(matches) == 1 else (None, None)


def _render_origin(facts):
    origin = next((row["value"] for row in facts.values() if row["field"] == "产地"), "")
    if not origin:
        return
    st.markdown("#### 商品产地")
    st.write(origin)
    atlases = _origin_atlas()
    province, city = _match_origin(origin, atlases)
    if province:
        atlas = atlases[province]
        svg = atlas["svg"]
        highlighted = escape(city or province, quote=True)
        svg = svg.replace(f'class="city" data-region="{highlighted}"',
                          f'class="city selected" data-region="{highlighted}"')
        x, y = atlas["cities"].get(city, (125, 85))
        label = escape(city.removesuffix("市") if city else province)
        svg = svg.replace('<text id="atlas-city-label"></text>',
                          f'<text x="{x}" y="{y}">{label}</text>')
        st.markdown(
            '<style>.studio-atlas svg{width:100%;background:#eff5f8;border-radius:8px}'
            '.studio-atlas .context{fill:#e0e7eb;stroke:#fff;stroke-width:.6}'
            '.studio-atlas .city{fill:#b9ccd9;stroke:#fff;stroke-width:.65}'
            '.studio-atlas .selected{fill:#7097b1;stroke:#456c86}'
            '.studio-atlas text{font-size:12px;text-anchor:middle;fill:#203d52;'
            'paint-order:stroke;stroke:#f5f8fa;stroke-width:2}</style>'
            f'<div class="studio-atlas">{svg}</div>', unsafe_allow_html=True,
        )
        st.caption("边界数据：阿里云 DataV GeoAtlas")
        return
    st.caption("请在产地填写省和市，例如浙江省杭州市。")


WORKSPACE_VERSION = 2


def _phone(channel, title, body):
    st.markdown(
        '<div class="studio-phone"><div class="studio-phone-bar">'
        f'{escape(channel)}</div><article><h4>{escape(title)}</h4>'
        f'<p>{escape(body)}</p></article></div>', unsafe_allow_html=True,
    )


def render_studio():
    model = _model_settings()
    st.markdown("""
    <style>
    .st-key-studio-layout {background:#f3f3f5;padding:1rem;border-radius:12px}
    .st-key-studio-layout [data-testid="stColumn"] {background:#fafafc;padding:1rem;border-radius:8px;min-width:0}
    .studio-phone {max-width:340px;margin:14px auto;border:7px solid #202124;
      border-radius:34px;background:white;color:#1d1d1f;height:510px;overflow:auto}
    .studio-phone-bar {text-align:center;font-weight:600;padding:15px;background:#f5f5f7;border-bottom:1px solid #ddd}
    .studio-phone article {padding:20px;overflow-wrap:anywhere}
    .studio-phone article p {white-space:pre-wrap;line-height:1.85}
    </style>
    """, unsafe_allow_html=True)
    st.markdown("### 齐鲁卖点 · 创作室")
    st.button("加载合成演示", on_click=_load_demo, help="加载预写演示内容，不调用或冒充模型。")
    layout = st.container(key="studio-layout")
    info, drafts, creative = layout.columns([1, 1.65, 1.1], gap="medium")
    with info:
        st.markdown("### 本次商品")
        facts = st.session_state.get("confirmed_facts") or {}
        if facts:
            if st.session_state.get("product_description") == DESCRIPTION:
                st.image(str(ROOT / "data/studio/apple-studio.png"), caption="合成商品图")
            for row in facts.values():
                st.write(f'{row["field"]} · {row["value"]}')
        else:
            st.caption("录入商品并确认资料后，这里会显示商品摘要。")
        _render_origin(facts)
        left = st.expander("录入商品与识图")
        right = st.expander("核对并确认商品事实", expanded=bool(st.session_state.get("recognition_message")))
        with left:
            if is_public_deployment():
                st.caption("上传资料会发送至托管服务器处理，请使用获授权的材料。")
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
                    st.session_state["recognition_message"] = "模型提出的信息已填入商品事实区，请逐项检查后保存。"
                    st.rerun()
                except StudioError as exc:
                    st.error(str(exc))
            st.caption("照片不能证明甜度、认证或健康功效。也可以跳过识别，直接手动填写商品事实。")
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
                st.caption("已确认。可在右栏设置表达方式。")
    with creative:
        st.markdown("### 表达设定")
        audience = st.selectbox("目标受众", ["家庭日常购买", "年轻上班族", "节日送礼", "社区团购"])
        channels = st.multiselect("发布渠道", CHANNELS, default=CHANNELS)
        tone = st.selectbox("表达风格", ["自然清楚", "简短直接", "温暖生活化"])
        goal_col, length_col = st.columns(2)
        with goal_col:
            goal = st.selectbox("这次文案的目标", GOALS)
        with length_col:
            length = st.selectbox("文案篇幅", list(LENGTHS))
        confirmed_for_brief = st.session_state.get("confirmed_facts") or {}
        focus_ids = st.multiselect("重点讲哪些信息（可选）", list(confirmed_for_brief),
            format_func=lambda fid: f"{confirmed_for_brief[fid]['field']}：{confirmed_for_brief[fid]['value']}")
        creative_direction = st.text_area("想要的创作方向（可选）", max_chars=600, height=90,
            placeholder="例如：从下班后给家里添水果的场景切入，口吻像熟悉的店主，结尾邀请咨询。")
        st.caption("创作方向用于场景和表达。新增产品卖点请先回到产品信息页填写并确认。")
        st.caption("完整成稿：详情页约220—360字，朋友圈约100—180字，口播约45—60秒；信息较少时会适当缩短。")
        if model and model.remote:
            generation_permission = st.checkbox("允许将已确认信息发送到模型服务生成文案", value=False)
        else:
            generation_permission = True
        if st.button("生成多渠道文案", type="primary", disabled=not current_valid or not channels or not model or not generation_permission):
            try:
                with st.spinner("正在创作多渠道文案…"):
                    items = model.generate(st.session_state["confirmed_facts"], audience, channels, tone,
                        goal=goal, length=length, focus_ids=focus_ids, creative_direction=creative_direction)
                bundle = new_bundle(st.session_state["confirmed_facts"], items, model=model.name, audience=audience, tone=tone,
                                    synthetic_input=synthetic_input,
                                    creative_brief={"goal": goal, "length": length, "focus_fact_ids": focus_ids,
                                                    "creative_direction": creative_direction})
                bundle["input_fingerprint"] = sig
                bundle["image_sha256"] = hashlib.sha256(image).hexdigest() if image else None
                st.session_state["studio_bundle"] = bundle
                persist(bundle)
                st.success("真实模型生成已完成，可在中间查看文稿。")
            except StudioError as exc:
                st.error(str(exc))
        if not current_valid:
            st.info("请先在产品信息页确认并保存事实。")
    bundle = st.session_state.get("studio_bundle")
    with drafts:
        if not bundle:
            _phone("渠道预览", "你的文稿会显示在这里", "请先在左侧录入并确认商品，再从右侧生成文案。也可以点击上方的加载合成演示。")
        else:
            if bundle["synthetic"]:
                st.warning("合成演示：下面的文案预先编写，未调用模型，不对应真实商品。")
            else:
                st.caption(f"模型：{bundle['model']} · 提示词：{bundle['prompt_version']} · {bundle['id']}")
                if bundle.get("synthetic_input"):
                    st.warning("当前为合成商品的真实模型测试，生成文案不代表真实商家或真实产品。")
            channel = st.selectbox("预览渠道", [item["channel"] for item in bundle["items"]])
            for index, item in enumerate(bundle["items"]):
                if item["channel"] != channel:
                    continue
                _phone(channel, item["title"], item["body"])
                with st.expander("编辑当前文稿"):
                    st.markdown("### " + item["channel"])
                    with st.form(f"draft_{bundle['id']}_{index}"):
                        title = st.text_input("标题", value=item["title"], key=f"draft_title_{bundle['id']}_{index}")
                        body = st.text_area("正文", value=item["body"], height=280, key=f"draft_body_{bundle['id']}_{index}")
                        if st.form_submit_button("保存修改"):
                            if not title.strip() or not body.strip():
                                st.error("标题和正文不能为空。")
                            else:
                                save_edit(bundle, index, title, body)
                                persist(bundle)
                                st.rerun()
                    for warning in audit_copy(item["title"] + item["body"], bundle["facts"]):
                        st.warning(warning)
                    st.caption("依据编号：" + ", ".join(item["fact_ids"]) + "；编号由模型自报，仍需人工核对。")
            st.download_button("下载文案 Markdown", export_markdown(bundle), file_name="齐鲁卖点-创作草稿.md", mime="text/markdown")
            st.download_button("下载创作记录 JSON", json.dumps(bundle, ensure_ascii=False, indent=2), file_name="齐鲁卖点-创作记录.json", mime="application/json")
            st.caption("导出和送审使用已保存的版本。尚未点击保存的编辑不会进入报告。")
    with creative:
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
