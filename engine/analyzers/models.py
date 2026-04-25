"""
RepScan 数据模型

核心哲学：
  每一次反馈，都是一次未被满足的期待。

不再关注情感正负面，而是：
  用户说了什么（意图） → 背后是什么期待（解码） → 应该做什么（行动）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional


# ============================================================
#  原始输入
# ============================================================


@dataclass
class RawItem:
    """原始输入项 — 用户说的一句话/一段反馈"""
    content: str  # 反馈内容（必要）
    platform: str = ""  # 来源：小红书/淘宝/客服记录等
    author: str = "用户"
    title: str = ""
    url: str = ""
    created_at: str = ""
    extra: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "platform": self.platform,
            "author": self.author,
            "title": self.title,
            "url": self.url,
            "created_at": self.created_at,
        }


# ============================================================
#  分析输出
# ============================================================


@dataclass
class TaggedUser:
    """带标签的用户反馈"""
    content: str  # 用户原话
    user_tag: str  # 用户标签（eg. 品质控 🔍）


@dataclass
class Insight:
    """一条用户洞察"""
    rank: int  # 优先级排序
    label: str  # 洞察标签（eg. 新鲜度）
    weight: float  # 关注度占比 (%) 0-100
    user_expected: str  # 解码后：用户真正想要的是什么
    actionable: str  # 可执行建议：你应该做什么
    tagged_users: List[TaggedUser]  # 代表用户（原始反馈）


@dataclass
class InsightReport:
    """洞察报告 — 取代旧的 AnalysisReport"""
    report_id: str
    task_id: str = ""
    total_inputs: int = 0  # 输入总数
    summary: str = ""  # 一句话概括
    insights: List[Insight] = field(default_factory=list)
    user_tags_density: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """序列化为字典（JSON 友好）"""
        return {
            "report_id": self.report_id,
            "task_id": self.task_id,
            "total_inputs": self.total_inputs,
            "summary": self.summary,
            "insights": [
                {
                    "rank": i.rank,
                    "label": i.label,
                    "weight": i.weight,
                    "user_expected": i.user_expected,
                    "actionable": i.actionable,
                    "tagged_users": [
                        {"content": u.content, "user_tag": u.user_tag}
                        for u in i.tagged_users
                    ],
                }
                for i in self.insights
            ],
            "user_tags_density": self.user_tags_density,
        }

    def agent_summary(self) -> dict:
        """给 Agent 快速阅读的摘要"""
        top = self.insights[:3] if self.insights else []
        return {
            "summary": self.summary,
            "total_inputs": self.total_inputs,
            "top_concerns": [{"label": i.label, "weight": f"{i.weight}%"} for i in top],
            "user_tags_density": self.user_tags_density,
        }
