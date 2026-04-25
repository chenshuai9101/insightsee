#!/bin/bash
# RepScan Cron 监控脚本 — 每日口碑检查
#
# OpenClaw cron 配置（复制到 openclaw.json cron 配置处）:
#
#   {
#     "name": "每日口碑监控-老孙水果",
#     "schedule": {"expr": "0 8 * * *", "tz": "Asia/Shanghai"},
#     "payload": {
#       "kind": "agentTurn",
#       "message": "运行口碑检查：调用 repscan API (http://localhost:8000/api/search) 搜索关键词'老孙水果' 平台'小红书' max_results=10，分析结果并用中文总结给我看。重点关注负面反馈、问题归因和紧急程度。"
#     },
#     "sessionTarget": "isolated",
#     "delivery": {"mode": "announce"}
#   }
#
# --- 或者直接使用 bash 独立调用 ---
# 以下为直接用 cron 调 API 并把结果发到你的 Telegram 或保存文件

set -e

API_URL="${1:-http://localhost:8000}"
KEYWORD="${2:-老孙水果}"
PLATFORM="${3:-小红书}"
MAX_RESULTS="${4:-10}"

# 调用 API
echo "🔍 正在搜索: $KEYWORD 在 $PLATFORM ..."
RESPONSE=$(curl -s -X POST "$API_URL/api/search" \
  -H "Content-Type: application/json" \
  -d "{\"keyword\": \"$KEYWORD\", \"platform\": \"$PLATFORM\", \"max_results\": $MAX_RESULTS}")

# 提取摘要
VERDICT=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['report']['agent_summary']['verdict'])" 2>/dev/null || echo "解析失败")
URGENCY=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['report']['urgency_level'])" 2>/dev/null || echo "未知")

echo "========================================"
echo "  RepScan 每日口碑报告"
echo "  关键词: $KEYWORD"
echo "  平台:   $PLATFORM"
echo "  时间:   $(date '+%Y-%m-%d %H:%M')"
echo "========================================"
echo ""
echo "📊 $VERDICT"
echo "⚡ 紧急程度: $URGENCY"
echo ""
echo "完整报告: $API_URL/docs"
