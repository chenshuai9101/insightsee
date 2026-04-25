"""
Prompt 模板模块

所有 LLM Prompt 集中管理，便于后续优化和国际化。
"""

# ============================================================
# 情感分类 + 问题分类 + 紧急程度 + 摘要（聚合分析）
# ============================================================

# 系统指令：定义 AI 角色和行为
SYSTEM_PROMPT = """你是一个专业的中文舆情分析专家。你的任务是对用户评论进行多维度分析。

分析维度：
1. **情感分类**：判断每条评论的情感倾向（正面/负面/中性）
2. **问题分类**：对于负面评论，归因到具体问题类型
3. **紧急程度**：评估整体紧急程度
4. **摘要生成**：提炼趋势摘要和关键发现

请严格按 JSON 格式输出，不要额外解释。"""

# 情感倾向的可选值
SENTIMENT_OPTIONS = ["positive", "negative", "neutral"]

# 问题分类的可选值（用于负面评论）
CATEGORY_OPTIONS = [
    "产品质量",
    "服务态度",
    "价格",
    "配送",
    "售后",
    "其他",
]

# 紧急程度可选值
URGENCY_OPTIONS = ["high", "medium", "low"]


def build_analysis_prompt(items_text: str) -> list[dict]:
    """
    构建完整分析 Prompt。

    Args:
        items_text: 格式化后的评论列表文本

    Returns:
        包含 system 和 user 消息的列表
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""分析以下用户评论的情感倾向、问题分类、紧急程度。

评论列表：
{items_text}

请输出 JSON 格式（不要包含 markdown 代码块标记，直接返回纯 JSON）：
{{
  "sentiments": [
    {{"index": 0, "sentiment": "positive|negative|neutral", "score": 0.95, "reason": "情感判断理由（中文）", "category": "问题分类（仅负面评论需要，其他为空字符串）"}},
    ...
  ],
  "summary": "整体趋势一句话摘要（中文）",
  "key_findings": ["关键发现1（中文）", "关键发现2（中文）"],
  "urgency_level": "high|medium|low",
  "urgency_reason": "紧急程度判断理由（中文）"
}}""",
        },
    ]


def format_items(items: list) -> str:
    """
    将原始数据列表格式化为 Prompt 中的文本块。

    Args:
        items: RawItem 列表

    Returns:
        格式化后的文本字符串
    """
    lines = []
    for i, item in enumerate(items):
        content = item.content.strip().replace("\n", " ")
        platform = item.platform or "未知平台"
        author = item.author or "匿名"
        lines.append(f"[{i}] 平台={platform}, 用户={author}: {content}")
    return "\n".join(lines)


def build_retry_prompt(error_message: str, raw_output: str) -> list[dict]:
    """
    当 LLM 输出不符合 JSON 格式时，构建修正 Prompt。

    Args:
        error_message: 解析错误信息
        raw_output: LLM 原始输出

    Returns:
        修正 Prompt 消息列表
    """
    return [
        {
            "role": "user",
            "content": f"""你之前返回的格式有误，需要重新输出。

错误信息：{error_message}

你之前的输出：
{raw_output}

请只输出合法的 JSON 对象（不要代码块标记），严格按照以下格式：
{{
  "sentiments": [
    {{"index": 0, "sentiment": "positive|negative|neutral", "score": 0.95, "reason": "...", "category": "..."}},
    ...
  ],
  "summary": "...",
  "key_findings": ["...", "..."],
  "urgency_level": "high|medium|low",
  "urgency_reason": "..."
}}""",
        },
    ]
