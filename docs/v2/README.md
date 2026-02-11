# NeuroMemory 文档中心

> **AI Agent 记忆框架**
>
> 为 AI agent 开发者提供记忆管理能力，直接在 Python 程序中使用

---

## 文档导航

### 新手入门

- **[快速开始](GETTING_STARTED.md)** — 10 分钟上手指南

### 核心文档

- **[架构设计](ARCHITECTURE.md)** — 系统架构、Provider 模式、数据模型
- **[使用指南](SDK_GUIDE.md)** — 完整 Python API 用法和代码示例

### 开发指南

- **[CLAUDE.md](../../CLAUDE.md)** (项目根目录) — Claude Code 工作指南、项目约定

---

## 快速链接

```python
import asyncio
from neuromemory import NeuroMemory, SiliconFlowEmbedding

async def main():
    async with NeuroMemory(
        database_url="postgresql+asyncpg://neuromemory:neuromemory@localhost:5432/neuromemory",
        embedding=SiliconFlowEmbedding(api_key="your-key"),
    ) as nm:
        await nm.add_memory(user_id="alice", content="I work at Google")
        results = await nm.search(user_id="alice", query="workplace")
        print(results)

asyncio.run(main())
```

---

## 核心特性

### 六大功能模块

| 模块 | 入口 | 功能 |
|------|------|------|
| 语义记忆 | `nm.add_memory()` / `nm.search()` | 向量存储和相似度检索 |
| KV 存储 | `nm.kv` | 键值存储（偏好、配置） |
| 对话管理 | `nm.conversations` | 会话消息存储和管理 |
| 文件管理 | `nm.files` | 文件上传、文本提取、embedding 生成 |
| 图数据库 | `nm.graph` | 知识图谱（Apache AGE） |
| 记忆提取 | `nm.extract_memories()` | LLM 自动提取偏好/事实/事件 |

### 可插拔 Provider

- **Embedding**: SiliconFlow (BAAI/bge-m3) / OpenAI (text-embedding-3-small)
- **LLM**: OpenAI / DeepSeek（用于记忆分类提取）
- **Storage**: MinIO / AWS S3 / 华为云 OBS

### 异步优先

全链路 async/await，上下文管理器自动管理连接

---

## 技术栈

| 组件 | 技术 |
|------|------|
| Framework | Python 3.10+ async |
| 数据库 | PostgreSQL 16 + pgvector |
| 图数据库 | Apache AGE |
| ORM | SQLAlchemy 2.0 (asyncpg) |
| Embedding | 可插拔 Provider |
| 文件存储 | S3 兼容 |

---

## 安装

```bash
# 启动 PostgreSQL
docker compose -f docker-compose.v2.yml up -d db

# 安装
pip install -e ".[all]"
```

详见 [快速开始](GETTING_STARTED.md)

---

## 文档结构

```
docs/v2/
├── README.md               # 本文档（文档中心）
├── GETTING_STARTED.md      # 快速开始
├── ARCHITECTURE.md         # 架构设计
└── SDK_GUIDE.md            # 使用指南
```

---

## 相关链接

- **GitHub**: https://github.com/your-repo/NeuroMemory
- **Issues**: https://github.com/your-repo/NeuroMemory/issues
- **v1 文档**: [../v1/](../v1/) (已弃用，仅供参考)

---

**最后更新**: 2026-02-11
