"""
RepScan API Server — FastAPI 后端服务

核心哲学：
  每一次反馈，都是一次未被满足的期待。

核心端点：
  POST /api/insight      ⭐ 解析用户反馈 → 输出洞察（包含用户标签）
  POST /api/search       🔍 搜索公开内容 → 分析洞察
  POST /api/analyze-file 📄 上传文件 → 分析洞察
  
旧端点（保留兼容）：
  POST /api/analyze  — 文本分析
  GET  /api/tasks    — 演示数据
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from engine.analyzers.analyzer import InsightEngine, InsightConfig
from engine.analyzers.models import RawItem
from engine.crawler_manager import CrawlerManager

try:
    from engine.search import SearchEngine
    HAS_SEARCH_ENGINE = True
except ImportError:
    HAS_SEARCH_ENGINE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("repscan.api")

app = FastAPI(title="RepScan API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mgr = CrawlerManager()
search_engine = SearchEngine() if HAS_SEARCH_ENGINE else None


# ============================================================
#  请求模型
# ============================================================


class InsightRequest(BaseModel):
    """POST /api/insight 请求体"""
    texts: List[str]
    source: str = "manual"


class SearchRequest(BaseModel):
    """POST /api/search 请求体"""
    keyword: str
    platform: Optional[str] = None
    max_results: int = 10


class FolderRequest(BaseModel):
    """POST /api/analyze-folder 请求体"""
    path: str
    source: str = "用户反馈"


# ============================================================
#  辅助函数
# ============================================================


def _new_engine() -> InsightEngine:
    """创建分析引擎实例（可从 env 读取 LLM 配置）"""
    api_key = os.environ.get("REPSCAN_LLM_API_KEY", "mock")
    model = os.environ.get("REPSCAN_LLM_MODEL", "deepseek-chat")
    base_url = os.environ.get("REPSCAN_LLM_BASE_URL", "")
    return InsightEngine(InsightConfig(
        api_key=api_key,
        model=model,
        base_url=base_url,
    ))


def _parse_file(file_bytes: bytes, filename: str) -> List[str]:
    """解析上传文件，返回文本列表"""
    texts = []
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".csv":
        try:
            decoded = file_bytes.decode("utf-8-sig")
            reader = csv.reader(io.StringIO(decoded))
            for row in reader:
                if row and row[0].strip():
                    texts.append(row[0].strip())
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"CSV 解析失败: {e}")
    elif ext == ".json":
        try:
            data = json.loads(file_bytes.decode("utf-8"))
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("items", data.get("texts", data.get("comments", [])))
            for item in items:
                if isinstance(item, str):
                    texts.append(item.strip())
                elif isinstance(item, dict):
                    texts.append(item.get("content", item.get("text", str(item))).strip())
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"JSON 解析失败: {e}")
    else:
        # TXT / 默认
        for line in file_bytes.decode("utf-8").split("\n"):
            line = line.strip()
            if line:
                texts.append(line)

    if not texts:
        raise HTTPException(status_code=400, detail="文件中未找到有效内容")
    return texts


# ============================================================
#  ⭐ 核心端点
# ============================================================


@app.post("/api/insight")
async def get_insight(req: InsightRequest):
    """
    ⭐ 核心端点：分析用户反馈 → 输出洞察（期待解码 + 用户标签 + 行动建议）

    这是最常用的接口。把用户反馈文本传进来，返回结构化的洞察。
    每条洞察包含：
    - label:        洞察标签
    - weight:       关注度权重(%)
    - user_expected:用户真正的期待
    - actionable:   你应该做什么
    - tagged_users: 代表用户（标注了用户类型标签）
    """
    if not req.texts:
        raise HTTPException(status_code=400, detail="No texts provided")

    items = [RawItem(content=t, platform=req.source) for t in req.texts]
    engine = _new_engine()
    report = await engine.analyze(items)

    return {
        "source": req.source,
        "input_count": len(req.texts),
        "report": report.to_dict(),
    }


@app.post("/api/analyze-file")
async def analyze_file(file: UploadFile = File(...)):
    """
    上传文件 → 解析 → 输出洞察

    支持 TXT / CSV / JSON 格式。
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    content = await file.read()
    filename = file.filename or "unknown.txt"
    texts = _parse_file(content, filename)

    items = [RawItem(content=t, platform=f"文件:{filename}") for t in texts]
    engine = _new_engine()
    report = await engine.analyze(items)

    return {
        "filename": filename,
        "total_lines": len(texts),
        "report": report.to_dict(),
    }


@app.post("/api/analyze-folder")
async def analyze_folder(req: FolderRequest):
    """
    分析文件夹下所有文本文件 → 输出综合洞察

    递归扫描 .txt / .csv / .json / .log / .md
    """
    folder = os.path.expanduser(req.path)
    if not os.path.isdir(folder):
        raise HTTPException(status_code=400, detail=f"文件夹不存在: {folder}")

    all_texts = []
    file_stats = []
    supported = {".txt", ".csv", ".json", ".log", ".md", ".text"}

    for root, _dirs, files in os.walk(folder):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in supported:
                continue

            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    raw = f.read()
                file_texts = _parse_file(raw.encode(), fname)
                if file_texts:
                    all_texts.extend(file_texts)
                    file_stats.append({"file": fname, "lines": len(file_texts)})
            except Exception as e:
                logger.warning(f"读取文件 {fpath} 失败: {e}")

    if not all_texts:
        raise HTTPException(status_code=400, detail=f"文件夹 {folder} 中未找到有效文本")

    items = [RawItem(content=t, platform=req.source) for t in all_texts]
    engine = _new_engine()
    report = await engine.analyze(items)

    return {
        "folder": folder,
        "files_analyzed": len(file_stats),
        "total_lines": len(all_texts),
        "file_stats": file_stats,
        "report": report.to_dict(),
    }


@app.post("/api/search")
async def search_and_analyze(req: SearchRequest):
    """
    搜索公开内容 → 分析产出洞察

    Agent 用这个接口搜某个品牌/产品的公开反馈。
    """
    if not req.keyword or req.keyword.strip() == "":
        raise HTTPException(status_code=400, detail="keyword is required")

    search_results = []

    if search_engine:
        try:
            search_results = await search_engine.search(
                keyword=req.keyword,
                platform=req.platform,
                max_results=req.max_results,
            )
            logger.info(f"搜索引擎返回 {len(search_results)} 条结果")
        except Exception as e:
            logger.warning(f"搜索引擎搜索失败: {e}")

    if not search_results:
        logger.warning("搜索无结果，使用模拟数据降级")
        mock = mgr.get_mock_data(req.max_results)
        for item in mock:
            item.title = f"关于「{req.keyword}」的反馈"
        search_results = mock

    engine = _new_engine()
    report = await engine.analyze(search_results)

    return {
        "query": {"keyword": req.keyword, "platform": req.platform},
        "source_count": len(search_results),
        "search_source": "duckduckgo" if search_engine and search_results else "mock",
        "report": report.to_dict(),
    }


# ============================================================
#  旧端点（保留兼容，包裹为 insight）
# ============================================================


@app.post("/api/analyze")
async def analyze_texts(req: InsightRequest):
    """（保留兼容）分析文本 → 输出洞察"""
    return await get_insight(req)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": "0.3.0",
        "engine": "llm" if os.environ.get("REPSCAN_LLM_API_KEY") else "mock",
        "search_engine": "duckduckgo" if search_engine else None,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/tasks")
def list_tasks():
    """演示任务列表"""
    return {
        "tasks": [
            {"id": "demo-001", "name": "老孙水果店 用户反馈分析", "source": "小红书"},
            {"id": "demo-002", "name": "ChatGPT 用户抱怨分析", "source": "知乎"},
        ]
    }


@app.get("/api/sources")
def list_sources():
    """数据源列表"""
    sources = []

    # 搜索引擎平台
    if HAS_SEARCH_ENGINE:
        from engine.search.search_engine import SearchEngine as SE
        for p in SE.list_supported_platforms():
            sources.append(p)

    sources.append({"id": "file", "name": "文件上传", "status": "available"})
    sources.append({"id": "manual", "name": "手动输入", "status": "available"})

    return {"sources": sources}


# ============================================================
#  启动
# ============================================================

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 RepScan API Server v0.3.0 starting...")
    engine_type = "LLM" if os.environ.get("REPSCAN_LLM_API_KEY") else "Mock"
    logger.info(f"   分析引擎: {engine_type}")
    logger.info(f"   搜索引擎: {'DuckDuckGo ✅' if search_engine else '未加载 ❌'}")
    logger.info(f"   API 文档: http://localhost:9090/docs")
    uvicorn.run(app, host="0.0.0.0", port=9090)
