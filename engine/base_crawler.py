"""
RepScan 爬虫引擎 - 基础接口定义
所有平台爬虫必须继承 BaseCrawler 并实现 search 和 get_comments 方法。

RawItem 统一从 engine.analyzers.models 导入。
"""
from __future__ import annotations

import asyncio
import random

from .analyzers.models import RawItem


class RateLimiter:
    """频率限制器 - 每次请求前按随机间隔等待"""

    def __init__(self, min_delay: float = 2.0, max_delay: float = 5.0):
        self.min_delay = min_delay
        self.max_delay = max_delay

    async def wait(self):
        """随机等待 min_delay ~ max_delay 秒"""
        delay = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)


class BaseCrawler:
    """
    爬虫基类 - 所有平台爬虫必须继承此类

    子类必须设置：
        platform: str        # 平台名称
        request_delay: float # 请求间隔（秒）
    """

    platform: str = "base"
    request_delay: float = 3.0

    def __init__(self):
        self.rate_limiter = RateLimiter(
            min_delay=max(2.0, self.request_delay * 0.7),
            max_delay=max(5.0, self.request_delay * 1.3),
        )
        # 预设 5 组随机 User-Agent
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        ]

    def _random_headers(self) -> dict:
        """生成随机请求头"""
        import random as _random
        return {
            "User-Agent": _random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }

    async def search(self, keyword: str, limit: int = 20) -> list[RawItem]:
        """
        搜索关键词，返回帖子列表

        Args:
            keyword: 搜索关键词
            limit: 最大返回条数

        Returns:
            list[RawItem]: 搜索结果列表
        """
        raise NotImplementedError

    async def get_comments(self, target_id: str, limit: int = 50) -> list[RawItem]:
        """
        获取帖子/回答的评论列表

        Args:
            target_id: 帖子 ID 或 URL
            limit: 最大返回条数

        Returns:
            list[RawItem]: 评论列表
        """
        raise NotImplementedError
