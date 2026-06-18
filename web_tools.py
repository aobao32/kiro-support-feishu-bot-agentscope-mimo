"""网络工具模块。

提供 Kiro 官方文档抓取和 GitHub Issues 搜索能力，作为知识库之外的补充知识来源。
两个函数均为普通同步函数，由 agentscope 的 FunctionTool 适配为工具。
"""

import json
import re
import urllib.parse
import urllib.request

from config import GITHUB_REPO, HTTP_TIMEOUT


def fetch_kiro_docs(url: str) -> str:
    """获取 Kiro 官方文档或社区页面内容（自动去除 HTML 标签，返回纯文本）。

    Args:
        url: 要获取的文档 URL，例如 https://kiro.dev/docs/troubleshooting/
    """
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "KiroSupportBot/1.0"},
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s{3,}", "\n\n", text)
        return text[:8000]
    except Exception as e:
        return f"获取文档失败: {e}"


def search_github_issues(query: str) -> str:
    """搜索 Kiro GitHub Issues，查找已知问题和解决方案。

    Args:
        query: 搜索关键词，支持中英文，例如 "login failed" 或 "登录失败"
    """
    search_url = (
        "https://api.github.com/search/issues"
        f"?q={urllib.parse.quote(query)}+repo:{GITHUB_REPO}"
        "&sort=relevance&per_page=5"
    )
    try:
        req = urllib.request.Request(
            search_url,
            headers={
                "User-Agent": "KiroSupportBot/1.0",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            data = json.loads(resp.read())
        items = data.get("items", [])
        if not items:
            return "未找到相关 Issues。"
        results = []
        for item in items:
            body = (item.get("body") or "")[:300]
            results.append(
                f"[{item['state'].upper()}] {item['title']}\n"
                f"  URL: {item['html_url']}\n"
                f"  {body}"
            )
        return "\n\n".join(results)
    except Exception as e:
        return f"搜索 GitHub Issues 失败: {e}"
