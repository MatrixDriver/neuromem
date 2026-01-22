# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

NeuroMemory 是一个神经符号混合记忆系统（Neuro-Symbolic Hybrid Memory），实现 **Memory-as-a-Service** 架构，为主流程 LLM 提供私有上下文检索服务。

**核心设计**：Y 型分流架构
- **同步路径**：立即检索相关记忆，返回结构化 JSON
- **异步路径**：后台执行隐私分类 + 记忆写入（Fire-and-forget）

**双层记忆系统**：
- **关联记忆 (Graph Layer)**: Neo4j 知识图谱，存储实体关系，支持多跳推理
- **语义记忆 (Vector Layer)**: Qdrant 向量数据库，负责语义检索

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| LLM | DeepSeek / Gemini | 可切换，用于隐私分类和实体提取 |
| Embedding | SiliconFlow / Local / Gemini | 可切换，384/768/1024 维向量 |
| Vector DB | Qdrant | localhost:6333 |
| Graph DB | Neo4j 5.26.0 | localhost:7474 (Web), localhost:17687 (Bolt) |
| Framework | Mem0 + FastAPI | 混合记忆管理 + REST API |

## 常用命令

```bash
# 启动数据库服务
docker-compose up -d

# 停止服务
docker-compose down

# 激活虚拟环境 (PowerShell)
.\.venv\Scripts\Activate.ps1

# 安装依赖
uv pip install -e ".[dev]"

# 运行 CLI 交互模式
python main.py

# 启动 HTTP Server（开发模式）
uvicorn http_server:app --host 0.0.0.0 --port 8765 --reload

# 运行测试
pytest                                    # 全部测试
pytest -m "not slow"                      # 跳过 LLM 调用的测试
pytest tests/test_cognitive.py::TestPrivacyFilter  # 运行特定测试类
```

## 服务访问

- Neo4j Browser: http://localhost:7474 (用户名: `neo4j`, 密码: `password123`)
- Qdrant API: http://localhost:6333
- REST API: http://localhost:8765 (需手动启动)
- API 文档: http://localhost:8765/docs (Swagger UI)

## 核心模块

| 文件 | 职责 |
|------|------|
| `private_brain.py` | 核心类 `PrivateBrain`，实现 Y 型分流架构 |
| `privacy_filter.py` | LLM 隐私分类器（PRIVATE/PUBLIC） |
| `http_server.py` | FastAPI REST API 入口 |
| `mcp_server.py` | MCP Server 入口（Cursor/Claude Desktop 集成） |
| `config.py` | 模型切换、数据库连接配置 |
| `main.py` | CLI 交互模式入口 |

## 模型切换配置

在 `config.py` 中修改：

```python
LLM_PROVIDER = "deepseek"       # "gemini" 或 "deepseek"
EMBEDDING_PROVIDER = "siliconflow"  # "gemini", "local", "siliconflow"
ENABLE_GRAPH_STORE = True       # 是否启用 Neo4j 图谱
```

## 环境变量

在 `.env` 文件中配置：
```
DEEPSEEK_API_KEY=your-deepseek-api-key
GOOGLE_API_KEY=your-gemini-api-key
SILICONFLOW_API_KEY=your-siliconflow-api-key
```

## REST API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/process` | POST | 处理记忆（生产模式，返回 JSON） |
| `/debug` | POST | 处理记忆（调试模式，返回自然语言报告） |
| `/graph/{user_id}` | GET | 获取用户知识图谱 |
| `/health` | GET | 健康检查 |

## 测试

测试文件位于 `tests/test_cognitive.py`，包含：
- `TestIdentityExtraction` / `TestPronounResolution`：单元测试（无 LLM）
- `TestPrivacyFilter`：隐私分类集成测试
- `TestPrivateBrain`：核心功能测试
- `TestMultiHopRetrieval`：多跳检索端到端测试

使用 `@pytest.mark.slow` 标记需要 LLM 调用的测试。

## 架构说明

详细架构设计参见 `docs/ARCHITECTURE.md` 和 `docs/ARCHITECTURE_V2.md`。
