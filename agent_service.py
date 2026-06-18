"""Agent 服务模块。

基于 AgentScope 2.0 管理每个用户的 Agent 实例，全异步接口。
使用 OpenAIChatModel 连接 MiMo（OpenAI 兼容接口）。

设计要点：
- 每个用户维护独立的 Agent 实例，从而拥有独立的多轮对话上下文（仅内存，不落盘）。
- 通过 PermissionMode.BYPASS 让 Agent 自主调用自定义工具，无需人工确认。
- MiMo 在使用 Function Call 时建议关闭深度思考，避免输出不稳定。
- 不活跃的 Agent 实例按 TTL 自动回收，释放内存。
"""

import asyncio
import sys
import time
from dataclasses import dataclass, field

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import OpenAICredential
from agentscope.model import OpenAIChatModel
from agentscope.message import UserMsg
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.state import AgentState
from agentscope.tool import FunctionTool, Toolkit

from config import (
    AGENT_MAX_ITERS,
    AGENT_TTL_SECONDS,
    MIMO_API_KEY,
    MIMO_BASE_URL,
    MIMO_MAX_TOKENS,
    MIMO_MODEL_ID,
    MIMO_TEMPERATURE,
    MIMO_THINKING_ENABLED,
    PROMPT_FILE,
)
from kb_tool import build_kb_tool_description, read_kb_file
from logger import get_logger
from web_tools import fetch_kiro_docs, search_github_issues

logger = get_logger(__name__)

AGENT_NAME = "Kiro助手"


@dataclass
class UserAgentState:
    """用户 Agent 状态，包含 Agent 实例、最后活跃时间和并发锁。"""

    agent: Agent
    last_active: float
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class AgentService:
    """管理每个用户的 AgentScope Agent 实例，全异步接口。"""

    def __init__(self) -> None:
        # 检查 API Key
        if not MIMO_API_KEY:
            logger.error("环境变量 MIMO_API_KEY 未设置，请先配置后再启动。")
            sys.exit(1)

        # 创建 MiMo 模型（OpenAI 兼容接口，自定义 base_url）
        # MiMo 通过 extra_body.thinking 控制深度思考；使用 Function Call 时建议关闭。
        thinking_type = "enabled" if MIMO_THINKING_ENABLED else "disabled"
        self._model = OpenAIChatModel(
            credential=OpenAICredential(
                api_key=MIMO_API_KEY,
                base_url=MIMO_BASE_URL,
            ),
            model=MIMO_MODEL_ID,
            stream=False,
            parameters=OpenAIChatModel.Parameters(
                max_tokens=MIMO_MAX_TOKENS,
                temperature=MIMO_TEMPERATURE,
            ),
            extra_body={"thinking": {"type": thinking_type}},
        )

        # 加载 System Prompt
        try:
            with open(PROMPT_FILE, "r", encoding="utf-8") as f:
                self._system_prompt = f.read()
        except FileNotFoundError:
            logger.error(
                "System Prompt 文件不存在: %s，请先创建后再启动。", PROMPT_FILE
            )
            sys.exit(1)
        logger.info("System Prompt 已加载: %s", PROMPT_FILE)

        # 知识库工具描述（动态列出当前可用的 KB 文件）
        self._kb_tool_description = build_kb_tool_description()

        # 用户 Agent 字典
        self._agents: dict[str, UserAgentState] = {}

        # 全局锁，保护 _agents 字典的并发访问
        self._global_lock = asyncio.Lock()

        logger.info(
            "AgentService 初始化完成，模型: %s, 深度思考: %s",
            MIMO_MODEL_ID,
            thinking_type,
        )

    def _build_toolkit(self) -> Toolkit:
        """为单个 Agent 构建工具集。

        - read_kb_file: 知识库按需读取（动态描述列出可用文件）
        - fetch_kiro_docs: 抓取 Kiro 官网文档
        - search_github_issues: 搜索 Kiro GitHub Issues
        """
        return Toolkit(
            tools=[
                FunctionTool(
                    read_kb_file,
                    description=self._kb_tool_description,
                    is_read_only=True,
                ),
                FunctionTool(fetch_kiro_docs, is_read_only=True),
                FunctionTool(search_github_issues, is_read_only=True),
            ],
        )

    def _create_agent(self, user_id: str) -> Agent:
        """创建一个新的用户 Agent 实例。"""
        # BYPASS 权限模式：让 Agent 自主调用自定义工具，无需人工确认
        state = AgentState(
            permission_context=PermissionContext(mode=PermissionMode.BYPASS),
        )
        return Agent(
            name=AGENT_NAME,
            system_prompt=self._system_prompt,
            model=self._model,
            toolkit=self._build_toolkit(),
            state=state,
            react_config=ReActConfig(max_iters=AGENT_MAX_ITERS),
        )

    async def get_or_create_agent(self, user_id: str) -> Agent:
        """获取或创建用户的 Agent 实例（异步锁保护）。"""
        async with self._global_lock:
            if user_id in self._agents:
                self._agents[user_id].last_active = time.time()
                logger.info("复用已有 Agent: user_id=%s", user_id)
                return self._agents[user_id].agent

            agent = self._create_agent(user_id)
            self._agents[user_id] = UserAgentState(
                agent=agent,
                last_active=time.time(),
            )
            logger.info("创建新 Agent: user_id=%s", user_id)
            return agent

    async def ask(self, user_id: str, message: str) -> str:
        """向指定用户的 Agent 发送消息并返回回复文本。"""
        start_time = time.time()
        msg_summary = message[:50]
        try:
            await self.get_or_create_agent(user_id)
            user_lock = self._agents[user_id].lock

            # 同一用户的消息串行处理，避免并发修改对话上下文
            async with user_lock:
                agent = self._agents[user_id].agent
                result = await agent.reply(UserMsg("user", message))

            reply = result.get_text_content() or (
                "抱歉，我暂时无法回答这个问题，请稍后再试。"
            )
            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                "用户消息处理完成: user_id=%s, 消息摘要='%s', 耗时=%.1fms",
                user_id,
                msg_summary,
                elapsed_ms,
            )
            return reply.strip()
        except Exception:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.exception(
                "处理用户消息异常: user_id=%s, 消息摘要='%s', 耗时=%.1fms",
                user_id,
                msg_summary,
                elapsed_ms,
            )
            return "抱歉，处理您的消息时出现了问题，请稍后再试。"

    async def evict_inactive(self) -> list[str]:
        """移除超过 TTL 的不活跃 Agent 实例，返回被移除的 user_id 列表。"""
        async with self._global_lock:
            now = time.time()
            expired_ids = [
                uid
                for uid, state in self._agents.items()
                if (now - state.last_active) > AGENT_TTL_SECONDS
            ]
            for uid in expired_ids:
                del self._agents[uid]

            if expired_ids:
                logger.info(
                    "已清除 %d 个不活跃 Agent: %s",
                    len(expired_ids),
                    expired_ids,
                )
            return expired_ids
