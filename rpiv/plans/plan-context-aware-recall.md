---
description: "功能实施计划: context-aware-recall"
status: pending
created_at: 2026-03-05T14:30:00
updated_at: 2026-03-05T14:30:00
archived_at: null
related_files:
  - rpiv/requirements/prd-context-aware-recall.md
  - rpiv/research-context-aware-recall.md
---

# 功能：情境感知自动召回（Context-Aware Recall）

以下计划应该是完整的，但在开始实施之前，验证文档和代码库模式以及任务合理性非常重要。

特别注意现有工具、类型和模型的命名。从正确的文件导入等。

## 功能描述

在 recall 流程中增加情境感知能力：通过 embedding 原型匹配自动推断用户当前情境（work/personal/social/learning），对匹配情境的 trait 记忆施加 soft boost（0~0.10），模拟人脑的情境依赖记忆。零额外延迟、零额外成本、API 签名不变。

## 用户故事

作为 neuromem SDK 开发者，
我想要 recall 自动根据用户当前情境优先返回匹配的 trait 记忆，
以便终端用户获得更精准、更自然的个性化体验。

## 问题陈述

V2 trait 系统已在存储端标注情境（`trait_context` 列），但 recall 端完全没有利用这些信息。同等语义相关度的工作偏好和生活偏好在排序中无法区分，全靠语义碰运气。

## 解决方案陈述

新增 ContextService 服务，使用 embedding 原型匹配（复用已有 query_embedding）+ 关键词兜底推断情境，在 scored_search 的评分公式中增加 context_match_bonus，trait 情境完全匹配 +0.10*confidence，general +0.07*confidence。情境不明确时 confidence=0，完全退化为现有行为。

## 功能元数据

**功能类型**：新功能
**估计复杂度**：中
**主要受影响的系统**：SearchService, NeuroMemory recall
**依赖项**：无新增外部依赖（纯 Python 实现余弦相似度）

---

## 上下文参考

### 相关代码库文件（实施前必读）

- `neuromem/services/search.py` (全文, 重点第 248-471 行) - scored_search 方法，包含完整的评分公式 SQL，emotion_match 的实现模式是 context_match 的参考模板
- `neuromem/_core.py` (第 1128-1412 行) - recall 方法，第 1176 行计算 query_embedding，第 1186-1206 行并行 fetch，第 1404-1412 行返回值构造
- `neuromem/_core.py` (第 1481-1560 行) - _fetch_vector_memories 方法，SearchService 实例化和 scored_search 调用模式
- `neuromem/_core.py` (第 562-624 行) - NeuroMemory.__init__，理解构造参数和初始化流程
- `neuromem/_core.py` (第 816-843 行) - _cached_embed 方法，理解 embedding 缓存机制
- `neuromem/providers/embedding.py` - EmbeddingProvider ABC，embed/embed_batch/dims 签名
- `neuromem/models/memory.py` (第 70 行) - trait_context 列定义：`mapped_column(String(20), nullable=True)`
- `neuromem/db.py` (第 113 行, 第 222 行) - trait_context 列 DDL 和索引 idx_trait_context
- `neuromem/services/trait_engine.py` (第 116, 193, 354 行) - trait_context 写入路径参考

### 要创建的新文件

- `neuromem/services/context.py` - ContextService：原型向量管理 + 情境推断算法 + 关键词兜底
- `tests/test_context.py` - ContextService 单元测试

### 要遵循的模式

**Service 创建模式**（参考所有现有 Service）：

```python
# neuromem/services/search.py:41 — SearchService 构造模式
class SearchService:
    def __init__(self, db: AsyncSession, embedding: EmbeddingProvider, ...):
        self.db = db
        self._embedding = embedding
```

ContextService 不需要 db session（纯计算，不操作数据库），只需要 embedding provider。

**emotion_match 集成模式**（scored_search 中动态构建 SQL 片段）：

```python
# neuromem/services/search.py:333-344
if current_emotion and isinstance(current_emotion, dict):
    q_valence = float(current_emotion.get("valence", 0))
    q_arousal = float(current_emotion.get("arousal", 0))
    emotion_bonus_sql = (
        f"0.10 * GREATEST(0, 1.0 - SQRT(...) / 2.83)"
    )
else:
    emotion_bonus_sql = "0"
```

context_match 用完全相同的模式：构建 SQL 片段字符串，注入到最终查询。

**recall 返回值扩展模式**：

```python
# neuromem/_core.py:1404-1412 — 直接在 dict 中新增 key
return {
    "vector_results": vector_results,
    ...
    "merged": merged[:limit],
    # 新增两个字段即可
}
```

**命名约定**：
- Service 类名：`ContextService`（与 `SearchService`, `MemoryService` 一致）
- 文件名：`context.py`（小写，与 `search.py`, `memory.py` 一致）
- 常量：全大写下划线（`MARGIN_THRESHOLD`, `MAX_CONTEXT_BOOST`）

**日志模式**：
```python
logger = logging.getLogger(__name__)
```

---

## 实施计划

### Phase 1：基础 — ContextService 核心

新增 `neuromem/services/context.py`，实现情境推断的完整能力：
- 纯 Python 余弦相似度函数
- 中英双语原型句子定义
- 原型向量懒加载 + 内存缓存
- 情境推断算法（embedding 匹配 + 关键词兜底）

### Phase 2：评分集成 — SearchService SQL 扩展

修改 `neuromem/services/search.py`，在 scored_search 的评分公式中增加 context_match_bonus。

### Phase 3：Facade 集成 — recall 方法连接

修改 `neuromem/_core.py`，在 recall 中调用 ContextService 推断情境，将结果传入 scored_search，并扩展返回值。

### Phase 4：测试与验证

编写单元测试和集成测试，验证情境推断、评分加成、退化行为、返回值扩展。

---

## 逐步任务

### 任务 1：CREATE `neuromem/services/context.py`

**IMPLEMENT**：创建 ContextService，包含以下组件：

#### 1.1 纯 Python 余弦相似度函数

```python
import math

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度。"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
```

不引入 numpy/scipy 依赖。4 个情境 x 1024 维 = 约 0.4-1.2ms，满足性能要求。

#### 1.2 原型句子定义

定义 `CONTEXT_PROTOTYPE_SENTENCES: dict[str, list[str]]`，4 个情境（work/personal/social/learning），每个包含约 30 个中英文句子（中英各 15 句）。

```python
CONTEXT_PROTOTYPE_SENTENCES: dict[str, list[str]] = {
    "work": [
        # 中文 (~15句)
        "帮我写一个 Python 函数",
        "这个 API 接口怎么设计",
        "代码审查发现了一个 bug",
        "明天有个技术评审会议",
        "部署到生产环境",
        "项目架构需要重构",
        "数据库查询太慢了需要优化",
        "这个模块的单元测试怎么写",
        "CI/CD 流水线配置有问题",
        "这个需求的技术方案怎么做",
        "线上出了一个紧急故障",
        "代码合并有冲突需要解决",
        "这个功能的性能指标是什么",
        "项目进度需要更新一下",
        "帮我做一下代码重构",
        # 英文 (~15句)
        "Help me write a Python function",
        "How should I design this API endpoint",
        "Found a bug during code review",
        "I have a technical review meeting tomorrow",
        "Deploy to production environment",
        "The project architecture needs refactoring",
        "Database query is too slow and needs optimization",
        "How to write unit tests for this module",
        "CI/CD pipeline configuration has issues",
        "What's the technical approach for this requirement",
        "There's an urgent production incident",
        "Need to resolve merge conflicts",
        "What are the performance metrics for this feature",
        "Need to update the project progress",
        "Help me refactor this code",
    ],
    "personal": [
        # 中文
        "周末去哪里玩",
        "晚饭吃什么好",
        "最近在看一部电视剧",
        "我妈妈生日快到了",
        "今天天气真好想出去走走",
        "最近睡眠质量不太好",
        "家里需要买些什么东西",
        "推荐一部好看的电影",
        "最近在减肥控制饮食",
        "宠物猫今天不太舒服",
        "想买一台新的笔记本电脑",
        "假期准备去旅行",
        "最近在学做饭",
        "健身计划怎么安排",
        "家里要装修了",
        # 英文
        "Where should I go this weekend",
        "What should I have for dinner",
        "I've been watching a TV series lately",
        "My mom's birthday is coming up",
        "The weather is nice today I want to go for a walk",
        "My sleep quality has been poor lately",
        "What do I need to buy for home",
        "Recommend a good movie",
        "I'm on a diet controlling my food intake",
        "My cat doesn't feel well today",
        "I want to buy a new laptop",
        "Planning to travel during the holiday",
        "I've been learning to cook recently",
        "How should I plan my fitness routine",
        "My home needs renovation",
    ],
    "social": [
        # 中文
        "朋友聚会怎么安排",
        "同事关系不太好怎么处理",
        "社交场合穿什么合适",
        "如何拒绝别人的邀请",
        "团建活动有什么好的建议",
        "和朋友吵架了怎么和好",
        "第一次见面聊什么话题好",
        "怎么维持长距离的友谊",
        "邻居太吵了怎么沟通",
        "送朋友什么礼物好",
        "同学聚会要不要参加",
        "怎么在社交中给人留下好印象",
        "约会去哪里比较好",
        "如何处理人际冲突",
        "怎么扩大社交圈子",
        # 英文
        "How to plan a friends gathering",
        "How to deal with difficult colleague relationships",
        "What to wear for social occasions",
        "How to decline an invitation politely",
        "Any good suggestions for team building activities",
        "Had a fight with a friend how to make up",
        "What topics to talk about when meeting someone for the first time",
        "How to maintain long-distance friendships",
        "My neighbor is too noisy how to communicate",
        "What gift should I get for a friend",
        "Should I attend the class reunion",
        "How to make a good impression in social settings",
        "Where is a good place for a date",
        "How to handle interpersonal conflicts",
        "How to expand my social circle",
    ],
    "learning": [
        # 中文
        "这个概念的原理是什么",
        "推荐一些学习资源",
        "怎么入门机器学习",
        "这篇论文的核心观点是什么",
        "有没有好的在线课程推荐",
        "这个数学公式怎么推导",
        "如何提高英语口语水平",
        "这个历史事件的背景是什么",
        "量子计算的基本概念是什么",
        "怎么系统地学习一门新技能",
        "这本书的主要内容是什么",
        "深度学习和传统机器学习有什么区别",
        "这个实验的设计思路是什么",
        "怎么写好一篇学术论文",
        "请解释一下这个理论",
        # 英文
        "What's the principle behind this concept",
        "Recommend some learning resources",
        "How to get started with machine learning",
        "What are the key points of this paper",
        "Are there any good online courses you'd recommend",
        "How to derive this mathematical formula",
        "How to improve English speaking skills",
        "What's the historical background of this event",
        "What are the basic concepts of quantum computing",
        "How to systematically learn a new skill",
        "What are the main contents of this book",
        "What's the difference between deep learning and traditional ML",
        "What's the design approach of this experiment",
        "How to write a good academic paper",
        "Please explain this theory",
    ],
}
```

#### 1.3 关键词兜底字典

```python
CONTEXT_KEYWORDS: dict[str, set[str]] = {
    "work": {"代码", "项目", "API", "部署", "会议", "deadline", "code", "debug",
             "重构", "测试", "review", "上线", "需求", "sprint", "issue", "bug",
             "服务器", "数据库", "接口", "编程", "开发", "server", "deploy",
             "commit", "merge", "pull request", "CI", "CD"},
    "personal": {"周末", "家里", "旅行", "做饭", "朋友", "家人", "生日", "假期",
                 "看电影", "运动", "健身", "宠物", "减肥", "睡眠", "装修",
                 "weekend", "home", "travel", "cooking", "family", "birthday",
                 "holiday", "movie", "exercise", "fitness", "pet"},
    "social": {"聚会", "社交", "团建", "聊天", "约会", "关系", "邻居", "同事",
               "礼物", "party", "gathering", "date", "relationship",
               "colleague", "friend", "gift", "reunion"},
    "learning": {"学习", "教程", "原理", "论文", "课程", "入门", "理解", "概念",
                 "公式", "理论", "实验", "学术", "study", "tutorial", "theory",
                 "paper", "course", "concept", "formula", "research",
                 "principle", "textbook"},
}
```

#### 1.4 ContextService 类

```python
class ContextService:
    """情境推断服务 — 从 query embedding 推断用户当前情境。

    不操作数据库，纯计算服务。原型向量懒加载并缓存在内存中。
    """

    MARGIN_THRESHOLD = 0.05
    MAX_CONTEXT_BOOST = 0.10
    GENERAL_CONTEXT_BOOST = 0.07
    CONFIDENCE_NORMALIZER = 0.15  # margin / normalizer -> confidence (capped at 1.0)

    def __init__(self, embedding: EmbeddingProvider):
        self._embedding = embedding
        self._prototypes: dict[str, list[float]] | None = None
        self._prototype_norms: dict[str, float] | None = None

    async def ensure_prototypes(self) -> None:
        """懒加载原型向量。首次调用时计算，后续调用跳过。"""
        if self._prototypes is not None:
            return

        try:
            # 收集所有句子并批量 embed
            all_sentences: list[str] = []
            context_ranges: dict[str, tuple[int, int]] = {}
            offset = 0
            for ctx, sentences in CONTEXT_PROTOTYPE_SENTENCES.items():
                context_ranges[ctx] = (offset, offset + len(sentences))
                all_sentences.extend(sentences)
                offset += len(sentences)

            embeddings = await self._embedding.embed_batch(all_sentences)

            # 计算每个情境的均值向量
            self._prototypes = {}
            self._prototype_norms = {}
            dims = len(embeddings[0]) if embeddings else 0
            for ctx, (start, end) in context_ranges.items():
                ctx_embeddings = embeddings[start:end]
                mean_vec = [
                    sum(e[d] for e in ctx_embeddings) / len(ctx_embeddings)
                    for d in range(dims)
                ]
                self._prototypes[ctx] = mean_vec
                self._prototype_norms[ctx] = math.sqrt(sum(x * x for x in mean_vec))

            logger.info("Context prototypes initialized: %d contexts, %d dims", len(self._prototypes), dims)
        except Exception as e:
            logger.warning("Failed to initialize context prototypes: %s", e)
            self._prototypes = {}
            self._prototype_norms = {}

    def infer_context(self, query_embedding: list[float], query_text: str = "") -> tuple[str, float]:
        """从 query embedding 推断最可能的情境。

        Args:
            query_embedding: 已计算的 query 向量
            query_text: 原始查询文本，用于关键词兜底

        Returns:
            (context_label, confidence)
            confidence=0 时返回 ("general", 0.0)
        """
        # 原型未就绪时安全退化
        if not self._prototypes:
            return ("general", 0.0)

        # 计算 query 与各原型的余弦相似度
        query_norm = math.sqrt(sum(x * x for x in query_embedding))
        if query_norm == 0:
            return ("general", 0.0)

        similarities: dict[str, float] = {}
        for ctx, proto in self._prototypes.items():
            proto_norm = self._prototype_norms.get(ctx, 0.0)
            if proto_norm == 0:
                similarities[ctx] = 0.0
                continue
            dot = sum(q * p for q, p in zip(query_embedding, proto))
            similarities[ctx] = dot / (query_norm * proto_norm)

        # 排序取最强匹配
        sorted_items = sorted(similarities.items(), key=lambda x: x[1], reverse=True)
        best_ctx, best_score = sorted_items[0]
        second_score = sorted_items[1][1] if len(sorted_items) > 1 else 0.0
        margin = best_score - second_score

        # margin 低于阈值 -> 尝试关键词兜底
        if margin < self.MARGIN_THRESHOLD:
            kw_result = self._infer_context_keywords(query_text)
            if kw_result:
                return kw_result
            return ("general", 0.0)

        confidence = min(margin / self.CONFIDENCE_NORMALIZER, 1.0)
        return (best_ctx, confidence)

    def _infer_context_keywords(self, query_text: str) -> tuple[str, float] | None:
        """关键词兜底推断。"""
        if not query_text:
            return None

        query_lower = query_text.lower()
        scores: dict[str, int] = {}
        for ctx, keywords in CONTEXT_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw.lower() in query_lower)
            if count > 0:
                scores[ctx] = count

        if not scores:
            return None

        best_ctx = max(scores, key=scores.get)
        best_count = scores[best_ctx]
        # 至少匹配 2 个关键词才有一定置信度，1 个关键词给较低置信度
        if best_count >= 2:
            return (best_ctx, 0.6)
        elif best_count == 1:
            # 检查是否有其他情境也匹配了 1 个关键词
            tied = [ctx for ctx, c in scores.items() if c == 1]
            if len(tied) == 1:
                return (best_ctx, 0.4)
        return None

    def clear_prototypes(self) -> None:
        """清除原型向量缓存（provider 变更时调用）。"""
        self._prototypes = None
        self._prototype_norms = None
        logger.info("Context prototypes cache cleared")
```

**IMPORTS**：
```python
from __future__ import annotations

import logging
import math

from neuromem.providers.embedding import EmbeddingProvider
```

**GOTCHA**：
- 不能引入 numpy/scipy —— SDK 保持轻量依赖
- `embed_batch` 是 async 方法，`ensure_prototypes` 必须是 async
- `infer_context` 是同步方法（纯计算，不涉及 IO），但调用前必须确保 `ensure_prototypes` 已完成
- 原型向量的 norm 预计算缓存在 `_prototype_norms` 中，减少每次推断的计算量

**VALIDATE**：`cd D:/CODE/NeuroMem && uv run python -c "from neuromem.services.context import ContextService; print('import ok')"`

---

### 任务 2：UPDATE `neuromem/services/search.py` — scored_search 增加 context_match

**IMPLEMENT**：在 `scored_search` 方法中增加两个新参数和 context_match SQL 片段。

#### 2.1 方法签名扩展

在 `scored_search` 的参数列表中新增（第 262 行 `current_emotion` 参数之后）：

```python
    async def scored_search(
        self,
        ...
        current_emotion: dict | None = None,
        query_context: str | None = None,        # 新增
        context_confidence: float = 0.0,          # 新增
    ) -> list[dict]:
```

#### 2.2 构建 context_match SQL 片段

在 emotion_bonus_sql 构建之后（约第 344 行），添加 context_match SQL 构建：

```python
        # Context matching bonus SQL fragment
        if query_context and query_context != "general" and context_confidence > 0:
            # 使用 trait_context 独立列（非 metadata JSONB），已有索引 idx_trait_context
            context_bonus_sql = (
                f"CASE"
                f"  WHEN memory_type = 'trait' AND trait_context = '{query_context}'"
                f"  THEN {0.10 * context_confidence:.4f}"
                f"  WHEN memory_type = 'trait' AND trait_context = 'general'"
                f"  THEN {0.07 * context_confidence:.4f}"
                f"  ELSE 0"
                f" END"
            )
        else:
            context_bonus_sql = "0"
```

**重要**：使用 `trait_context` 独立列（`models/memory.py:70`），而非 `metadata->>'context'`。`trait_context` 有专用索引 `idx_trait_context`（`db.py:222`），性能更优。

#### 2.3 SQL 查询中注入 context_match

需要在两个位置添加 context_match：

**位置 1**：vector_ranked CTE 的 SELECT 列表中增加 `trait_context` 列（约第 379 行）：

```sql
SELECT id, content, memory_type, metadata, created_at, extracted_timestamp,
       access_count, last_accessed_at, trait_stage, trait_context,  -- 新增 trait_context
       1 - (embedding <=> '{vector_str}') AS vector_score,
       ...
```

**位置 2**：最终 SELECT 中，在 `{emotion_bonus_sql} AS emotion_match` 之后增加：

```sql
                   -- context_match_bonus: 0~0.10
                   {context_bonus_sql} AS context_match,
```

**位置 3**：final score 计算中，在 `+ {emotion_bonus_sql}` 之后增加：

```sql
                      + {context_bonus_sql}
```

#### 2.4 结果 dict 中增加 context_match 字段

在结果构建循环中（约第 461 行），增加：

```python
                "context_match": round(float(row.context_match), 4),
```

**PATTERN**：`neuromem/services/search.py:333-344`（emotion_match SQL 片段构建模式）

**GOTCHA**：
- `trait_context` 列在 vector_ranked CTE 和 hybrid CTE 中都需要传递
- context_bonus_sql 中直接内联数值（`0.10 * confidence`），不用 SQL 参数，与 emotion_bonus_sql 模式一致
- 注意 SQL 字符串拼接中的空格和换行
- `query_context` 值来自 ContextService 推断，可能的值只有 work/personal/social/learning/general，不存在 SQL 注入风险（但仍然建议使用 f-string 内联值而非字符串拼接，因为原代码就是这个模式）

**VALIDATE**：`cd D:/CODE/NeuroMem && uv run python -c "from neuromem.services.search import SearchService; print('import ok')"`

---

### 任务 3：UPDATE `neuromem/_core.py` — recall 集成 ContextService

**IMPLEMENT**：在 recall 方法中添加情境推断调用，并将结果传入 scored_search。

#### 3.1 NeuroMemory.__init__ 中初始化 ContextService

在 `__init__` 方法中（约第 622 行 embedding_cache 之后），添加：

```python
        # Context inference service (lazy prototype initialization)
        from neuromem.services.context import ContextService
        self._context_service = ContextService(self._embedding)
```

#### 3.2 recall 方法中调用情境推断

在 `query_embedding` 计算之后（第 1176 行之后），添加：

```python
        # Infer context from query (zero extra latency — reuses query_embedding)
        await self._context_service.ensure_prototypes()
        inferred_context, context_confidence = self._context_service.infer_context(
            query_embedding, query_text=query
        )
```

#### 3.3 将推断结果传入 _fetch_vector_memories

修改 `_fetch_vector_memories` 调用，新增 `query_context` 和 `context_confidence` 参数。

**_fetch_vector_memories 方法签名扩展**：

```python
    async def _fetch_vector_memories(
        self,
        ...
        current_emotion: dict | None = None,
        query_context: str | None = None,           # 新增
        context_confidence: float = 0.0,             # 新增
    ) -> list[dict]:
```

**common_kwargs 中添加**（约第 1504 行）：

```python
        common_kwargs = dict(
            decay_rate=decay_rate,
            query_embedding=query_embedding,
            as_of=as_of,
            created_after=created_after,
            created_before=created_before,
            current_emotion=current_emotion,
            query_context=query_context,              # 新增
            context_confidence=context_confidence,     # 新增
        )
```

**recall 方法中的调用**（约第 1187 行）：

```python
        coros = [
            self._fetch_vector_memories(
                user_id, query, limit, query_embedding, _event_after, _event_before, _decay,
                as_of=as_of,
                memory_type=memory_type,
                created_after=created_after,
                created_before=created_before,
                current_emotion=current_emotion,
                query_context=inferred_context,          # 新增
                context_confidence=context_confidence,    # 新增
            ),
            ...
```

#### 3.4 recall 返回值扩展

在返回 dict 中（约第 1404 行），新增两个字段：

```python
        return {
            "vector_results": vector_results,
            "conversation_results": conversation_results,
            "graph_results": graph_results,
            "graph_context": graph_context,
            "user_profile": user_profile,
            "active_traits": active_traits,
            "merged": merged[:limit],
            "inferred_context": inferred_context,          # 新增
            "context_confidence": context_confidence,       # 新增
        }
```

**PATTERN**：`neuromem/_core.py:1186-1194`（recall 并行 fetch 调用模式），`neuromem/_core.py:1504-1511`（common_kwargs 构建模式）

**GOTCHA**：
- `ensure_prototypes()` 是 async 方法，首次调用会触发 `embed_batch`（约 120 句，1-3 秒），后续调用跳过（已缓存）
- 不能把 `ensure_prototypes()` 放到 `asyncio.gather` 中并行执行——它必须在 `infer_context` 之前完成
- `ContextService` 实例持有 embedding provider 引用，与 NeuroMemory 实例共生命周期

**VALIDATE**：`cd D:/CODE/NeuroMem && uv run python -c "from neuromem._core import NeuroMemory; print('import ok')"`

---

### 任务 4：CREATE `tests/test_context.py` — 单元测试

**IMPLEMENT**：测试 ContextService 的核心功能。

#### 4.1 测试纯 Python 余弦相似度

```python
from neuromem.services.context import cosine_similarity

def test_cosine_similarity_identical():
    """相同向量的相似度为 1.0。"""
    v = [1.0, 2.0, 3.0]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-6

def test_cosine_similarity_orthogonal():
    """正交向量的相似度为 0.0。"""
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(cosine_similarity(a, b)) < 1e-6

def test_cosine_similarity_zero_vector():
    """零向量返回 0.0。"""
    a = [0.0, 0.0]
    b = [1.0, 2.0]
    assert cosine_similarity(a, b) == 0.0
```

#### 4.2 测试 ContextService 推断逻辑

由于 MockEmbeddingProvider 基于 hash 生成确定性向量，原型向量在 mock 下无语义意义。因此需要直接注入已知原型向量来测试推断逻辑。

```python
import pytest
from neuromem.services.context import ContextService

@pytest.fixture
def context_service_with_prototypes(nm):
    """注入已知原型向量的 ContextService。"""
    svc = ContextService(nm._embedding)
    # 手动注入原型向量（绕过 embed_batch）
    svc._prototypes = {
        "work": [1.0, 0.0, 0.0, 0.0],
        "personal": [0.0, 1.0, 0.0, 0.0],
        "social": [0.0, 0.0, 1.0, 0.0],
        "learning": [0.0, 0.0, 0.0, 1.0],
    }
    svc._prototype_norms = {ctx: 1.0 for ctx in svc._prototypes}
    return svc

def test_infer_context_clear_match(context_service_with_prototypes):
    """明确情境时返回正确标签和高置信度。"""
    svc = context_service_with_prototypes
    ctx, conf = svc.infer_context([1.0, 0.0, 0.0, 0.0])
    assert ctx == "work"
    assert conf > 0

def test_infer_context_ambiguous(context_service_with_prototypes):
    """情境不明确时返回 general, 0.0。"""
    svc = context_service_with_prototypes
    # 均匀向量 -> 所有原型相似度相同 -> margin = 0
    ctx, conf = svc.infer_context([0.5, 0.5, 0.5, 0.5])
    assert ctx == "general"
    assert conf == 0.0

def test_infer_context_no_prototypes():
    """原型未初始化时安全退化。"""
    from unittest.mock import MagicMock
    svc = ContextService(MagicMock())
    ctx, conf = svc.infer_context([1.0, 0.0, 0.0])
    assert ctx == "general"
    assert conf == 0.0
```

#### 4.3 测试关键词兜底

```python
def test_keyword_fallback_work(context_service_with_prototypes):
    """embedding 无法区分时，关键词兜底识别 work。"""
    svc = context_service_with_prototypes
    result = svc._infer_context_keywords("帮我调试这个 bug，代码有问题")
    assert result is not None
    assert result[0] == "work"

def test_keyword_fallback_no_match(context_service_with_prototypes):
    """无关键词匹配时返回 None。"""
    svc = context_service_with_prototypes
    result = svc._infer_context_keywords("今天感觉还不错")
    assert result is None
```

#### 4.4 测试 ensure_prototypes 懒加载

```python
@pytest.mark.requires_db
async def test_ensure_prototypes_lazy_load(nm):
    """ensure_prototypes 首次调用后缓存，二次调用跳过。"""
    svc = ContextService(nm._embedding)
    assert svc._prototypes is None
    await svc.ensure_prototypes()
    assert svc._prototypes is not None
    assert len(svc._prototypes) == 4  # work, personal, social, learning
    # 二次调用不重新计算
    first_ref = svc._prototypes
    await svc.ensure_prototypes()
    assert svc._prototypes is first_ref
```

**PATTERN**：`tests/test_recall.py`（现有测试模式），`conftest.py`（nm fixture 使用）

**VALIDATE**：`cd D:/CODE/NeuroMem && uv run pytest tests/test_context.py -v`

---

### 任务 5：UPDATE 现有测试 — 回归验证

**IMPLEMENT**：确保现有测试不因新增 context_match 字段而失败。

需要检查的关键点：
1. `scored_search` SQL 新增了 `context_match` 列和 `trait_context` 列引用——现有测试中 vector_ranked CTE 的列列表变化不应破坏断言
2. recall 返回值新增了 `inferred_context` 和 `context_confidence` 字段——如果现有测试对返回值做严格 key 检查，需要更新

**检查方式**：
```bash
cd D:/CODE/NeuroMem && uv run pytest tests/ -v --tb=short 2>&1 | head -100
```

如果测试失败，根据错误信息修复：
- SQL 列不存在 -> 检查 vector_ranked CTE 中是否正确添加了 trait_context
- key 断言失败 -> 新增字段不应导致问题（dict 新增 key 不会破坏 `result["vector_results"]` 等访问）
- context_match 列不存在 -> 确认 SQL 中 context_bonus_sql 默认值为 "0"

**VALIDATE**：`cd D:/CODE/NeuroMem && uv run pytest tests/ -v -m "not slow"`

---

### 任务 6：集成测试 — 端到端验证情境 boost

**IMPLEMENT**：在 `tests/test_context.py` 或新建 `tests/test_recall_context.py` 中添加集成测试。

```python
@pytest.mark.requires_db
async def test_recall_returns_context_fields(nm):
    """recall 返回值包含 inferred_context 和 context_confidence。"""
    user_id = "test_context_user"
    await nm.ingest(user_id=user_id, role="user", content="I prefer functional programming")
    import asyncio
    await asyncio.sleep(0.5)  # 等待后台提取

    result = await nm.recall(user_id=user_id, query="help me write code")
    assert "inferred_context" in result
    assert "context_confidence" in result
    assert isinstance(result["inferred_context"], str)
    assert isinstance(result["context_confidence"], float)
    assert result["context_confidence"] >= 0.0
    assert result["context_confidence"] <= 1.0

@pytest.mark.requires_db
async def test_recall_context_match_in_scores(nm):
    """scored_search 结果中包含 context_match 字段。"""
    user_id = "test_context_score_user"
    await nm.ingest(user_id=user_id, role="user", content="I like using Python for data analysis at work")
    import asyncio
    await asyncio.sleep(0.5)

    result = await nm.recall(user_id=user_id, query="help me write Python code")
    for r in result.get("vector_results", []):
        assert "context_match" in r
```

**VALIDATE**：`cd D:/CODE/NeuroMem && uv run pytest tests/test_context.py -v`

---

## 测试策略

### 单元测试

- `cosine_similarity`：相同向量、正交向量、零向量、反方向向量
- `ContextService.infer_context`：明确情境、模糊情境（退化）、空原型（退化）、零向量
- `ContextService._infer_context_keywords`：单关键词、多关键词、无匹配、多情境冲突
- `ContextService.ensure_prototypes`：懒加载、二次调用跳过、embed_batch 失败时安全退化

### 集成测试

- recall 返回值包含 `inferred_context` 和 `context_confidence`
- scored_search 结果包含 `context_match` 字段
- 情境匹配的 trait 评分高于不匹配的（需要真实 embedding 或精心构造的 mock）

### 边缘情况

- embedding provider 初始化前调用 recall（原型未就绪）
- 全部 trait 都是 general 情境
- 只有一种情境的 trait 存在
- query_embedding 为零向量
- 空数据库 recall

---

## 验证命令

### 级别 1：语法检查

```bash
cd D:/CODE/NeuroMem && uv run python -c "from neuromem.services.context import ContextService; print('ok')"
cd D:/CODE/NeuroMem && uv run python -c "from neuromem.services.search import SearchService; print('ok')"
cd D:/CODE/NeuroMem && uv run python -c "from neuromem._core import NeuroMemory; print('ok')"
```

### 级别 2：单元测试

```bash
cd D:/CODE/NeuroMem && uv run pytest tests/test_context.py -v
```

### 级别 3：回归测试

```bash
cd D:/CODE/NeuroMem && uv run pytest tests/ -v -m "not slow"
```

### 级别 4：全量测试

```bash
cd D:/CODE/NeuroMem && uv run pytest tests/ -v
```

---

## 验收标准

- [ ] `neuromem/services/context.py` 实现完整的 ContextService
- [ ] 纯 Python 余弦相似度，无 numpy/scipy 依赖
- [ ] 中英双语原型句子（4 情境 x ~30 句）
- [ ] `scored_search` SQL 增加 context_match CASE WHEN，使用 `trait_context` 独立列
- [ ] `recall` 方法返回 `inferred_context` 和 `context_confidence`
- [ ] recall 签名不变（非破坏性扩展）
- [ ] margin < 0.05 时安全退化为 ("general", 0.0)
- [ ] 原型向量懒加载 + 内存缓存
- [ ] 关键词兜底处理强信号
- [ ] 所有现有测试通过（零回归）
- [ ] 新增测试覆盖推断逻辑 + 评分加成 + 退化行为

---

## 完成检查清单

- [ ] 所有任务按顺序完成
- [ ] 每个任务验证命令通过
- [ ] 全量测试通过
- [ ] context_match 默认值为 0（confidence=0 时），确保无回归
- [ ] 代码遵循现有 Service 模式和命名约定

---

## 备注

### 关键设计决策

1. **纯 Python 余弦相似度**：不引入 numpy，SDK 保持轻量。4 个情境 x 1024 维只需约 1ms。
2. **使用 `trait_context` 独立列**：设计文档中写的是 `metadata->>'context'`，调研报告确认实际应使用独立列（有索引，性能更优）。
3. **SQL 内联数值**：context_bonus_sql 中直接内联 `0.10 * confidence` 的计算结果，与 emotion_bonus_sql 模式一致，避免 SQL 参数增加。
4. **ContextService 不操作数据库**：纯计算服务，构造函数只接收 embedding provider。与其他 Service（需要 db session）的模式不同，因为情境推断不涉及数据库操作。
5. **原型向量 norm 预计算**：原型向量不变，其 L2 norm 预计算缓存在 `_prototype_norms`，每次推断只需计算 query 的 norm 一次。
