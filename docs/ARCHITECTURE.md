# NeuroMemory 主架构文档

> **版本**: 1.0.0
> **状态**: 生产级服务
> **最后更新**: 2025-01

---

## 目录

1. [实现状态总览](#1-实现状态总览)
2. [系统概述](#2-系统概述)
3. [设计目标与约束](#3-设计目标与约束)
4. [架构概览](#4-架构概览)
5. [核心组件设计](#5-核心组件设计)
6. [数据模型](#6-数据模型)
7. [接口设计](#7-接口设计)
8. [快速开始](#8-快速开始)
9. [配置参考](#9-配置参考)
10. [部署架构](#10-部署架构)
11. [可观测性设计](#11-可观测性设计)
12. [未来扩展 (TODO)](#12-未来扩展-todo)
13. [技术决策记录 (ADR)](#13-技术决策记录-adr)

---

## 1. 实现状态总览

### 1.1 组件实现状态矩阵

| 组件 | 状态 | 说明 |
|------|------|------|
| **存储层** | | |
| ├─ Neo4j 图谱存储 | ✅ 已实现 | 通过 Mem0 集成，支持实体关系存储 |
| ├─ Qdrant 向量存储 | ✅ 已实现 | 通过 Mem0 集成，支持语义检索 |
| └─ 情景存储 (Episodic) | 📋 规划 | 暂不实现，作为未来扩展 |
| **集成层** | | |
| └─ Mem0 Framework | ✅ 已实现 | 混合存储、实体提取、检索融合 |
| **服务层** | | |
| ├─ 混合检索 (HybridRetriever) | ✅ 已实现 | 通过 brain.search() |
| ├─ 深度推理 (ReasoningCore) | ✅ 已实现 | 通过 LLM invoke |
| └─ 记忆整合 (MemoryConsolidator) | ✅ 已实现 | 通过 brain.add() |
| **接入层** | | |
| ├─ Python SDK (NeuroMemory 类) | 🚧 开发中 | 优先实现，封装底层函数 |
| ├─ REST API | 📋 规划 | 计划使用 FastAPI |
| └─ CLI 工具 | 📋 规划 | 计划使用 Click/Typer |
| **可观测性** | | |
| ├─ Metrics (Prometheus) | 📋 规划 | 业务指标 + 系统指标 |
| ├─ Tracing (Jaeger) | 📋 规划 | 分布式链路追踪 |
| └─ Logging (结构化) | 📋 规划 | JSON 格式日志 |
| **认知编排** | | |
| ├─ 线性流程 | ✅ 已实现 | 检索 → 推理 → 整合 |
| └─ LangGraph 复杂编排 | 📋 规划 | 条件分支、循环推理等 |

**图例**: ✅ 已实现 | 🚧 开发中 | 📋 规划

### 1.2 功能完成度

```
核心功能 (Core)           [████████░░] 80%
├─ 混合记忆存储            [██████████] 100%
├─ 混合检索                [██████████] 100%
├─ LLM 推理                [██████████] 100%
├─ 模型切换                [██████████] 100%
└─ 用户隔离                [██████████] 100%

接入层 (Access)           [██░░░░░░░░] 20%
├─ Python SDK              [████░░░░░░] 40%  <- 当前优先
├─ REST API                [░░░░░░░░░░] 0%
└─ CLI 工具                [░░░░░░░░░░] 0%

可观测性 (Observability)  [░░░░░░░░░░] 0%
├─ Metrics                 [░░░░░░░░░░] 0%
├─ Tracing                 [░░░░░░░░░░] 0%
└─ Logging                 [░░░░░░░░░░] 0%
```

---

## 2. 系统概述

### 2.1 项目背景

传统的 RAG（检索增强生成）系统采用"扁平"的向量存储方案，将记忆打散成碎片，丢失了结构和关联。虽然它能识别语义相似性（如"苹果"和"手机"向量接近），但难以推理因果关系或实体间的复杂网络。

NeuroMemory 采用**神经符号混合记忆系统 (Neuro-Symbolic Hybrid Memory)** 架构，融合知识图谱 (GraphRAG) 与高维向量 (Vector)，模拟人类海马体和大脑皮层的工作方式，实现真正的多跳推理能力。

### 2.2 系统定位

NeuroMemory 是一个**生产级记忆服务**，提供：

- **Python SDK**: 供应用程序直接集成 `[🚧 开发中]`
- **命令行 CLI**: 供开发者调试和管理 `[📋 规划]`
- **REST API**: 供任意客户端远程调用 `[📋 规划]`

### 2.3 核心能力

| 能力 | 状态 | 描述 |
|------|------|------|
| **混合检索** | ✅ | 并行执行向量语义搜索和图谱关系遍历 |
| **多跳推理** | ✅ | 通过图谱路径实现 `A → B → C` 的逻辑链条推理 |
| **自动知识提取** | ✅ | LLM 自动从文本中提取实体和关系 |
| **模型可切换** | ✅ | 支持 DeepSeek/Gemini 作为 LLM，本地/云端 Embedding |
| **用户隔离** | ✅ | 基于 user_id 的数据隔离 |

---

## 3. 设计目标与约束

### 3.1 设计目标

| 目标 | 优先级 | 说明 |
|------|--------|------|
| **准确性** | P0 | 减少幻觉，提供可追溯的推理路径 |
| **可扩展性** | P0 | 支持模型、存储组件的灵活切换 |
| **可观测性** | P1 | 完整的 Metrics + Tracing + Logging `[📋 规划]` |
| **易用性** | P1 | 简洁的 API，多种接入方式 |
| **性能** | P2 | 检索延迟 < 500ms (P95) |

### 3.2 设计约束

| 约束 | 说明 |
|------|------|
| **记忆永久存储** | 不实现自动过期/遗忘机制 |
| **简单用户隔离** | 基于 user_id 参数，不含认证/授权系统 |
| **线性认知流程** | 当前采用简单的 检索→推理→整合 流程 |

### 3.3 非目标 (Out of Scope)

- 用户认证/授权系统
- 记忆自动遗忘/过期
- 分布式图数据库集群
- 实时流式处理

---

## 4. 架构概览

### 4.1 系统分层架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    接入层 (Access Layer) [部分规划]                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │
│  │ Python SDK  │  │  CLI Tool   │  │  REST API (FastAPI)         │  │
│  │ [🚧 开发中] │  │ [📋 规划]   │  │  [📋 规划]                  │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────────┬──────────────┘  │
└─────────┼────────────────┼────────────────────────┼─────────────────┘
          │                │                        │
          └────────────────┼────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       服务层 (Service Layer) [✅ 已实现]              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    CognitiveEngine                          │    │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────────┐  │    │
│  │  │HybridRetriever│ │ ReasoningCore │ │MemoryConsolidator │  │    │
│  │  │   [✅ 实现]   │ │   [✅ 实现]   │ │     [✅ 实现]     │  │    │
│  │  └───────────────┘ └───────────────┘ └───────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    集成层 (Integration Layer) [✅ 已实现]             │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                      Mem0 Framework                          │   │
│  │   • 混合存储抽象    • 实体提取    • 检索融合                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      存储层 (Storage Layer) [✅ 已实现]               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────────┐   │
│  │   Neo4j 图谱     │  │   Qdrant 向量   │  │  情景存储          │   │
│  │   [✅ 已实现]    │  │   [✅ 已实现]   │  │  [📋 规划]        │   │
│  └─────────────────┘  └─────────────────┘  └───────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        外部依赖 (External)                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────────┐   │
│  │  LLM Provider   │  │Embedding Provider│ │   可观测性平台     │   │
│  │ DeepSeek/Gemini │  │  Local/Gemini   │  │   [📋 规划]       │   │
│  │   [✅ 已实现]   │  │   [✅ 已实现]   │  │                   │   │
│  └─────────────────┘  └─────────────────┘  └───────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 记忆双层架构

NeuroMemory 的核心是**双层记忆系统**（三层架构中的情景流暂未实现）：

```
┌─────────────────────────────────────────────────────────────────┐
│                     记忆系统 (Memory System)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────┐   ┌─────────────────────────┐    │
│   │    关联记忆 (Graph)      │   │    语义记忆 (Vector)     │    │
│   │    ═══════════════      │   │    ═══════════════      │    │
│   │    [✅ 已实现]          │   │    [✅ 已实现]          │    │
│   │                         │   │                         │    │
│   │  存储: Neo4j            │   │  存储: Qdrant           │    │
│   │  内容: 实体 + 关系       │   │  内容: 文本 + 嵌入向量   │    │
│   │  查询: Cypher 图遍历    │   │  查询: 余弦相似度        │    │
│   │                         │   │                         │    │
│   │  ┌───────────────────┐  │   │  ┌───────────────────┐  │    │
│   │  │ (DeepMind)        │  │   │  │ "DeepMind是..."   │  │    │
│   │  │     │             │  │   │  │  [0.12, -0.34..]  │  │    │
│   │  │  [子公司]          │  │   │  └───────────────────┘  │    │
│   │  │     │             │  │   │  ┌───────────────────┐  │    │
│   │  │     ▼             │  │   │  │ "Demis是CEO..."   │  │    │
│   │  │ (Google)          │  │   │  │  [0.45, 0.21...]  │  │    │
│   │  └───────────────────┘  │   │  └───────────────────┘  │    │
│   │                         │   │                         │    │
│   │  优势: 精确逻辑推理     │   │  优势: 模糊语义匹配      │    │
│   │  场景: 多跳关系查询     │   │  场景: 相似内容检索      │    │
│   └─────────────────────────┘   └─────────────────────────┘    │
│                                                                 │
│                         ┌───────────┐                          │
│                         │  混合检索  │                          │
│                         │  Fusion   │                          │
│                         └─────┬─────┘                          │
│                               │                                │
│                               ▼                                │
│                    ┌───────────────────┐                       │
│                    │   统一结果集       │                       │
│                    │ [{memory, type}]  │                       │
│                    └───────────────────┘                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 认知处理流程

当前采用简单的三阶段线性流程 `[✅ 已实现]`：

```
┌──────────────────────────────────────────────────────────────────┐
│                    认知处理流程 (Cognitive Pipeline)               │
└──────────────────────────────────────────────────────────────────┘

  用户输入
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: 混合检索 (Hybrid Retrieval) [✅ 已实现]                 │
│  ─────────────────────────────────────                          │
│                                                                 │
│    ┌─────────────┐              ┌─────────────┐                │
│    │ 向量搜索    │   并行执行   │ 图谱遍历    │                │
│    │ (Qdrant)   │◄────────────►│ (Neo4j)    │                │
│    └──────┬──────┘              └──────┬──────┘                │
│           │                            │                        │
│           └────────────┬───────────────┘                        │
│                        ▼                                        │
│              ┌─────────────────┐                                │
│              │   结果融合       │                                │
│              │   去重 & 排序    │                                │
│              └────────┬────────┘                                │
└───────────────────────┼─────────────────────────────────────────┘
                        │
                        ▼  knowledge_context
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: 深度推理 (Reasoning) [✅ 已实现]                        │
│  ──────────────────────────────                                 │
│                                                                 │
│    ┌─────────────────────────────────────────────────────┐     │
│    │  System Prompt                                      │     │
│    │  ┌───────────────────────────────────────────────┐  │     │
│    │  │ 你是一个拥有"图谱思维"的超级智能。              │  │     │
│    │  │                                               │  │     │
│    │  │ [已提取的知识网络]                             │  │     │
│    │  │ - DeepMind 是 Google 的子公司                  │  │     │
│    │  │ - Demis Hassabis 是 DeepMind 的 CEO           │  │     │
│    │  │ ...                                           │  │     │
│    │  └───────────────────────────────────────────────┘  │     │
│    └─────────────────────────────────────────────────────┘     │
│                        │                                        │
│                        ▼                                        │
│              ┌─────────────────┐                                │
│              │  LLM 推理生成    │                                │
│              │ (DeepSeek/Gemini)│                                │
│              └────────┬────────┘                                │
└───────────────────────┼─────────────────────────────────────────┘
                        │
                        ▼  answer
┌─────────────────────────────────────────────────────────────────┐
│  Phase 3: 记忆整合 (Consolidation) [✅ 已实现]                    │
│  ──────────────────────────────────                             │
│                                                                 │
│    ┌─────────────────────────────────────────────────────┐     │
│    │  brain.add(user_input)                              │     │
│    │  brain.add(answer)                                  │     │
│    │                                                     │     │
│    │  Mem0 后台处理:                                      │     │
│    │  • LLM 提取实体关系 → 写入 Neo4j                    │     │
│    │  • 文本向量化 → 写入 Qdrant                         │     │
│    └─────────────────────────────────────────────────────┘     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                        │
                        ▼
                    返回 answer
```

---

## 5. 核心组件设计

### 5.1 组件总览

```
┌─────────────────────────────────────────────────────────────────┐
│                         组件依赖图                               │
└─────────────────────────────────────────────────────────────────┘

                    ┌───────────────────┐
                    │   main.py         │
                    │   (入口 & 演示)    │
                    └─────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
    ┌─────────────────┐ ┌───────────┐ ┌─────────────────┐
    │ create_brain()  │ │create_chat│ │cognitive_process│
    │                 │ │  _llm()   │ │     ()          │
    └────────┬────────┘ └─────┬─────┘ └────────┬────────┘
             │                │                │
             ▼                │                │
    ┌─────────────────┐       │                │
    │  config.py      │◄──────┴────────────────┘
    │  (配置中心)      │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    MEM0_CONFIG                              │
    │  ┌─────────────┐ ┌─────────────┐ ┌────────────┐ ┌────────┐ │
    │  │vector_store │ │ graph_store │ │    llm     │ │embedder│ │
    │  │  (Qdrant)   │ │  (Neo4j)    │ │(DeepSeek/  │ │(Local/ │ │
    │  │             │ │             │ │ Gemini)    │ │Gemini) │ │
    │  └─────────────┘ └─────────────┘ └────────────┘ └────────┘ │
    └─────────────────────────────────────────────────────────────┘
```

### 5.2 配置模块 (config.py) `[✅ 已实现]`

**职责**: 集中管理所有配置，提供模型切换能力

```python
# 配置结构
config.py
├── API 密钥管理
│   ├── GOOGLE_API_KEY
│   └── DEEPSEEK_API_KEY
├── 模型切换开关
│   ├── LLM_PROVIDER: "gemini" | "deepseek"
│   ├── EMBEDDING_PROVIDER: "gemini" | "local"
│   └── ENABLE_GRAPH_STORE: bool
├── 模型配置详情
│   ├── GEMINI_CONFIG
│   ├── DEEPSEEK_CONFIG
│   └── LOCAL_EMBEDDING_CONFIG
└── 配置生成函数
    ├── _get_llm_config()
    ├── _get_embedder_config()
    ├── _get_collection_name()
    └── get_chat_config()
```

**关键设计决策**:

- Collection 名称包含 provider 和维度信息，避免向量维度冲突
- DeepSeek 使用 OpenAI 兼容接口
- 图谱存储可通过开关禁用

### 5.3 认知引擎 (main.py) `[✅ 已实现]`

**职责**: 实现核心认知流程

| 函数 | 职责 | 状态 |
|------|------|------|
| `create_brain()` | 初始化 Mem0 Memory 实例 | ✅ |
| `create_chat_llm()` | 创建对话用 LLM 实例 | ✅ |
| `cognitive_process()` | 执行完整认知流程 | ✅ |

**cognitive_process 流程**:

```python
def cognitive_process(brain, user_input, user_id):
    # 1. 混合检索
    search_results = brain.search(user_input, user_id=user_id)

    # 2. 构建知识上下文
    knowledge_context = format_results(search_results)

    # 3. LLM 推理
    response = llm.invoke(system_prompt + knowledge_context, user_input)

    # 4. 记忆整合
    brain.add(user_input, user_id=user_id)
    brain.add(answer, user_id=user_id)

    return answer
```

### 5.4 Python SDK (NeuroMemory 类) `[🚧 开发中]`

**目标**: 封装底层函数，提供简洁易用的 API

```python
# [🚧 开发中] 目标接口设计

class NeuroMemory:
    """神经符号混合记忆系统主接口"""

    def __init__(self, config: dict = None):
        """初始化记忆系统"""
        self._brain = Memory.from_config(config or MEM0_CONFIG)
        self._llm = create_chat_llm()

    def add(self, content: str, user_id: str = "default", metadata: dict = None) -> str:
        """添加记忆，返回 memory_id"""
        pass

    def search(self, query: str, user_id: str = "default", limit: int = 10) -> list:
        """混合检索记忆"""
        pass

    def ask(self, question: str, user_id: str = "default") -> str:
        """基于记忆回答问题 (完整认知流程)"""
        pass

    def get_graph(self, user_id: str = "default", depth: int = 2) -> dict:
        """获取用户的知识图谱"""
        pass
```

### 5.5 Mem0 集成层 `[✅ 已实现]`

**职责**: 抽象底层存储，提供统一的记忆操作接口

Mem0 Framework 提供的核心能力：

| 能力 | 说明 |
|------|------|
| **混合存储** | 同时写入 Vector Store 和 Graph Store |
| **实体提取** | 使用 LLM 从文本中提取实体和关系 |
| **混合检索** | 并行查询向量库和图谱，融合结果 |
| **自动去重** | 基于语义相似度的记忆去重 |

---

## 6. 数据模型

### 6.1 向量存储数据模型 (Qdrant) `[✅ 已实现]`

```
Collection: neuro_memory_{provider}_{dims}
例如: neuro_memory_huggingface_384

Document Schema:
┌─────────────────────────────────────────────────────────────────┐
│  {                                                              │
│    "id": "uuid-v4",                                             │
│    "vector": [0.12, -0.34, ...],  // 384 或 768 维              │
│    "payload": {                                                 │
│      "memory": "DeepMind 是 Google 的子公司",                    │
│      "user_id": "user_001",                                     │
│      "created_at": "2025-01-12T10:00:00Z",                      │
│      "metadata": { ... }                                        │
│    }                                                            │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 图谱存储数据模型 (Neo4j) `[✅ 已实现]`

```
节点 (Nodes):
┌─────────────────────────────────────────────────────────────────┐
│  (:Entity {                                                     │
│    name: "DeepMind",                                            │
│    type: "Organization",                                        │
│    user_id: "user_001",                                         │
│    created_at: datetime()                                       │
│  })                                                             │
└─────────────────────────────────────────────────────────────────┘

关系 (Relationships):
┌─────────────────────────────────────────────────────────────────┐
│  (:Entity {name: "DeepMind"})                                   │
│       -[:SUBSIDIARY_OF {                                        │
│           user_id: "user_001",                                  │
│           source: "user input"                                  │
│         }]->                                                    │
│  (:Entity {name: "Google"})                                     │
└─────────────────────────────────────────────────────────────────┘

示例图谱:
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   (Demis Hassabis)──[CEO_OF]──►(DeepMind)──[SUBSIDIARY_OF]──►(Google)
│                                    │                            │
│                                    │                            │
│                               [CREATED]                         │
│                                    │                            │
│                                    ▼                            │
│                               (Gemini)                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.3 用户隔离模型 `[✅ 已实现]`

```
┌─────────────────────────────────────────────────────────────────┐
│                      用户数据隔离策略                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  方式: 基于 user_id 字段的逻辑隔离                               │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Qdrant: payload.user_id 过滤                           │   │
│  │  Neo4j: 节点/边属性 user_id 过滤                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  查询示例:                                                       │
│  • Qdrant: filter={"user_id": "user_001"}                      │
│  • Neo4j: MATCH (n {user_id: "user_001"})                      │
│                                                                 │
│  注意: 这是逻辑隔离，不是物理隔离。适用于单租户或信任环境。        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. 接口设计

### 7.1 Python SDK 接口 `[🚧 开发中]`

```python
# 核心接口定义

class NeuroMemory:
    """神经符号混合记忆系统主接口"""

    def __init__(self, config: dict = None):
        """初始化记忆系统"""
        pass

    def add(
        self,
        content: str,
        user_id: str = "default",
        metadata: dict = None
    ) -> str:
        """
        添加记忆

        Args:
            content: 要记忆的文本内容
            user_id: 用户标识
            metadata: 可选元数据

        Returns:
            memory_id: 记忆唯一标识
        """
        pass

    def search(
        self,
        query: str,
        user_id: str = "default",
        limit: int = 10
    ) -> list[MemoryResult]:
        """
        混合检索记忆

        Args:
            query: 查询文本
            user_id: 用户标识
            limit: 返回结果数量上限

        Returns:
            检索结果列表，包含来源类型 (vector/graph)
        """
        pass

    def ask(
        self,
        question: str,
        user_id: str = "default"
    ) -> str:
        """
        基于记忆回答问题 (完整认知流程)

        Args:
            question: 用户问题
            user_id: 用户标识

        Returns:
            AI 生成的回答
        """
        pass

    def get_graph(
        self,
        user_id: str = "default",
        depth: int = 2
    ) -> dict:
        """
        获取用户的知识图谱

        Args:
            user_id: 用户标识
            depth: 遍历深度

        Returns:
            图谱数据 (nodes, edges)
        """
        pass
```

### 7.2 REST API 接口 `[📋 规划]`

```yaml
# OpenAPI 3.0 风格定义

POST /api/v1/memory
  description: 添加记忆
  request:
    body:
      content: string (required)
      user_id: string (default: "default")
      metadata: object
  response:
    memory_id: string

GET /api/v1/memory/search
  description: 混合检索
  parameters:
    query: string (required)
    user_id: string
    limit: integer (default: 10)
  response:
    results: array[MemoryResult]

POST /api/v1/ask
  description: 基于记忆回答问题
  request:
    body:
      question: string (required)
      user_id: string
  response:
    answer: string
    sources: array[MemoryResult]

GET /api/v1/graph
  description: 获取知识图谱
  parameters:
    user_id: string
    depth: integer (default: 2)
  response:
    nodes: array[Node]
    edges: array[Edge]

GET /api/v1/health
  description: 健康检查
  response:
    status: "healthy" | "unhealthy"
    components:
      neo4j: boolean
      qdrant: boolean
      llm: boolean
```

### 7.3 CLI 接口 `[📋 规划]`

```bash
# 命令行工具设计

neuromemory add "DeepMind 是 Google 的子公司" --user user_001
neuromemory search "Google 有哪些子公司" --user user_001 --limit 5
neuromemory ask "Demis 和 Gemini 有什么关系" --user user_001
neuromemory graph export --user user_001 --format json
neuromemory graph visualize --user user_001 --open-browser
neuromemory status  # 检查服务状态
```

---

## 8. 快速开始

### 8.1 环境要求

| 依赖 | 版本要求 | 说明 |
|------|----------|------|
| Python | >= 3.10 | 推荐 3.11+ |
| Docker | >= 20.0 | 用于运行数据库服务 |
| Docker Compose | >= 2.0 | 容器编排 |
| 内存 | >= 8GB | Neo4j + Qdrant 需要 |

### 8.2 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/NeuroMemory.git
cd NeuroMemory

# 2. 创建虚拟环境
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Linux/macOS
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
# 创建 .env 文件，填入 API 密钥
echo "DEEPSEEK_API_KEY=your-key-here" > .env
echo "GOOGLE_API_KEY=your-key-here" >> .env

# 5. 启动数据库服务
docker-compose up -d

# 6. 验证服务状态
docker-compose ps
# 确保 memory_graph_db 和 memory_vector_db 状态为 running
```

### 8.3 服务访问

| 服务 | 地址 | 凭证 |
|------|------|------|
| Neo4j Browser | http://localhost:7474 | neo4j / password123 |
| Qdrant API | http://localhost:6333 | 无需认证 |
| Qdrant Dashboard | http://localhost:6333/dashboard | 无需认证 |

### 8.4 运行演示

```bash
# 运行多跳推理演示
python main.py
```

预期输出：

```
==================================================
NeuroMemory 多跳推理演示
当前配置: LLM=deepseek, Embedding=local
==================================================

--- 正在构建初始记忆 ---
[输入] DeepMind 是 Google 的子公司。
[海马体] 激活记忆:
  - [vector] ...
[前额叶] 生成回答:
...
[后台] 知识图谱已更新。

... (更多输出)

--- 测试推理能力 ---
[输入] Demis Hassabis 和 Gemini 模型有什么关系？
[海马体] 激活记忆:
  - [graph] Demis Hassabis 是 DeepMind 的 CEO
  - [graph] Gemini 是 DeepMind 团队研发的
  - ...
[前额叶] 生成回答:
Demis Hassabis 作为 DeepMind 的 CEO，领导了 Gemini 模型的研发...
```

### 8.5 基础使用 (当前方式)

```python
from mem0 import Memory
from config import MEM0_CONFIG
from main import cognitive_process, create_brain

# 初始化
brain = create_brain()

# 添加记忆
cognitive_process(brain, "张三是李四的老板", user_id="test_user")
cognitive_process(brain, "李四负责人工智能项目", user_id="test_user")

# 查询推理
answer = cognitive_process(brain, "张三管理什么项目？", user_id="test_user")
```

### 8.6 使用 SDK (开发中)

```python
# [🚧 开发中] 目标使用方式

from neuromemory import NeuroMemory

# 初始化
memory = NeuroMemory()

# 添加记忆
memory.add("张三是李四的老板", user_id="test_user")
memory.add("李四负责人工智能项目", user_id="test_user")

# 检索
results = memory.search("张三管理什么", user_id="test_user")

# 问答 (完整认知流程)
answer = memory.ask("张三管理什么项目？", user_id="test_user")
print(answer)
```

---

## 9. 配置参考

### 9.1 环境变量

| 变量名 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `DEEPSEEK_API_KEY` | 是* | - | DeepSeek API 密钥 |
| `GOOGLE_API_KEY` | 是* | - | Google Gemini API 密钥 |

> \* 根据 `LLM_PROVIDER` 和 `EMBEDDING_PROVIDER` 设置，至少需要其中一个

### 9.2 模型切换配置 (config.py)

```python
# LLM 提供商选择
LLM_PROVIDER = "deepseek"  # 可选: "deepseek" | "gemini"

# Embedding 提供商选择
EMBEDDING_PROVIDER = "local"  # 可选: "local" | "gemini"

# 图谱存储开关
ENABLE_GRAPH_STORE = True  # True: 启用 Neo4j | False: 仅向量存储
```

### 9.3 LLM 模型配置

| 提供商 | 模型 | 用途 | 温度 |
|--------|------|------|------|
| DeepSeek | deepseek-chat | 对话推理 | 0.7 |
| DeepSeek | deepseek-chat | 实体提取 (Mem0) | 0.0 |
| Gemini | gemini-2.0-flash | 对话推理 | 0.7 |
| Gemini | gemini-2.0-flash | 实体提取 (Mem0) | 0.0 |

### 9.4 Embedding 模型配置

| 提供商 | 模型 | 维度 | 说明 |
|--------|------|------|------|
| Local (HuggingFace) | paraphrase-multilingual-MiniLM-L12-v2 | 384 | 本地运行，无 API 成本 |
| Gemini | text-embedding-004 | 768 | 云端 API，更高精度 |

### 9.5 数据库连接配置

```python
# Neo4j 配置 (在 MEM0_CONFIG 中)
"graph_store": {
    "provider": "neo4j",
    "config": {
        "url": "neo4j://localhost:17687",
        "username": "neo4j",
        "password": "password123",
    },
}

# Qdrant 配置 (在 MEM0_CONFIG 中)
"vector_store": {
    "provider": "qdrant",
    "config": {
        "host": "localhost",
        "port": 6333,
        "collection_name": "neuro_memory_huggingface_384",  # 自动生成
    },
}
```

### 9.6 Collection 命名规则

向量数据库的 Collection 名称根据 Embedding 配置自动生成：

```
neuro_memory_{provider}_{dims}
```

示例：
- 本地 HuggingFace: `neuro_memory_huggingface_384`
- Gemini: `neuro_memory_gemini_768`

> 这确保了不同 Embedding 模型的向量不会混在同一个 Collection 中

### 9.7 Docker Compose 服务配置

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

## 10. 部署架构

### 10.1 本地开发部署 `[✅ 当前方式]`

```
┌─────────────────────────────────────────────────────────────────┐
│                     本地开发环境                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Host Machine                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Python Application (.venv)                             │   │
│  │  • main.py                                              │   │
│  │  • config.py                                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Docker Compose                                         │   │
│  │  ┌─────────────────────┐  ┌─────────────────────┐      │   │
│  │  │ memory_graph_db     │  │ memory_vector_db    │      │   │
│  │  │ (Neo4j 5.26.0)      │  │ (Qdrant latest)     │      │   │
│  │  │                     │  │                     │      │   │
│  │  │ :7474 (Browser)     │  │ :6333 (API)         │      │   │
│  │  │ :17687 (Bolt)       │  │                     │      │   │
│  │  │                     │  │                     │      │   │
│  │  │ ./neo4j_data:/data  │  │ ./qdrant_data:      │      │   │
│  │  │                     │  │   /qdrant/storage   │      │   │
│  │  └─────────────────────┘  └─────────────────────┘      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  外部服务                                                        │
│  ┌─────────────────────┐  ┌─────────────────────┐              │
│  │ DeepSeek API        │  │ Google Gemini API   │              │
│  │ api.deepseek.com    │  │ (备选)              │              │
│  └─────────────────────┘  └─────────────────────┘              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 10.2 生产部署架构 `[📋 规划]`

```
┌─────────────────────────────────────────────────────────────────┐
│                     生产环境部署架构                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Load Balancer                        │   │
│  │                    (Nginx / Traefik)                    │   │
│  └─────────────────────────────┬───────────────────────────┘   │
│                                │                                │
│         ┌──────────────────────┼──────────────────────┐        │
│         ▼                      ▼                      ▼        │
│  ┌─────────────┐        ┌─────────────┐        ┌─────────────┐ │
│  │ API Server  │        │ API Server  │        │ API Server  │ │
│  │ (Replica 1) │        │ (Replica 2) │        │ (Replica N) │ │
│  └──────┬──────┘        └──────┬──────┘        └──────┬──────┘ │
│         │                      │                      │        │
│         └──────────────────────┼──────────────────────┘        │
│                                │                                │
│         ┌──────────────────────┼──────────────────────┐        │
│         ▼                      ▼                      ▼        │
│  ┌─────────────┐        ┌─────────────┐        ┌─────────────┐ │
│  │   Neo4j     │        │   Qdrant    │        │   Redis     │ │
│  │  (Primary)  │        │  (Cluster)  │        │  (Cache)    │ │
│  └─────────────┘        └─────────────┘        └─────────────┘ │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  可观测性平台                             │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐           │   │
│  │  │Prometheus │  │  Jaeger   │  │   Loki    │           │   │
│  │  │ (Metrics) │  │ (Tracing) │  │ (Logging) │           │   │
│  │  └───────────┘  └───────────┘  └───────────┘           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 11. 可观测性设计 `[📋 规划]`

### 11.1 观测三支柱

```
┌─────────────────────────────────────────────────────────────────┐
│                     可观测性架构 [📋 规划]                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │    Metrics      │  │    Tracing      │  │    Logging      │ │
│  │  (Prometheus)   │  │    (Jaeger)     │  │  (Loki/ELK)     │ │
│  │                 │  │                 │  │                 │ │
│  │  • 请求延迟     │  │  • 请求链路    │  │  • 结构化日志   │ │
│  │  • 吞吐量       │  │  • 跨服务追踪  │  │  • 错误堆栈     │ │
│  │  • 错误率       │  │  • 性能瓶颈    │  │  • 审计日志     │ │
│  │  • 资源使用     │  │                 │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│           │                    │                    │          │
│           └────────────────────┼────────────────────┘          │
│                                ▼                                │
│                    ┌─────────────────────┐                     │
│                    │      Grafana        │                     │
│                    │   统一可视化面板     │                     │
│                    └─────────────────────┘                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 11.2 关键指标 (Metrics)

```yaml
# 业务指标
neuromemory_memory_add_total:
  type: counter
  description: 记忆添加总数
  labels: [user_id, status]

neuromemory_search_duration_seconds:
  type: histogram
  description: 检索延迟分布
  labels: [user_id, source_type]  # source_type: vector/graph/hybrid

neuromemory_reasoning_duration_seconds:
  type: histogram
  description: LLM 推理延迟
  labels: [model, user_id]

# 系统指标
neuromemory_neo4j_nodes_total:
  type: gauge
  description: Neo4j 节点总数

neuromemory_qdrant_vectors_total:
  type: gauge
  description: Qdrant 向量总数

neuromemory_llm_tokens_total:
  type: counter
  description: LLM Token 消耗
  labels: [model, direction]  # direction: input/output
```

### 11.3 分布式追踪 (Tracing)

```
一次 cognitive_process 调用的追踪链路:

┌─────────────────────────────────────────────────────────────────┐
│  Trace: cognitive_process                                       │
│  TraceID: abc123                                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Span] cognitive_process (parent)                              │
│  ├── [Span] hybrid_retrieval                                    │
│  │   ├── [Span] qdrant_search ──────────────── 50ms            │
│  │   └── [Span] neo4j_traverse ─────────────── 80ms            │
│  │                                                              │
│  ├── [Span] llm_reasoning                                       │
│  │   └── [Span] deepseek_invoke ────────────── 1200ms          │
│  │                                                              │
│  └── [Span] memory_consolidation                                │
│      ├── [Span] entity_extraction ──────────── 800ms           │
│      ├── [Span] qdrant_upsert ──────────────── 30ms            │
│      └── [Span] neo4j_merge ────────────────── 60ms            │
│                                                                 │
│  Total: 2220ms                                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 11.4 结构化日志 (Logging)

```json
{
  "timestamp": "2025-01-12T10:30:00.123Z",
  "level": "INFO",
  "service": "neuromemory",
  "trace_id": "abc123",
  "span_id": "def456",
  "user_id": "user_001",
  "event": "cognitive_process_completed",
  "duration_ms": 2220,
  "details": {
    "input_length": 50,
    "retrieval_results": 5,
    "retrieval_sources": {"vector": 3, "graph": 2},
    "output_length": 200,
    "model": "deepseek-chat"
  }
}
```

---

## 12. 未来扩展 (TODO)

### 12.1 情景流 (Episodic Stream)

**优先级**: P2
**状态**: 📋 规划

```
┌─────────────────────────────────────────────────────────────────┐
│  [TODO] 情景流设计                                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  目标: 利用 LLM 长窗口保留完整对话历史作为"短期工作记忆"           │
│                                                                 │
│  设计方向:                                                       │
│  • 使用 Gemini 1.5 Pro 2M 窗口                                  │
│  • 保留最近 N 轮对话原文                                         │
│  • 与 Graph/Vector 层融合的检索策略                              │
│                                                                 │
│  待解决问题:                                                     │
│  • 情景记忆与长期记忆的边界                                       │
│  • 情景压缩/摘要策略                                             │
│  • 多用户情景隔离                                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 12.2 LangGraph 复杂编排

**优先级**: P2
**状态**: 📋 规划

```
┌─────────────────────────────────────────────────────────────────┐
│  [TODO] LangGraph 认知流程编排                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  当前: 简单线性流程 (检索 → 推理 → 整合)                          │
│                                                                 │
│  扩展方向:                                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                         │   │
│  │    ┌─────────┐                                         │   │
│  │    │ 输入    │                                         │   │
│  │    └────┬────┘                                         │   │
│  │         │                                              │   │
│  │         ▼                                              │   │
│  │    ┌─────────┐    需要更多信息?                         │   │
│  │    │ 检索    │◄─────────────────────┐                  │   │
│  │    └────┬────┘                      │                  │   │
│  │         │                           │ Yes              │   │
│  │         ▼                           │                  │   │
│  │    ┌─────────┐                 ┌────┴────┐            │   │
│  │    │ 分析    │────────────────►│ 判断    │            │   │
│  │    └────┬────┘                 └────┬────┘            │   │
│  │         │                           │ No               │   │
│  │         ▼                           ▼                  │   │
│  │    ┌─────────┐                 ┌─────────┐            │   │
│  │    │ 推理    │◄────────────────│ 整合    │            │   │
│  │    └────┬────┘                 └─────────┘            │   │
│  │         │                                              │   │
│  │         ▼                                              │   │
│  │    ┌─────────┐                                         │   │
│  │    │ 输出    │                                         │   │
│  │    └─────────┘                                         │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  潜在场景:                                                       │
│  • 多轮迭代检索 (检索不足时自动扩展查询)                           │
│  • 并行推理分支 (不同假设的并行验证)                               │
│  • 条件分支 (根据问题类型选择不同策略)                             │
│  • 自我反思循环 (答案质量自检)                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 12.3 其他扩展点

| 扩展项 | 优先级 | 状态 | 说明 |
|--------|--------|------|------|
| Python SDK | P0 | 🚧 开发中 | 封装底层函数，提供易用 API |
| REST API | P1 | 📋 规划 | FastAPI 实现，支持远程调用 |
| CLI 工具 | P2 | 📋 规划 | Click/Typer 实现 |
| 可观测性 | P1 | 📋 规划 | Metrics + Tracing + Logging |
| 图谱可视化 | P2 | 📋 规划 | Web UI 展示知识图谱 |
| 批量导入 | P2 | 📋 规划 | 支持文档批量解析和导入 |
| 记忆遗忘机制 | P3 | 📋 规划 | 基于访问频率/时间的智能遗忘 |
| 多模态记忆 | P3 | 📋 规划 | 支持图片/音频等多模态内容 |
| 分布式部署 | P3 | 📋 规划 | Neo4j 集群 + Qdrant 分片 |

---

## 13. 技术决策记录 (ADR)

### ADR-001: 选择 Mem0 作为记忆框架

**状态**: ✅ 已采纳
**日期**: 2025-01

**背景**:
需要一个支持混合存储（向量 + 图谱）的记忆管理框架。

**决策**:
选择 Mem0 框架，因为：
- 原生支持 graph_store 配置
- 自动实体关系提取
- 简洁的 API 设计
- 活跃的社区维护

**后果**:
- 正面: 快速实现混合记忆功能
- 负面: 受限于 Mem0 的抽象层，部分底层优化受限

---

### ADR-002: 选择 DeepSeek 作为默认 LLM

**状态**: ✅ 已采纳
**日期**: 2025-01

**背景**:
需要选择默认的 LLM 提供商。

**决策**:
默认使用 DeepSeek，同时保留 Gemini 切换能力，因为：
- DeepSeek 性价比高
- 中文理解能力强
- OpenAI 兼容接口，便于切换

**后果**:
- 正面: 降低 API 成本
- 负面: 需要维护两套 LLM 配置

---

### ADR-003: 选择本地 HuggingFace 作为默认 Embedding

**状态**: ✅ 已采纳
**日期**: 2025-01

**背景**:
需要选择 Embedding 方案。

**决策**:
默认使用本地 HuggingFace 模型 `paraphrase-multilingual-MiniLM-L12-v2`，因为：
- 无 API 调用成本
- 支持多语言
- 384 维向量足够日常使用

**权衡**:
- 放弃了架构文档中提到的 3072 维 OpenAI Embedding
- 如需更高精度可切换到 Gemini (768 维)

---

### ADR-004: 简单 user_id 隔离而非完整租户系统

**状态**: ✅ 已采纳
**日期**: 2025-01

**背景**:
需要支持多用户数据隔离。

**决策**:
采用简单的 user_id 参数隔离，而非完整的租户管理系统，因为：
- 降低系统复杂度
- 当前场景不需要认证/授权
- 可通过外部系统补充用户管理

**后果**:
- 正面: 简化实现
- 负面: 不适用于真正的多租户 SaaS 场景

---

### ADR-005: Python SDK 优先于 REST API 和 CLI

**状态**: ✅ 已采纳
**日期**: 2025-01

**背景**:
需要确定接入层的开发优先级。

**决策**:
优先开发 Python SDK，然后是 REST API，最后是 CLI，因为：
- SDK 是最直接的集成方式
- 可以快速验证接口设计
- REST API 可基于 SDK 构建
- CLI 主要用于调试，优先级较低

**后果**:
- 正面: 快速提供可用的编程接口
- 负面: 延迟了 HTTP API 的可用性

---

## 附录

### A. 术语表

| 术语 | 定义 |
|------|------|
| 神经符号混合 (Neuro-Symbolic) | 结合神经网络（向量）和符号系统（图谱）的 AI 架构 |
| 多跳推理 (Multi-hop Reasoning) | 通过多个中间实体推导最终答案的推理能力 |
| 混合检索 (Hybrid Retrieval) | 同时使用向量搜索和图谱遍历的检索策略 |
| 记忆整合 (Consolidation) | 将新信息融入长期记忆的过程 |

### B. 参考资料

- [Mem0 Documentation](https://docs.mem0.ai/)
- [Neo4j Graph Database](https://neo4j.com/docs/)
- [Qdrant Vector Database](https://qdrant.tech/documentation/)
- [LangChain Documentation](https://python.langchain.com/)

---

*文档结束*
