#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="${1:-$BASE_DIR/../insightsee-skill-dist}"

echo "================================"
echo "  InsightSee Skill 打包脚本 👁️"
echo "================================"
echo "  源目录: $BASE_DIR"
echo "  输出目录: $OUTPUT_DIR"
echo ""

rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

echo "📦 复制核心文件..."
cp "$BASE_DIR/SKILL.md" "$OUTPUT_DIR/SKILL.md"
cp "$BASE_DIR/LLM_CONFIG.md" "$OUTPUT_DIR/LLM_CONFIG.md" 2>/dev/null || true
cp "$BASE_DIR/api_server.py" "$OUTPUT_DIR/api_server.py"
cp "$BASE_DIR/requirements.txt" "$OUTPUT_DIR/requirements.txt"

echo "📦 复制 engine 模块..."
mkdir -p "$OUTPUT_DIR/engine"
cp -R "$BASE_DIR/engine/base_crawler.py" "$OUTPUT_DIR/engine/base_crawler.py"
cp -R "$BASE_DIR/engine/crawler_manager.py" "$OUTPUT_DIR/engine/crawler_manager.py"
mkdir -p "$OUTPUT_DIR/engine/crawlers"
for f in __init__.py manual_input.py browser_crawler.py weibo.py zhihu.py xiaohongshu.py README.md; do
  [ -f "$BASE_DIR/engine/crawlers/$f" ] && cp "$BASE_DIR/engine/crawlers/$f" "$OUTPUT_DIR/engine/crawlers/$f" || true
done
mkdir -p "$OUTPUT_DIR/engine/analyzers"
for f in __init__.py models.py analyzer.py openai_adapter.py prompts.py analyzer_tag_patterns.py; do
  [ -f "$BASE_DIR/engine/analyzers/$f" ] && cp "$BASE_DIR/engine/analyzers/$f" "$OUTPUT_DIR/engine/analyzers/$f" || true
done
mkdir -p "$OUTPUT_DIR/engine/search"
cp "$BASE_DIR/engine/search/__init__.py" "$OUTPUT_DIR/engine/search/__init__.py"
cp "$BASE_DIR/engine/search/search_engine.py" "$OUTPUT_DIR/engine/search/search_engine.py"

echo "📦 复制 scripts..."
mkdir -p "$OUTPUT_DIR/scripts"
for f in start.sh build-skill.sh cron-monitor.sh; do
  [ -f "$BASE_DIR/scripts/$f" ] && cp "$BASE_DIR/scripts/$f" "$OUTPUT_DIR/scripts/$f" || true
done

echo "📦 复制 assets（包含收款码）..."
mkdir -p "$OUTPUT_DIR/assets"
if [ -d "$BASE_DIR/assets" ]; then
  for f in "$BASE_DIR/assets/"*; do
    [ -f "$f" ] && cp "$f" "$OUTPUT_DIR/assets/"
  done
fi

rm -rf "$OUTPUT_DIR/.git" 2>/dev/null || true
chmod +x "$OUTPUT_DIR/scripts/"*.sh 2>/dev/null || true

echo ""
echo "================================"
echo "  ✅ 打包完成！"
echo "================================"
echo "  大小: $(du -sh "$OUTPUT_DIR" | cut -f1)"
echo "  输出: $OUTPUT_DIR"
echo ""
