# RepScan LLM 配置指南

RepScan 默认使用**关键词匹配**模式（零依赖，免费无需 API Key），
分析质量够用但不完美（无法理解讽刺、上下文语气）。

如果希望提升分析质量，可配置 LLM 模式。
**LLM 模式完全可选，不强制。**

## 配置方式

启动前设置环境变量：

```bash
# OpenAI / DeepSeek / Claude / OpenRouter 均支持
export REPSCAN_LLM_API_KEY="sk-your-key-here"
export REPSCAN_LLM_MODEL="deepseek-chat"    # 默认模型名
export REPSCAN_LLM_BASE_URL="https://api.deepseek.com"  # 可选，默认 OpenAI
```

## 支持的模型

| 服务商 | 推荐模型 | BASE_URL |
|--------|----------|----------|
| DeepSeek | deepseek-chat | https://api.deepseek.com |
| OpenAI | gpt-4o-mini | https://api.openai.com/v1 |
| Claude | claude-3-haiku | https://api.anthropic.com |
| OpenRouter | deepseek/deepseek-chat | https://openrouter.ai/api/v1 |
| 本地 Ollama | 任意模型 | http://localhost:11434/v1 |

## 在 OpenClaw 中配置

编辑 `openclaw.json`:

```json
{
  "skills": {
    "repscan": {
      "env": {
        "REPSCAN_LLM_API_KEY": "sk-xxx",
        "REPSCAN_LLM_MODEL": "deepseek-chat",
        "REPSCAN_LLM_BASE_URL": "https://api.deepseek.com"
      }
    }
  }
}
```

配置过一次后，Agent 会自动读取并使用 LLM 分析，无需用户手动操作。

## 不配置会怎样？

**完全不影响使用。** 关键词匹配模式已经能覆盖 80%+ 的常见抱怨场景。
LLM 模式属于"锦上添花"——理解讽刺、反话、隐含抱怨时更精准。

但所有核心功能（搜索+分析+文件上传+归因+紧急度判断）在免费模式下均可用。
