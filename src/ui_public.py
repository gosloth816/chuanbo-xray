"""无需上传文件即可验证的公开资料入口。"""

import html

import streamlit as st

from .pipeline import analyze_documents
from .public_data import CASES, load_public_case, sources
from .ui_sidebar import build_llm


def render_public_cases(store, enable_llm, llm_base, llm_model):
    options = list(CASES)
    controls, preview = st.columns([0.92, 1.25], gap="large")
    with controls:
        st.markdown("<div class='small-label'>开始审核</div><h2 class='start-title'>选一份材料</h2>", unsafe_allow_html=True)
        st.write("可以先用公开资料体验核对流程，也可以在下方上传自己的文案。")
        chosen = st.selectbox("选择公开资料案例", options, index=options.index("real_announcement"), format_func=lambda key: CASES[key]["title"])
        st.caption(f"2 份公开技术资料 · {len(CASES[chosen]['claims'])} 条待核对表述")
        st.markdown(f"<div class='quiet-note'>{html.escape(CASES[chosen]['description'])}</div>", unsafe_allow_html=True)
        use_model = False
        if enable_llm:
            use_model = st.checkbox("此案例使用本机大模型", key="public_case_llm")
        if st.button("运行公开资料案例", type="primary", width="stretch"):
            try:
                llm = build_llm(enable_llm, llm_base, llm_model) if use_model else None
                with st.spinner("正在核对资料…"):
                    review = analyze_documents(title=CASES[chosen]["title"], documents=load_public_case(chosen),
                                               mode="local_llm" if use_model else "offline_rules", llm=llm)
                    store.save_review(review, action="public_case_analyzed", details={"case_id": chosen, "mode": review.mode})
                    st.session_state["review"] = review
                    st.session_state["flash"] = "公开资料案例已完成。"
                    st.rerun()
            except Exception as exc:
                st.error(f"案例未完成：{exc}")
        st.caption("运行后，打开“② 证据审查台”查看并修改结论。")
        if CASES[chosen].get("real_promotion"):
            st.caption("依据是真实公开技术资料；当前文案为企业官网原文节选，不是自编案例。")
            source = CASES[chosen]["promotion_source"]
            st.markdown(f"[查看完整宣传原文]({source['url']})")
        else:
            st.caption("依据是真实公开技术资料；演练文案含自编压力测试，不代表真实企业发布。")
        with st.expander("资料来源与文案来源"):
            if CASES[chosen].get("real_promotion"):
                st.write(CASES[chosen]["promotion_source"]["context"])
            for source in sources():
                st.markdown(f"[{source['title']}]({source['url']})")
                st.caption(f"发布：{source['published_at']} · 获取：{source['retrieved_at']} · SHA-256：{source['sha256'][:16]}…")
            for text, origin in zip(CASES[chosen]["claims"], CASES[chosen]["origin"]):
                st.write(f"【{origin}】{text}")
            st.caption("2025年资料仅用于历史一致性核对；公开指导不等于特定产品效果证明，数据不是企业实测或用户反馈。")

    with preview:
        rows = "".join(
            f"<div class='manuscript-row'><span class='line-number'>{i:02d}</span>"
            f"<div><p>{html.escape(text)}</p><span class='origin-note'>{html.escape(origin)}</span></div></div>"
            for i, (text, origin) in enumerate(zip(CASES[chosen]["claims"], CASES[chosen]["origin"]), 1)
        )
        facts = ""
        if CASES[chosen].get("real_promotion"):
            meta = CASES[chosen]["promotion_source"]
            facts = (
                "<div class='source-facts'>"
                f"<div class='source-fact'><span>发布来源</span><strong>{html.escape(meta['publisher'])}</strong></div>"
                f"<div class='source-fact'><span>发布日期</span><strong>{html.escape(meta['published_at'])}</strong></div>"
                "<div class='source-fact'><span>数据对象</span><strong>组合方案 · 不能直接转述为单品效果</strong></div>"
                "<div class='source-fact'><span>当前依据</span><strong>通用技术指导 2 份；未提供对应原始试验报告</strong></div></div>"
            )
        st.markdown(
            "<article class='manuscript'><div class='manuscript-meta'><span>待审核原文</span><span>材料预览</span></div>"
            f"<h2>{html.escape(CASES[chosen]['title'].split('：')[-1])}</h2>"
            "<div class='manuscript-rule'></div>" + rows +
            facts + "<div class='manuscript-bottom'>待核验材料 · 此处未展示系统结论</div></article>",
            unsafe_allow_html=True,
        )
    st.markdown("<div class='workspace-divider'></div>", unsafe_allow_html=True)
