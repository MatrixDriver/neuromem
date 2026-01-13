# 配置参考

> 返回 [主架构文档](ARCHITECTURE.md)

---

## 目录

- [环境变量](#环境变量)
- [模型切换配置](#模型切换配置)
- [LLM 模型配置](#llm-模型配置)
- [Embedding 模型配置](#embedding-模型配置)
- [数据库连接配置](#数据库连接配置)
- [Collection 命名规则](#collection-命名规则)
- [Docker Compose 服务配置](#docker-compose-服务配置)

---

## 环境变量

| 变量名 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `DEEPSEEK_API_KEY` | 是* | - | DeepSeek API 密钥 |
| `GOOGLE_API_KEY` | 是* | - | Google Gemini API 密钥 |

> \* 根据 `LLM_PROVIDER` 和 `EMBEDDING_PROVIDER` 设置，至少需要其中一个

---

## 模型切换配置

在 `config.py` 中修改以下变量：

```python
# LLM 提供商选择
LLM_PROVIDER = "deepseek"  # 可选: "deepseek" | "gemini"

# Embedding 提供商选择
EMBEDDING_PROVIDER = "local"  # 可选: "local" | "gemini"

# 图谱存储开关
ENABLE_GRAPH_STORE = True  # True: 启用 Neo4j | False: 仅向量存储
```

---

## LLM 模型配置

| 提供商 | 模型 | 用途 | 温度 |
|--------|------|------|------|
| DeepSeek | deepseek-chat | 对话推理 | 0.7 |
| DeepSeek | deepseek-chat | 实体提取 (Mem0) | 0.0 |
| Gemini | gemini-2.0-flash | 对话推理 | 0.7 |
| Gemini | gemini-2.0-flash | 实体提取 (Mem0) | 0.0 |

---

## Embedding 模型配置

| 提供商 | 模型 | 维度 | 说明 |
|--------|------|------|------|
| Local (HuggingFace) | paraphrase-multilingual-MiniLM-L12-v2 | 384 | 本地运行，无 API 成本 |
| Gemini | text-embedding-004 | 768 | 云端 API，更高精度 |

---

## 数据库连接配置

### Neo4j 配置

```python
# 在 MEM0_CONFIG 中
"graph_store": {
    "provider": "neo4j",
    "config": {
        "url": "neo4j://localhost:17687",
        "username": "neo4j",
        "password": "password123",
    },
}
```

### Qdrant 配置

```python
# 在 MEM0_CONFIG 中
"vector_store": {
    "provider": "qdrant",
    "config": {
        "host": "localhost",
        "port": 6333,
        "collection_name": "neuro_memory_huggingface_384",  # 自动生成
    },
}
```

---

## Collection 命名规则

向量数据库的 Collection 名称根据 Embedding 配置自动生成：

```
neuro_memory_{provider}_{dims}
```

示例：
- 本地 HuggingFace: `neuro_memory_huggingface_384`
- Gemini: `neuro_memory_gemini_768`

> 这确保了不同 Embedding 模型的向量不会混在同一个 Collection 中

---

## Docker Compose 服务配置

```yaml
# docker-compose.yml 关键配置

services:
  neo4j:
    image: neo4j:5.26.0
    ports:
      - "7474:7474"   # Browser UI
      - "17687:7687"  # Bolt 协议 (注意: 映射到 17687)
    environment:
      - NEO4J_AUTH=neo4j/password123
      - NEO4J_PLUGINS=["apoc", "graph-data-science"]

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"   # REST API + Dashboard
```

---

## 相关文档

- [快速开始](GETTING_STARTED.md) - 安装和运行指南
- [部署架构](DEPLOYMENT.md) - 详细部署配置
