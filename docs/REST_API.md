# NeuroMemory REST API 文档

> 基于 [v2.0 架构](ARCHITECTURE_V2.md) | 返回 [主架构文档](ARCHITECTURE.md)
>
> **版本**: v2.0  
> **最后更新**: 2026-01-22

---

## 目录

- [概述](#概述)
- [快速开始](#快速开始)
- [API 端点](#api-端点)
  - [处理记忆 (生产模式)](#1-处理记忆生产模式)
  - [处理记忆 (调试模式)](#2-处理记忆调试模式)
  - [获取用户知识图谱](#3-获取用户知识图谱)
  - [健康检查](#4-健康检查)
- [响应格式](#响应格式)
- [错误处理](#错误处理)
- [使用示例](#使用示例)
- [DIFY 集成指南](#dify-集成指南)

---

## 概述

NeuroMemory REST API 提供了一个高性能的记忆服务接口，基于 FastAPI 构建。该服务将用户输入视为"刺激"，通过 Y 型分流架构同时执行：

- **同步路径**: 立即检索相关记忆，返回结构化上下文
- **异步路径**: 后台进行隐私分类和记忆存储

### 基本信息

| 项目 | 说明 |
|------|------|
| **Base URL** | `http://localhost:8765` |
| **协议** | HTTP/HTTPS |
| **数据格式** | JSON |
| **认证** | 无（建议在生产环境中通过网关添加认证） |

### 启动服务

```bash
# 开发模式（自动重载）
uvicorn http_server:app --host 0.0.0.0 --port 8765 --reload

# 生产模式
uvicorn http_server:app --host 0.0.0.0 --port 8765 --workers 4
```

---

## 快速开始

### 1. 存储一条记忆并查询

```bash
# 存储记忆（系统会自动判断是否为私有数据）
curl -X POST http://localhost:8765/process \
  -H "Content-Type: application/json" \
  -d '{"input": "我女儿叫灿灿，今年5岁了", "user_id": "user_001"}'

# 查询记忆
curl -X POST http://localhost:8765/process \
  -H "Content-Type: application/json" \
  -d '{"input": "我女儿叫什么名字？", "user_id": "user_001"}'
```

### 2. 查看用户知识图谱

```bash
curl http://localhost:8765/graph/user_001
```

---

## API 端点

### 1. 处理记忆（生产模式）

处理用户输入，检索相关记忆并异步存储。返回结构化 JSON，适合注入到 LLM prompt 中。

#### 请求

```
POST /process
Content-Type: application/json
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `input` | string | ✅ | 用户输入（查询或陈述） |
| `user_id` | string | ✅ | 用户唯一标识 |

#### 请求示例

```json
{
    "input": "小朱的女儿叫什么？",
    "user_id": "user_001"
}
```

#### 响应示例（有记忆）

```json
{
    "status": "success",
    "vector_chunks": [
        {
            "memory": "灿灿还有一个弟弟，叫帅帅",
            "score": 0.87
        },
        {
            "memory": "小朱有两个孩子",
            "score": 0.82
        }
    ],
    "graph_relations": [
        {
            "source": "小朱",
            "relationship": "女儿",
            "target": "灿灿"
        },
        {
            "source": "灿灿",
            "relationship": "弟弟",
            "target": "帅帅"
        }
    ],
    "metadata": {
        "retrieval_time_ms": 123,
        "has_memory": true
    }
}
```

#### 响应示例（无记忆）

```json
{
    "status": "success",
    "vector_chunks": [],
    "graph_relations": [],
    "metadata": {
        "retrieval_time_ms": 15,
        "has_memory": false
    }
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 处理状态：`success` 或 `error` |
| `vector_chunks` | array | 向量检索匹配的记忆片段 |
| `vector_chunks[].memory` | string | 记忆内容 |
| `vector_chunks[].score` | number | 相似度分数 (0-1) |
| `graph_relations` | array | 知识图谱中的关系三元组 |
| `graph_relations[].source` | string | 关系起点实体 |
| `graph_relations[].relationship` | string | 关系类型 |
| `graph_relations[].target` | string | 关系终点实体 |
| `metadata.retrieval_time_ms` | number | 检索耗时（毫秒） |
| `metadata.has_memory` | boolean | 是否检索到相关记忆 |

---

### 2. 处理记忆（调试模式）

返回详细的处理过程报告（自然语言格式），用于开发调试和验证系统行为。

#### 请求

```
POST /debug
Content-Type: application/json
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `input` | string | ✅ | 用户输入 |
| `user_id` | string | ✅ | 用户唯一标识 |

#### 请求示例

```json
{
    "input": "小朱的儿子叫什么",
    "user_id": "user_001"
}
```

#### 响应示例

```json
{
    "report": "=== 检索过程 ===\n[向量检索] 查询: \"小朱的儿子叫什么\"\n  - 匹配: \"灿灿还有一个弟弟，叫帅帅\" (score: 0.87)\n  - 匹配: \"小朱有两个孩子\" (score: 0.82)\n\n[图谱检索] 起始节点: 小朱\n  - 路径1: 小朱 --[女儿]--> 灿灿 --[弟弟]--> 帅帅\n  - 路径2: 小朱 --[有孩子]--> 帅帅\n\n=== 存储决策 ===\n[LLM 分类] 输入类型: 问题查询\n[决策] 不存储 - 这是查询而非新知识\n\n=== 性能统计 ===\n- 向量检索: 45ms\n- 图谱检索: 78ms\n- 总耗时: 123ms"
}
```

#### 报告内容说明

报告包含以下部分：

1. **检索过程**
   - 向量检索：语义匹配结果及分数
   - 图谱检索：实体关系路径

2. **存储决策**
   - LLM 分类结果（PRIVATE/PUBLIC）
   - 存储决策及原因

3. **性能统计**
   - 各阶段耗时
   - 总处理时间

4. **原始数据**（可选）
   - 向量 ID
   - 完整图谱三元组

---

### 3. 获取用户知识图谱

获取指定用户的完整知识图谱结构。

#### 请求

```
GET /graph/{user_id}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | path | ✅ | 用户唯一标识 |

#### 响应示例

```json
{
    "status": "success",
    "user_id": "user_001",
    "memories": [
        {
            "id": "mem_001",
            "content": "小朱有两个孩子",
            "created_at": "2026-01-20T10:30:00Z"
        },
        {
            "id": "mem_002",
            "content": "灿灿是小朱的女儿",
            "created_at": "2026-01-20T10:31:00Z"
        }
    ],
    "entities": [
        {"name": "小朱", "type": "PERSON"},
        {"name": "灿灿", "type": "PERSON"},
        {"name": "帅帅", "type": "PERSON"}
    ],
    "relations": [
        {"source": "小朱", "relationship": "女儿", "target": "灿灿"},
        {"source": "小朱", "relationship": "儿子", "target": "帅帅"},
        {"source": "灿灿", "relationship": "弟弟", "target": "帅帅"}
    ],
    "metadata": {
        "total_memories": 2,
        "total_entities": 3,
        "total_relations": 3
    }
}
```

---

### 4. 健康检查

检查服务运行状态，用于负载均衡器和容器编排的健康探测。

#### 请求

```
GET /health
```

#### 响应示例

```json
{
    "status": "healthy",
    "service": "neuro-memory"
}
```

---

## 响应格式

### 通用响应结构

所有 API 响应均为 JSON 格式，包含以下通用字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | `success` 或 `error` |

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| `200` | 请求成功 |
| `422` | 请求参数验证失败 |
| `500` | 服务器内部错误 |

---

## 错误处理

NeuroMemory 采用**静默降级**策略，确保不影响主流程 LLM 的运行。

### 错误响应示例

```json
{
    "status": "error",
    "vector_chunks": [],
    "graph_relations": [],
    "metadata": {
        "retrieval_time_ms": 0,
        "has_memory": false,
        "error": "Database connection timeout"
    }
}
```

### 错误处理策略

| 错误类型 | 处理方式 |
|----------|----------|
| 检索失败 | 返回空 context，不抛出异常 |
| 存储失败 | 记录日志，不影响响应 |
| LLM 分类失败 | 默认按 PRIVATE 处理（宁可多存不漏存） |

---

## 使用示例

### cURL

```bash
# 处理记忆（生产模式）
curl -X POST http://localhost:8765/process \
  -H "Content-Type: application/json" \
  -d '{
    "input": "我最喜欢的颜色是蓝色",
    "user_id": "user_001"
  }'

# 调试模式
curl -X POST http://localhost:8765/debug \
  -H "Content-Type: application/json" \
  -d '{
    "input": "我喜欢什么颜色？",
    "user_id": "user_001"
  }'

# 获取知识图谱
curl http://localhost:8765/graph/user_001

# 健康检查
curl http://localhost:8765/health
```

### Python (requests)

```python
import requests

BASE_URL = "http://localhost:8765"

# 处理记忆
def process_memory(input_text: str, user_id: str) -> dict:
    response = requests.post(
        f"{BASE_URL}/process",
        json={"input": input_text, "user_id": user_id}
    )
    return response.json()

# 使用示例
result = process_memory("我女儿灿灿今年5岁了", "user_001")

if result["metadata"]["has_memory"]:
    print("找到相关记忆:")
    for chunk in result["vector_chunks"]:
        print(f"  - {chunk['memory']} (score: {chunk['score']})")
    for rel in result["graph_relations"]:
        print(f"  - {rel['source']} --[{rel['relationship']}]--> {rel['target']}")
else:
    print("没有找到相关记忆")
```

### Python (httpx async)

```python
import httpx
import asyncio

async def process_memory_async(input_text: str, user_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8765/process",
            json={"input": input_text, "user_id": user_id}
        )
        return response.json()

# 使用示例
async def main():
    result = await process_memory_async("小朱的儿子叫什么？", "user_001")
    print(result)

asyncio.run(main())
```

### JavaScript (fetch)

```javascript
async function processMemory(input, userId) {
    const response = await fetch('http://localhost:8765/process', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            input: input,
            user_id: userId
        })
    });
    return response.json();
}

// 使用示例
processMemory('我喜欢吃苹果', 'user_001')
    .then(result => {
        console.log('记忆处理结果:', result);
    });
```

---

## DIFY 集成指南

### 在 DIFY 工作流中调用 NeuroMemory

NeuroMemory 可以作为 DIFY 工作流的外部 HTTP 节点使用，为对话注入私有记忆上下文。

### 配置步骤

1. **添加 HTTP 请求节点**
   - 方法：`POST`
   - URL：`http://your-server:8765/process`
   - Headers：`Content-Type: application/json`

2. **配置请求体**

```json
{
    "input": "{{user_input}}",
    "user_id": "{{user_id}}"
}
```

3. **处理响应**

在后续的 LLM 节点中，使用返回的记忆上下文：

```
{% if http_result.metadata.has_memory %}
以下是用户的相关记忆，请参考这些信息回答：

向量记忆：
{% for chunk in http_result.vector_chunks %}
- {{ chunk.memory }}
{% endfor %}

知识图谱：
{% for rel in http_result.graph_relations %}
- {{ rel.source }} 的 {{ rel.relationship }} 是 {{ rel.target }}
{% endfor %}
{% endif %}

用户问题：{{ user_input }}
```

### 典型工作流

```
用户输入 → [NeuroMemory] → 记忆上下文 → [LLM] → 回复用户
                ↓
        (异步存储新记忆)
```

---

## 交互式文档

服务启动后，可以通过以下地址访问交互式 API 文档：

| 文档类型 | 地址 |
|----------|------|
| **Swagger UI** | `http://localhost:8765/docs` |
| **ReDoc** | `http://localhost:8765/redoc` |

这些文档提供了在线测试接口的功能，方便快速验证 API 行为。

---

## 相关文档

- [v2.0 架构设计](ARCHITECTURE_V2.md) - 了解系统架构
- [快速开始](GETTING_STARTED.md) - 环境配置和启动
- [测试指南](TESTING.md) - 测试用例和方法

---

*文档结束*
