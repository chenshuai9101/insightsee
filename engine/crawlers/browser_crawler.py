"""
通用浏览器爬虫 - 使用 Playwright 自动化
作为一个通用引擎，统一处理微博/知乎/小红书的搜索爬取
"""

import re
import json
import random
import asyncio
from typing import Optional

from bs4 import BeautifulSoup

from engine.base_crawler import BaseCrawler
from engine.analyzers.models import RawItem


class BrowserCrawler(BaseCrawler):
    """
    通用浏览器爬虫

    使用 Playwright 浏览器自动化，绕过主流中文社交平台的反爬机制。
    每个平台配置独立的搜索 URL 和解析逻辑。

    Phase 1 支持: 知乎（无需登录）、微博（建议带 Cookie）、小红书（需 Cookie）
    """

    platform = "browser"
    request_delay = 1.0

    PLATFORMS = {
        "zhihu": {
            "search": "https://www.zhihu.com/search?type=content&q={keyword}",
            "needs_login": False,
        },
        "weibo": {
            "search": "https://s.weibo.com/weibo?q={keyword}",
            "needs_login": True,  # 需 Cookie
        },
        "xiaohongshu": {
            "search": "https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_search",
            "needs_login": True,  # 需 Cookie
        },
    }

    def __init__(self, cookies: str = "", platform: str = "zhihu"):
        super().__init__()
        self._cookies = cookies
        self._target_platform = platform
        self._browser = None
        self._context = None
        self._page = None

    def set_platform(self, platform: str):
        """切换到指定平台"""
        if platform not in self.PLATFORMS:
            raise ValueError(f"不支持的平台: {platform}，可选: {list(self.PLATFORMS.keys())}")
        self._target_platform = platform

    def set_cookies(self, cookies: str):
        """设置浏览器 Cookie"""
        self._cookies = cookies

    async def _ensure_browser(self):
        """启动/复用浏览器实例"""
        if self._browser is None:
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
            # 注入 Cookie
            if self._cookies:
                await self._context.add_cookies(self._parse_cookies(self._cookies))
            self._page = await self._context.new_page()
        return self._page

    async def _cleanup(self):
        """关闭浏览器"""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if hasattr(self, '_pw') and self._pw:
            await self._pw.stop()

    async def search(self, keyword: str, limit: int = 20) -> list[RawItem]:
        """
        在目标平台搜索关键词

        Args:
            keyword: 搜索关键词
            limit: 最大返回条数

        Returns:
            list[RawItem]: 搜索结果
        """
        platform_info = self.PLATFORMS.get(self._target_platform)
        if not platform_info:
            return []

        url = platform_info["search"].format(keyword=keyword)
        page = await self._ensure_browser()

        print(f"  [BrowserCrawler] 访问 {self._target_platform}: {url}")

        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            # 等待初始渲染完成
            await asyncio.sleep(random.uniform(3, 5))

            # 滚动加载
            for _ in range(3):
                await page.evaluate('window.scrollBy(0, 800)')
                await asyncio.sleep(1)

            html = await page.content()
            items = self._parse_content(html)

            if not items:
                # 检查是否是登录拦截
                page_text = await page.inner_text('body')
                if any(kw in page_text for kw in ['登录', '扫码', '验证', 'login', 'Login']):
                    print(f"  ⚠️  {self._target_platform} 需要登录，当前无有效 Cookie")
                    # 返回提示 RawItem
                    items = [
                        RawItem(
                            platform=self._target_platform,
                            content=f"[{self._target_platform} 需要登录才能搜索] 请提供有效的 Cookie",
                            author="system",
                            title="需要登录",
                            url=url,
                            created_at="",
                        )
                    ]

        except Exception as e:
            print(f"  [BrowserCrawler] 搜索出错: {e}")
            items = []
        finally:
            await self._cleanup()

        return items[:limit]

    async def get_comments(self, target_url: str, limit: int = 30) -> list[RawItem]:
        """获取指定页面的评论"""
        page = await self._ensure_browser()

        try:
            await page.goto(target_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(random.uniform(3, 5))

            # 滚动加载评论
            for _ in range(5):
                await page.evaluate('window.scrollBy(0, 500)')
                await asyncio.sleep(1)

            html = await page.content()
            items = self._parse_comments(html)

        except Exception as e:
            print(f"  [BrowserCrawler] 获取评论出错: {e}")
            items = []
        finally:
            await self._cleanup()

        return items[:limit]

    # ------------------------------------------------------------------ #
    #  解析逻辑
    # ------------------------------------------------------------------ #

    def _parse_content(self, html: str) -> list[RawItem]:
        """根据当前平台解析页面内容"""
        parse_map = {
            "zhihu": self._parse_zhihu_search,
            "weibo": self._parse_weibo_search,
            "xiaohongshu": self._parse_xiaohongshu_search,
        }
        parser = parse_map.get(self._target_platform, self._parse_generic)
        return parser(html)

    def _parse_zhihu_search(self, html: str) -> list[RawItem]:
        """解析知乎搜索结果"""
        soup = BeautifulSoup(html, "lxml")
        items = []

        # 方法1: 查找搜索结果卡片
        for card in soup.find_all('div', class_=re.compile(r'List-item|SearchItem|css-')) + \
                     soup.find_all('div', attrs={'data-za-module': 'SearchResultItem'}):
            try:
                title_el = card.find('a', class_=re.compile(r'title|ContentItem')) or card.find('h2')
                title = title_el.get_text(strip=True) if title_el else ''

                # 内容
                content = ''
                for selector in ['span.RichText', 'div.RichContent-inner', 'p[class]', 'div[class*=Content]']:
                    el = card.select_one(selector)
                    if el and len(el.get_text(strip=True)) > 10:
                        content = el.get_text(strip=True)
                        break
                if not content:
                    content = card.get_text(' ', strip=True)[:200]

                # 链接
                url = ''
                link = card.find('a', href=re.compile(r'/question/'))
                if link:
                    href = link.get('href', '')
                    url = href if href.startswith('http') else f'https://www.zhihu.com{href}'

                # 作者
                author = ''
                author_el = card.find('meta', attrs={'itemprop': 'name'}) or \
                            card.find('a', class_=re.compile(r'Author|UserLink|name'))
                if author_el:
                    author = author_el.get('content', '') or author_el.get_text(strip=True)

                if title or content:
                    items.append(RawItem(
                        platform='zhihu',
                        content=content or title,
                        author=author,
                        title=title,
                        url=url,
                        created_at='',
                    ))
            except Exception:
                continue

        return items

    def _parse_weibo_search(self, html: str) -> list[RawItem]:
        """解析微博搜索结果"""
        soup = BeautifulSoup(html, "lxml")
        items = []

        # s.weibo.com 新版
        for card in soup.find_all('div', class_=re.compile(r'card')) + \
                     soup.find_all('div', attrs={'action-type': 'feed_list_item'}):
            try:
                content = ''
                content_el = card.find('p', class_=re.compile(r'txt')) or card.select_one('p[node-type]')
                if content_el:
                    content = content_el.get_text(strip=True)
                if not content:
                    content = card.get_text(' ', strip=True)

                author = ''
                author_el = card.find('a', class_=re.compile(r'name'))
                if author_el:
                    author = author_el.get_text(strip=True)

                url = ''
                time_el = card.find('a', class_=re.compile(r'date'))
                if time_el:
                    url = time_el.get('href', '')
                    if url and not url.startswith('http'):
                        url = f'https:{url}' if url.startswith('//') else f'https://weibo.com{url}'

                if content and len(content) > 5:
                    items.append(RawItem(
                        platform='weibo',
                        content=content,
                        author=author,
                        title=content[:50],
                        url=url,
                        created_at='',
                    ))
            except Exception:
                continue

        return items

    def _parse_xiaohongshu_search(self, html: str) -> list[RawItem]:
        """解析小红书搜索结果"""
        items = []

        # 尝试提取 __INITIAL_STATE__
        match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html, re.DOTALL)
        if match:
            try:
                state = json.loads(match.group(1))
                notes = state.get('searchResult', {}).get('notes', [])
                for note in notes:
                    note_card = note.get('note_card', {}) or note
                    items.append(RawItem(
                        platform='xiaohongshu',
                        content=note_card.get('desc', note_card.get('display_title', '')),
                        author=note_card.get('user', {}).get('nickname', ''),
                        title=note_card.get('display_title', ''),
                        url=f"https://www.xiaohongshu.com/discovery/item/{note_card.get('note_id', '')}",
                        created_at='',
                    ))
            except (json.JSONDecodeError, AttributeError):
                pass

        # 兜底：BS4
        if not items:
            soup = BeautifulSoup(html, "lxml")
            for card in soup.find_all('section', class_=re.compile(r'note-item')):
                try:
                    title = card.find('a', class_=re.compile(r'title'))
                    items.append(RawItem(
                        platform='xiaohongshu',
                        content=card.get_text(' ', strip=True)[:200],
                        author='',
                        title=title.get_text(strip=True) if title else '',
                        url='',
                        created_at='',
                    ))
                except Exception:
                    continue

        return items

    def _parse_generic(self, html: str) -> list[RawItem]:
        """通用解析 - 提取页面文字"""
        soup = BeautifulSoup(html, "lxml")
        items = []

        for tag in soup.find_all(['article', 'section', 'div'], class_=re.compile(r'content|article|post|item')):
            text = tag.get_text(' ', strip=True)
            if text and len(text) > 20:
                items.append(RawItem(
                    platform=self._target_platform,
                    content=text[:200],
                    author='',
                    title='',
                    url='',
                    created_at='',
                ))

        return items[:20]

    def _parse_comments(self, html: str) -> list[RawItem]:
        """通用评论解析"""
        soup = BeautifulSoup(html, "lxml")
        items = []

        for comment_el in soup.find_all(['div', 'li', 'span'], class_=re.compile(r'comment|reply|Review|review')):
            text = comment_el.get_text(strip=True)
            if text and len(text) > 5:
                items.append(RawItem(
                    platform=self._target_platform,
                    content=text,
                    author='',
                    title='',
                    url='',
                    created_at='',
                ))

        return items

    def _parse_cookies(self, cookie_str: str) -> list[dict]:
        """将 Cookie 字符串解析为 Playwright 格式"""
        cookies = []
        for part in cookie_str.split(';'):
            part = part.strip()
            if '=' in part:
                name, value = part.split('=', 1)
                cookies.append({
                    'name': name.strip(),
                    'value': value.strip(),
                    'domain': f'.{self._target_platform}.com',
                    'path': '/',
                })
        return cookies


# =========================== 测试 ===========================
if __name__ == "__main__":
    async def test():
        crawler = BrowserCrawler(platform="zhihu")

        print("=" * 50)
        print("🔍 测试知乎搜索 (不用登录): keyword='手机 不好用 抱怨'")
        print("=" * 50)
        results = await crawler.search("手机 不好用 抱怨", limit=5)
        print(f"\n  找到 {len(results)} 条:")
        for r in results:
            print(f"\n  📌 [{r.author}] {r.title}")
            if r.content:
                print(f"     {r.content[:100]}")
            if r.url:
                print(f"     🔗 {r.url}")

        print("\n" + "=" * 50)
        print("🔍 测试微博搜索 (需要登录, 预期提醒)")
        print("=" * 50)
        crawler.set_platform("weibo")
        results = await crawler.search("水果 差", limit=3)
        for r in results:
            print(f"  {r.content[:100]}")

    asyncio.run(test())
