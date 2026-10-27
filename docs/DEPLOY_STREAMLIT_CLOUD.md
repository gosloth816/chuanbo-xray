# Streamlit Community Cloud 部署说明

## 目标

把传播 X 光部署成一个公开网页，让评委或其他人通过链接直接打开，不需要安装 Python，也不需要访问项目作者的电脑。

- GitHub 仓库：https://github.com/gosloth816/chuanbo-xray
- 公开演示地址：部署完成后填写
- 部署平台：Streamlit Community Cloud
- 费用：使用平台免费额度，不购买服务、不绑定支付方式

## 云端运行模式

应用会根据运行环境自动区分本地模式和公开演示模式。公开演示模式下：

- 页面明确提示上传材料会发送到托管服务器；
- 提醒用户不要上传敏感或未获授权的真实商业材料；
- SQLite 运行记录写入临时目录，实例重启后可能丢失；
- 不显示仅对项目作者本机有效的 localhost 模型配置；
- 当前默认使用本地规则核验，不声称云端大模型已经接通。

## 本地模式与云端模式的区别

| 项目 | 本地模式 | 公开演示模式 |
| --- | --- | --- |
| 访问地址 | 127.0.0.1 | Streamlit Cloud 公网网址 |
| 是否需要作者电脑开机 | 是 | 否 |
| 上传材料处理位置 | 作者电脑 | 云平台服务器 |
| 运行记录 | `data/runtime` | 临时目录 |
| 本地大模型入口 | 可配置 | 隐藏 |
| 当前分析方式 | 本地规则 | 本地规则 |

## 部署步骤

1. 确认 GitHub 仓库代码已推送；
2. 使用 GitHub 账号登录 https://share.streamlit.io；
3. 选择 **Create app**；
4. 选择 **Deploy a public app from GitHub**；
5. Repository 选择 `gosloth816/chuanbo-xray`；
6. Branch 选择 `master`；
7. Main file path 填写 `app.py`；
8. Python 版本选择 3.10 或平台支持的相近版本；
9. 点击 **Deploy**；
10. 等待构建完成，保存生成的公开网址。

## 后续修改

GitHub 的 `master` 分支连接到 Streamlit Cloud 后，每次提交并推送新代码，平台会自动重新构建。公开网址保持不变。

## 大模型说明

公开网页目前运行离线规则核验模式。若要启用云端大模型，需要：

- 添加服务器端模型接口；
- 把 API Key 存在 Streamlit Secrets，不提交到 GitHub；
- 用真实材料测试引用准确率、错误放行率和耗时；
- 明确告知用户材料是否会发送给模型服务商。

在完成上述步骤前，不得在项目材料中声称云端大模型已经接入或达到某个准确率。
