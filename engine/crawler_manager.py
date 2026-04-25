"""爬虫管理器 — 管理所有数据源注册与调用"""

from typing import Optional
from engine.analyzers.models import RawItem

# 手动适配器和 Mock 生成器不需要 Playwright
from engine.crawlers.manual_input import ManualInputAdapter, MockDataGenerator

# 浏览器爬虫（需 playwright 环境）
try:
    from engine.crawlers.browser_crawler import BrowserCrawler
    HAS_BROWSER = True
except ImportError:
    HAS_BROWSER = False


class CrawlerManager:
    """爬虫管理器 - 注册表模式"""

    def __init__(self, browser_cookies: str = ""):
        self._browser_cookies = browser_cookies
        self._manual = ManualInputAdapter()
        self._mock = MockDataGenerator()
        self._browser: Optional[object] = None
        if HAS_BROWSER and browser_cookies:
            self._init_browser_crawler(browser_cookies)

    def _init_browser_crawler(self, cookies: str):
        """初始化浏览器爬虫"""
        pass  # 暂不使用，跳过

    # ------------------------------------------------------------------ #
    #  数据入口
    # ------------------------------------------------------------------ #

    def add_manual_text(
        self, text: str, source: str = "manual", author: str = "用户"
    ) -> RawItem:
        """添加手动输入的文本"""
        return self._manual.from_text(text, source, author)

    def add_manual_batch(
        self, texts: list[str], source: str = "manual"
    ) -> list[RawItem]:
        """批量添加手动输入"""
        return self._manual.from_batch(texts, source)

    def get_mock_data(self, count: int = 12) -> list[RawItem]:
        """获取模拟测试数据"""
        data = self._mock.generate_product_complaints()
        return data[:count]

    def get_mock_service_data(self) -> list[RawItem]:
        """获取服务类模拟数据"""
        return self._mock.generate_service_complaints()

    # ------------------------------------------------------------------ #
    #  可用数据源查询
    # ------------------------------------------------------------------ #

    @staticmethod
    def available_sources() -> list[dict]:
        """返回当前可用的数据源列表"""
        sources = [
            {
                "id": "manual",
                "name": "手动输入",
                "status": "ready",
                "description": "手动粘贴抱怨文本",
            },
            {
                "id": "mock",
                "name": "测试数据",
                "status": "ready",
                "description": "内置测试数据（演示用）",
            },
        ]

        if HAS_BROWSER:
            sources.extend([
                {
                    "id": "weibo",
                    "name": "微博",
                    "status": "needs_login",
                    "description": "s.weibo.com（需 Cookie）",
                },
                {
                    "id": "zhihu",
                    "name": "知乎",
                    "status": "needs_login",
                    "description": "zhihu.com（需登录）",
                },
                {
                    "id": "xiaohongshu",
                    "name": "小红书",
                    "status": "needs_login",
                    "description": "xiaohongshu.com（需 Cookie）",
                },
            ])
        else:
            sources.extend([
                {
                    "id": "weibo",
                    "name": "微博",
                    "status": "needs_playwright",
                    "description": "需安装 Playwright",
                },
                {
                    "id": "zhihu",
                    "name": "知乎",
                    "status": "needs_playwright",
                    "description": "需安装 Playwright",
                },
                {
                    "id": "xiaohongshu",
                    "name": "小红书",
                    "status": "needs_playwright",
                    "description": "需安装 Playwright",
                },
            ])

        return sources


# =========================== 测试 ===========================
if __name__ == "__main__":
    mgr = CrawlerManager()

    print("=== 可用数据源 ===")
    for s in mgr.available_sources():
        status_emoji = {"ready": "✅", "needs_login": "🔒", "needs_playwright": "⚠️"}.get(s["status"], "❓")
        print(f"  {status_emoji} {s['name']} ({s['id']}): {s['description']}")

    print("\n=== 手动输入测试 ===")
    item = mgr.add_manual_text("这产品太差了，用了一周就坏了", "taobao")
    print(f"  {item.platform} | {item.content} | @{item.author}")

    print("\n=== Mock数据测试 ===")
    data = mgr.get_mock_data(5)
    for d in data:
        print(f"  [{d.platform}] @{d.author}: {d.content[:40]}...")
