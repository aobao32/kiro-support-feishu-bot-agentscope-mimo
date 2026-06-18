# Kiro 助手 — 飞书技术支持机器人

基于 [AgentScope 2.0](https://github.com/agentscope-ai/agentscope) + [MiMo-v2.5-pro](https://mimo.mi.com/) 构建的飞书机器人，专注回答 [Kiro](https://kiro.dev) IDE/CLI 相关技术问题。

## 一、功能

### 1、核心能力

- 通过飞书 WebSocket 长连接接收用户消息，实时回复
- 基于 AgentScope 2.0 框架 + MiMo-v2.5-pro 模型（OpenAI 兼容接口）生成回复
- 内置工具：知识库按需读取、Kiro 官方文档抓取、GitHub Issues 搜索
- 每用户独立 Agent 实例，支持多轮对话上下文（仅内存）
- 不活跃 Agent 自动回收（默认 48 小时）

### 2、知识来源优先级

知识库（`read_kb_file`）→ Kiro 官网（`fetch_kiro_docs`）→ GitHub Issues（`search_github_issues`），找到答案即停止。

## 二、项目结构

```
kiro-support-feishu-bot-agentscope-mimo/
├── main.py              # 入口：asyncio 事件循环线程 + 飞书 WS 客户端
├── agent_service.py     # Agent 管理，每用户独立实例（AgentScope）
├── feishu_gateway.py    # 飞书消息收发网关
├── config.py            # 配置管理（敏感信息从环境变量读取）
├── kb_tool.py           # 知识库按需读取工具
├── web_tools.py         # 文档抓取 & GitHub Issues 搜索工具
├── logger.py            # 日志模块（终端 + 按日滚动文件）
├── knowledge_base/      # 知识库目录（放入 .md 文件）
├── prompts/             # System Prompt 目录
├── pyproject.toml       # 项目配置 & 依赖声明
└── .python-version      # Python 版本（3.12）
```

## 三、环境要求

- Python 3.11+（推荐 3.12，AgentScope 官方验证版本）
- [uv](https://docs.astral.sh/uv/) 包管理器

## 四、快速开始

### 1、安装依赖

```bash
uv sync
```

### 2、配置环境变量

| 环境变量 | 必填 | 说明 |
|---------|------|------|
| `MIMO_API_KEY` | 是 | MiMo 模型 API Key |
| `APP_ID` | 是 | 飞书开放平台应用 App ID |
| `APP_SECRET` | 是 | 飞书开放平台应用 App Secret |

```bash
export MIMO_API_KEY="your-mimo-api-key"
export APP_ID="your-feishu-app-id"
export APP_SECRET="your-feishu-app-secret"
```

### 3、配置 Prompt 和知识库

- `prompts/kiro_agent_prompt.md`（必须）：Agent 的 System Prompt，可复制 `kiro_agent_prompt.example` 修改
- `knowledge_base/*.md`（可选）：Markdown 知识库文件，如 `KB_1.md`，Agent 按需读取

```bash
cp prompts/kiro_agent_prompt.example prompts/kiro_agent_prompt.md
cp your_kb_file.md knowledge_base/KB_1.md
```

### 4、启动

```bash
uv run python main.py
```

## 五、飞书应用配置

本节完整说明如何在飞书开放平台创建机器人、配置能力与权限、建立长连接并发布。完成后将得到 `APP_ID` 和 `APP_SECRET` 两个值，供本项目环境变量使用（见第四节的2、配置环境变量）。

### 1、创建企业自建应用

进入[飞书开放平台](https://open.feishu.cn/app)，点击`创建企业自建应用`按钮。如下截图。

![](https://blogimg.bitipcman.com/workshop/openclaw/oc-09.png)

在创建自定义应用的弹出对话框内，输入名称，点击`创建`按钮。如下截图。

![](https://blogimg.bitipcman.com/workshop/openclaw/oc-10.png)

### 2、开启机器人能力

向导创建完成后会自动切换到能力界面，点击第一项，将此应用的能力设置为机器人。如下截图。

![](https://blogimg.bitipcman.com/workshop/openclaw/oc-11.png)

### 3、获取 App ID 和 App Secret

点击左侧的`凭证与基础信息`菜单，从右侧复制 App ID 和 App Secret 两个值，后续将作为本项目的环境变量 `APP_ID` 和 `APP_SECRET` 使用。如下截图。

![](https://blogimg.bitipcman.com/workshop/openclaw/oc-12.png)

### 4、配置权限

在左侧菜单`开发配置`下，点击`权限管理`，再点击右侧的`开通权限`按钮。如下截图。

![](https://blogimg.bitipcman.com/workshop/openclaw/oc-13.png)

在开通权限对话框内，搜索关键字找到下表权限后，点击`确认开通权限`按钮。如下截图。

![](https://blogimg.bitipcman.com/workshop/openclaw/oc-14.png)

要开通的权限列表包括：

| 权限 | 范围 | 说明 |
|------|------|------|
| `im:message` | 消息 | 发送和接收消息 |
| `im:message:update` | 编辑 | 更新/编辑已发送消息 |
| `im:message:readonly` | 读取 | 获取历史消息 |
| `im:message:recall` | 撤回 | 撤回已发送消息 |
| `im:message:send_as_bot` | 发送 | 以机器人身份发送消息 |
| `im:message.group_at_msg:readonly` | 群聊 | 接收群内 @机器人 的消息 |
| `im:message.group_msg` | 群聊 | 读取所有群消息（敏感） |
| `im:message.p2p_msg:readonly` | 私聊 | 读取发给机器人的私聊消息 |
| `im:message.reactions:read` | 表情 | 查看消息表情回复 |
| `im:resource` | 媒体 | 上传和下载图片/文件 |
| `contact:user.base:readonly` | 用户信息 | 获取用户基本信息（用于解析发送者姓名，避免群聊/私聊把不同人当成同一说话者） |

全部添加后界面如下截图。

![](https://blogimg.bitipcman.com/workshop/openclaw/oc-15.png)

### 5、用测试代码建立长连接

接下来测试本项目与飞书后台 API 的连接。只有外部应用连接成功，才能继续在飞书开放平台配置事件功能；若未先建立连接，后续配置会提示尚未连接。

本项目已通过 `uv sync` 安装 `lark-oapi`，可直接在项目根目录创建一个临时测试文件 `lark_test.py`，内容如下：

```python
import lark_oapi as lark

def do_p2_im_message_receive_v1(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    print(f'[ receive ], data: {lark.JSON.marshal(data, indent=4)}')

event_handler = lark.EventDispatcherHandler.builder("", "") \
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1) \
    .build()

cli = lark.ws.Client("YOUR_APP_ID", "YOUR_APP_SECRET",
                     event_handler=event_handler,
                     log_level=lark.LogLevel.DEBUG)
cli.start()
```

将 `YOUR_APP_ID` 和 `YOUR_APP_SECRET` 替换为第 3 步获取的真实值，然后执行：

```bash
uv run python lark_test.py
```

连接成功返回结果如下（信息已脱敏）：

```text
[Lark] [2026-02-11 08:46:01,055] [INFO] connected to wss://msg-frontier.feishu.cn/ws/v2?fpid=111&aid=11111&device_id=1111111111111&access_key=1111111111111111111111111&service_id=1111111111118&ticket=11111111111111111111111111111111111111111 [conn_id=111111111111111]
[Lark] [2026-02-11 08:46:01,056] [DEBUG] ping success [conn_id=1111111111111111]
[Lark] [2026-02-11 08:46:01,305] [DEBUG] receive pong [conn_id=1111111111111111]
```

连接成功后，先不要停止程序，保持长连接活跃状态，回到飞书控制台继续配置。

### 6、配置事件长连接

确认上一步程序保持运行、长连接活跃。在飞书开放平台左侧点击`事件与回调`菜单，在右侧点击`事件配置`标签页，点击下方的订阅方式。如下截图。

![](https://blogimg.bitipcman.com/workshop/openclaw/oc-16.png)

在订阅方式位置，选择`使用长连接接收事件（推荐）`，然后点击保存。如下截图。

![](https://blogimg.bitipcman.com/workshop/openclaw/oc-17.png)

此时需确保上一步的测试程序处于活跃状态，即可完成配置。

### 7、配置事件订阅

在`事件与回调`界面配置完长连接后，点击右下角的`添加事件`。如下截图。

![](https://blogimg.bitipcman.com/workshop/openclaw/oc-18-2.png)

在添加事件对话框中，通过关键字搜索添加下表事件。如下截图。

![](https://blogimg.bitipcman.com/workshop/openclaw/oc-19.png)

| 事件 | 说明 |
|------|------|
| `im.message.receive_v1` | 接收消息（必需） |
| `im.message.message_read_v1` | 消息已读回执 |
| `im.chat.member.bot.added_v1` | 机器人进群 |
| `im.chat.member.bot.deleted_v1` | 机器人被移出群 |

即可完成事件配置。配置完成后，可停止第 5 步的临时测试程序并删除 `lark_test.py`，改用第四节的 `uv run python main.py` 启动正式服务。

### 8、向飞书企业管理员申请发布机器人

注意：飞书机器人要想被外部应用调用，必须进行版本发布操作。如果你是飞书企业用户，这一步需要企业管理员审批；如果你是飞书个人用户，那么创建的机器人只能和自己对话，无法添加到与他人的对话中。与他人互动的飞书机器人要求必须是企业账号且完成企业营业执照审核。

进入左侧`应用发布`菜单，点击`版本管理与发布`，在右侧点击`创建版本`并填写表单。注意版本号必须是 `x.x.x` 格式。如下截图。

![](https://blogimg.bitipcman.com/workshop/openclaw/oc-20.png)

在发布申请下方，可选择向整个组织发布还是只向部分成员发布、是否对外共享，这都需要管理员审批。填写完整的申请理由后，点击保存即提交申请。如下截图。

![](https://blogimg.bitipcman.com/workshop/openclaw/oc-21.png)

等待管理员完成审批即可。

## 六、设计说明

### 1、模型接入

MiMo 提供 OpenAI 兼容接口，通过 AgentScope 的 `OpenAIChatModel` + 自定义 `base_url` 接入。按 MiMo 官方建议，使用 Function Call 时关闭深度思考（`extra_body.thinking=disabled`），避免输出不稳定。

### 2、工具权限

Agent 使用 `PermissionMode.BYPASS` 权限模式，自主调用内置只读工具，无需人工确认。

### 3、并发与回收

每用户独立 Agent 实例并加锁串行处理其消息，避免并发修改对话上下文；后台定时任务按 TTL 回收不活跃实例。

## 参考文档

- [AgentScope 文档](https://docs.agentscope.io/)
- [MiMo API 文档（OpenAI 兼容）](https://mimo.mi.com/docs/en-US/api/chat/openai-api)
- [飞书开放平台](https://open.feishu.cn/)
- [Kiro 官网](https://kiro.dev/)
