# 核心组件设计

> 返回 [主架构文档](ARCHITECTURE.md)
>
> **最后更新**: 2026-01

---

## 目录

- [组件总览](#组件总览)
- [配置模块 (config.py)](#配置模块-configpy)
- [认知引擎 (main.py)](#认知引擎-mainpy)
  - [异步记忆整合模块](#异步记忆整合模块)
  - [代词消解模块](#代词消解模块)
  - [图谱关系处理模块](#图谱关系处理模块)
  - [意图判断模块](#意图判断模块)
  - [LLM 工厂](#llm-工厂)
  - [核心认知流程](#核心认知流程)
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
    ┌─────────────┬───────────┼───────────┬─────────────┐
    │             │           │           │             │
    ▼             ▼           ▼           ▼             ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────────┐
│ 异步    │ │ 代词    │ │ 图谱    │ │ 意图    │ │ cognitive_    │
│ 记忆    │ │ 消解    │ │ 关系    │ │ 判断    │ │ process()     │
│ 整合    │ │ 模块    │ │ 处理    │ │ 模块    │ │               │
└────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └───────┬───────┘
     │           │           │           │             │
     └───────────┴───────────┴───────────┴─────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
    ┌─────────────────┐ ┌───────────┐ ┌─────────────────┐
    │ create_brain()  │ │create_chat│ │  config.py      │
    │                 │ │  _llm()   │ │  (配置中心)      │
    └────────┬────────┘ └─────┬─────┘ └────────┬────────┘
             │                │                │
             └────────────────┼────────────────┘
                              ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    MEM0_CONFIG                              │
    │  ┌─────────────┐ ┌─────────────┐ ┌────────────┐ ┌────────┐ │
    │  │vector_store │ │ graph_store │ │    llm     │ │embedder│ │
    │  │  (Qdrant)   │ │  (Neo4j)    │ │(DeepSeek/  │ │(Local/ │ │
    │  │             │ │             │ │ Gemini)    │ │Gemini/ │ │
    │  │             │ │             │ │            │ │Silicon)│ │
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
│   ├── DEEPSEEK_API_KEY
│   └── SILICONFLOW_API_KEY   # 新增
├── 模型切换开关
│   ├── LLM_PROVIDER: "gemini" | "deepseek"
│   ├── EMBEDDING_PROVIDER: "gemini" | "local" | "siliconflow"  # 新增 siliconflow
│   └── ENABLE_GRAPH_STORE: bool
├── 模型配置详情
│   ├── GEMINI_CONFIG
│   ├── DEEPSEEK_CONFIG
│   ├── LOCAL_EMBEDDING_CONFIG
│   └── SILICONFLOW_EMBEDDING_CONFIG  # 新增
└── 配置生成函数
    ├── _get_llm_config()
    ├── _get_embedder_config()
    ├── _get_collection_name()
    └── get_chat_config()
```

### 关键设计决策

- Collection 名称包含 provider 和维度信息，避免向量维度冲突
- DeepSeek 使用 OpenAI 兼容接口
- SiliconFlow 使用 OpenAI 兼容接口 (BAAI/bge-m3, 1024 维)
- 图谱存储可通过开关禁用

### Embedding 提供商对比

| 提供商 | 模型 | 维度 | 说明 |
|--------|------|------|------|
| local | paraphrase-multilingual-MiniLM-L12-v2 | 384 | 本地 HuggingFace，无 API 成本 |
| gemini | text-embedding-004 | 768 | Google API |
| siliconflow | BAAI/bge-m3 | 1024 | 国内云端，高精度，OpenAI 兼容接口 |

---

## 认知引擎 (main.py) `[✅ 已实现]`

**职责**: 实现核心认知流程

| 函数/类 | 职责 | 状态 |
|---------|------|------|
| `_background_consolidate()` | 后台执行记忆整合（异步） | ✅ |
| `extract_user_identity()` | 从输入中提取用户身份信息 | ✅ |
| `resolve_pronouns()` | 将代词"我"替换为用户名 | ✅ |
| `normalize_relation_type()` | 归一化关系类型（英文→中文） | ✅ |
| `dedupe_relations()` | 对图谱关系进行去重 | ✅ |
| `IntentResult` | 意图判断结果模型 | ✅ |
| `classify_intent()` | 通过 LLM 判断用户输入的意图类型 | ✅ |
| `create_brain()` | 初始化 Mem0 Memory 实例 | ✅ |
| `create_chat_llm()` | 创建对话用 LLM 实例 | ✅ |
| `cognitive_process()` | 执行完整认知流程 | ✅ |

---

### 异步记忆整合模块

**职责**: 将记忆整合改为后台异步任务，用户无需等待

```python
from concurrent.futures import ThreadPoolExecutor

# 后台整合线程池（max_workers=2 确保不会积压太多任务）
_consolidation_executor = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="mem_consolidate"
)

def _background_consolidate(brain: Memory, texts: list[str], user_id: str) -> None:
    """后台执行记忆整合（异步，不阻塞主流程）"""
    for text in texts:
        try:
            brain.add(text, user_id=user_id)
        except Exception as e:
            _consolidation_logger.warning(f"记忆保存失败: {e}")
```

**性能优化效果**: 用户感知延迟从 ~38s 降低到 ~10s

---

### 代词消解模块

**职责**: 自动提取用户身份并将代词"我"替换为用户名

```python
# 用户身份上下文（内存缓存）
USER_IDENTITY_CACHE: dict[str, dict] = {}

def extract_user_identity(user_input: str, user_id: str) -> str | None:
    """
    从输入中提取用户身份信息
    
    匹配模式: "我的名字叫XXX"、"我叫XXX"、"我是XXX" 等
    """
    patterns = [
        r"我的名字叫(\S+)",
        r"我叫(\S+)",
        r"我是(\S+)",
        r"我的名字是(\S+)",
    ]
    # ... 提取并缓存用户名

def resolve_pronouns(user_input: str, user_id: str) -> str:
    """
    将代词"我"替换为用户名（如果已知）
    
    示例: "我的儿子" → "小朱的儿子"
    """
    # 排除身份声明语句，避免 "我的名字叫小朱" → "小朱的名字叫小朱"
```

---

### 图谱关系处理模块

**职责**: 归一化和去重图谱关系

```python
# 关系类型映射（英文 → 中文）
RELATION_NORMALIZE_MAP = {
    "daughter": "女儿",
    "son": "儿子",
    "has": "有",
    "has_name": "名字",
    "brother": "弟弟",
    "sister": "姐妹",
    "father": "父亲",
    "mother": "母亲",
    # ...
}

def normalize_relation_type(rel_type: str) -> str:
    """归一化关系类型（英文 → 中文）"""
    return RELATION_NORMALIZE_MAP.get(rel_type.lower(), rel_type)

def dedupe_relations(relations: list) -> list:
    """对图谱关系进行去重（基于 source|relationship|target 唯一键）"""
```

---

### 意图判断模块

**职责**: 通过 LLM 判断用户输入的意图类型

```python
class IntentResult(BaseModel):
    """意图判断结果"""
    intent: Literal["personal", "factual", "general"]
    reasoning: str
    needs_external_search: bool

def classify_intent(user_input: str) -> IntentResult:
    """
    意图类型:
    - personal: 个人信息/记忆查询（从本地记忆检索）
    - factual:  需要外部事实知识（可能需要搜索）
    - general:  通用对话/闲聊（直接对话）
    """
```

---

### LLM 工厂

**职责**: 根据配置创建 LLM 实例

```python
def create_chat_llm():
    """根据配置创建对话 LLM 实例"""
    chat_config = get_chat_config()
    
    if chat_config["provider"] == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(...)
    elif chat_config["provider"] == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(...)

def create_brain() -> Memory:
    """初始化混合记忆系统"""
    return Memory.from_config(MEM0_CONFIG)
```

---

### 核心认知流程

```python
def cognitive_process(brain, user_input, user_id):
    # Step 0.5: 提取用户身份（如果有）
    extract_user_identity(user_input, user_id)
    
    # Step 0.6: 代词消解（用于存储和检索）
    resolved_input = resolve_pronouns(user_input, user_id)
    
    # Step 1: 意图判断
    intent_result = classify_intent(resolved_input)
    
    # Step 2: 混合检索
    search_results = brain.search(resolved_input, user_id=user_id)
    
    # Step 3: 处理结果（向量记忆 + 图谱关系归一化去重）
    knowledge_context = format_results(search_results)
    
    # Step 4: 深度推理（包含用户身份上下文）
    response = llm.invoke(system_prompt + knowledge_context, user_input)
    
    # Step 5: 异步记忆整合（不阻塞用户）
    _consolidation_executor.submit(_background_consolidate, brain, texts, user_id)
    
    return answer  # 立即返回
```

---

## Python SDK (NeuroMemory 类) `[✅ 已实现]`

**目标**: 封装底层函数，提供简洁易用的 API。底层委托 `PrivateBrain`（`get_brain()`）。

```python
from neuromemory import NeuroMemory

m = NeuroMemory()
m.add("张三是李四的老板", user_id="test_user")   # 返回 memory_id
m.search("张三管理什么", user_id="test_user", limit=5)  # 返回 dict: memories, relations, metadata
m.ask("张三管理什么项目？", user_id="test_user")  # 返回 answer 字符串
m.get_graph(user_id="test_user", depth=2)        # 返回 dict: status, nodes, edges, ...
```

配套 **CLI**：`neuromemory status`、`add`、`search`、`ask`、`graph export`、`graph visualize`。安装：`uv pip install -e .` 或 `pip install -e .`。详见 [API.md](API.md)、[GETTING_STARTED.md](GETTING_STARTED.md)。

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
        "config": {
            "host": "localhost",
            "port": 6400,  # 使用 6400 避免 Windows 保留端口冲突（6333 在保留范围 6296-6395 内）
            "collection_name": "neuro_memory_openai_1024",  # 自动生成
            "embedding_model_dims": 1024,  # 明确指定向量维度
        }
    },
    "graph_store": {  # 可通过 ENABLE_GRAPH_STORE 开关禁用
        "provider": "neo4j",
        "config": {
            "url": "neo4j://localhost:17687",
            "username": "neo4j",
            "password": "password123",
        }
    },
    "llm": {
        "provider": "openai",  # DeepSeek 使用 OpenAI 兼容接口
        "config": {
            "model": "deepseek-chat",
            "temperature": 0.0,
            "openai_base_url": "https://api.deepseek.com",
        }
    },
    "embedder": {
        "provider": "openai",  # SiliconFlow 使用 OpenAI 兼容接口
        "config": {
            "model": "BAAI/bge-m3",
            "embedding_dims": 1024,
            "openai_base_url": "https://api.siliconflow.cn/v1",
            "api_key": SILICONFLOW_API_KEY,
        }
    }
}

brain = Memory.from_config(MEM0_CONFIG)
```

---

## 相关文档

- [接口设计](API.md) - 完整 API 定义
- [数据模型](DATA_MODEL.md) - 数据结构说明
- [配置参考](CONFIGURATION.md) - 详细配置选项
