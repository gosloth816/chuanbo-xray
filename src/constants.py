"""应用级常量与可读标签。"""

import os

APP_NAME = "传播 X 光"
APP_SUBTITLE = "农业科技产品宣传材料诊断与证据核验工具"
APP_VERSION = "2.0.0"
PROMPT_VERSION = "xray-claim-review-v2.2"

VERDICT_LABELS = {
    "supported": "有资料支持",
    "conditionally_supported": "有条件支持",
    "insufficient": "证据不足",
    "conflicting": "资料冲突",
    "manual_review": "待人工核验",
}

VERDICT_SHORT = {
    "supported": "支持",
    "conditionally_supported": "条件支持",
    "insufficient": "证据不足",
    "conflicting": "资料冲突",
    "manual_review": "待核验",
}

VERDICT_DESCRIPTIONS = {
    "supported": "上传资料中存在与主张直接相关的内容，且未发现明显冲突。该结论不构成独立事实认定。",
    "conditionally_supported": "资料只支持特定作物、地区、剂量、试验条件或范围，宣传表述需要补充适用边界。",
    "insufficient": "在上传资料中未检索到足以支持该主张的内容。没有找到证据不等于证明宣传虚假。",
    "conflicting": "不同资料或主张与资料之间存在数值、范围或结论上的明显冲突，需要人工核对。",
    "manual_review": "系统无法可靠处理该主张，或引用未通过原文校验，必须由审核人员确认。",
}

VERDICT_COLORS = {
    "supported": "#13795B",
    "conditionally_supported": "#B7791F",
    "insufficient": "#667085",
    "conflicting": "#B42318",
    "manual_review": "#6941C6",
}

REVIEW_STATUS_LABELS = {
    "unreviewed": "未复核",
    "accepted": "已确认",
    "modified": "已修改",
    "rejected": "已驳回",
}

ROLE_LABELS = {
    "promotion": "宣传材料",
    "reference": "产品/技术资料",
    "poster": "宣传海报转写",
    "other": "其他材料",
}

ANALYSIS_MODE_LABELS = {
    "offline_rules": "本地规则核验",
    "local_llm": "本地大模型增强",
}

SUPPORTED_DOCUMENT_TYPES = ["txt", "md", "pdf", "docx"]
SUPPORTED_IMAGE_TYPES = ["png", "jpg", "jpeg"]

LIMITATIONS = [
    "本工具只核验用户上传资料与宣传主张之间的关系，不判断资料本身是否真实、完整或具有法律效力。",
    "未检索到证据不等于宣传虚假；系统不会据此作出真实性或违法性结论。",
    "本地规则模式依赖关键词、数值和限制语提示，适合流程验证，不等同于语义专家的完整判断。",
    "扫描版 PDF 和图片若没有可提取文字或人工转写，系统不会猜测其内容。",
    "AI 判断不是事实认定，必须由企业审核人员复核后才能作为发布前参考。",
]

def is_public_deployment() -> bool:
    if os.environ.get("XRAY_DEPLOYMENT_MODE", "").lower() == "public":
        return True
    if os.environ.get("SPACE_ID"):
        return True
    if os.environ.get("IS_STREAMLIT_CLOUD", "").lower() in {"1", "true", "yes"}:
        return True
    if os.environ.get("STREAMLIT_SHARING_MODE", "").lower() == "streamlit":
        return True
    # Streamlit Community Cloud mounts the application under /mount/src.
    return os.path.isdir("/mount/src")


AI_DISCLOSURE = {
    "runtime_default": "默认运行模式不调用任何外部模型服务，使用本地文档解析、关键词检索、数值核对与规则分类。",
    "local_llm": "本地运行时，如启用大模型增强，程序只允许连接 localhost / 127.0.0.1 / ::1。",
    "public_demo": "云端公开演示运行时，上传材料会发送到应用托管服务器处理；请勿上传敏感或未获授权的真实商业材料。",
    "development": "项目开发过程中使用 Codex 辅助编写代码、测试和文档；业务规则、测试数据与人工审核结论均保留运行记录。",
    "no_paid_service": "本应用当前不包含付费、订阅或充值环节。",
}
