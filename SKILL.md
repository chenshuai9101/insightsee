---
name: insightsee
description: |
  洞察眼 (InsightSee) — 用户需求解码器。
  
  把用户反馈（客服记录/评论/问卷/吐槽）解码成「用户到底想要什么」。
  不是情感分析，不是抱怨雷达，是读懂期待。
---

# 👁️ 洞察眼 InsightSee

> **用户每次反馈，都是一次未被满足的期待。**

InsightSee 是一个**开箱即用的用户需求洞察引擎**。
它不分析情感正负面，而是解码用户的**期待信号**：
- 用户说"太慢了" → **期待交付效率**
- 用户说"不划算" → **期待价格匹配**
- 用户说"要走人了" → **期待挽回**

## 🎯 一句话

**输入：** 用户反馈文本（批量或单条）
**输出：** 优先满足用户什么期待 + 用户是属于哪类人

## ✨ 核心能力

| 能力 | 说明 |
|:---|:------|
| **6大需求阵营** | 品质体验 / 交付效率 / 价格感知 / 服务沟通 / 体验细节 / 流失风险 |
| **9种用户画像** | 品质控🔍 / 急用客户⚡ / 价格敏感型💰 / 不满意客户😤 / 满意客户😊 / 怕麻烦型😩 / 注重体验✨ / 即将流失⚠️ |
| **覆盖18行业** | 电商/外卖/银行/航空/健身/教育/酒店/网约车/家装/保险/游戏/视频/快递/SaaS/物业/铁路/社交/政务 |
| **处理速度** | ~25万条/秒（无需GPU，CPU即可） |
| **无需训练** | 内置884关键词，Mock模式立即可用 |
| **零外部依赖** | 纯Python标准库，不调API，不下载模型 |

## 🚀 使用方式

### 方式一：Python SDK（推荐）

```python
from engine.analyzers.models import RawItem
from engine.analyzers.analyzer import InsightEngine, InsightConfig
import asyncio

# 1. 创建引擎（Mock模式，立即可用）
engine = InsightEngine(InsightConfig("mock", "mock"))

# 2. 输入用户反馈
items = [
    RawItem(content="商品质量太差了，用了几天就坏了"),
    RawItem(content="价格还可以，物流也挺快的"),
]

# 3. 解码
result = asyncio.run(engine.analyze(items))

# 4. 看结果
print(result.summary)
# → "用户最关注的是：品质体验(50%) > 交付效率(50%)"

for insight in result.insights:
    print(f"[{insight.label}] {insight.weight}%的用户")
    print(f"    期待: {insight.user_expected}")
    print(f"    建议: {insight.actionable}")
```

### 方式二：REST API

```bash
# 启动API服务
python3 api_server.py

# 提交分析
curl -X POST localhost:9090/analyze \
  -H "Content-Type: application/json" \
  -d '{"items": [{"content": "质量太差了"}]}'

# 查看所有端点
curl localhost:9090/
```

### 方式三：脚本一键运行

```bash
bash scripts/start.sh
# 启动后访问 http://localhost:9090/docs
```

## 🏗️ 包结构

```
insightsee-skill/
├── SKILL.md                  ← 你在这里
├── api_server.py             ← REST API 服务
├── LLM_CONFIG.md             ← LLM扩展配置
├── requirements.txt          ← 仅用于API扩展
├── assets/
│   ├── wechat_pay.jpg        ← 微信打赏码
│   └── alipay.jpg            ← 支付宝打赏码
├── engine/                   ← 核心引擎
│   ├── analyzers/
│   │   ├── __init__.py
│   │   ├── models.py         ← 数据模型
│   │   ├── analyzer.py       ← 分析引擎（核心）
│   │   ├── analyzer_tag_patterns.py ← 884关键词自动生成
│   │   ├── prompts.py        ← LLM提示词模板
│   │   └── openai_adapter.py ← LLM适配层
│   ├── search/               ← 搜索引擎
│   └── crawlers/             ← 爬虫（可扩展）
└── scripts/
    ├── start.sh              ← 一键启动
    ├── build-skill.sh        ← 构建打包
    └── cron-monitor.sh       ← 定时监控
```

## 🆚 与传统方案对比

| 场景 | 传统NLP方案 | 洞察眼 InsightSee |
|:---|:----------|:----------------|
| 启动时间 | 半天~3天(配GPU/下载模型/训练) | **1分钟** |
| 外部依赖 | TF/PyTorch/jieba/numpy/scikit-learn | **零**（纯Python标准库） |
| 联网需求 | 必须下载模型和词向量 | **离线可用** |
| 覆盖行业 | 单一行业语料 | **18行业开箱即用** |
| 处理速度 | 需GPU推理 | **25万条/秒 CPU** |
| 可解释性 | 黑盒模型 | **每条匹配可追溯** |
| 定制成本 | 重新训练 | **改词库即可** |

## 🛠️ 扩展

### 增加新行业的关键词

编辑 `engine/analyzers/industry_terms.py`，添加行业特有词汇后重新生成：

```bash
python3 engine/analyzers/generate_patterns.py
```

### 接入LLM增强（可选）

看 `LLM_CONFIG.md`，支持 OpenAI/Claude/DeepSeek 等。

## ☕ 支持作者

如果 InsightSee 帮你省了时间，欢迎打赏一杯咖啡 ☕

| 微信 | 支付宝 |
|:---:|:-----:|
| ![wechat](assets/wechat_pay.jpg) | ![alipay](assets/alipay.jpg) |

## 📜 许可证

MIT License — 随意商用，备注来源即可。
