---
description: "测试规格: 情境感知自动召回（Context-Aware Recall）"
status: completed
created_at: 2026-03-05T13:00:00
updated_at: 2026-03-05T13:00:00
archived_at: null
---

# 测试规格：情境感知自动召回（Context-Aware Recall）

基于 PRD `rpiv/requirements/prd-context-aware-recall.md` 和测试策略 `rpiv/validation/test-strategy-context-aware-recall.md` 编写。

---

## 1. 测试文件映射

| 测试文件 | 测试对象 | 层级 | 需要数据库 |
|----------|----------|------|-----------|
| `tests/test_context_inference.py` | `ContextService` 纯算法 | 单元 | 否 |
| `tests/test_recall_context_match.py` | `scored_search` context_match SQL | 集成 | 是 |
| `tests/test_recall_context_e2e.py` | `recall()` 端到端 | 端到端 | 是 |

---

## 2. test_context_inference.py — ContextService 单元测试

### 2.1 TestCosineSimilarity

测试余弦相似度计算工具函数的正确性。

| ID | 用例名 | 输入 | 预期输出 | 断言 |
|----|--------|------|----------|------|
| CS-1 | `test_cosine_identical_vectors` | vec_a = vec_b = [1,0,0,...] | 1.0 | `abs(result - 1.0) < 1e-6` |
| CS-2 | `test_cosine_orthogonal_vectors` | vec_a = [1,0,0,...], vec_b = [0,1,0,...] | 0.0 | `abs(result) < 1e-6` |
| CS-3 | `test_cosine_opposite_vectors` | vec_a = [1,0], vec_b = [-1,0] | -1.0 | `abs(result + 1.0) < 1e-6` |
| CS-4 | `test_cosine_zero_vector` | vec_a = [0,0,...], vec_b = any | 0.0（不抛异常） | `result == 0.0` |

### 2.2 TestInferContext

测试情境推断核心算法。使用人工构造的原型向量，精确控制相似度。

**测试 fixture**：构造 4 个正交方向的原型向量（维度 4），每个情境占据一个坐标轴方向：
```python
prototypes = {
    "work": [1, 0, 0, 0],
    "personal": [0, 1, 0, 0],
    "social": [0, 0, 1, 0],
    "learning": [0, 0, 0, 1],
}
```

| ID | 用例名 | query_embedding | 预期 context | 预期 confidence | 断言 |
|----|--------|----------------|-------------|-----------------|------|
| IC-1 | `test_infer_clear_work` | [0.9, 0.1, 0.0, 0.0] | "work" | > 0 | context=="work", confidence > 0 |
| IC-2 | `test_infer_clear_personal` | [0.0, 0.9, 0.1, 0.0] | "personal" | > 0 | context=="personal" |
| IC-3 | `test_infer_clear_social` | [0.0, 0.0, 0.9, 0.1] | "social" | > 0 | context=="social" |
| IC-4 | `test_infer_clear_learning` | [0.1, 0.0, 0.0, 0.9] | "learning" | > 0 | context=="learning" |
| IC-5 | `test_infer_ambiguous_returns_general` | [0.5, 0.5, 0.5, 0.5] | "general" | 0.0 | context=="general", confidence==0.0 |
| IC-6 | `test_infer_dominant_with_noise` | [0.8, 0.3, 0.2, 0.1] | "work" | > 0 | context=="work" |

### 2.3 TestMarginThreshold

测试 margin 阈值边界行为。MARGIN_THRESHOLD = 0.05。

构造方式：用精确计算的向量使得 cosine similarity 产生指定 margin。

| ID | 用例名 | 构造的 margin | 预期 | 断言 |
|----|--------|-------------|------|------|
| MT-1 | `test_margin_below_threshold` | 0.04 | ("general", 0.0) | degradation |
| MT-2 | `test_margin_at_threshold` | 0.05 | ("general", 0.0) | 严格小于，等于也退化 |
| MT-3 | `test_margin_above_threshold` | 0.06 | (best_ctx, >0) | 正常推断 |
| MT-4 | `test_margin_zero_all_equal` | 0.0 | ("general", 0.0) | 所有原型距离相同 |

### 2.4 TestConfidenceNormalization

测试 confidence 归一化逻辑：`confidence = min(margin / 0.15, 1.0)`。

| ID | 用例名 | margin | 预期 confidence | 断言 |
|----|--------|--------|-----------------|------|
| CN-1 | `test_confidence_max_at_015` | 0.15 | 1.0 | `confidence == 1.0` |
| CN-2 | `test_confidence_half` | 0.075 | 0.5 | `abs(confidence - 0.5) < 0.01` |
| CN-3 | `test_confidence_cap_above_015` | 0.30 | 1.0 | 超过 0.15 仍然 cap 在 1.0 |

### 2.5 TestKeywordFallback

测试关键词兜底规则。

| ID | 用例名 | query | embedding 结果 | 预期 | 断言 |
|----|--------|-------|---------------|------|------|
| KF-1 | `test_keyword_work` | "帮我调试这段代码" | margin < 0.05 | ("work", >0) | 关键词"代码"命中 work |
| KF-2 | `test_keyword_personal` | "周末去爬山" | margin < 0.05 | ("personal", >0) | 关键词"周末"命中 personal |
| KF-3 | `test_keyword_learning` | "学习深度学习教程" | margin < 0.05 | ("learning", >0) | 关键词"学习""教程"命中 |
| KF-4 | `test_keyword_no_match` | "今天天气不错" | margin < 0.05 | ("general", 0.0) | 无关键词命中 |
| KF-5 | `test_keyword_not_used_when_embedding_confident` | "帮我写代码" | margin > 0.05 → "work" | ("work", >0) | embedding 结果优先 |
| KF-6 | `test_keyword_multi_context_conflict` | "学习写代码" | margin < 0.05 | 取命中数最多的情境 | 不 crash，返回合理结果 |

### 2.6 TestPrototypeCaching

| ID | 用例名 | 操作 | 断言 |
|----|--------|------|------|
| PC-1 | `test_prototypes_cached_after_first_call` | 调用 infer_context 两次，第二次不触发 embed | 第二次调用 embed_batch 次数 = 0 |
| PC-2 | `test_cache_invalidation_on_provider_change` | 调用后更换 embedding provider，再调用 | 重新计算原型向量 |

### 2.7 TestPerformance

| ID | 用例名 | 操作 | 断言 |
|----|--------|------|------|
| PF-1 | `test_infer_context_latency` | 原型已缓存，调用 infer_context 1000 次取平均 | 单次 < 1ms |

---

## 3. test_recall_context_match.py — scored_search 集成测试

### 3.1 Helper 函数

```python
async def _insert_trait_with_context(
    db_session, mock_embedding, *,
    user_id, content, trait_context, trait_stage="established",
    trait_confidence=0.7,
) -> str:
    """插入带 trait_context 的 trait 记忆。"""
    # 1. SearchService.add_memory 插入 trait
    # 2. UPDATE memories SET metadata = jsonb_set(metadata, '{context}', :ctx)
    # 3. UPDATE trait_stage, trait_confidence
    # 返回 memory id
```

### 3.2 TestContextMatchBonus

验证 SQL CASE 表达式的 boost 值正确性。

前置条件：`scored_search` 接收 `query_context` 和 `context_confidence` 参数。

| ID | 用例名 | 数据 | query_context | confidence | 预期 context_match |
|----|--------|------|--------------|------------|-------------------|
| CM-1 | `test_exact_context_match` | trait[work] | "work" | 0.8 | 0.08 (0.10*0.8) |
| CM-2 | `test_general_context_partial_match` | trait[general] | "work" | 0.8 | 0.056 (0.07*0.8) |
| CM-3 | `test_context_mismatch_no_boost` | trait[personal] | "work" | 0.8 | 0.0 |
| CM-4 | `test_fact_no_context_boost` | fact | "work" | 0.8 | 0.0 |
| CM-5 | `test_zero_confidence_no_boost` | trait[work] | "work" | 0.0 | 0.0 |
| CM-6 | `test_full_confidence_max_boost` | trait[work] | "work" | 1.0 | 0.10 |

验证方式：检查 scored_search 返回结果中的 context_match 字段值（如暴露），或通过 score 差异反推。

### 3.3 TestContextMatchSorting

验证 context_match 正确改变排序。

| ID | 用例名 | 数据 | 预期排序 |
|----|--------|------|----------|
| SO-1 | `test_work_trait_ranks_higher_in_work_context` | trait_A[work] + trait_B[personal]，语义相近 | trait_A > trait_B |
| SO-2 | `test_general_trait_between_match_and_mismatch` | trait_A[work] + trait_B[general] + trait_C[personal] | A > B > C |
| SO-3 | `test_no_sorting_change_when_confidence_zero` | trait_A[work] + trait_B[personal]，confidence=0 | 保持原始排序 |

### 3.4 TestContextMatchWithOtherBonuses

验证 context_match 与其他 bonus 叠加，不互斥。

| ID | 用例名 | 场景 | 断言 |
|----|--------|------|------|
| OB-1 | `test_context_match_stacks_with_trait_boost` | established trait[work]，work context | score > 同条件无 context_match |
| OB-2 | `test_context_match_does_not_override_trait_boost` | core trait[personal] vs emerging trait[work]，work context | core 仍可能排名更高（trait_boost 0.25 > context_match 0.10） |
| OB-3 | `test_total_bonus_reasonable_range` | 所有 bonus 叠加 | total bonus < 0.80 |

---

## 4. test_recall_context_e2e.py — recall() 端到端测试

### 4.1 TestRecallContextAware

通过 `NeuroMemory.recall()` 验证完整流程。

| ID | 用例名 | 操作 | 断言 |
|----|--------|------|------|
| E2E-1 | `test_recall_returns_inferred_context` | recall(query) | result 包含 "inferred_context" key |
| E2E-2 | `test_recall_returns_context_confidence` | recall(query) | result 包含 "context_confidence" key，值为 float |
| E2E-3 | `test_recall_context_confidence_range` | recall(query) | 0.0 <= context_confidence <= 1.0 |
| E2E-4 | `test_recall_context_is_valid_label` | recall(query) | inferred_context in {"work", "personal", "social", "learning", "general"} |

### 4.2 TestRecallGracefulDegradation

| ID | 用例名 | 场景 | 断言 |
|----|--------|------|------|
| GD-1 | `test_recall_without_traits` | 用户只有 fact，无 trait | recall 正常返回，context_match 不影响结果 |
| GD-2 | `test_recall_prototype_not_ready` | ContextService 原型未初始化 | recall 正常返回，inferred_context="general"，confidence=0.0 |
| GD-3 | `test_recall_empty_query` | recall(query="") | 不 crash，返回合理结果 |

### 4.3 TestRecallBackwardCompat

| ID | 用例名 | 场景 | 断言 |
|----|--------|------|------|
| BC-1 | `test_recall_old_trait_no_context` | trait 无 metadata.context（旧数据） | 不 crash，trait 无 context_match boost |
| BC-2 | `test_recall_result_structure_compatible` | recall 返回值 | 仍包含 vector_results, graph_results, merged 等原有字段 |

### 4.4 TestRecallBilingualContext（@pytest.mark.slow）

需要真实 embedding provider，验证中英文 query 的情境推断。

| ID | 用例名 | query | 预期 context |
|----|--------|-------|-------------|
| BL-1 | `test_chinese_work_query` | "帮我写一个排序算法" | "work" |
| BL-2 | `test_english_work_query` | "Help me review this code" | "work" |
| BL-3 | `test_chinese_personal_query` | "周末去哪里玩" | "personal" |
| BL-4 | `test_english_personal_query` | "What should I cook for dinner" | "personal" |

---

## 5. 测试数据构造规范

### 5.1 单元测试向量构造

使用低维向量（dim=4）构造正交原型，精确控制余弦相似度：

```python
# 4 个正交原型
MOCK_PROTOTYPES = {
    "work":     [1.0, 0.0, 0.0, 0.0],
    "personal": [0.0, 1.0, 0.0, 0.0],
    "social":   [0.0, 0.0, 1.0, 0.0],
    "learning": [0.0, 0.0, 0.0, 1.0],
}

# 明确指向 work 的 query（与 work 原型相似度最高）
WORK_QUERY = [0.9, 0.1, 0.05, 0.05]

# 模糊 query（与所有原型相似度相近）
AMBIGUOUS_QUERY = [0.5, 0.5, 0.5, 0.5]
```

### 5.2 集成测试数据

插入带情境标注的 trait：

```python
# 工作 trait
trait_work = {
    "content": "偏好函数式编程风格",
    "memory_type": "trait",
    "trait_context": "work",
    "trait_stage": "established",
    "trait_confidence": 0.7,
}

# 生活 trait
trait_personal = {
    "content": "喜欢极简风格",
    "memory_type": "trait",
    "trait_context": "personal",
    "trait_stage": "established",
    "trait_confidence": 0.7,
}

# 通用 trait
trait_general = {
    "content": "回答时喜欢简洁直接",
    "memory_type": "trait",
    "trait_context": "general",
    "trait_stage": "established",
    "trait_confidence": 0.7,
}
```

---

## 6. 用户故事覆盖矩阵

| 用户故事 | 覆盖的测试 ID |
|----------|--------------|
| US-1：工作 trait 自动排序靠前 | SO-1, CM-1, E2E-1 |
| US-2：情境不明确时零干扰 | MT-1/2/4, IC-5, SO-3, GD-2 |
| US-3：返回推断信息 | E2E-1/2/3/4 |
| US-4：general trait 部分 boost | CM-2, SO-2 |
| US-5：生活场景优先生活偏好 | SO-1（反向），BL-3/4 |
| US-6：零额外延迟 | PF-1 |

---

## 7. 验收标准映射

| 验收标准 | 覆盖的测试 ID |
|----------|--------------|
| AC-1：新增测试通过 | 全部新增测试 |
| AC-2：现有测试无回归 | `pytest tests/ -v` 全套 |
| AC-3：延迟 < 1ms | PF-1 |
| AC-4：返回 inferred_context + context_confidence | E2E-1/2 |
| AC-5：confidence=0 时 context_match=0 | CM-5, SO-3 |
| AC-6：非 trait 的 context_match=0 | CM-4 |
| AC-7：原型缓存正常 | PC-1/2 |
