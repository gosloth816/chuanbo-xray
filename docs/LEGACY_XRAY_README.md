# 传播 X 光

**农业科技产品宣传材料诊断与证据核验工具**

传播 X 光帮助山东农业科技企业、植保产品企业的市场宣传人员和审核人员，在材料发布前逐条核查宣传主张：上传资料是否支持、是否遗漏关键适用条件、是否存在资料冲突，以及哪些内容必须由人确认。

本工具不是文案生成器，也不是违法或造假判定系统。系统判断不是事实认定，所有结论都允许人工修改并留下理由。

## 公开演示

- 在线演示：https://chuanbo-xray.streamlit.app
- GitHub：https://github.com/gosloth816/chuanbo-xray
- 云端公开演示使用离线规则模式，上传材料会发送到托管服务器处理，请勿上传敏感或未获授权的真实商业材料。

## 当前可运行状态

- 本地 Streamlit Web 应用可启动、可上传、可诊断、可人工复核、可导出报告。
- 默认使用本地规则核验模式，不需要 API 密钥，不调用付费服务。
- 支持 TXT、MD、PDF、DOCX 文档解析；海报支持图片预览和人工文字转写。
- 支持 OpenAI 兼容的**本机**模型服务，代码会拒绝 localhost / 127.0.0.1 / ::1 之外的地址。
- 三个合成测试案例共有 14 条人工参考答案；当前离线规则流程实际匹配 14/14，引用逐字校验通过 50/50。
- 自动测试与评估结果见 `docs/verification.json`、`docs/evaluation_results.md`。

> 上述 14/14 只说明当前规则在三个合成案例上的流程一致性，不代表真实业务准确率，也不能替代真实用户测试。

## 界面预览

![传播 X 光首页](docs/ui-home.png)

![证据审查台](docs/ui-review.png)

![审核报告](docs/ui-report.png)

以上截图来自内置合成案例的实际本地运行。界面采用 CSS 玻璃质感、Bento 布局、轻噪点背景、克制动效和响应式布局，不依赖 Three.js、远程字体或外部 UI 服务。
## 快速启动

### 方式一：双击或运行脚本

```powershell
.\run.ps1
```

如果尚无 `.venv`，脚本会使用本机 Python 创建虚拟环境，并从 `requirements.txt` 安装开源依赖。启动后打开终端显示的本地地址。窄屏或移动端如果侧边栏收起，点击页面左上角的 `»` 按钮展开；展开后可点击侧栏右上角的 `«` 收起。

Windows 也可以直接双击 `run.bat`。

### 方式二：手动启动

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## 演示流程

1. 在“新建诊断”页面选择内置合成案例；
2. 点击“加载合成演示案例”；
3. 在“证据审查台”查看每条主张、判断依据和原始证据；
4. 对任一主张填写复核人、人工意见和最终表述；
5. 在“导出报告”下载 HTML、Markdown 或 JSON；
6. 在“关于与验证”查看 AI 使用披露和最近测试记录。

三个演示案例均为明确标注的合成测试数据，不对应任何真实产品、企业、试验或论文。

## 核心机制

```text
宣传材料 + 产品/技术资料
→ 文档解析并保留页码或段落位置
→ 提取可核验宣传主张
→ 关键词检索相关证据
→ 数值、范围、限制语核对
→ 每个引用进行原文逐字校验
→ 输出支持 / 条件支持 / 证据不足 / 资料冲突 / 待人工核验
→ 人工确认、修改或驳回
→ 导出带操作留痕的报告
```

### 判断类别

| 类别 | 含义 |
| --- | --- |
| 有资料支持 | 上传资料中存在直接相关内容，且未发现明显冲突 |
| 有条件支持 | 资料只支持特定作物、地区、剂量或试验条件 |
| 证据不足 | 上传资料中未检索到足以支持主张的内容；不等于宣传虚假 |
| 资料冲突 | 数值、范围或结论存在明显不一致 |
| 待人工核验 | 系统不能可靠判断，或引用校验失败 |

## 隐私与成本边界

- 不包含付费、订阅或充值功能。
- **本地运行模式**：材料只在当前电脑处理，审核记录保存在 `data/runtime/chuanbo_xray.sqlite3`，本地模型接口只允许连接回环地址。
- **云端公开演示模式**：上传材料会发送到托管服务器处理，页面会明确提示不要上传敏感或未获授权的真实商业材料；运行记录位于临时目录并在实例重启后清除。
- 代码会按照比赛公开演示需求推送到 GitHub 公共仓库，并由 Streamlit Community Cloud 托管。
- 本地模型为可选项，默认关闭；模型连接失败时直接报错，不使用固定文案冒充模型结果。
- 当前公开演示尚未启用云端大模型服务，因此大模型增强路径仍处于接口和结构验证阶段。

## 测试与评估

```powershell
# 完整自动测试
.\.venv\Scripts\python.exe -m pytest

# 合成验证集评估并生成真实结果文件
.\.venv\Scripts\python.exe scripts\run_evaluation.py

# 运行测试并写入 docs/verification.json
.\.venv\Scripts\python.exe scripts\run_verification.py
```

测试覆盖文档解析、检索、引用校验、规则分类、本地模型地址限制、SQLite 留痕、报告导出和 Streamlit 交互。

## 目录结构

```text
app.py                     Streamlit 入口
src/parsing.py             文档解析与可定位分块
src/evidence.py            检索、引用校验与离线分类
src/pipeline.py            完整分析流水线
src/local_llm.py           仅本机可用的可选模型客户端
src/storage.py             SQLite 审核记录与操作留痕
src/report.py              HTML / Markdown / JSON 报告
src/ui_*.py                界面模块
data/demo/                 三个合成演示案例
scripts/                   评估与验证脚本
tests/                     自动化测试
docs/                      产品说明、AI 披露、测试与演示材料
```

## 重要边界

- 只核验上传资料与宣传主张之间的关系，不判断资料本身是否真实、完整或具有法律效力。
- 扫描版 PDF 和图片不会被猜测内容；需要可提取文本或人工转写。
- 本地规则模式适合 MVP 流程验证，不能等同于完整语义专家判断。
- 正式发布前仍需企业审核、专业判断和必要的法律审查。

更多材料：[产品说明](docs/PRODUCT.md)、[AI 使用披露](docs/AI_USE_DISCLOSURE.md)、[测试计划](docs/TEST_PLAN.md)、[演示脚本](docs/DEMO_SCRIPT.md)。


## 2026赛道三参赛检查

正式规则对照见 [赛道三要求](docs/COMPETITION_ALIGNMENT.md)，本轮评价与改进见 [参赛评估](docs/TRACK3_REVIEW.md)。此前大创附件为误传，不作为本次依据。

当前主要缺口是实际大模型端到端运行与真实小范围测试。公开网页默认运行规则引擎；不能据此宣称大模型已完成实际调用验证。可运行 `scripts/verify_local_model.py` 检查本机服务并保存成功或失败记录。报告现包含程序分析耗时、人工复核进度、引用校验和待处理事项；程序耗时不能替代人工审核效率对照。


## 无需自带材料的公开资料演练

首页点击“运行公开资料案例”，再到证据审查台复核、导出报告即可。两份济南市农业农村局公开技术资料已保存本地快照，演练时无需联网下载。输入含原文摘录及明确标注的自编压力测试，不能冒充真实企业宣传或用户测试。

[公开资料与参赛强化说明](docs/PUBLIC_DATA_AND_POSITIONING.md) · [8条演练实际结果](docs/public_evaluation.md) · [公开资料报告示例](docs/public_case_evidence_scope.html)。运行 `.venv\Scripts\python.exe scripts/evaluate_public_cases.py` 可重现演练。网页设计已使用用户提供ZIP中的Mintlify和Linear参考，适配说明见 [DESIGN.md](DESIGN.md)。


## 当前版本说明

最新界面按用户选择的Apple方向设计。首页新增真实企业官网宣传短节选，保留发布者、日期与组合方案上下文；公开技术指导不等于单品或方案效果证明。[赛道与现实价值复核](docs/REALITY_CHECK.md)明确列出当前缺口，不能把本机规则演示宣传为已验证的大模型业务产品。
