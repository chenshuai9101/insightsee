"""
知乎爬虫 - 使用 Playwright 浏览器自动化绕过反爬
"""

import re
import random
import asyncio
from typing import Optional

from bs4 import BeautifulSoup

from engine.base_crawler import BaseCrawler
from engine.analyzers.models import RawItem


class ZhihuCrawler(BaseCrawler):
    """知乎爬虫 - 基于 Playwright 浏览器自动化"""

    platform = "zhihu"
    request_delay = 1.0

    SEARCH_URL = "https://www.zhihu.com/search?type=content&q={keyword}"

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
        """搜索知乎内容"""
        items = []
        page = await self._ensure_browser()

        try:
            url = self.SEARCH_URL.format(keyword=keyword)
            print(f"  [知乎] 访问: {url}")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(random.uniform(3, 5))

            # 滚动
            for _ in range(3):
                await page.evaluate('window.scrollBy(0, 800)')
                await asyncio.sleep(1)

            html = await page.content()
            items = self._parse_search_page(html)

        except Exception as e:
            print(f"  [知乎] 搜索出错: {e}")
        finally:
            await self._cleanup()

        return items[:limit]

    async def get_comments(self, target_id: str, limit: int = 50) -> list[RawItem]:
        """获取知乎回答的评论"""
        page = await self._ensure_browser()
        items = []

        try:
            answer_id = self._extract_answer_id(target_id)
            if answer_id:
                url = f"https://www.zhihu.com/answer/{answer_id}"
            else:
                url = target_id

            await page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(random.uniform(3, 5))

            # 滚动加载评论
            for _ in range(5):
                await page.evaluate('window.scrollBy(0, 500)')
                await asyncio.sleep(1)

            # 尝试展开评论
            try:
                view_all = await page.query_selector('button:has-text("查看全部评论")')
                if view_all:
                    await view_all.click()
                    await asyncio.sleep(2)
            except Exception:
                pass

            html = await page.content()
            items = self._parse_comment_page(html)

        except Exception as e:
            print(f"  [知乎] 获取评论出错: {e}")
        finally:
            await self._cleanup()

        return items[:limit]

    # ------------------------------------------------------------------ #
    #  解析方法
    # ------------------------------------------------------------------ #

    def _parse_search_page(self, html: str) -> list[RawItem]:
        """解析知乎搜索页"""
        soup = BeautifulSoup(html, "lxml")
        items = []

        # 最新知乎版式：data-za-module 标记
        cards = soup.find_all('div', attrs={'data-za-module': 'SearchResultItem'})
        if not cards:
            cards = soup.find_all('div', class_=re.compile(r'List-item|SearchResult'))

        for card in cards:
            try:
                item = self._parse_card(card)
                if item:
                    items.append(item)
            except Exception:
                continue

        return items

    def _parse_card(self, card) -> Optional[RawItem]:
        """解析单个搜索结果卡片"""
        title = ''
        title_el = card.find('a', attrs={'data-za-detail-view-element_name': 'Title'}) \
                   or card.find('h2') or card.find('strong')
        if title_el:
            title = title_el.get_text(strip=True)

        content = ''
        content_el = card.find('span', class_=re.compile(r'RichText|CommentContent')) \
                     or card.find('div', class_=re.compile(r'ContentItem|Summary'))
        if content_el:
            content = content_el.get_text(strip=True)

        author = ''
        author_el = card.find('meta', attrs={'itemprop': 'name'}) \
                     or card.find('a', class_=re.compile(r'Author|UserLink'))
        if author_el:
            author = author_el.get_text(strip=True)

        url = ''
        url_el = title_el if title_el and title_el.name == 'a' else None
        if not url_el:
            url_el = card.find('a', href=re.compile(r'/question/'))
        if url_el:
            href = url_el.get('href', '')
            url = href if href.startswith('http') else f'https://www.zhihu.com{href}'

        if not content and not title:
            return None

        return RawItem(
            platform=self.platform,
            content=content or title,
            author=author,
            title=title,
            url=url,
            created_at='',
        )

    def _parse_comment_page(self, html: str) -> list[RawItem]:
        """解析知乎评论页"""
        soup = BeautifulSoup(html, "lxml")
        items = []

        comments = soup.find_all('div', class_=re.compile(r'CommentItem|CommentContent'))
        for c in comments:
            text = c.get_text(strip=True)
            if text and len(text) > 2:
                items.append(RawItem(
                    platform=self.platform,
                    content=text,
                    author='',
                    title='',
                    url='',
                    created_at='',
                ))

        return items

    @staticmethod
    def _extract_answer_id(target: str) -> Optional[str]:
        """提取回答 ID"""
        if re.match(r'^\d+$', target):
            return target
        m = re.search(r'zhihu\.com/question/\d+/answer/(\d+)', target)
        if m:
            return m.group(1)
        m = re.search(r'answer/(\d+)', target)
        if m:
            return m.group(1)
        return None


# =========================== 测试 ===========================
if __name__ == "__main__":
    async def test():
        crawler = ZhihuCrawler()
        print("=" * 50)
        print("🔍 测试知乎搜索: keyword='手机 不好用'")
        print("=" * 50)
        results = await crawler.search("手机 不好用", limit=5)
        print(f"  找到 {len(results)} 条:")
        for r in results:
            print(f"  [{r.author}] {r.title}")
            if r.content:
                print(f"  {r.content[:60]}")
    asyncio.run(test())
