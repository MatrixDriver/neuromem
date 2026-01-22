"""
NeuroMemory HTTP Server

基于 FastAPI 的 HTTP 服务端，供 DIFY 等 HTTP 客户端调用。

启动方式:
    uvicorn http_server:app --host 0.0.0.0 --port 8765

开发模式（自动重载）:
    uvicorn http_server:app --host 0.0.0.0 --port 8765 --reload

生产模式:
    uvicorn http_server:app --host 0.0.0.0 --port 8765 --workers 4
"""
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("neuro_memory.http")

from config import HTTP_SERVER_CONFIG
from private_brain import get_brain

# =============================================================================
# FastAPI 应用初始化
# =============================================================================

app = FastAPI(
    title="NeuroMemory API",
    description="私有化外挂大脑服务 - Memory-as-a-Service",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 配置 CORS（支持 DIFY 等跨域调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=HTTP_SERVER_CONFIG.get("cors_origins", ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# 请求/响应模型
# =============================================================================

class ProcessRequest(BaseModel):
    """处理记忆请求"""
    input: str
    user_id: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "input": "小朱的女儿叫什么？",
                    "user_id": "user_001"
                }
            ]
        }
    }


class DebugResponse(BaseModel):
    """调试模式响应"""
    report: str


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    service: str


# =============================================================================
# API 端点
# =============================================================================

@app.post("/process", summary="处理记忆（生产模式）")
async def process_memory(request: ProcessRequest) -> dict:
    """
    处理用户输入，检索相关记忆并异步存储。
    
    返回结构化 JSON，包含：
    - vector_chunks: 语义相关的记忆片段
    - graph_relations: 知识图谱中的关系
    - metadata: 检索耗时、是否有记忆等信息
    
    适用于：将记忆上下文注入到 LLM prompt 中
    """
    logger.info(f"[/process] user_id={request.user_id}, input={request.input[:50]}...")
    
    try:
        brain = get_brain()
        result = brain.process(request.input, request.user_id)
        return result
    except Exception as e:
        logger.error(f"[/process] 处理失败: {e}")
        # 静默降级：返回空结果而非抛出异常
        return {
            "status": "error",
            "vector_chunks": [],
            "graph_relations": [],
            "metadata": {
                "retrieval_time_ms": 0,
                "has_memory": False,
                "error": str(e),
            }
        }


@app.post("/debug", summary="处理记忆（调试模式）")
async def debug_process_memory(request: ProcessRequest) -> DebugResponse:
    """
    调试模式：处理用户输入并返回详细的处理过程。
    
    返回自然语言格式的报告，包含：
    - 检索过程（向量匹配结果、图谱关系）
    - 存储决策（隐私分类结果、是否存储）
    - 性能统计（各阶段耗时）
    - 原始数据
    
    适用于：开发调试、验证系统行为
    """
    logger.info(f"[/debug] user_id={request.user_id}, input={request.input[:50]}...")
    
    try:
        brain = get_brain()
        report = brain.process_debug(request.input, request.user_id)
        return DebugResponse(report=report)
    except Exception as e:
        logger.error(f"[/debug] 处理失败: {e}")
        return DebugResponse(report=f"=== 错误 ===\n处理失败: {e}")


@app.get("/graph/{user_id}", summary="获取用户知识图谱")
async def get_user_graph(user_id: str) -> dict:
    """
    获取用户的完整知识图谱。
    
    返回用户存储的所有记忆和实体关系。
    
    适用于：查看用户记忆状态、调试图谱结构
    """
    logger.info(f"[/graph] user_id={user_id}")
    
    try:
        brain = get_brain()
        result = brain.get_user_graph(user_id)
        return result
    except Exception as e:
        logger.error(f"[/graph] 获取失败: {e}")
        return {
            "status": "error",
            "user_id": user_id,
            "error": str(e),
        }


@app.get("/health", summary="健康检查")
async def health_check() -> HealthResponse:
    """
    健康检查端点。
    
    用于负载均衡器、容器编排等场景的健康探测。
    """
    return HealthResponse(status="healthy", service="neuro-memory")


# =============================================================================
# 启动入口
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    host = HTTP_SERVER_CONFIG.get("host", "0.0.0.0")
    port = HTTP_SERVER_CONFIG.get("port", 8765)
    
    logger.info(f"启动 NeuroMemory HTTP Server: http://{host}:{port}")
    logger.info(f"API 文档: http://{host}:{port}/docs")
    
    uvicorn.run(
        "http_server:app",
        host=host,
        port=port,
        reload=False,
    )
