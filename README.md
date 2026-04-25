# 🔍 InsightSee — User Demand Decoding Engine

> **🏢 InsightLabs — Agent 原生互联网基础设施**  
> MIT · 免费 · 开源  
> 📦 [InsightBrowser](https://github.com/chenshuai9101/insightbrowser) · [InsightLens](https://github.com/chenshuai9101/insightlens) · [InsightSee](https://github.com/chenshuai9101/insightsee) · [InsightHub](https://github.com/chenshuai9101/insighthub)  
> ☕ 如果对你有帮助，欢迎捐赠 → assets/ 有收款码

---

Turn user feedback into structured insights. 884 keywords, 18 industries, zero dependencies.

InsightSee decodes user expectations from raw feedback — not sentiment analysis, but real demand extraction. Built for agents, by an agent.

## Features

- **884 keywords** across 6 demand dimensions, 18 industries
- **9 user tag types**: quality-seeker, price-sensitive, at-risk, etc.
- **Zero external dependencies**: no numpy, no torch, no transformers
- **18,000-line pattern library**: `analyzer_tag_patterns.py`
- **Mock mode ready**: works without LLM, perfectly offline
- **API server**: REST API on port 9090

## Quick Start

```bash
python3 -m pip install -r requirements.txt
python3 api_server.py
# → http://localhost:9090
```

## API

- `POST /api/insight` — Analyze feedback texts, returns InsightReport
- `POST /api/analyze` — Raw analysis results per item
- `GET /api/health` — Server status

## Industry Coverage

| Industry | Coverage | Industry | Coverage |
|----------|----------|----------|----------|
| Aviation | 99.5% | Social | 99.2% |
| Home | 93.0% | Ride-hailing | 91.9% |
| SaaS | 91.9% | Government | 90.2% |
| Video | 89.8% | Fitness | 87.1% |
| E-commerce | 86.7% | Railway | 83.3% |
| Property | 81.5% | Logistics | 81.0% |
| Insurance | 77.3% | Banking | 76.5% |
| Food delivery | 75.1% | Hotel | 74.1% |
| Gaming | 72.7% | Online edu | 71.0% |

## License

MIT
