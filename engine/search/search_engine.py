"""
搜索引擎适配器

使用免费搜索引擎搜索公开平台的用户抱怨内容。
Phase 1: DuckDuckGo（免费，无需 API Key）
Phase 2: Google Custom Search / Brave Search API

搜索方式：site:domain.com keyword
支持的平台通过 site 语法在 DuckDuckGo 中搜索。
"""
from __future__ import annotations

import html
import json
import logging
import random
import re
import time
from typing import Dict, List, Optional

from engine.analyzers.models import RawItem

logger = logging.getLogger(__name__)

# 各平台对应的 site: 域名
PLATFORM_DOMAINS: Dict[str, List[str]] = {
    "weibo": ["weibo.com", "s.weibo.com"],
    "zhihu": ["zhihu.com"],
    "xiaohongshu": ["xiaohongshu.com"],
    "taobao": ["taobao.com"],
    "dianping": ["dianping.com"],
    "douyin": ["douyin.com"],
    "bilibili": ["bilibili.com"],
    "douban": ["douban.com"],
    "baidu_tieba": ["tieba.baidu.com"],
}

# DuckDuckGo HTML 搜索（无需 API Key）
DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"

# 各平台简称映射
PLATFORM_NAME_MAP: Dict[str, str] = {
    "微博": "weibo",
    "weibo": "weibo",
    "知乎": "zhihu",
    "zhihu": "zhihu",
    "小红书": "xiaohongshu",
    "xiaohongshu": "xiaohongshu",
    "淘宝": "taobao",
    "taobao": "taobao",
    "大众点评": "dianping",
    "dianping": "dianping",
    "抖音": "douyin",
    "douyin": "douyin",
    "B站": "bilibili",
    "bilibili": "bilibili",
    "豆瓣": "douban",
    "douban": "douban",
    "百度贴吧": "baidu_tieba",
    "baidu_tieba": "baidu_tieba",
}


class SearchEngine:
    """
    搜索引擎适配器

    使用 DuckDuckGo 搜索公开平台内容。
    零依赖 API Key，完全免费。

    用法:
        se = SearchEngine()
        results = await se.search("老孙水果", platform="小红书", max_results=10)
    """

    def __init__(self, timeout: int = 15):
        """
        初始化搜索引擎。

        Args:
            timeout: HTTP 请求超时（秒）
        """
        self.timeout = timeout
        self.user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        ]

    def _platform_to_domain(self, platform: str) -> List[str]:
        """将平台名称或 ID 转为域名列表"""
        key = PLATFORM_NAME_MAP.get(platform)
        if not key:
            return []
        return PLATFORM_DOMAINS.get(key, [])

    def _clean_ddg_result(self, text: str) -> str:
        """
        清理 DuckDuckGo 搜索结果中的 HTML 标签和多余内容。
        """
        text = re.sub(r'<[^>]+>', '', text)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    async def search(
        self,
        keyword: str,
        platform: Optional[str] = None,
        max_results: int = 10,
    ) -> List[RawItem]:
        """
        搜索公开平台的用户反馈内容。

        Args:
            keyword: 搜索关键词（如"老孙水果"）
            platform: 目标平台（如"xiaohongshu"、“小红书”），不传则搜全网
            max_results: 最大返回条数

        Returns:
            RawItem 列表
        """
        import httpx

        items: List[RawItem] = []

        # 构建 site: 查询
        query_parts = [keyword]
        if platform:
            domains = self._platform_to_domain(platform)
            if domains:
                # 同时搜索多个域名
                site_query = " OR ".join(f"site:{d}" for d in domains)
                query_parts.insert(0, f"({site_query})")
            platform_id = PLATFORM_NAME_MAP.get(platform, platform)
        else:
            platform_id = platform or ""

        query = " ".join(query_parts)

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                data = {
                    "q": query,
                }
                headers = {
                    "User-Agent": random.choice(self.user_agents),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                }

                resp = await client.post(
                    DUCKDUCKGO_URL,
                    data=data,
                    headers=headers,
                )

                if resp.status_code != 200:
                    logger.warning(f"DuckDuckGo 返回状态码 {resp.status_code}")
                    return items

                items = self._parse_ddg_results(resp.text, platform_id, keyword)

        except Exception as e:
            logger.warning(f"DuckDuckGo 搜索失败: {e}")
            # 搜索失败时返回空列表，上层会降级到 mock 数据

        return items[:max_results]

    def _parse_ddg_results(
        self,
        html_text: str,
        platform_id: str,
        keyword: str,
    ) -> List[RawItem]:
        """解析 DuckDuckGo HTML 搜索结果"""
        soup = None
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "lxml")
        except ImportError:
            # 纯正则兜底
            return self._parse_ddg_results_regex(html_text, platform_id)

        items: List[RawItem] = []
        # DuckDuckGo 结果卡片
        for result in soup.select(".result"):
            try:
                # 标题
                title_el = result.select_one(".result__title a")
                title = self._clean_ddg_result(title_el.get_text()) if title_el else ""

                # 链接
                url = ""
                if title_el and title_el.get("href"):
                    href = title_el["href"]
                    # DuckDuckGo 使用重定向链接
                    if "uddg=" in href:
                        import urllib.parse
                        parsed = urllib.parse.urlparse(href)
                        qs = urllib.parse.parse_qs(parsed.query)
                        url = qs.get("uddg", [""])[0]
                    else:
                        url = href

                # 摘要/内容
                snippet_el = result.select_one(".result__snippet")
                content = self._clean_ddg_result(snippet_el.get_text()) if snippet_el else title

                # 来源网站
                cite_el = result.select_one(".result__url")
                domain = cite_el.get_text(strip=True) if cite_el else ""

                if content and len(content) > 5:
                    # 尝试提取作者（从标题或内容中简单推断）
                    author = ""

                    items.append(RawItem(
                        content=content,
                        platform=platform_id or self._guess_platform(domain),
                        author=author,
                        title=title,
                        url=url,
                        created_at="",
                    ))

            except Exception:
                continue

        return items

    def _parse_ddg_results_regex(self, text: str, platform_id: str) -> List[RawItem]:
        """纯正则解析 DuckDuckGo 结果（兜底方案）"""
        items: List[RawItem] = []
        # 匹配结果卡片
        pattern = re.compile(
            r'<a rel="nofollow" class="result__a" href="([^"]+)".*?>(.*?)</a>'
            r'.*?<a class="result__snippet"[^>]*>(.*?)</a>',
            re.DOTALL,
        )

        for match in pattern.finditer(text):
            href = match.group(1)
            title = self._clean_ddg_result(match.group(2))
            snippet = self._clean_ddg_result(match.group(3))

            # 提取真实 URL
            url_match = re.search(r'uddg=([^&]+)', href)
            url = ""
            if url_match:
                import urllib.parse
                url = urllib.parse.unquote(url_match.group(1))
            else:
                url = href

            content = snippet or title
            if content:
                items.append(RawItem(
                    content=content,
                    platform=platform_id,
                    author="",
                    title=title,
                    url=url,
                    created_at="",
                ))

        return items

    @staticmethod
    def _guess_platform(domain: str) -> str:
        """从域名推测平台名"""
        domain = domain.lower()
        for name, domains in PLATFORM_DOMAINS.items():
            for d in domains:
                if d in domain:
                    return name
        return ""

    @staticmethod
    def list_supported_platforms() -> List[dict]:
        """返回支持的平台列表（用于 API 返回）"""
        return [
            {"id": "weibo", "name": "微博", "domain": "weibo.com"},
            {"id": "zhihu", "name": "知乎", "domain": "zhihu.com"},
            {"id": "xiaohongshu", "name": "小红书", "domain": "xiaohongshu.com"},
            {"id": "taobao", "name": "淘宝", "domain": "taobao.com"},
            {"id": "dianping", "name": "大众点评", "domain": "dianping.com"},
            {"id": "douyin", "name": "抖音", "domain": "douyin.com"},
            {"id": "bilibili", "name": "B站", "domain": "bilibili.com"},
            {"id": "douban", "name": "豆瓣", "domain": "douban.com"},
            {"id": "baidu_tieba", "name": "百度贴吧", "domain": "tieba.baidu.com"},
        ]


# ===================== 测试 =====================
if __name__ == "__main__":
    import asyncio

    async def test():
        se = SearchEngine()
        print("=" * 50)
        print("🔍 DuckDuckGo 搜索测试: site:xiaohongshu.com 老孙水果")
        print("=" * 50)
        results = await se.search("老孙水果 抱怨 差评", platform="小红书", max_results=5)
        print(f"找到 {len(results)} 条结果:\n")
        for r in results:
            print(f"  📌 [{r.platform}]")
            print(f"     标题: {r.title[:60] if r.title else '(无)'}")
            print(f"     内容: {r.content[:80]}...")
            if r.url:
                print(f"     🔗 {r.url}")
            print()

        print("=" * 50)
        print("🔍 DuckDuckGo 搜索测试: 全网搜索 ChatGPT 抱怨")
        print("=" * 50)
        results2 = await se.search("ChatGPT 不好用 抱怨", max_results=5)
        print(f"找到 {len(results2)} 条结果:\n")
        for r in results2:
            print(f"  📌 [{r.platform}] {r.title[:50]}")
            if r.content:
                print(f"     {r.content[:80]}...")

    asyncio.run(test())
