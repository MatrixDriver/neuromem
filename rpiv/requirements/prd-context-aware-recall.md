---
description: "产品需求文档: context-aware-recall"
status: in-progress
created_at: 2026-03-05T14:00:00
updated_at: 2026-03-05T14:30:00
archived_at: null
---

# 情境感知自动召回（Context-Aware Recall）PRD

## 1. 执行摘要

neuromem 的 V2 trait 系统已在存储端为每个 trait 标注了情境（work/personal/social/learning/general），但 recall 端完全没有利用这些情境信息。当前的召回纯靠语义相似度 + recency + importance + trait_boost + emotion_match 排序，不感知用户当前所处的情境，导致工作场景和生活场景的 trait 在排序中无法区分。

本功能通过 embedding 原型匹配自动推断用户当前情境，对匹配情境的 trait 记忆施加 soft boost，模拟人脑的情境依赖记忆（Tulving 编码特异性原则）。这是业界首个在 recall 时做自动情境推断的记忆系统——调研显示 Mem0、Zep、ChatGPT、Letta、Cursor 等产品均无此能力。

**MVP 目标**：在零额外延迟、零额外成本的前提下，让 recall 自动将情境匹配的 trait 排序前移，同时保持情境不明确时的零干扰。

## 2. 使命

**使命声明**：让 AI 记忆系统像人脑一样，自动根据当前情境优先召回匹配的记忆，无需用户或开发者手动配置。

**核心原则**：

1. **模拟人脑，减少人为配置**：情境推断完全自动化，不需要用户设置或调用方传参
2. **soft boost，不是 hard filter**：情境不匹配的记忆不会被排除，只是排名靠后——就像工作时也能想起家里的事，只是需要更强的触发
3. **graceful degradation**：推断不出情境时退化为现有行为，零副作用
4. **零额外开销**：复用已有的 query_embedding，不引入额外的 LLM 调用或网络请求

## 3. 目标用户

**主要用户**：neuromem SDK 开发者（集成方）
- 技术舒适度：高，熟悉 Python async 编程和 AI 应用开发
- 需求：recall 返回更精准的结果排序，减少调用方的后处理工作
- 痛点：当前同等语义相关度的 trait 排序依赖运气，无法区分工作偏好和生活偏好

**终端用户**：AI 应用的使用者
- 完全无感知此功能，自动生效
- 价值体现：与 AI 对话时，系统自动在工作场景优先调用工作相关偏好，在生活场景优先调用生活相关偏好

## 4. MVP 范围

### 范围内

- [x] embedding 原型匹配推断情境（中英双语原型句子，每个情境约 30 句）
- [x] 关键词兜底规则（处理强信号词如"代码"、"周末"等）
- [x] context_match_bonus 0~0.10 x confidence 叠加到 scored_search
- [x] general 情境的 trait 获得 0.07 x confidence 的部分 boost
- [x] margin 阈值安全退化（margin < 0.05 时返回 general, 0.0）
- [x] recall 返回值增加 `inferred_context` + `context_confidence` 字段
- [x] 原型向量 SDK 初始化时计算并缓存在内存中
- [x] 对比实验验证排序质量（MRR 衡量）
- [x] 单元测试覆盖情境推断 + 评分加成 + 退化行为

### 范围外

- [ ] fact/episodic 的情境标注和 boost（仅 trait）
- [ ] LLM 推断情境（成本和延迟不可接受）
- [ ] 自适应原型（从用户记忆中学习，冷启动问题）
- [ ] 可关闭开关（单情境 Space 中 boost 均匀分配，等效无影响）
- [ ] `context_hint` 参数（调用方显式传入情境）
- [ ] A/B 线上观测
- [ ] fact 层面的情境标注

## 5. 用户故事

**US-1**：作为 SDK 开发者，我希望 recall 自动将工作相关的 trait 在用户讨论代码时排序靠前，以便用户获得更精准的编程偏好建议。

> 示例：用户问"帮我写个 Python 脚本"，`trait[work]: "偏好函数式编程风格"` 自动排在 `trait[personal]: "喜欢极简风格"` 前面。

**US-2**：作为 SDK 开发者，我希望当系统无法判断用户情境时，recall 行为与现有版本完全一致，以便升级无风险。

> 示例：用户问"今天怎么样？"，无法判断情境，所有 trait 保持原始排序，confidence = 0.0。

**US-3**：作为 SDK 开发者，我希望 recall 返回推断出的情境信息，以便我可以在 UI 中展示或用于调试。

> 示例：recall 返回 `{"inferred_context": "work", "context_confidence": 0.82, ...}`。

**US-4**：作为 SDK 开发者，我希望标注为 general 的 trait 在任何情境下都获得部分 boost，以便通用偏好不被情境化偏好完全压过。

> 示例：`trait[general]: "回答时喜欢简洁直接"` 在工作和生活场景都获得 0.07 x confidence 的加成。

**US-5**：作为终端用户，我希望与 AI 聊生活话题时，系统自动优先使用我的生活偏好而非工作偏好，以便体验更自然。

> 示例：用户聊"周末去哪里玩"，`trait[personal]: "喜欢自然风光"` 排序高于 `trait[work]: "偏好敏捷开发"`。

**US-6**：作为 SDK 开发者，我希望情境推断不增加任何延迟或成本，以便 recall 高频调用场景下的性能不受影响。

> 示例：情境推断仅需计算 4 个余弦相似度（复用已有 query_embedding），耗时 < 0.1ms。

## 6. 核心架构与模式

### 整体流程

```
当前 recall 流程:
  query -> embed -> 向量检索 + BM25 -> RRF 融合 -> bonus 加成 -> 排序

增加情境感知后:
  query -> embed -> 向量检索 + BM25 -> RRF 融合 -> bonus 加成 -> [+ context_match_bonus] -> 排序
                                                                        |
                                                                从 query 自动推断情境
```

### 新增服务

新增 `ContextService`（`neuromem/services/context.py`），职责：

1. 管理情境原型向量（初始化、缓存、更新）
2. 从 query_embedding 推断情境（embedding 原型匹配 + 关键词兜底）
3. 提供 `infer_context()` 方法供 `_core.py` 调用

### 设计模式

- 遵循现有 Service 分层：ContextService 接收 embedding provider，不直接操作数据库
- 原型向量缓存在 ContextService 实例内存中（dict），不持久化
- 与 SearchService 的交互：_core.py 先调用 ContextService 推断情境，再将结果传入 SearchService 的 scored_search

### 评分公式扩展

```
score = prospective_penalty
        x base_relevance
        x (1 + recency + importance + trait_boost + emotion_match + context_match)
```

| bonus 类型 | 范围 | 人脑机制 |
|-----------|------|---------|
| recency | 0~0.15 | 遗忘曲线 |
| importance | 0~0.15 | 情绪编码增强 |
| trait_boost | 0~0.25 | 自我图式效应 |
| emotion_match | 0~0.10 | 心境一致性效应 |
| **context_match** | **0~0.10** | **情境依赖记忆** |

## 7. 功能规格

### 7.1 情境原型向量

为 4 个情境标签（work/personal/social/learning）各准备约 30 个中英双语典型句子，计算 embedding 均值作为原型向量。

**初始化时机**：ContextService 首次调用 `infer_context()` 时懒加载计算，缓存在内存。

**缓存失效**：embedding provider 变更时清除缓存。

**容错**：缓存未就绪时跳过情境推断，返回 `("general", 0.0)`。

### 7.2 情境推断算法

```python
def infer_context(query_embedding, prototypes) -> tuple[str, float]:
    # 1. 计算 query 与 4 个原型的余弦相似度
    similarities = {ctx: cosine_sim(query_embedding, proto) for ctx, proto in prototypes.items()}

    # 2. 取最强匹配
    best_ctx = max(similarities, key=similarities.get)
    sorted_scores = sorted(similarities.values(), reverse=True)
    margin = sorted_scores[0] - sorted_scores[1]

    # 3. margin < 0.05 -> 情境不明确，安全退化
    if margin < MARGIN_THRESHOLD:  # 0.05
        return ("general", 0.0)

    # 4. 归一化 confidence 到 0~1
    confidence = min(margin / 0.15, 1.0)
    return (best_ctx, confidence)
```

**关键词兜底**：当 embedding margin 低于阈值时，检查预定义关键词集合。如果关键词也无法判断，返回 `("general", 0.0)`。

### 7.3 评分加成（SQL 层）

```sql
CASE
    WHEN memory_type = 'trait' AND metadata->>'context' = :query_context
    THEN 0.10 * :context_confidence
    WHEN memory_type = 'trait' AND metadata->>'context' = 'general'
    THEN 0.07 * :context_confidence
    ELSE 0
END AS context_match
```

### 7.4 返回值扩展

recall 返回的 dict 增加两个字段（非破坏性）：

```python
{
    "vector_results": [...],
    "graph_results": [...],
    "merged": [...],
    "inferred_context": "work",       # 推断出的情境标签
    "context_confidence": 0.82,       # 推断置信度 (0~1)
}
```

## 8. 技术栈

- **核心语言**：Python 3.10+，async/await
- **向量计算**：numpy（余弦相似度），复用已有依赖
- **数据库**：PostgreSQL + pgvector（SQL 层 CASE 表达式）
- **ORM**：SQLAlchemy 2.0 async
- **Embedding**：复用 SDK 已有的 EmbeddingProvider ABC（SiliconFlow/OpenAI）
- **测试**：pytest + pytest-asyncio，MockEmbeddingProvider

**无新增依赖**。

## 9. 安全与配置

### 安全

- 无外部 API 调用（零额外攻击面）
- 情境推断纯本地计算，不涉及用户数据泄露
- 原型句子为预定义静态内容，不含敏感信息

### 配置

- 无新增环境变量
- 无新增构造函数参数（MVP 阶段）
- 常量定义在 ContextService 内部：`MARGIN_THRESHOLD = 0.05`，`MAX_CONTEXT_BOOST = 0.10`，`GENERAL_CONTEXT_BOOST = 0.07`

## 10. API 规范

**`recall()` 签名不变**：

```python
async def recall(
    self,
    user_id: str,
    query: str,
    *,
    limit: int = 20,
    # ... 现有参数不变
) -> dict:
```

**返回值扩展**（非破坏性，新增两个 key）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `inferred_context` | `str` | 推断出的情境标签（work/personal/social/learning/general） |
| `context_confidence` | `float` | 推断置信度，0.0~1.0 |

调用方可以选择使用这些信息，也可以忽略。

## 11. 成功标准

### MVP 成功定义

情境感知功能在 SDK 内部自动生效，现有 API 兼容，现有测试全部通过，且排序质量有可衡量的提升。

### 功能要求

- [x] 情境推断延迟 < 1ms（复用 query_embedding）
- [x] 零额外 LLM 调用成本
- [x] recall 签名不变，返回值非破坏性扩展
- [x] 现有全部测试通过（零回归）
- [x] margin 低于阈值时退化为现有行为
- [x] embedding 计算失败时 graceful degradation

### 质量指标

- **MRR 提升**：构造带情境标注的测试数据集，对比开启/关闭 context_match 的 Mean Reciprocal Rank，目标记忆排名应有可衡量的提升
- **零误伤**：情境不明确的 query 不应导致排序恶化（confidence = 0 时 boost = 0）

### 用户体验目标

- SDK 开发者：升级后无需改代码，自动获得更好的排序
- 终端用户：无感知，对话体验更自然

## 12. 实施阶段

### Phase 1：情境推断核心（ContextService）

**目标**：建立情境推断基础能力

交付物：
- [x] `neuromem/services/context.py` — ContextService 类
- [x] 中英双语原型句子定义（4 情境 x ~30 句）
- [x] `infer_context()` 方法（embedding 匹配 + 关键词兜底）
- [x] 原型向量懒加载 + 内存缓存
- [x] 单元测试：推断准确性、margin 退化、缓存行为

验证标准：单独调用 ContextService 能正确推断不同情境的 query

### Phase 2：评分集成（SearchService + _core.py）

**目标**：将情境推断结果集成到 recall 评分流程

交付物：
- [x] `search.py` scored_search SQL 增加 context_match CASE 表达式
- [x] `_core.py` recall 方法调用 ContextService，传入结果
- [x] recall 返回值增加 `inferred_context` + `context_confidence`
- [x] 集成测试：端到端 recall 验证情境 boost 效果

验证标准：recall 返回结果中情境匹配的 trait 排名高于不匹配的 trait

### Phase 3：验证与调优

**目标**：确认排序质量提升

交付物：
- [x] 构造测试数据集（带情境的 trait + 不同情境的 query）
- [x] MRR 对比实验
- [x] 现有测试回归验证
- [x] 如需要，调整 MARGIN_THRESHOLD 和 boost 力度

验证标准：MRR 有可衡量提升，现有测试全部通过

## 13. 未来考虑

### MVP 后增强

- **自适应原型向量**：从用户实际记忆（context=work 的 trait embedding 均值）学习更精确的情境原型，替代预定义句子
- **`context_hint` 可选参数**：允许调用方显式传入情境覆盖自动推断
- **fact 层面的情境标注**：在 ingest 时为 fact 也推断情境，扩大 context_match 的作用范围
- **A/B 线上观测**：在生产环境中对比开启/关闭 context_match 的效果

### 远期方向

- 设置页从"指令式配置"变为"记忆空间用途描述"——空间用途本身作为情境推断的全局先验信号
- 多情境加权（当前只取最强单情境）
- 情境转换检测（用户在对话中从工作切换到生活时自动调整）

## 14. 风险与缓解措施

| 风险 | 影响 | 缓解策略 |
|------|------|---------|
| embedding 模型对中英文混合原型的语义表示不均匀 | 某些情境在特定语言下推断不准 | 中英文句子各 15 句取均值，确保双语平衡；关键词兜底补救 |
| margin 阈值过高导致大量 query 退化为 general | 功能等于没开 | 通过 MRR 实验调优阈值，初始值 0.05 偏保守 |
| margin 阈值过低导致误判情境 | 错误 boost 导致排序恶化 | boost 力度上限 0.10，即使误判也是 soft boost，不会过滤掉记忆 |
| 原型向量计算增加 SDK 初始化时间 | 用户体验受影响 | 懒加载（首次 recall 时计算），约 30 句 x 4 情境 = 120 次 embedding，可接受 |
| 现有测试因新增 context_match 字段破坏断言 | 测试回归 | context_match 默认为 0（confidence=0 时），不影响现有评分 |

## 15. 附录

### 关联文档

- 设计文档：`D:/CODE/NeuroMem/docs/design/context-aware-recall.md`
- 需求摘要：`D:/CODE/NeuroMem/rpiv/brainstorm-summary-context-aware-recall.md`
- V2 设计文档：`D:/CODE/NeuroMem/docs/design/memory-classification-v2.md` 3.2、6
- SDK CLAUDE.md：`D:/CODE/NeuroMem/CLAUDE.md`

### 关键设计决策（brainstorm 阶段确认）

| # | 决策点 | 选择 | 理由 |
|---|--------|------|------|
| 1 | 作用范围 | 仅 trait | trait 已有 context 标注，改动最小 |
| 2 | 语言覆盖 | 中英双语原型 | 覆盖主流使用场景 |
| 3 | 多情境处理 | 取最强单情境 | 简单可靠，margin 不足时安全退化 |
| 4 | 自适应原型 | MVP 不做 | 避免冷启动问题，后续演进 |
| 5 | 透明度 | 暴露在返回结果中 | 支持调试和 Trait Transparency |
| 6 | 验证方式 | 对比实验 | 构造数据集，MRR 衡量 |
| 7 | 可关闭性 | 默认开启，不可关闭 | 单情境 Space 中 boost 均匀分配，等效无影响 |

### 涉及文件

| 文件 | 改动类型 |
|------|---------|
| `neuromem/services/context.py` | 新增 — ContextService |
| `neuromem/services/search.py` | 修改 — scored_search 增加 context_match |
| `neuromem/_core.py` | 修改 — recall 调用 ContextService |
| `tests/test_context.py` | 新增 — 情境推断单元测试 |
| `tests/test_recall.py` | 修改 — recall 集成测试 |
