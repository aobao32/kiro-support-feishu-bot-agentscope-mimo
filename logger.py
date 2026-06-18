"""日志模块。

提供统一的日志配置：
- 终端输出（StreamHandler）
- 按日期滚动的文件日志（TimedRotatingFileHandler），受 ENABLE_FILE_LOG 控制
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler

from config import ENABLE_FILE_LOG, LOG_DIR

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"


def get_logger(name: str) -> logging.Logger:
    """获取配置好的 logger 实例。

    Args:
        name: logger 名称，通常传入 __name__。

    Returns:
        配置好 handler 的 Logger 实例。
    """
    logger = logging.getLogger(name)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    # 不向 root logger 冒泡，避免第三方库重复输出
    logger.propagate = False

    formatter = logging.Formatter(LOG_FORMAT)

    # 终端输出
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # 按日期滚动的文件日志
    if ENABLE_FILE_LOG:
        os.makedirs(LOG_DIR, exist_ok=True)
        file_handler = TimedRotatingFileHandler(
            filename=os.path.join(LOG_DIR, "agent.log"),
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
