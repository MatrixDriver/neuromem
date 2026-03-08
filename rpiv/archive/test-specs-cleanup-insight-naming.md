---
description: "测试规格: cleanup-insight-naming"
status: archived
created_at: 2026-03-08T11:00:00
updated_at: 2026-03-08T11:30:00
archived_at: 2026-03-08T11:30:00
---

# 测试规格：清理 insight 命名残留

基于 PRD `rpiv/requirements/prd-cleanup-insight-naming.md` 和测试策略 `rpiv/validation/test-strategy-cleanup-insight-naming.md` 编写。

## 1. SDK 测试变更

### 1.1 现有测试更新（test_reflection.py）

**文件**：`D:/CODE/NeuroMem/tests/test_reflection.py`

此文件是受影响最大的测试文件，所有 insight 引用需更新为 trait。

| 行号/位置 | 当前代码 | 更新后 | 说明 |
|-----------|---------|--------|------|
| L14 | `insight_response: str = ""` | `trait_response: str = ""` | MockLLMProvider 参数名 |
| L15 | `self._insight_response = insight_response` | `self._trait_response = trait_response` | 内部变量 |
| L22 | `return self._insight_response` | `return self._trait_response` | 返回值 |
| L29 | `test_reflect_generates_insights` | `test_reflect_generates_traits` | 函数名 |
| L30 | docstring "insights" | docstring "traits" | 文档 |
| L39-53 | mock JSON `"insights": [...]` | `"traits": [...]` | LLM mock 响应 |
| L67 | `assert "insights" in result` | `assert "traits" in result` | 断言键名 |
| L69-71 | `result["insights"]` | `result["traits"]` | 断言引用 |
| L80 | `result["insights"] == []` | `result["traits"] == []` | 空结果断言 |
| L85 | `test_reflect_stores_as_insight_type` | `test_reflect_stores_as_trait_type` | 函数名 |
| L90-99 | mock JSON `"insights": [...]` | `"traits": [...]` | LLM mock 响应 |
| L108 | `result["insights"]` | `result["traits"]` | 断言 |
| L148 | mock JSON `"insights": []` | `"traits": []` | LLM mock 响应 |
| L156 | `assert "insights" in result` | `assert "traits" in result` | 断言 |
| L179 | mock JSON `"insights": [...]` | `"traits": [...]` | LLM mock 响应 |
| L185 | `result["insights"]` | `result["traits"]` | 断言 |
| L190 | `test_parse_insight_result_handles_invalid_json` | `test_parse_trait_result_handles_invalid_json` | 函数名 |
| L200 | `result["insights"] == []` | `result["traits"] == []` | 断言 |
| L214 | mock JSON `"insights": [...]` | `"traits": [...]` | LLM mock 响应 |
| L243-244 | `"insights_generated" in result` / `"insights" in result` | `"traits_generated"` / `"traits"` | Facade 断言 |

### 1.2 现有测试更新（test_reflect_watermark.py）

**文件**：`D:/CODE/NeuroMem/tests/test_reflect_watermark.py`

| 行号/位置 | 当前代码 | 更新后 | 说明 |
|-----------|---------|--------|------|
| L25 | mock 返回 `"insights": [...]` | `"traits": [...]` | LLM mock 响应 |
| L59 | `result["insights_generated"]` | `result["traits_generated"]` | 断言键名 |
| 所有后续 `insights_generated` 引用 | 同上 | 同上 | 全文替换 |

### 1.3 现有测试不受影响（test_reflection_v2.py）

**文件**：`D:/CODE/NeuroMem/tests/test_reflection_v2.py`

此文件使用 V2 反思引擎格式（`new_trends`/`new_behaviors`/`reinforcements`/`contradictions`），不包含 `insight` 引用。**无需修改**。

### 1.4 现有测试不受影响（test_reflect_api.py）

**文件**：`D:/CODE/NeuroMem/tests/test_reflect_api.py`

此文件使用 V2 格式（`trends`/`behaviors`），不包含 `insight` 引用。**无需修改**。

### 1.5 新增测试用例：digest() 返回值字段负向断言

**目标**：防止 mock 假通过，确保返回值中不存在旧字段名。

**测试位置**：可添加到 `test_reflection.py` 的 `test_reflect_facade_method` 中，或独立新增。

```python
# TC-RENAME-01: digest() 返回值不含 insight 前缀键
@pytest.mark.asyncio
async def test_digest_returns_trait_fields_not_insight(nm_with_mock_llm):
    """digest() must return traits_generated/traits, never insights_generated/insights."""
    result = await nm_with_mock_llm.digest("test_user", batch_size=10)

    # 正向断言：新字段存在
    assert "traits_generated" in result
    assert "traits" in result

    # 负向断言：旧字段不存在
    assert "insights_generated" not in result
    assert "insights" not in result

    # 确保无任何 insight 前缀键
    insight_keys = [k for k in result.keys() if "insight" in k.lower()]
    assert insight_keys == [], f"Found insight-related keys: {insight_keys}"
```

### 1.6 新增测试用例：ReflectionService.digest() 返回值字段

```python
# TC-RENAME-02: ReflectionService.digest() 返回 traits 而非 insights
@pytest.mark.asyncio
async def test_reflection_service_returns_traits_key(db_session, mock_embedding):
    """ReflectionService.digest() result dict uses 'traits' key."""
    mock_llm = MockLLMProvider(
        trait_response='{"traits": [{"content": "test", "category": "pattern"}]}',
    )
    svc = ReflectionService(db_session, mock_embedding, mock_llm)
    result = await svc.digest("test_user", [{"content": "test", "memory_type": "fact", "metadata": {}}])

    assert "traits" in result
    assert "insights" not in result
```

### 1.7 新增测试用例：LLM prompt JSON key 兼容

```python
# TC-RENAME-03: _parse_trait_result 兼容旧 "insights" key（LLM fallback）
@pytest.mark.asyncio
async def test_parse_trait_result_fallback_from_insights_key(db_session, mock_embedding):
    """_parse_trait_result should accept 'insights' key as fallback for LLM compatibility."""
    mock_llm = MockLLMProvider(
        trait_response='{"insights": [{"content": "fallback test", "category": "pattern"}]}',
    )
    svc = ReflectionService(db_session, mock_embedding, mock_llm)
    result = await svc.digest("fallback_user", [{"content": "data", "memory_type": "fact", "metadata": {}}])

    # Should still work via fallback parsing
    assert "traits" in result
    assert len(result["traits"]) >= 1
```

### 1.8 静态搜索验证

```bash
# TC-RENAME-04: SDK 源码无 insight 残留（排除允许保留的）
grep -rn "insight" D:/CODE/NeuroMem/neuromem/ --include="*.py" \
  | grep -v "__pycache__" \
  | grep -v "db.py" \
  | grep -v "# .*insight"  # 排除注释中的历史说明
# 期望：零结果（或仅剩 db.py 迁移代码和注释中的历史说明）
```

## 2. Cloud 后端测试变更

### 2.1 现有测试更新（test_core.py）

**文件**：`D:/CODE/neuromem-cloud/server/tests/test_core.py`

| 行号 | 当前代码 | 更新后 |
|------|---------|--------|
| L96 | `nm.digest.return_value = {"insights_generated": 3}` | `{"traits_generated": 3}` |
| L97 | `assert result == {"user_id": "alice", "insights_generated": 3}` | `{"user_id": "alice", "traits_generated": 3}` |
| L105 | `nm.digest.return_value = {}` | 不变 |
| L107 | `assert result["insights_generated"] == 0` | `assert result["traits_generated"] == 0` |

### 2.2 现有测试更新（test_schemas.py）

**文件**：`D:/CODE/neuromem-cloud/server/tests/test_schemas.py`

检查 DigestResponse 相关测试中是否有 `insights_generated` 字段引用，需更新为 `traits_generated`。

### 2.3 现有测试更新（test_reflection_worker.py）

**文件**：`D:/CODE/neuromem-cloud/server/tests/test_reflection_worker.py`

检查 `_digest_user` 返回值中 `insights_generated` 引用，更新为 `traits_generated`。

### 2.4 其他可能受影响的 Cloud 测试

需 grep 搜索确认：

```bash
grep -rn "insight" D:/CODE/neuromem-cloud/server/tests/ --include="*.py" | grep -v __pycache__
```

涉及的文件都需要将 `insights_generated` → `traits_generated`。

### 2.5 新增测试用例：Cloud API digest 响应字段

```python
# TC-CLOUD-01: do_digest 返回 traits_generated 而非 insights_generated
@pytest.mark.asyncio
async def test_do_digest_returns_traits_generated():
    nm = _mock_nm()
    nm.digest.return_value = {"traits_generated": 5}
    result = await do_digest(nm, space_id="alice")
    assert "traits_generated" in result
    assert "insights_generated" not in result
    assert result["traits_generated"] == 5
```

## 3. Cloud 前端测试

### 3.1 TypeScript 编译验证

```bash
# TC-WEB-01: TypeScript 编译通过
cd D:/CODE/neuromem-cloud/web && npx tsc --noEmit
# 期望：exit code 0，零错误
```

### 3.2 i18n 文案验证（静态搜索）

```bash
# TC-WEB-02: 前端源码无 insight 残留
grep -rn "insight" D:/CODE/neuromem-cloud/web/src/ --include="*.ts" --include="*.tsx" \
  | grep -v "node_modules" \
  | grep -v "// .*insight"  # 排除注释
# 期望：零结果
```

## 4. 跨项目集成验证

### 4.1 静态分析总检查

```bash
# TC-CROSS-01: 全生态 insight 残留搜索
# SDK
grep -rn "insight" D:/CODE/NeuroMem/neuromem/ --include="*.py" | grep -v __pycache__ | grep -v db.py | grep -v "# "
# Cloud 后端
grep -rn "insight" D:/CODE/neuromem-cloud/server/src/ --include="*.py" | grep -v __pycache__
# Cloud 前端
grep -rn "insight" D:/CODE/neuromem-cloud/web/src/ --include="*.ts" --include="*.tsx"
# 期望：SDK 仅剩 db.py 迁移代码；Cloud 零结果
```

## 5. 测试用例汇总

| ID | 类型 | 项目 | 描述 | 优先级 |
|----|------|------|------|--------|
| TC-RENAME-01 | 新增单元 | SDK | digest() 返回 traits 字段，不含 insights 字段 | P0 |
| TC-RENAME-02 | 新增单元 | SDK | ReflectionService.digest() 返回 traits 键 | P0 |
| TC-RENAME-03 | 新增单元 | SDK | _parse_trait_result 兼容旧 insights key（LLM fallback） | P1 |
| TC-RENAME-04 | 静态分析 | SDK | 源码无 insight 残留 | P0 |
| TC-CLOUD-01 | 新增单元 | Cloud | do_digest 返回 traits_generated | P0 |
| TC-WEB-01 | 编译验证 | Cloud Web | TypeScript 编译通过 | P0 |
| TC-WEB-02 | 静态分析 | Cloud Web | 前端源码无 insight 残留 | P0 |
| TC-CROSS-01 | 静态分析 | 跨项目 | 全生态 insight 残留搜索 | P0 |

现有测试更新（非新增）：
- `test_reflection.py`：约 20 处 insight → trait 更新
- `test_reflect_watermark.py`：约 3 处 insights_generated → traits_generated
- `test_core.py`（Cloud）：3 处 insights_generated → traits_generated
- 其他 Cloud 测试文件：grep 后确认

## 6. 通过标准

1. **SDK 测试**：`uv run pytest tests/ -v -m "not slow"` 全部通过
2. **Cloud 后端测试**：`uv run pytest tests/ -v` 全部通过
3. **Cloud 前端**：`npx tsc --noEmit` 零错误
4. **静态分析**：TC-RENAME-04、TC-WEB-02、TC-CROSS-01 均零残留（允许 db.py 迁移代码和历史说明注释）
5. **负向断言**：TC-RENAME-01 确认返回值无 insight 前缀键
