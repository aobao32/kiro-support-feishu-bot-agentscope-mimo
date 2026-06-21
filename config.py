"""Kiro 助手配置管理模块。

集中管理非敏感配置项（模型参数、路径、超时时间等），
敏感配置从环境变量读取，避免硬编码。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ── 项目路径 ─────────────────────────────────────────────────────────────────

# 项目根目录（kiro-support-feishu-bot-agentscope-mimo/）
_PROJECT_DIR = Path(__file__).parent

# ── 环境变量加载 ─────────────────────────────────────────────────────────────

# 在读取 os.environ 之前，先加载项目根目录下的 .env 文件，使后台运行
# （nohup / launchd 等脱离登录 shell 的场景）也能读到敏感配置。
# 已存在于真实环境中的变量优先，不会被 .env 覆盖（override=False）。
load_dotenv(_PROJECT_DIR / ".env", override=False)

# ── 模型配置（MiMo，OpenAI 兼容接口）─────────────────────────────────────────

# MiMo OpenAI 兼容 base_url
MIMO_BASE_URL: str = "https://api.xiaomimimo.com/v1"
# 模型 ID（Pro 系列，1M 上下文，支持 Function Call / Web Search / 深度思考）
MIMO_MODEL_ID: str = "mimo-v2.5-pro"
# 单次回复最大输出 token 数
MIMO_MAX_TOKENS: int = 4096
# 采样温度（thinking 关闭时才可自定义）
MIMO_TEMPERATURE: float = 0.3
# 是否开启深度思考。MiMo 官方建议：使用 Function Call 时关闭 thinking，
# 否则 tool_calls 可能混入 reasoning_content，导致输出不稳定。
MIMO_THINKING_ENABLED: bool = False

# ── 路径配置 ──────────────────────────────────────────────────────────────────

# System Prompt 文件（必须存在，否则启动报错）
PROMPT_FILE: str = str(_PROJECT_DIR / "prompts" / "kiro_agent_prompt.md")
# 知识库目录（存放 .md 文件，Agent 按需读取）
KB_DIR: str = str(_PROJECT_DIR / "knowledge_base")

# ── Agent 管理配置 ───────────────────────────────────────────────────────────

# 单用户 Agent 不活跃多久后从内存回收（秒）
AGENT_TTL_SECONDS: int = 48 * 3600  # 48 小时
# 单次回复 reasoning-acting 循环最大迭代轮数
AGENT_MAX_ITERS: int = 20

# ── 联网工具配置 ─────────────────────────────────────────────────────────────

# GitHub Issues 搜索目标仓库
GITHUB_REPO: str = "kirodotdev/Kiro"
# HTTP 请求超时（秒）
HTTP_TIMEOUT: int = 10

# ── 日志配置 ─────────────────────────────────────────────────────────────────

# 是否将日志同步写入本地文件（True=开启，False=仅打印到终端）
ENABLE_FILE_LOG: bool = True
# 日志文件存放目录（相对于项目根目录）
LOG_DIR: str = str(_PROJECT_DIR / "logs")

# ── 敏感配置（从环境变量读取，不硬编码）─────────────────────────────────────

# MiMo 模型 API Key
MIMO_API_KEY: str = os.environ.get("MIMO_API_KEY", "")
# 飞书开放平台应用 App ID
APP_ID: str = os.environ.get("APP_ID", "")
# 飞书开放平台应用 App Secret
APP_SECRET: str = os.environ.get("APP_SECRET", "")
