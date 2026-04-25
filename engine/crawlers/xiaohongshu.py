"""
小红书爬虫 - 使用公开搜索页面 + 浏览器模拟策略

小红书反爬严格（WAF、Sign 校验），Phase 1 采用:
  1. 首选: 通过 HTTPX 请求公开搜索页面（带 Cookie）
  2. 兜底: 提示用户使用 Playwright 浏览器方案

注意: 需要用户提供有效的 Cookie 才能正常工作。
"""

import json
import re
import asyncio
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from engine.base_crawler import BaseCrawler
from engine.analyzers.models import RawItem


class XiaohongshuCrawler(BaseCrawler):
    """
    小红书爬虫

    使用说明:
        由于小红书反爬严格，需要提供 Cookie:
        1. 在浏览器登录 xiaohongshu.com
        2. 打开开发者工具 (F12) → Network 标签
        3. 复制任意请求的 Cookie 值
        4. 设置: crawler.cookies = "your_cookie_string"
    """

    platform = "xiaohongshu"
    request_delay = 4.0  # 小红书频率限制更严格

    SEARCH_URL = "https://www.xiaohongshu.com/search_result"
    API_SEARCH = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"

    def __init__(self, cookies: str = ""):
        super().__init__()
        self._cookies = cookies

    @property
    def cookies(self) -> str:
        return self._cookies

    @cookies.setter
    def cookies(self, value: str):
        self._cookies = value

    def _build_headers(self, include_ajax: bool = False) -> dict:
        """构建请求头，可选添加 AJAX 相关头"""
        headers = self._random_headers()
        if self._cookies:
            headers["Cookie"] = self._cookies
        if include_ajax:
            headers.update(
                {
                    "Accept": "application/json, text/plain, */*",
                    "Origin": "https://www.xiaohongshu.com",
                    "Referer": "https://www.xiaohongshu.com/explore",
                    "X-Requested-With": "XMLHttpRequest",
                }
            )
        return headers

    async def search(self, keyword: str, limit: int = 20) -> list[RawItem]:
        """
        搜索小红书笔记

        策略:
        1. 先尝试 API 接口（EDITH）
        2. 如果 API 失败，尝试页面抓取
        3. 如果都失败，提示用户配置 Cookie

        Args:
            keyword: 搜索关键词
            limit: 最大返回条数

        Returns:
            list[RawItem]: 搜索结果列表
        """
        items = []

        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True
        ) as client:
            # 策略 1: API 搜索
            if self._cookies:
                try:
                    items = await self._api_search(client, keyword, limit)
                except Exception:
                    items = []

            # 策略 2: 页面抓取
            if not items:
                try:
                    items = await self._page_search(client, keyword, limit)
                except Exception:
                    items = []

            # 策略 3: 兜底 - 返回说明
            if not items:
                print(
                    "⚠️  小红书搜索无结果。请设置有效的 Cookie：\n"
                    "  crawler = XiaohongshuCrawler()\n"
                    "  crawler.cookies = 'your_cookie_here'\n"
                    "  或者使用 Playwright 浏览器方案。"
                )

        return items[:limit]

    async def get_comments(
        self, target_id: str, limit: int = 50
    ) -> list[RawItem]:
        """
        获取笔记评论 - 小红书评论 API 需要 Sign 签名

        Phase 1 暂未实现评论获取（需要逆向 Sign 算法或使用浏览器方案）
        后续版本会补充。

        Args:
            target_id: 笔记 ID
            limit: 最大返回条数

        Returns:
            list[RawItem]: 空列表（待实现）
        """
        # Phase 1: 待实现
        print("⚠️  小红书评论获取功能将在 Phase 2 实现（需要逆向 Sign 算法）")
        return []

    # ------------------------------------------------------------------ #
    #  内部方法 - API 搜索
    # ------------------------------------------------------------------ #

    async def _api_search(
        self, client: httpx.AsyncClient, keyword: str, limit: int
    ) -> list[RawItem]:
        """通过 EDITH API 搜索"""
        items = []
        cursor = ""
        page_size = min(20, limit)

        while len(items) < limit:
            payload = {
                "keyword": keyword,
                "page": len(items) // page_size + 1,
                "page_size": page_size,
                "search_id": "",
                "sort": "general",
                "note_type": 0,
            }
            if cursor:
                payload["cursor"] = cursor

            await self.rate_limiter.wait()

            try:
                resp = await client.post(
                    self.API_SEARCH,
                    json=payload,
                    headers=self._build_headers(include_ajax=True),
                )

                if resp.status_code != 200:
                    break

                data = resp.json()
                if data.get("success") is False:
                    break

                notes = data.get("data", {}).get("items", [])
                if not notes:
                    break

                for note in notes:
                    note_data = note.get("note_card", {}) or note
                    item = self._parse_api_note(note_data)
                    if item:
                        items.append(item)

                cursor = data.get("data", {}).get("cursor", "")
                if data.get("data", {}).get("has_more") is False:
                    break

            except (httpx.RequestError, httpx.TimeoutException, json.JSONDecodeError):
                await asyncio.sleep(10)
                break

        return items

    @staticmethod
    def _parse_api_note(note: dict) -> Optional[RawItem]:
        """解析 API 返回的笔记数据"""
        note_id = note.get("note_id", "")
        display_title = note.get("display_title", "")

        # 内容
        desc = note.get("desc", "") or ""

        # 作者
        user = note.get("user", {}) or {}
        author = user.get("nickname", "")

        # 时间
        time = note.get("time", "")
        if isinstance(time, (int, float)):
            import datetime
            time = datetime.datetime.fromtimestamp(time).strftime("%Y-%m-%d %H:%M")

        if not desc and not display_title:
            return None

        return RawItem(
            platform="xiaohongshu",
            content=desc or display_title,
            author=author,
            title=display_title,
            url=f"https://www.xiaohongshu.com/discovery/item/{note_id}",
            created_at=str(time),
        )

    # ------------------------------------------------------------------ #
    #  内部方法 - 页面搜索
    # ------------------------------------------------------------------ #

    async def _page_search(
        self, client: httpx.AsyncClient, keyword: str, limit: int
    ) -> list[RawItem]:
        """通过公开搜索页面抓取"""
        items = []

        params = {
            "source": "web_search_result_search",
            "keyword": keyword,
        }

        await self.rate_limiter.wait()

        try:
            resp = await client.get(
                self.SEARCH_URL,
                params=params,
                headers=self._build_headers(),
            )
            resp.raise_for_status()

            # 解析页面
            items = self._parse_search_page(resp.text)

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 429):
                print("⚠️  小红书页面搜索被限制，建议配置 Cookie 或使用浏览器方案")
            raise
        except (httpx.RequestError, httpx.TimeoutException):
            raise

        return items

    def _parse_search_page(self, html: str) -> list[RawItem]:
        """解析小红书搜索页面 HTML"""
        items = []

        # 方法 1: 查找内嵌的 window.__INITIAL_STATE__
        match = re.search(r"window\.__INITIAL_STATE__\s*=\s*({.*?});", html, re.DOTALL)
        if match:
            try:
                state = json.loads(match.group(1))
                note_list = state.get("searchResult", {}).get("notes", [])
                for note in note_list:
                    item = self._parse_api_note(note)
                    if item:
                        items.append(item)
            except (json.JSONDecodeError, AttributeError):
                pass

        # 方法 2: BeautifulSoup 解析
        if not items:
            soup = BeautifulSoup(html, "lxml")
            for card in soup.find_all("section", class_=re.compile(r"note-item|search-result-item")):
                try:
                    item = self._parse_card(card)
                    if item:
                        items.append(item)
                except Exception:
                    continue

        return items

    def _parse_card(self, card) -> Optional[RawItem]:
        """解析搜索结果卡片"""
        # 标题
        title = ""
        title_tag = card.find("a", class_=re.compile(r"title|note-title"))
        if title_tag:
            title = title_tag.get_text(strip=True)

        # 内容
        content = ""
        desc_tag = card.find("p", class_=re.compile(r"desc|note-desc"))
        if desc_tag:
            content = desc_tag.get_text(strip=True)

        # 作者
        author = ""
        author_tag = card.find("a", class_=re.compile(r"author|user|name"))
        if author_tag:
            author = author_tag.get_text(strip=True)

        # 链接
        url = ""
        link_tag = card.find("a", href=re.compile(r"/discovery/item/"))
        if link_tag:
            href = link_tag.get("href", "")
            url = f"https://www.xiaohongshu.com{href}" if href.startswith("/") else href

        # 时间 - 小红书页面上通常没有直接展示，跳过

        if not content and not title:
            return None

        return RawItem(
            platform=self.platform,
            content=content or title,
            author=author,
            title=title,
            url=url,
            created_at="",
        )


# =========================== 本地测试 ===========================
if __name__ == "__main__":

    async def test():
        crawler = XiaohongshuCrawler()
        print("=" * 50)
        print("🔍 测试小红书搜索: keyword='不好用 吐槽'")
        print("=" * 50)
        print("📌 提示: 如果没有 Cookie 可能无结果\n")

        # 可以在这里设置 Cookie 进行测试：
        # crawler.cookies = "your_cookie_here"

        try:
            results = await crawler.search("不好用 吐槽", limit=5)
            print(f"  找到 {len(results)} 条结果:\n")
            for r in results:
                print(f"  [{r.author}] {r.title or '(无标题)'}")
                print(f"  {r.content[:80]}...")
                print(f"  链接: {r.url}\n")
        except Exception as e:
            print(f"  ❌ 搜索出错: {e}")

    asyncio.run(test())
