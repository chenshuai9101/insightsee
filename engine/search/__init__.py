"""
RepScan 搜索引擎模块

Phase 1: DuckDuckGo（免费，无需 API Key）
Phase 2: Google Custom Search / Brave Search（付费）

用法:
    from engine.search import SearchEngine
    se = SearchEngine()
    results = await se.search("关键词", platform="小红书")
"""

from .search_engine import SearchEngine, PLATFORM_DOMAINS, PLATFORM_NAME_MAP

__all__ = ["SearchEngine", "PLATFORM_DOMAINS", "PLATFORM_NAME_MAP"]
