#!/bin/bash
# RepScan 启动脚本
#
# 用法:
#   bash scripts/start.sh [--api-only]
#
# 选项:
#   --api-only    仅启动 API 服务（不启动 Web UI，推荐 Agent 使用）
#   无参数        全栈启动（API + Web UI）

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
API_ONLY=false

# 参数解析
for arg in "$@"; do
    case "$arg" in
        --api-only) API_ONLY=true ;;
    esac
done

echo "================================"
echo "  RepScan 抱怨雷达 🎯"
echo "================================"

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ 需要 Python3"
    exit 1
fi

# 安装 Python 依赖
echo "📦 检查并安装 Python 依赖..."
if [ -f "$BASE_DIR/requirements.txt" ]; then
    pip3 install -q -r "$BASE_DIR/requirements.txt" 2>/dev/null || true
fi

# 启动后端
echo "🚀 启动 API 服务 (http://localhost:8000)..."
cd "$BASE_DIR"
nohup python3 api_server.py > /tmp/repscan-api.log 2>&1 &
API_PID=$!
echo "  API PID: $API_PID"

sleep 2

# 检查 API 是否启动成功
if kill -0 $API_PID 2>/dev/null; then
    echo "  ✅ API 服务已启动"
else
    echo "  ❌ API 服务启动失败，查看日志: cat /tmp/repscan-api.log"
    exit 1
fi

# Web UI（仅在非 --api-only 时启动）
if [ "$API_ONLY" = false ]; then
    if command -v node &> /dev/null && [ -f "$BASE_DIR/web/package.json" ]; then
        echo "📦 检查前端依赖..."
        cd "$BASE_DIR/web"
        if [ ! -d "node_modules" ]; then
            npm install --silent 2>/dev/null || true
        fi

        echo "🚀 启动 Web UI (http://localhost:5173)..."
        nohup npx vite --host --port 5173 > /tmp/repscan-web.log 2>&1 &
        WEB_PID=$!
        echo "  Web PID: $WEB_PID"
    else
        echo "⚠️  Node.js 不可用或前端文件不完整，跳过 Web UI"
    fi
fi

echo ""
echo "================================"
echo "  ✅ RepScan 启动完成！"
echo "================================"
echo ""
echo "  API:     http://localhost:8000"
echo "  API Doc: http://localhost:8000/docs"
if [ "$API_ONLY" = false ]; then
    echo "  Web UI:  http://localhost:5173"
fi
echo ""
echo "  Agent 调用示例:"
echo '    curl -X POST http://localhost:8000/api/search \'
echo '      -H "Content-Type: application/json" \'
echo '      -d '"'"{'\"'"'keyword'\"'":'\"'"'老孙水果'\"'",'\"'"'platform'\"'":'\"'"'小红书'\"'"'}'"
echo ""
echo "  停止: kill $API_PID${WEB_PID:+ $WEB_PID}"
echo ""

# 打开浏览器（仅全栈模式）
if [ "$API_ONLY" = false ] && command -v open &> /dev/null; then
    open "http://localhost:5173" 2>/dev/null || true
fi
