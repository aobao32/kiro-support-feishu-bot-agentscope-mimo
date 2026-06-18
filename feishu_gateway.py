"""飞书 WebSocket 网关模块。

处理飞书消息收发，通过 asyncio 桥接将同步回调委托给异步事件循环：
- 主线程：运行飞书 WS 客户端（阻塞）
- 独立线程：运行 asyncio 事件循环，处理 Agent 异步调用
"""

import asyncio
import json
import re
import sys

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageReactionRequest,
    CreateMessageReactionRequestBody,
    CreateMessageRequest,
    CreateMessageRequestBody,
    Emoji,
    P2ImMessageReceiveV1,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)

from agent_service import AgentService
from config import APP_ID, APP_SECRET
from logger import get_logger

logger = get_logger(__name__)

# 飞书支持的表情 key 白名单，无效的 :XXX: 占位符会降级为普通文本
_VALID_EMOJI_TYPES = {
    "OK", "THUMBSUP", "THANKS", "FINGERHEART", "FISTBUMP", "JIAYI", "DONE",
    "BLUSHFACE", "PALM", "LOVE", "WITTY", "SMART", "SCOWL", "SOBER", "ERROR",
    "TOASTED", "JOYFUL", "TRICK", "ENOUGH", "TEARS", "CLAP", "STRIVE",
    "Typing", "GetYou", "AreTheBest", "SALUTE", "ROSE", "HEART", "Yes",
    "Fire", "Status_PrivateMessage", "Salute", "Get",
}


class FeishuGateway:
    """飞书 WebSocket 网关，处理消息收发。"""

    def __init__(
        self,
        agent_service: AgentService,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._agent_service = agent_service
        self._loop = loop

        # 检查飞书应用凭证
        if not APP_ID or not APP_SECRET:
            logger.error(
                "环境变量 APP_ID 或 APP_SECRET 未设置，请先配置后再启动。"
            )
            sys.exit(1)

        # 初始化飞书客户端（用于发送消息 / reaction）
        self._client = (
            lark.Client.builder()
            .app_id(APP_ID)
            .app_secret(APP_SECRET)
            .build()
        )

        # 消息去重：set 用于 O(1) 查找，list 保持插入顺序以便清理
        self._processed_ids: set[str] = set()
        self._processed_ids_order: list[str] = []

        logger.info("FeishuGateway 初始化完成")

    # ------------------------------------------------------------------
    # 消息去重
    # ------------------------------------------------------------------

    def _is_duplicate(self, message_id: str) -> bool:
        """检查 message_id 是否已处理过。超过 1000 条时清理最早的 500 条。"""
        if message_id in self._processed_ids:
            return True

        self._processed_ids.add(message_id)
        self._processed_ids_order.append(message_id)

        if len(self._processed_ids_order) > 1000:
            to_remove = self._processed_ids_order[:500]
            self._processed_ids_order = self._processed_ids_order[500:]
            for mid in to_remove:
                self._processed_ids.discard(mid)

        return False

    # ------------------------------------------------------------------
    # 消息接收回调
    # ------------------------------------------------------------------

    def handle_message(self, data: P2ImMessageReceiveV1) -> None:
        """消息事件回调（同步），桥接到异步处理。"""
        try:
            message = data.event.message
            message_id = message.message_id

            # 去重
            if self._is_duplicate(message_id):
                logger.debug("重复消息，跳过: %s", message_id)
                return

            # 添加 reaction 表示已收到正在处理
            self._send_reaction(message_id, "Get")

            # 非文本消息直接回复提示
            if message.message_type != "text":
                logger.info(
                    "收到非文本消息 (type=%s), message_id=%s",
                    message.message_type,
                    message_id,
                )
                self._send_reply(data, "请发送文字消息。")
                return

            # 提取文本内容
            text = json.loads(message.content)["text"]
            user_id = data.event.sender.sender_id.open_id
            logger.info(
                "收到消息: user=%s, text=%s, message_id=%s",
                user_id,
                text[:50],
                message_id,
            )

            # 通过 asyncio 桥接到异步事件循环处理 Agent 调用
            future = asyncio.run_coroutine_threadsafe(
                self._agent_service.ask(user_id, text),
                self._loop,
            )
            reply_text = future.result()  # 阻塞等待异步结果

            self._send_reply(data, reply_text)

        except Exception:
            logger.exception("处理消息时发生异常")

    # ------------------------------------------------------------------
    # 消息发送
    # ------------------------------------------------------------------

    def _send_reply(self, data: P2ImMessageReceiveV1, reply_text: str) -> None:
        """根据消息类型（p2p/群聊）发送回复。"""
        content_json = json.dumps(self._text_to_post(reply_text))
        message = data.event.message
        chat_type = message.chat_type
        message_id = message.message_id

        try:
            if chat_type == "p2p":
                # 私聊：直接向 chat_id 发送新消息
                request = (
                    CreateMessageRequest.builder()
                    .receive_id_type("chat_id")
                    .request_body(
                        CreateMessageRequestBody.builder()
                        .receive_id(message.chat_id)
                        .msg_type("post")
                        .content(content_json)
                        .build()
                    )
                    .build()
                )
                response = self._client.im.v1.message.create(request)
            else:
                # 群聊：回复原消息（自动 @ 提问者并形成话题）
                request = (
                    ReplyMessageRequest.builder()
                    .message_id(message_id)
                    .request_body(
                        ReplyMessageRequestBody.builder()
                        .msg_type("post")
                        .content(content_json)
                        .build()
                    )
                    .build()
                )
                response = self._client.im.v1.message.reply(request)

            if not response.success():
                logger.error(
                    "发送回复失败: code=%s, msg=%s, chat_type=%s, message_id=%s",
                    response.code,
                    response.msg,
                    chat_type,
                    message_id,
                )
        except Exception:
            logger.error("发送回复异常: message_id=%s", message_id, exc_info=True)

    def _send_reaction(self, message_id: str, emoji_type: str) -> None:
        """给消息添加 reaction。"""
        try:
            request = (
                CreateMessageReactionRequest.builder()
                .message_id(message_id)
                .request_body(
                    CreateMessageReactionRequestBody.builder()
                    .reaction_type(
                        Emoji.builder().emoji_type(emoji_type).build()
                    )
                    .build()
                )
                .build()
            )
            response = self._client.im.v1.message_reaction.create(request)
            if not response.success():
                logger.warning(
                    "添加 reaction 失败: code=%s, msg=%s, message_id=%s",
                    response.code,
                    response.msg,
                    message_id,
                )
        except Exception:
            logger.warning(
                "添加 reaction 异常: message_id=%s", message_id, exc_info=True
            )

    # ------------------------------------------------------------------
    # 富文本转换
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_unicode_emoji(text: str) -> str:
        """移除文本中的 Unicode emoji 字符，避免飞书 post API 报错。"""
        return re.sub(
            r"[\U0001F300-\U0001FAFF"
            r"\U00002600-\U000027BF"
            r"\U0001F000-\U0001F02F"
            r"\U0001F0A0-\U0001F0FF"
            r"\U0001F100-\U0001F1FF"
            r"\u2600-\u26FF"
            r"\u2700-\u27BF"
            r"]+",
            "",
            text,
        )

    def _text_to_post(self, text: str) -> dict:
        """将纯文本（含 :EMOJI_TYPE: 占位符）转换为飞书 post 富文本结构。

        无效的 emoji_type 会降级为普通文本，避免飞书 API 报错。
        """
        paragraphs = []
        for line in text.split("\n"):
            line = self._strip_unicode_emoji(line)
            parts = re.split(r":([A-Z][A-Z0-9_a-z]*):", line)
            elements = []
            for i, part in enumerate(parts):
                if i % 2 == 0:
                    if part:
                        elements.append({"tag": "text", "text": part})
                else:
                    if part in _VALID_EMOJI_TYPES:
                        elements.append({"tag": "emotion", "emoji_type": part})
                    else:
                        elements.append({"tag": "text", "text": f":{part}:"})
            paragraphs.append(elements or [{"tag": "text", "text": ""}])

        return {"zh_cn": {"title": "", "content": paragraphs}}

    # ------------------------------------------------------------------
    # 启动
    # ------------------------------------------------------------------

    def start(self) -> None:
        """启动 WebSocket 客户端（阻塞调用）。"""
        # 为已订阅但无需业务处理的事件注册 no-op 处理器，
        # 避免 lark-oapi 收到事件时因 "processor not found" 打出 ERROR 日志。
        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self.handle_message)
            .register_p2_im_message_reaction_created_v1(lambda data: None)
            .register_p2_im_message_message_read_v1(lambda data: None)
            # 用户首次/重新打开与机器人的私聊窗口
            .register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(
                lambda data: None
            )
            # 机器人被拉入/移出群聊
            .register_p2_im_chat_member_bot_added_v1(lambda data: None)
            .register_p2_im_chat_member_bot_deleted_v1(lambda data: None)
            .build()
        )

        ws_client = lark.ws.Client(
            APP_ID,
            APP_SECRET,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        logger.info("正在启动飞书 WebSocket 长连接...")
        ws_client.start()
