---
description: "技术可行性调研: context-aware-recall"
status: completed
created_at: 2026-03-05T13:00:00
updated_at: 2026-03-05T13:00:00
---

# 技术可行性调研：情境感知自动召回

## 1. 余弦相似度计算

### 现状

neuromem 代码库中**没有**任何 Python 层面的余弦相似度实现。所有相似度计算都在 PostgreSQL 中通过 pgvector 的 `<=>` 操作符（余弦距离）完成。`pyproject.toml` 中也**没有** numpy 或 scipy 依赖。

**证据**：
- `neuromem/services/search.py` 中 `1 - (embedding <=> '{vector_str}')` 是唯一的相似度计算（SQL 层）
- Grep `cosine_similarity|numpy|scipy` 在 `neuromem/` 下无匹配

### 推荐方案

**纯 Python 实现**，不引入 numpy/scipy 依赖。理由：
1. 原型向量仅 4-5 个情境，每次 recall 只需计算 4-5 次余弦相似度，性能不是问题
2. neuromem 作为 SDK 保持轻量依赖是重要原则
3. 实现极简（约 5 行代码）：

```python
import math

def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
```

4. 1024 维向量的纯 Python 余弦相似度计算耗时约 0.1-0.3ms，4 个情境共 0.4-1.2ms，远低于 1ms 的约束上限（注意：原型向量的 norm 可以预计算缓存，进一步减半）

### 风险

- 无。纯计算，无外部依赖，无 IO。

---

## 2. Embedding 原型向量缓存

### EmbeddingProvider 接口

**签名**（`neuromem/providers/embedding.py`）：

```python
class EmbeddingProvider(ABC):
    async def embed(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dims(self) -> int: ...
```

### 批量 embed 支持

**所有生产 provider 都原生支持批量 embed**：
- `SiliconFlowEmbedding.embed_batch()` —— 直接将 `texts` 列表发送到 API（`neuromem/providers/siliconflow.py:31-48`）
- `OpenAIEmbedding.embed_batch()` —— 同上（`neuromem/providers/openai_embedding.py:31-48`）
- `SentenceTransformerEmbedding.embed_batch()` —— 本地批量编码

### embed 调用量估算

设计文档要求每个情境约 30 句（中英各 15 句），4 个情境 = 120 句。

- **批量调用**：`embed_batch(120 sentences)` = 1 次 API 调用
- SiliconFlow/OpenAI 的批量 API 对 120 条短文本无压力
- **计算时机**：SDK 初始化时一次性计算，缓存在内存中
- **缓存失效**：仅当 embedding provider 变更时需重算

### 与现有缓存的关系

`NeuroMemory._cached_embed()` 是基于 query 文本的 LRU 缓存（`_core.py:816-843`），最大 100 条。原型向量缓存应该**独立存储**，不占用 query 缓存空间。推荐在新的 `ContextService` 中维护独立的 `_prototypes: dict[str, list[float]]` 属性。

### 风险

- **初始化延迟**：120 句 × embed 一次 ≈ 1-3 秒（取决于 API 响应）。可通过 lazy 初始化（首次 recall 时触发）或后台 `asyncio.create_task()` 缓解。
- **MockEmbeddingProvider**：测试中的 mock provider 基于 hash 生成确定性向量。原型向量在 mock 下语义无效，但不影响功能测试（可验证推断逻辑本身）。

---

## 3. SQL 扩展性能

### 当前 scored_search 的 trait 处理

`scored_search`（`neuromem/services/search.py:248-471`）已有的 CASE WHEN：

```sql
-- trait_boost: 0~0.25 (search.py:427-435)
CASE
    WHEN memory_type = 'trait' THEN
        CASE trait_stage
            WHEN 'core'        THEN 0.25
            WHEN 'established' THEN 0.15
            WHEN 'emerging'    THEN 0.05
            ELSE 0
        END
    ELSE 0
END
```

**关键发现**：`trait_stage` 是 memories 表的**独立列**（不在 metadata JSONB 内），有直接列访问性能。

### context_match 的实现方式

设计文档中的 SQL 访问 `metadata->>'context'`。但实际 `trait_context` 是**独立列**（`models/memory.py:70`）：

```python
trait_context: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

并且已有索引（`db.py:222-223`）：

```sql
CREATE INDEX IF NOT EXISTS idx_trait_context
ON memories (user_id, trait_context) WHERE trait_context IS NOT NULL
```

**因此 context_match 应该使用 `trait_context` 列而非 `metadata->>'context'`**，性能更优。SQL 改为：

```sql
CASE
    WHEN memory_type = 'trait' AND trait_context = :query_context
    THEN 0.10 * :context_confidence
    WHEN memory_type = 'trait' AND trait_context = 'general'
    THEN 0.07 * :context_confidence
    ELSE 0
END AS context_match
```

### 性能影响

- **增加一个 CASE WHEN**：在已有 4 个 CASE WHEN 的 SQL 中再加一个，开销可忽略
- **`trait_context` 是独立列 + 有索引**：PostgreSQL 在 WHERE 或 CASE 中访问该列几乎零额外成本
- **不需要新建索引**：`idx_trait_context` 已存在

### 风险

- 无实质性能风险。CASE WHEN 在 SQL 执行计划中是行内计算，不影响索引使用或扫描方式。

---

## 4. 现有代码可复用性

### Services 目录结构

```
neuromem/services/
├── __init__.py
├── conversation.py      # ConversationService
├── encryption.py        # EncryptionService
├── file_processor.py    # FileProcessorService
├── files.py             # FileService
├── graph.py             # GraphService
├── graph_memory.py      # GraphMemoryService
├── kv.py                # KVService
├── memory.py            # MemoryService
├── memory_extraction.py # MemoryExtractionService
├── reflection.py        # ReflectionService
├── search.py            # SearchService
├── temporal.py          # TemporalExtractor/Service
└── trait_engine.py      # TraitEngine
```

### 可复用模式

1. **Service 创建模式**：每个 Service 接收 `db: AsyncSession` + `embedding: EmbeddingProvider` 作为构造参数。新的 `ContextService` 应遵循同样模式。

2. **recall 流程的插入点**：`_core.py:1176` 已计算 `query_embedding`，可直接传给 `ContextService.infer_context(query_embedding)`。结果传入 `scored_search()` 的新参数。

3. **scored_search 扩展模式**：
   - `emotion_match` 的实现方式（`search.py:333-344`）是完美参考：构建 SQL 片段字符串，注入到最终查询中
   - `context_match` 可以用完全相同的模式：在 `scored_search()` 中新增 `query_context` 和 `context_confidence` 参数，构建 SQL 片段

4. **返回值扩展**：recall 返回 dict（`_core.py:1404-1412`），直接新增 `"inferred_context"` 和 `"context_confidence"` 字段即可，非破坏性。

5. **embed_batch 复用**：原型向量初始化直接调用 `self._embedding.embed_batch(sentences)` 即可。

### 不可复用

- `_cached_embed()` 是文本 → 向量的 LRU 缓存，不适合原型向量缓存（原型是均值向量，不是单句 embedding）。

---

## 5. trait_context 字段现状

### 存储方式

**独立列**，不在 metadata JSONB 内：

```python
# neuromem/models/memory.py:70
trait_context: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

### 数据库层

- 列定义：`db.py:113` — `ALTER TABLE memories ADD COLUMN IF NOT EXISTS trait_context VARCHAR(20)`
- 数据同步：`db.py:173` — `trait_context = metadata->>'context'`（从 metadata 同步到独立列）
- 索引：`db.py:222-223` — `idx_trait_context ON memories (user_id, trait_context) WHERE trait_context IS NOT NULL`

### 写入路径

- `trait_engine.py:116` — `TraitEngine.store_behavior()` 直接设置 `trait_context=context`
- `trait_engine.py:193` — `TraitEngine.upgrade_trait()` 保留 `trait_context`
- `trait_engine.py:354` — trait 分裂时继承 `trait_context`

### 读取路径（recall 相关）

- `_core.py:1628` — `profile_view()` 的 SQL 查询包含 `trait_context`
- `_core.py:2074` — `get_traits()` 支持按 `trait_context` 过滤
- **但 `scored_search` 中没有使用 `trait_context`** — 这正是本功能要填补的空白

### 结论

`trait_context` 是成熟的独立列，有完整的写入/读取路径和索引支持。在 `scored_search` SQL 中直接引用 `trait_context` 列是最优方案，不需要走 `metadata->>'context'` 的 JSONB 路径。

---

## 6. 推荐技术方案

### 新增文件

| 文件 | 说明 |
|------|------|
| `neuromem/services/context.py` | ContextService，包含原型管理、推断算法、关键词兜底 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `neuromem/services/search.py` | `scored_search()` 新增 `query_context`/`context_confidence` 参数，SQL 增加 `context_match` CASE WHEN |
| `neuromem/_core.py` | recall 中调用 ContextService，将推断结果传入 scored_search，返回值增加两个字段 |

### 实现步骤

1. 在 `context.py` 中实现纯 Python `cosine_similarity()`
2. 定义 `CONTEXT_PROTOTYPES` 句子字典和 `CONTEXT_KEYWORDS` 兜底字典
3. 实现 `ContextService`：
   - `__init__(embedding: EmbeddingProvider)` — 持有 provider 引用
   - `async def ensure_prototypes()` — lazy 初始化，调用 `embed_batch` 计算均值向量
   - `def infer_context(query_embedding) -> tuple[str, float]` — 同步方法，纯计算
   - `def infer_context_keywords(query: str) -> tuple[str, float] | None` — 关键词兜底
4. `scored_search` 增加 context_match SQL（参考 emotion_match 模式）
5. `recall` 方法在获取 `query_embedding` 后调用情境推断，传入 scored_search

### 关键注意事项

1. **使用 `trait_context` 列而非 `metadata->>'context'`** — 设计文档中写的是 `metadata->>'context'`，实际应改用独立列
2. **原型向量 lazy 初始化** — 不在 `__init__` 中阻塞，首次 recall 或后台任务中计算
3. **原型向量的 norm 预计算** — 原型向量不变，其 norm 可以一次性计算缓存，余弦相似度计算减半
4. **测试中 mock provider 的原型向量无语义** — 需要在测试中直接注入已知原型向量，绕过 embed_batch

---

## 7. 潜在风险与缓解

| 风险 | 严重度 | 缓解措施 |
|------|--------|----------|
| 初始化延迟（120 句 embed） | 低 | lazy 初始化 + 后台 asyncio.create_task |
| 原型向量质量不佳导致误判 | 中 | margin 阈值兜底 + 关键词二次验证 + confidence 为 0 时完全退化 |
| 不同 embedding 模型效果差异 | 低 | 原型向量随 provider 重算；margin 机制自适应 |
| scored_search SQL 复杂度增加 | 极低 | 仅增加一个 CASE WHEN，与已有 trait_boost 模式一致 |
| 测试 mock provider 无法验证语义 | 低 | 单元测试直接注入原型向量，验证推断逻辑；集成测试使用真实 embedding |
