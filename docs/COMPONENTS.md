# 核心组件设计

> 返回 [主架构文档](ARCHITECTURE.md)

---

## 目录

- [组件总览](#组件总览)
- [配置模块 (config.py)](#配置模块-configpy)
- [认知引擎 (main.py)](#认知引擎-mainpy)
- [Python SDK (NeuroMemory 类)](#python-sdk-neuromemory-类)
- [Mem0 集成层](#mem0-集成层)

---

## 组件总览

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

---

## 配置模块 (config.py) `[✅ 已实现]`

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

### 关键设计决策

- Collection 名称包含 provider 和维度信息，避免向量维度冲突
- DeepSeek 使用 OpenAI 兼容接口
- 图谱存储可通过开关禁用

---

## 认知引擎 (main.py) `[✅ 已实现]`

**职责**: 实现核心认知流程

| 函数 | 职责 | 状态 |
|------|------|------|
| `create_brain()` | 初始化 Mem0 Memory 实例 | ✅ |
| `create_chat_llm()` | 创建对话用 LLM 实例 | ✅ |
| `cognitive_process()` | 执行完整认知流程 | ✅ |

### cognitive_process 流程

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

---

## Python SDK (NeuroMemory 类) `[🚧 开发中]`

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

---

## Mem0 集成层 `[✅ 已实现]`

**职责**: 抽象底层存储，提供统一的记忆操作接口

### Mem0 Framework 提供的核心能力

| 能力 | 说明 |
|------|------|
| **混合存储** | 同时写入 Vector Store 和 Graph Store |
| **实体提取** | 使用 LLM 从文本中提取实体和关系 |
| **混合检索** | 并行查询向量库和图谱，融合结果 |
| **自动去重** | 基于语义相似度的记忆去重 |

### 集成配置示例

```python
MEM0_CONFIG = {
    "vector_store": {
        "provider": "qdrant",
        "config": { ... }
    },
    "graph_store": {
        "provider": "neo4j",
        "config": { ... }
    },
    "llm": {
        "provider": "deepseek",
        "config": { ... }
    },
    "embedder": {
        "provider": "huggingface",
        "config": { ... }
    }
}

brain = Memory.from_config(MEM0_CONFIG)
```

---

## 相关文档

- [接口设计](API.md) - 完整 API 定义
- [数据模型](DATA_MODEL.md) - 数据结构说明
- [配置参考](CONFIGURATION.md) - 详细配置选项
