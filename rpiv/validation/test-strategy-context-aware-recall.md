---
description: "测试策略: 情境感知自动召回（Context-Aware Recall）"
status: completed
created_at: 2026-03-05T12:30:00
updated_at: 2026-03-05T12:30:00
archived_at: null
---

# 测试策略：情境感知自动召回（Context-Aware Recall）

## 1. 测试目标

本功能在 recall 流程中新增情境推断和 context_match_bonus，核心改动涉及三个文件。测试策略聚焦于：

1. **情境推断准确性**：不同情境的 query 能否正确分类为 work/personal/social/learning/general
2. **margin 阈值边界**：margin < 0.05 时 graceful degradation 为 `("general", 0.0)`
3. **评分排序正确性**：context_match 是否正确影响 trait 记忆排序
4. **关键词兜底**：embedding 原型匹配不确定时，关键词规则能否正确补位
5. **性能基准**：情境推断延迟 < 1ms（复用 query_embedding，仅 5 次余弦相似度计算）
6. **回归测试**：现有 recall/search 测试全部通过，无副作用
7. **中英双语原型向量**：中文和英文 query 都能正确推断情境

## 2. 测试范围

### 2.1 新增代码（需全面测试）

| 文件 | 改动 | 测试重点 |
|------|------|----------|
| `neuromem/services/context.py` | **新增** — 情境推断服务 | 原型向量计算、infer_context 算法、关键词兜底、缓存机制 |
| `neuromem/services/search.py` | `scored_search` 增加 `context_match` bonus | SQL CASE 逻辑、boost 值正确性、仅 trait 生效 |
| `neuromem/_core.py` | `recall` 调用情境推断 | 端到端集成、返回值新增字段 |

### 2.2 不受影响（需验证无回归）

| 功能 | 位置 | 验证方式 |
|------|------|----------|
| 向量检索 + BM25 RRF 融合 | `services/search.py` | 现有 `test_search.py` |
| trait_boost 权重 | `services/search.py` | 现有 `test_recall_trait_boost.py` |
| emotion_match 加成 | `services/search.py` | 现有 `test_recall_emotion.py` |
| 图谱 boost | `services/search.py` | 现有 `test_graph_boost.py` |
| recency/importance bonus | `services/search.py` | 现有 `test_recall.py` |
| 前瞻记忆降权 | `services/search.py` | 现有 `test_p2_prospective.py` |
| Zettelkasten 关联扩展 | `services/search.py` | 现有 `test_p2_zettelkasten.py` |

## 3. 测试分层

### 3.1 单元测试（无数据库依赖）

**目标**：验证 `ContextService` 的纯算法逻辑。

| 测试组 | 用例数 | 描述 |
|--------|--------|------|
| `TestInferContext` | 6+ | 给定预计算的原型向量和 query_embedding，验证推断结果 |
| `TestMarginThreshold` | 4+ | margin 边界条件：刚好低于/高于 0.05，所有相似度相等，只有一个原型 |
| `TestConfidenceNormalization` | 3+ | confidence 归一化到 [0, 1]，margin=0.15 → confidence=1.0，margin=0.075 → 0.5 |
| `TestKeywordFallback` | 5+ | 各情境关键词命中、多情境关键词冲突、无关键词 |
| `TestCosineSimilarity` | 3+ | 余弦相似度计算正确性，零向量处理，单位向量 |

### 3.2 集成测试（需数据库）

**目标**：验证 `scored_search` 中 context_match bonus 的 SQL 逻辑。

| 测试组 | 用例数 | 描述 |
|--------|--------|------|
| `TestContextMatchBonus` | 5+ | trait 情境完全匹配 +0.10*conf、general +0.07*conf、不匹配=0、非 trait=0 |
| `TestContextMatchSorting` | 3+ | 两条语义相近的 trait（不同情境），验证 context_match 改变排序 |
| `TestContextMatchWithOtherBonuses` | 3+ | context_match 与 trait_boost/emotion_match/recency 叠加不互斥 |

### 3.3 端到端测试（需数据库）

**目标**：通过 `NeuroMemory.recall()` 验证完整流程。

| 测试组 | 用例数 | 描述 |
|--------|--------|------|
| `TestRecallContextAware` | 4+ | recall 返回值包含 inferred_context 和 context_confidence 字段 |
| `TestRecallGracefulDegradation` | 3+ | embedding 缓存未就绪/推断失败时退化为现有行为 |
| `TestRecallBackwardCompat` | 2+ | 无 trait_context 的旧记忆不受影响，返回结构兼容 |

### 3.4 中英双语原型向量测试

**目标**：验证原型向量在中英文 query 上均有效。

| 测试组 | 用例数 | 描述 |
|--------|--------|------|
| `TestBilingualPrototypes` | 4+ | 中文 work query、英文 work query、中文 personal query、英文 personal query 均正确分类 |
| `TestPrototypeCaching` | 2+ | 首次计算后缓存命中，embedding provider 变更后重新计算 |

## 4. 关键测试场景详述

### 4.1 情境推断准确性

**测试数据**：为每个情境准备 3-5 个典型 query（中英各半）。

| 情境 | 中文示例 | 英文示例 | 预期 |
|------|----------|----------|------|
| work | "帮我写一个排序算法" | "Review this pull request" | context=work, confidence>0 |
| personal | "周末去哪里玩" | "What should I cook for dinner" | context=personal, confidence>0 |
| social | "同事聚会怎么安排" | "How to plan a team building" | context=social, confidence>0 |
| learning | "机器学习的基本原理" | "Explain the concept of recursion" | context=learning, confidence>0 |
| 模糊 | "今天天气不错" | "Hello" | context=general, confidence=0.0 |

**注意**：使用 MockEmbeddingProvider 时，hash-based 向量无法产生有意义的语义相似度。准确性测试需要：
- 单元测试层面：构造人工向量，精确控制相似度值
- 集成测试层面：验证 SQL 逻辑正确性（假设推断结果已给定）
- 慢测试（@pytest.mark.slow）：使用真实 embedding provider 验证端到端准确性

### 4.2 margin 阈值边界

```
场景 A：margin = 0.04（< 0.05）→ 返回 ("general", 0.0)
场景 B：margin = 0.05（= 0.05）→ 返回 ("general", 0.0)  // 严格小于
场景 C：margin = 0.06（> 0.05）→ 返回 (best_ctx, normalized_confidence)
场景 D：所有原型相似度相同 → margin = 0 → ("general", 0.0)
```

### 4.3 评分排序正确性

**核心场景**（对应设计文档 §2.4 的计算示例）：

```
query: "帮我优化这段 Python 代码"  → inferred context = "work", confidence = 0.8

trait A [work, established]:    base=0.72, context_match = 0.10 * 0.8 = 0.08 → 排名更高
trait B [personal, established]: base=0.70, context_match = 0                → 排名更低
trait C [general, established]:  base=0.70, context_match = 0.07 * 0.8 = 0.056 → 中间
```

验证点：
- trait A 得分 > trait C 得分 > trait B 得分
- fact 类型记忆的 context_match = 0（不受影响）
- confidence = 0 时，所有 trait 的 context_match = 0（等效关闭）

### 4.4 关键词兜底

```
场景 A：embedding margin 不足 + query 含 "代码" → keyword fallback → ("work", keyword_confidence)
场景 B：embedding margin 不足 + query 含 "周末" → keyword fallback → ("personal", keyword_confidence)
场景 C：embedding margin 不足 + 无关键词命中 → ("general", 0.0)
场景 D：embedding margin 充足 → 忽略关键词，使用 embedding 结果
场景 E：query 同时含 "代码" + "学习" → 多情境冲突处理
```

### 4.5 性能基准

**测试方式**：
- 在单元测试中对 `infer_context()` 计时，1000 次调用取平均值
- 阈值：单次调用 < 1ms（仅 5 个余弦相似度，纯 Python 计算）
- 不使用 `@pytest.mark.slow`，纯 CPU 计算无外部依赖

### 4.6 回归测试

**方式**：运行完整测试套件 `pytest tests/ -v`，确认：
- 所有现有测试通过（特别是 `test_recall.py`、`test_recall_trait_boost.py`、`test_recall_emotion.py`、`test_search.py`）
- 新增测试全部通过
- 无 warning 或 deprecation 提示（因新增代码引入）

## 5. 测试工具和 fixture

### 5.1 复用现有 fixture

- `db_session`：每个测试函数独立的数据库 session
- `mock_embedding`：MockEmbeddingProvider（hash-based 确定性向量）
- `mock_llm`：MockLLMProvider（空 JSON 响应）
- `nm`：完整 NeuroMemory 实例

### 5.2 新增 fixture/helper

| 名称 | 用途 |
|------|------|
| `_insert_trait_with_context()` | 插入带 trait_context 的 trait 记忆（扩展现有 `_insert_trait`） |
| `mock_prototypes` | 预构造的人工原型向量，精确控制相似度 |
| `context_service` | 独立的 ContextService 实例，用于单元测试 |

### 5.3 测试数据构造策略

由于 MockEmbeddingProvider 基于 hash 生成向量，**无法产生有意义的语义相似度**。测试策略分两层：

1. **算法层**（单元测试）：直接构造 `query_embedding` 和 `prototypes` 字典，精确控制相似度值，测试推断逻辑
2. **集成层**（数据库测试）：将 `infer_context` 的返回值作为参数传入 `scored_search`，验证 SQL bonus 逻辑，不依赖真实语义

## 6. 测试文件组织

```
tests/
  test_context_inference.py      # ContextService 单元测试（推断算法、关键词兜底、缓存）
  test_recall_context_match.py   # scored_search context_match bonus 集成测试
  test_recall_context_e2e.py     # recall() 端到端测试（返回值、graceful degradation）
```

**命名规范**：遵循现有 `test_recall_trait_boost.py`、`test_recall_emotion.py` 的模式。

## 7. 验收标准

| 编号 | 标准 | 验证方式 |
|------|------|----------|
| AC-1 | 所有新增测试通过 | `pytest tests/test_context_*.py tests/test_recall_context_*.py -v` |
| AC-2 | 所有现有测试无回归 | `pytest tests/ -v` 全部绿色 |
| AC-3 | 情境推断延迟 < 1ms | 性能基准测试断言 |
| AC-4 | recall 返回值包含 inferred_context + context_confidence | 端到端测试断言 |
| AC-5 | confidence=0 时 context_match=0（等效关闭） | 边界测试断言 |
| AC-6 | 非 trait 记忆的 context_match=0 | 集成测试断言 |
| AC-7 | 原型缓存正常工作 | 单元测试断言 |

## 8. 风险和缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| MockEmbeddingProvider 无法测试真实语义 | 无法验证原型向量在真实 embedding 下的分类效果 | 补充 `@pytest.mark.slow` 测试，使用 SiliconFlow embedding |
| context_match 与现有 bonus 叠加后分数溢出 | 排序异常 | 验证 total bonus 在合理范围内（< 0.80） |
| 关键词规则硬编码 | 新增情境关键词需手动更新 | 关键词作为配置常量，集中管理 |
| 原型向量缓存未清除导致 embedding 切换后结果错误 | 情境推断不准确 | 测试 provider 变更后缓存重建 |
