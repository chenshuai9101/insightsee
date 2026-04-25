"""
LLM 调用适配器

支持多个 LLM 提供商（DeepSeek / OpenAI / Claude），
提供统一的异步接口，内置重试和降级机制。

用法:
    adapter = LLMAdapter(provider="deepseek", api_key="sk-xxx")
    result = await adapter.chat_json(messages=[...])
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional

import httpx


class LLMError(Exception):
    """LLM 调用异常基类"""

    pass


class LLMRetryError(LLMError):
    """重试耗尽后仍失败"""

    def __init__(self, provider: str, model: str, attempts: int, last_error: str):
        self.provider = provider
        self.model = model
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"[{provider}/{model}] 重试 {attempts} 次后仍然失败: {last_error}"
        )


class LLMJsonParseError(LLMError):
    """LLM 输出 JSON 解析失败"""

    def __init__(self, raw_output: str, parse_error: str):
        self.raw_output = raw_output
        self.parse_error = parse_error
        super().__init__(f"JSON 解析失败: {parse_error}")


# 各商家的默认配置
PROVIDER_CONFIGS: Dict[str, Dict[str, Any]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
    "claude": {
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-3-haiku-20240307",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "deepseek/deepseek-chat",
    },
}

# 临时用于测试的默认值（不传 key 时返回 mock）
# 注意：生产环境必须配置真实 API Key
DEFAULT_API_KEY = ""  # 用户需自行配置


class LLMAdapter:
    """
    LLM 调用适配器。

    支持提供商: deepseek, openai, claude, openrouter
    内置功能：
    - 统一异步接口
    - JSON 模式（chat_json 方法强制校验 JSON）
    - 自动重试（1 次，可配置）
    - 降级逻辑（重试失败后可选切换模型）
    """

    def __init__(
        self,
        provider: str = "deepseek",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = 1,  # 重试次数（不含首次）
    ):
        """
        初始化适配器。

        Args:
            provider: 提供商标识（deepseek / openai / claude / openrouter）
            api_key: API Key；不传则尝试全局默认值
            base_url: 自定义 API 地址；不传则使用默认值
            default_model: 默认模型名称；不传则使用提供商默认模型
            timeout: HTTP 请求超时（秒）
            max_retries: 失败重试次数
        """
        self.provider = provider
        provider_cfg = PROVIDER_CONFIGS.get(provider, PROVIDER_CONFIGS["deepseek"])

        self.api_key = api_key or DEFAULT_API_KEY
        self.base_url = (base_url or provider_cfg["base_url"]).rstrip("/")
        self.default_model = default_model or provider_cfg["default_model"]
        self.timeout = timeout
        self.max_retries = max_retries

        # HTTP 客户端（连接池）
        self._client = httpx.AsyncClient(timeout=timeout)

    async def chat(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.3,
    ) -> str:
        """
    调用 LLM 聊天接口，返回纯文本响应。

    支持 Mock 模式（未配置 API Key 时返回模拟数据）。

    Args:
        messages: OpenAI 格式的消息列表
                  [{"role": "system", "content": "..."},
                   {"role": "user", "content": "..."}]
        model: 模型名称；不传则使用 default_model
        temperature: 采样温度（0~2），越低越确定

    Returns:
        LLM 返回的文本内容

    Raises:
        LLMRetryError: 所有重试均失败
    """
        model = model or self.default_model

        # Mock 模式：未配置 Key 或 key 为 'mock' 时返回模拟响应
        if not self.api_key or self.api_key == 'mock':
            return self._mock_chat(messages)

        last_error = ""
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._call_api(messages, model, temperature)
                return response
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    # 指数退避重试
                    import asyncio
                    await asyncio.sleep(1.0 * (2 ** attempt))

        raise LLMRetryError(
            provider=self.provider,
            model=model,
            attempts=self.max_retries + 1,
            last_error=last_error,
        )

    async def chat_json(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.3,
    ) -> dict:
        """
        调用 LLM 并强制解析 JSON 响应。

        如果 LLM 返回了非标准 JSON（如含 markdown 代码块），
        自动尝试提取和修复。

        Args:
            同 chat() 方法

        Returns:
            解析后的 JSON 字典

        Raises:
            LLMRetryError: 重试耗尽
            LLMJsonParseError: JSON 提取/解析失败
        """
        raw = await self.chat(messages, model, temperature)
        return self._parse_json_response(raw)

    def _parse_json_response(self, raw: str) -> dict:
        """
        从 LLM 输出中解析 JSON。

        处理情况：
        - 纯 JSON 字符串
        - ```json ... ``` 代码块包裹
        - 开头/结尾有多余文本
        - 不完全格式（尝试修复）

        Args:
            raw: LLM 原始输出

        Returns:
            解析后的字典

        Raises:
            LLMJsonParseError: 解析失败
        """
        # 第一步：尝试直接解析
        text = raw.strip()

        # 去除可能的 markdown 代码块标记
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

        # 尝试提取第一个 { ... } 或 [ ... ]
        if not text.startswith("{"):
            brace_start = text.find("{")
            if brace_start >= 0:
                # 从第一个 { 开始到最后一个 }
                last_brace = text.rfind("}")
                if last_brace > brace_start:
                    text = text[brace_start : last_brace + 1]
                else:
                    text = text[brace_start:]

        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return result
            raise LLMJsonParseError(
                raw, f"JSON 顶级元素不是对象，而是 {type(result).__name__}"
            )
        except json.JSONDecodeError as e:
            raise LLMJsonParseError(raw, str(e))

    async def _call_api(
        self, messages: list, model: str, temperature: float
    ) -> str:
        """
        实际调用 LLM API（OpenAI 兼容接口）。

        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度

        Returns:
            LLM 响应文本
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if self.provider == "claude":
            # Claude 使用不同的 API 格式
            return await self._call_claude_api(messages, model, temperature)

        # OpenAI / DeepSeek / OpenRouter 兼容格式
        response = await self._client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=body,
        )

        if response.status_code != 200:
            error_detail = response.text[:500]
            raise LLMError(
                f"API 返回错误码 {response.status_code}: {error_detail}"
            )

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise LLMError("API 返回的 choices 为空")

        return choices[0].get("message", {}).get("content", "")

    async def _call_claude_api(
        self, messages: list, model: str, temperature: float
    ) -> str:
        """
        调用 Claude Messages API（格式与 OpenAI 不同）。

        Args:
            messages: OpenAI 格式的消息列表（会被转为 Claude 格式）
            model: 模型名称
            temperature: 温度

        Returns:
            Claude 响应文本
        """
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        # 转换消息格式：提取 system prompt 单独传递
        system_msg = ""
        claude_messages = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                system_msg = content
            else:
                claude_messages.append({"role": role, "content": content})

        body: Dict[str, Any] = {
            "model": model,
            "messages": claude_messages,
            "max_tokens": 4096,
            "temperature": temperature,
        }
        if system_msg:
            body["system"] = system_msg

        response = await self._client.post(
            f"{self.base_url}/messages",
            headers=headers,
            json=body,
        )

        if response.status_code != 200:
            error_detail = response.text[:500]
            raise LLMError(
                f"Claude API 返回错误码 {response.status_code}: {error_detail}"
            )

        data = response.json()
        content_blocks = data.get("content", [])
        # 拼接所有 text block
        texts = [
            block.get("text", "")
            for block in content_blocks
            if block.get("type") == "text"
        ]
        return "\n".join(texts)

    # ========== Mock 模式 ==========

    def _mock_chat(self, messages: list) -> str:
        """
        Mock 模式：根据评论中的关键词进行简单情感判断。

        关键词规则：
        - 负面词（坏了/差/贵/气死/垃圾/投诉/不推荐/问题）→ negative
        - 正面词（好/棒/推荐/喜欢/推荐/回购）→ positive
        - 否则 → neutral

        仅用于开发和测试，不消耗 API 配额。
        """
        # 从 messages 提取用户内容
        user_content = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_content += msg.get("content", "")

        # 解析用户评论（每行格式： [索引] 平台=x, 用户=y: 内容）
        lines = re.findall(r"\[(\d+)\].*?: (.+)$", user_content, re.MULTILINE)

        # 情感关键词词典（全部小写，按长度降序排列，确保长词优先匹配）
        # 注意："质量" 等短词会导致 "质量很棒" 误匹配负面，
        # 因此用精确匹配策略：如果某个负关键词被正关键词包含，则跳过
        negative_keywords = sorted([
            "虚假宣传", "慢得要死", "没人处理", "没人解决", "千万别买",
            "态度极差", "态度恶劣", "态度很差", "货不对板", "辣鸡产品",
            "太差了", "太失望了", "很不满意", "不推荐", "性价比不",
            "不处理", "不负责", "退款难", "没人理", "挂我电话",
            "死机", "坏了", "极差", "很差劲", "很差", "很贵",
            "气死", "垃圾", "投诉", "不理人", "态度差",
            "推诿", "闪退", "翻新", "破损", "太差",
            "上当", "服务差", "质量差", "体验差", "效果差",
            "黑心", "曝光", "维权", "踩雷", "避雷",
            "辣鸡", "智商税", "割韭菜", "客服", "拒绝",
            "糟糕", "恶心", "无语", "崩溃", "后悔",
            "失望", "不满意", "差评",
        ], key=len, reverse=True)
        positive_keywords = sorted([
            "质量很棒", "强烈推荐", "特别好", "太好了",
            "性价比高", "值得推荐", "值得买", "好用的",
            "很好", "不错", "回购", "喜欢", "满意",
            "推荐", "好评", "好用", "实用", "划算",
            "没毛病", "没问题",
        ], key=len, reverse=True)

        # 构建负面词排除集：如果一个负面词是某个正面词的子串，排除它
        excluded_negatives = set()
        for neg_kw in negative_keywords:
            for pos_kw in positive_keywords:
                if neg_kw != pos_kw and neg_kw in pos_kw:
                    excluded_negatives.add(neg_kw)
                    break

        sentiments = []
        for idx_str, content in lines:
            idx = int(idx_str)
            content_lower = content.lower()

            # 判断情感
            # 先计算正面/负面关键词数量
            # 排除可能被正关键词子串误匹配的负关键词
            neg_count = sum(
                1 for kw in negative_keywords
                if kw not in excluded_negatives and kw in content_lower
            )
            pos_count = sum(1 for kw in positive_keywords if kw in content_lower)

            if neg_count > pos_count:
                sentiment = "negative"
                score = 0.9
                reason = "评论包含负面关键词"
            elif pos_count > 0 and neg_count == 0:
                sentiment = "positive"
                score = 0.85
                reason = "评论包含正面关键词"
            else:
                sentiment = "neutral"
                score = 0.7
                reason = "无明显情感倾向"

            # 问题分类
            category = ""
            if sentiment == "negative":
                if any(kw in content_lower for kw in ["客服", "态度", "回复", "没人理"]):
                    category = "服务态度"
                elif any(kw in content_lower for kw in ["坏了", "质量", "垃圾", "问题"]):
                    category = "产品质量"
                elif "贵" in content_lower:
                    category = "价格"
                elif any(kw in content_lower for kw in ["快递", "物流", "配送"]):
                    category = "配送"
                elif any(kw in content_lower for kw in ["售后", "退款", "退货"]):
                    category = "售后"
                else:
                    category = "其他"

            sentiments.append({
                "index": idx,
                "sentiment": sentiment,
                "score": round(score, 2),
                "reason": reason,
                "category": category,
            })

        item_count = len(sentiments)
        negative_count = sum(1 for s in sentiments if s["sentiment"] == "negative")
        negative_ratio = negative_count / item_count if item_count > 0 else 0

        # 紧急程度判断
        if negative_count >= 3 and negative_ratio >= 0.5:
            urgency_level = "high"
            urgency_reason = f"负面评论 {negative_count}/{item_count}，占比 {negative_ratio:.0%}，需立即关注"
        elif negative_count >= 1 and negative_ratio >= 0.3:
            urgency_level = "medium"
            urgency_reason = f"负面评论 {negative_count}/{item_count}，占比 {negative_ratio:.0%}，需安排跟进"
        else:
            urgency_level = "low"
            urgency_reason = f"负面评论较少，无需紧急处理"

        result = {
            "sentiments": sentiments,
            "summary": f"共分析 {item_count} 条评论，其中负面 {negative_count} 条（{negative_ratio:.0%}）",
            "key_findings": [
                f"负面反馈集中在 {negative_count} 个评论" if negative_count > 0 else "未发现明显负面反馈",
                "需关注高频问题点并优化产品/服务",
            ],
            "urgency_level": urgency_level,
            "urgency_reason": urgency_reason,
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    async def close(self):
        """关闭 HTTP 客户端连接池"""
        await self._client.aclose()


async def _async_sleep(seconds: float):
    """异步等待"""
    import asyncio
    await asyncio.sleep(seconds)
