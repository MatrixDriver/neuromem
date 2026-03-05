---
description: "代码审查报告: context-aware-recall"
status: completed
created_at: 2026-03-05T14:30:00
updated_at: 2026-03-05T15:00:00
archived_at: null
---

# 代码审查报告：情境感知自动召回（Context-Aware Recall）

## 审查范围

| 文件 | 类型 | 行数 |
|------|------|------|
| `neuromem/services/context.py` | 新增 | 295 行 |
| `neuromem/services/search.py` | 修改 | +18 行（context_match SQL） |
| `neuromem/_core.py` | 修改 | +12 行（ContextService 集成） |
| `tests/test_context.py` | 新增 | 134 行 |

**统计：**

- 修改的文件：2
- 添加的文件：2
- 删除的文件：0
- 新增行：约 459
- 删除行：约 5

## 发现的问题

### Issue 1

```
severity: critical
status: fixed
file: neuromem/services/search.py
line: 349-351
issue: SQL 注入风险 — query_context 通过 f-string 直接拼接到 SQL
detail: |
  query_context 作为 scored_search 的公共参数（类型 str | None），
  直接通过 f-string 拼接到 SQL 语句中：
    f"  WHEN memory_type = 'trait' AND trait_context = '{query_context}'"
  虽然当前调用链中 query_context 仅来自 ContextService.infer_context()
  （返回值域为 work/personal/social/learning/general），但 scored_search
  是公共方法，neuromem-cloud 的 API 层也可能直接调用。
  攻击者如果能控制 query_context 参数，可以注入任意 SQL。
suggestion: |
  方案 A（推荐）：在 scored_search 入口处加白名单验证：
    VALID_CONTEXTS = {"work", "personal", "social", "learning", "general"}
    if query_context and query_context not in VALID_CONTEXTS:
        query_context = None
  方案 B：改用参数化查询（SQL :param），但需要调整 CASE 表达式结构。
  方案 A 更简单且符合设计意图（情境标签是固定枚举）。
```

### Issue 2

```
severity: medium
status: open
file: neuromem/services/context.py
line: 280
issue: max() 的 type: ignore 注释掩盖了潜在类型问题
detail: |
  `max(scores, key=scores.get)  # type: ignore[arg-type]`
  使用 type: ignore 掩盖了 dict.get 返回 Optional[int] 而 max 期望
  Callable[[str], SupportsLessThan] 的类型不匹配。虽然运行时不会出错
  （因为 scores 中的值都是 int），但 type: ignore 降低了类型检查的价值。
suggestion: |
  改用 lambda 消除 type: ignore：
    best_ctx = max(scores, key=lambda ctx: scores[ctx])
```

### Issue 3

```
severity: medium
status: open
file: neuromem/services/context.py
line: 282-288
issue: 关键词兜底的 confidence 值硬编码且不一致
detail: |
  _infer_context_keywords 返回的 confidence 值为硬编码的 0.6（2+ hits）
  和 0.4（1 hit），而 embedding 路径的 confidence 通过 margin/0.15 归一化。
  两条路径的 confidence 含义不同：
  - embedding: 基于 margin 的连续值 (0, 1.0]
  - keyword: 离散值 0.4 或 0.6
  当 embedding margin 恰好低于阈值时，切换到 keyword 可能产生
  confidence 跳变（从 ~0 跳到 0.4/0.6），导致 context_match bonus
  不连续。
suggestion: |
  可以接受为 MVP 行为，但建议在代码注释中说明两条路径的
  confidence 语义差异，方便后续调优。或者将 keyword confidence
  降低到 0.3/0.5，使得跳变更平滑。
```

### Issue 4

```
severity: low
status: open
file: neuromem/services/context.py
line: 204
issue: embed_batch 对 120 个句子的一次性调用可能超出某些 provider 的批量限制
detail: |
  ensure_prototypes 一次性将约 120 个句子（4 情境 x 30 句）传给
  embed_batch。部分 embedding provider 可能有批量大小限制
  （如 OpenAI 限制为 2048 个输入，SiliconFlow 可能更低）。
  当前 MockEmbeddingProvider 和主流 provider 应该没问题，
  但作为防御性编程建议分批处理。
suggestion: |
  MVP 可以接受。如果未来遇到批量限制，添加分批逻辑：
    BATCH_SIZE = 50
    for i in range(0, len(all_sentences), BATCH_SIZE):
        batch_embeddings = await self._embedding.embed_batch(all_sentences[i:i+BATCH_SIZE])
        embeddings.extend(batch_embeddings)
```

### Issue 5

```
severity: low
status: open
file: neuromem/services/search.py
line: 395
issue: vector_ranked CTE 新增 trait_context 列，但 BM25 CTE 未包含
detail: |
  vector_ranked 查询增加了 trait_context 列，但 bm25_ranked CTE
  只 SELECT id 和 score。这不影响功能（trait_context 通过 vector_ranked
  传递到 hybrid），但如果未来 bm25_ranked 需要独立使用 trait_context，
  需要同步更新。
suggestion: |
  当前实现正确，无需修改。仅作为知识点记录。
```

### Issue 6

```
severity: low
status: open
file: neuromem/_core.py
line: 627
issue: ContextService 在 __init__ 中 import，不符合模块级导入惯例
detail: |
  `from neuromem.services.context import ContextService` 在
  NeuroMemory.__init__ 内部导入。虽然这避免了循环导入（如果存在），
  但与项目中其他 service 的导入风格不完全一致（部分在方法内导入，
  部分在模块级导入）。
suggestion: |
  与现有模式一致（如 SearchService 也在方法内导入），可以接受。
  不需要修改。
```

### Issue 7

```
severity: low
status: open
file: neuromem/services/context.py
line: 222-225
issue: ensure_prototypes 失败时设置空 dict 而非 None
detail: |
  当 embed_batch 抛出异常时，self._prototypes 被设为空 dict {}
  而非 None。这意味着后续调用 ensure_prototypes 不会重试
  （因为 `if self._prototypes is not None: return`），原型计算
  失败变成永久性的。
  对比：如果设为 None，下次调用会重试。
suggestion: |
  考虑是否应该在失败时保留 None，允许重试：
    except Exception as e:
        logger.warning("Failed to initialize context prototypes: %s", e)
        # Keep self._prototypes as None to allow retry on next call
  或者记录失败时间，在一定间隔后重试。MVP 阶段设空 dict
  也可接受（避免重复失败日志），但需要在注释中说明这一行为。
```

## 正面评价

1. **架构设计良好**：ContextService 作为纯计算服务，不访问数据库，职责清晰
2. **懒加载实现合理**：原型向量在首次 recall 时计算，不影响 SDK 初始化速度
3. **graceful degradation 完备**：原型未就绪、零向量、margin 不足等场景都正确退化为 `("general", 0.0)`
4. **与现有评分公式的集成干净**：context_bonus_sql 作为独立 SQL fragment 插入，不影响其他 bonus
5. **recall 返回值扩展是非破坏性的**：新增 `inferred_context` 和 `context_confidence` 字段
6. **中英双语原型句子覆盖全面**：每个情境各 30 句（15 中 + 15 英）
7. **关键词兜底规则合理**：在 embedding 不确定时提供额外信号
8. **测试覆盖充分**：dev-1 的 test_context.py 对 ContextService 有良好的单元测试

## 总结

| 级别 | 数量 |
|------|------|
| CRITICAL | 1（SQL 注入 -- 已修复） |
| HIGH | 0 |
| MEDIUM | 2 |
| LOW | 4 |

**结论**：Issue 1（SQL 注入）已通过白名单验证修复（search.py:349-351），34 个单元测试通过确认无回归。Issue 2-3 建议后续修复。Issue 4-7 可以作为后续改进。
