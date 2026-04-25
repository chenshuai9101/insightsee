"""
微博爬虫 - 使用 Playwright 浏览器自动化绕过反爬
"""

import re
import random
import asyncio
from typing import Optional

from bs4 import BeautifulSoup

from engine.base_crawler import BaseCrawler
from engine.analyzers.models import RawItem


class WeiboCrawler(BaseCrawler):
    """微博爬虫 - 基于 Playwright 浏览器自动化"""

    platform = "weibo"
    request_delay = 1.0  # 浏览器模式不需要长延迟

    SEARCH_URL = "https://s.weibo.com/weibo?q={keyword}"

    async def _ensure_browser(self):
        """确保浏览器实例"""
        if not hasattr(self, '_browser') or self._browser is None:
            from playwright.async_api import async_playwright
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                ]
            )
            self._context = await self._browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 800},
                locale='zh-CN',
            )
            self._page = await self._context.new_page()
        return self._page

    async def _cleanup(self):
        """清理浏览器资源"""
        if hasattr(self, '_browser') and self._browser:
            await self._browser.close()
        if hasattr(self, '_pw') and self._pw:
            await self._pw.stop()
        self._browser = None
        self._context = None
        self._page = None

    async def search(self, keyword: str, limit: int = 20) -> list[RawItem]:
        """搜索微博帖子 - 使用浏览器自动化"""
        items = []
        page = await self._ensure_browser()

        try:
            url = self.SEARCH_URL.format(keyword=keyword)
            print(f"  [微博] 访问: {url}")
            await page.goto(url, wait_until='networkidle', timeout=30000)

            # 等待搜索结果加载
            await asyncio.sleep(random.uniform(2, 4))

            # 滚动以触发懒加载
            for _ in range(3):
                await page.evaluate('window.scrollBy(0, 1000)')
                await asyncio.sleep(1)

            # 获取页面内容
            html = await page.content()
            items = self._parse_search_page(html)

            # 如果不够，翻页
            page_num = 2
            while len(items) < limit:
                try:
                    # 点击下一页
                    next_btn = await page.query_selector('a.next')
                    if not next_btn:
                        break
                    await next_btn.click()
                    await asyncio.sleep(random.uniform(2, 4))
                    html = await page.content()
                    new_items = self._parse_search_page(html)
                    if not new_items:
                        break
                    items.extend(new_items)
                    page_num += 1
                except Exception:
                    break

        except Exception as e:
            print(f"  [微博] 搜索出错: {e}")
        finally:
            await self._cleanup()

        return items[:limit]

    async def get_comments(self, target_id: str, limit: int = 50) -> list[RawItem]:
        """获取微博评论"""
        page = await self._ensure_browser()
        items = []

        try:
            # 尝试构建评论页 URL
            post_id = self._extract_post_id(target_id)
            if post_id:
                url = f"https://weibo.com/ajax/statuses/buildComments?is_reload=1&id={post_id}&is_show_bulletin=2&max_id=0"
            else:
                url = target_id if target_id.startswith('http') else f"https://weibo.com/{target_id}"

            await page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(random.uniform(2, 3))

            html = await page.content()
            items = self._parse_comment_page(html)

        except Exception as e:
            print(f"  [微博] 获取评论出错: {e}")
        finally:
            await self._cleanup()

        return items[:limit]

    # ------------------------------------------------------------------ #
    #  解析方法
    # ------------------------------------------------------------------ #

    def _parse_search_page(self, html: str) -> list[RawItem]:
        """解析微博 s.weibo.com 搜索页"""
        soup = BeautifulSoup(html, "lxml")
        items = []

        # s.weibo.com 搜索结果卡片
        for card in soup.find_all('div', attrs={'action-type': 'feed_list_item'}):
            try:
                item = self._parse_feed_card(card)
                if item:
                    items.append(item)
            except Exception:
                continue

        # 兜底：查找所有 card-wrap
        if not items:
            for card in soup.find_all('div', class_=re.compile(r'card-wrap|Card|WB_card')):
                try:
                    item = self._parse_feed_card(card)
                    if item:
                        items.append(item)
                except Exception:
                    continue

        return items

    def _parse_feed_card(self, card) -> Optional[RawItem]:
        """解析单条微博卡片"""
        # 内容
        content = ''
        content_el = card.find('p', class_='txt') or card.find('p', class_=re.compile(r'node_text'))
        if content_el:
            content = content_el.get_text(strip=True)

        # 作者
        author = ''
        author_el = card.find('a', class_='name') or card.find('a', class_=re.compile(r'name|W_text'))
        if author_el:
            author = author_el.get_text(strip=True)

        # 时间和链接
        created_at = ''
        url = ''
        time_el = card.find('a', class_=re.compile(r'date|time'))
        if time_el:
            created_at = time_el.get_text(strip=True)
            url = time_el.get('href', '')
            if url and not url.startswith('http'):
                url = 'https://weibo.com' + url

        if not content:
            return None

        return RawItem(
            platform=self.platform,
            content=content,
            author=author,
            title=content[:50],
            url=url,
            created_at=created_at,
        )

    def _parse_comment_page(self, html: str) -> list[RawItem]:
        """解析微博评论页"""
        soup = BeautifulSoup(html, "lxml")
        items = []

        for card in soup.find_all('div', class_='WB_text'):
            try:
                content = card.get_text(strip=True)
                if content and len(content) > 2:
                    items.append(RawItem(
                        platform=self.platform,
                        content=content,
                        author='',
                        title='',
                        url='',
                        created_at='',
                    ))
            except Exception:
                continue

        return items

    @staticmethod
    def _extract_post_id(url_or_id: str) -> Optional[str]:
        """从 ID 或 URL 中提取微博 post ID"""
        if re.match(r'^\d+$', url_or_id):
            return url_or_id
        m = re.search(r'weibo\.com/\d+/([A-Za-z0-9]+)', url_or_id)
        if m:
            return m.group(1)
        m = re.search(r'weibo\.cn/comment/([A-Za-z0-9]+)', url_or_id)
        if m:
            return m.group(1)
        return url_or_id


# =========================== 测试 ===========================
if __name__ == "__main__":
    async def test():
        crawler = WeiboCrawler()
        print("=" * 50)
        print("🔍 测试微博搜索: keyword='水果'")
        print("=" * 50)
        results = await crawler.search("水果", limit=5)
        print(f"  找到 {len(results)} 条:")
        for r in results:
            print(f"  [{r.author}] {r.content[:60]}")
        print()
        print("  备注: 浏览器模式可能请求 s.weibo.com，需要网络正常")
    asyncio.run(test())
