"""
RepScan 分析引擎

核心功能：将用户反馈解码为"期待洞察"。
- 输入：一组 RawItem（用户反馈）
- 输出：InsightReport（优先满足什么期待 + 用户标签）
"""

from __future__ import annotations

import uuid
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from engine.analyzers.models import (
    RawItem,
    InsightReport,
    Insight,
    TaggedUser,
)

logger = logging.getLogger("repscan.analyzer")

# 加载通用标签模式
from engine.analyzers.analyzer_tag_patterns import TAG_PATTERNS


# ============================================================
#  配置
# ============================================================


@dataclass
class InsightConfig:
    """分析引擎配置 — 默认零依赖可用"""
    api_key: str = "mock"
    model: str = "mock"
    base_url: str = ""


# ============================================================
#  用户标签模式定义（Mock 模式用的规则字典）
# ============================================================


# ============================================================


# ============================================================
#  分析引擎
# ============================================================


class InsightEngine:
    """
    洞察分析引擎 — 将用户反馈解码为产品优化方向。

    工作模式：
    - Mock 模式（默认）：基于关键词模式匹配，零依赖可用
    - LLM 模式：配置后调用大模型，分析更精准
    """

    def __init__(self, config: Optional[InsightConfig] = None):
        self.config = config or InsightConfig()
        self._use_llm = config.api_key not in ("", "mock") if config else False

    async def analyze(self, items: List[RawItem]) -> InsightReport:
        """
        分析一组用户反馈，返回 InsightReport。

        Args:
            items: 用户反馈列表

        Returns:
            洞察报告
        """
        if self._use_llm:
            return await self._llm_analyze(items)
        else:
            return self._mock_analyze(items)

    def _mock_analyze(self, items: List[RawItem]) -> InsightReport:
        """Mock 模式：基于关键词模式匹配"""
        if not items:
            return InsightReport(
                report_id=str(uuid.uuid4()),
                total_inputs=0,
                summary="未收到任何用户反馈",
            )

        # 对每条反馈逐条处理
        tagged_items = []  # (insight_label, user_tag, content)
        all_tags = []
        pattern_hits = {p["label"]: [] for p in TAG_PATTERNS}

        for item in items:
            content_lower = item.content.lower()
            matched = False

            for pattern in TAG_PATTERNS:
                for rule in pattern["tag_rules"]:
                    if any(kw in content_lower for kw in rule["keywords"]):
                        pattern_hits[pattern["label"]].append(item)
                        tagged_items.append({
                            "label": pattern["label"],
                            "user_tag": rule["user_tag"],
                            "content": item.content,
                        })
                        all_tags.append(rule["user_tag"])
                        matched = True
                        break
                if matched:
                    break

            if not matched:
                # 未匹配的内容统一标记
                tagged_items.append({
                    "label": "其他",
                    "user_tag": "普通用户 👤",
                    "content": item.content,
                })
                all_tags.append("普通用户 👤")

        # 计算权重
        total = len(items)
        weights = {}
        for t in tagged_items:
            lbl = t["label"]
            weights[lbl] = weights.get(lbl, 0) + 1

        # 排序生成 insight 列表
        sorted_labels = sorted(weights.items(), key=lambda x: -x[1])
        max_count = max(c for _, c in sorted_labels) if sorted_labels else 1

        insights = []
        for rank, (label, count) in enumerate(sorted_labels, 1):
            pct = round(count / total * 100)
            # 找该 label 下的原始 pattern 定义
            pattern_def = next(
                (p for p in TAG_PATTERNS if p["label"] == label),
                {"user_expected": "", "actionable": ""},
            )
            # 收集该 label 的代表用户
            these_users = [t for t in tagged_items if t["label"] == label]
            # 去重，最多展示 5 个
            seen = set()
            unique_users = []
            for u in these_users:
                key = u["content"]
                if key not in seen:
                    seen.add(key)
                    unique_users.append(u)
                    if len(unique_users) >= 5:
                        break

            insights.append(Insight(
                rank=rank,
                label=label if label != "其他" else f"其他（{count}条未归类）",
                weight=pct,
                user_expected=pattern_def["user_expected"],
                actionable=pattern_def["actionable"],
                tagged_users=[
                    TaggedUser(content=u["content"], user_tag=u["user_tag"])
                    for u in unique_users
                ],
            ))

        # 标签密度统计
        density = {}
        for t in all_tags:
            density[t] = density.get(t, 0) + 1
        # 按数量降序
        density = dict(sorted(density.items(), key=lambda x: -x[1]))

        # 生成摘要
        top_labels = [i.label for i in insights[:3]]
        top_weights = [f"{i.label}({i.weight}%)" for i in insights[:3]]
        summary = (
            f"共分析 {total} 条用户反馈。"
            f"用户最关注的是：{' > '.join(top_weights)}"
        )

        return InsightReport(
            report_id=str(uuid.uuid4()),
            total_inputs=total,
            summary=summary,
            insights=insights,
            user_tags_density=density,
        )

    async def _llm_analyze(self, items: List[RawItem]) -> InsightReport:
        """LLM 模式（预留接口，需配置 API Key）"""
        try:
            from engine.analyzers.openai_adapter import InsightAnalyzer

            analyzer = InsightAnalyzer(
                api_key=self.config.api_key,
                model=self.config.model,
                base_url=self.config.base_url,
            )
            content_list = [item.content for item in items]
            result = await analyzer.analyze(content_list)
            report = InsightReport(
                report_id=str(uuid.uuid4()),
                total_inputs=len(items),
                summary=result.get("summary", ""),
                insights=[
                    Insight(
                        rank=i.get("rank", idx + 1),
                        label=i.get("label", ""),
                        weight=i.get("weight", 0),
                        user_expected=i.get("user_expected", ""),
                        actionable=i.get("actionable", ""),
                        tagged_users=[
                            TaggedUser(content=u.get("content", ""), user_tag=u.get("user_tag", ""))
                            for u in i.get("tagged_users", [])
                        ],
                    )
                    for idx, i in enumerate(result.get("insights", []))
                ],
                user_tags_density=result.get("user_tags_density", {}),
            )
            return report
        except Exception as e:
            logger.warning(f"LLM 分析失败，降级到 Mock 模式: {e}")
            return self._mock_analyze(items)
