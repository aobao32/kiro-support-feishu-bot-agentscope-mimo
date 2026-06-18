"""知识库工具模块。

提供知识库文件读取能力，供 Agent 按需调用以获取 Kiro 技术支持相关知识。

知识库采用「工具按需读取」方式：Agent 先从工具描述里看到有哪些 KB 文件
及其主题摘要，再根据用户问题决定读取哪个文件，避免一次性把全部知识塞进上下文。
"""

import os

from config import KB_DIR


def _scan_kb_files() -> list[tuple[str, str]]:
    """扫描知识库目录，返回 (文件名, 首行摘要) 列表。"""
    summaries: list[tuple[str, str]] = []
    if not os.path.isdir(KB_DIR):
        return summaries
    for fname in sorted(os.listdir(KB_DIR)):
        if not fname.endswith(".md"):
            continue
        filepath = os.path.join(KB_DIR, fname)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
        except Exception:
            first_line = "(无法读取摘要)"
        summaries.append((fname, first_line))
    return summaries


def build_kb_tool_description() -> str:
    """构建包含可用文件列表的工具描述。

    在创建 Agent 时调用，把当前 knowledge_base 目录下的文件清单及主题摘要
    动态注入到工具描述，方便模型判断该读哪个文件。
    """
    base = (
        "读取本地知识库 Markdown 文件内容，按需调用以获取特定主题的详细信息。"
        "回答 Kiro 相关问题时应优先查询知识库。\n\n可用文档:\n"
    )
    entries = _scan_kb_files()
    if entries:
        for fname, summary in entries:
            base += f"- {fname}: {summary}\n"
    else:
        base += "- (暂无可用文档)\n"
    base += "\nArgs:\n    filename: 知识库文件名，例如 KB_1.md"
    return base


def read_kb_file(filename: str) -> str:
    """读取知识库文件内容。

    Args:
        filename: 知识库文件名，例如 KB_1.md
    """
    # 防止路径穿越：只允许读取 KB_DIR 下的文件名
    safe_name = os.path.basename(filename)
    filepath = os.path.join(KB_DIR, safe_name)
    if not os.path.isfile(filepath):
        return f"错误: 知识库文件 '{safe_name}' 不存在。请检查文件名是否正确。"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"错误: 读取文件 '{safe_name}' 时发生异常: {e}"
