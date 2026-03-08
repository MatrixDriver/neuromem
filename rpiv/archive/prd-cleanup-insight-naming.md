---
description: "产品需求文档: cleanup-insight-naming"
status: archived
created_at: 2026-03-08T10:15:00
updated_at: 2026-03-08T11:30:00
archived_at: 2026-03-08T11:30:00
---

# PRD: 清理 insight 命名残留

## 1. 执行摘要

neuromem V2 记忆分类设计已将 insight 类型降级为 trait 的 trend 阶段，数据迁移已完成（commit `f5813ff`），但代码中的函数名、变量名和 API 返回值字段名仍大量使用 `insight`，导致代码命名与设计文档存在概念不一致。

本次变更将 SDK 内部和公共 API 中所有 insight 命名统一重命名为 trait，同步适配 Cloud 后端和前端。这是一次纯重命名操作，不涉及逻辑变更。

**MVP 目标**：SDK 代码和 Cloud 全栈中不再有 insight 命名残留（历史迁移代码和注释中的历史说明除外），概念模型与 V2 设计文档完全一致。

## 2. 使命

**使命声明**：确保 neuromem 生态的代码命名与 V2 记忆分类设计完全一致，消除概念混乱。

**核心原则**：
1. **一致性优先**：所有代码中的命名必须与设计文档中的分类体系一致
2. **直接重命名**：公共 API 返回值直接重命名，不做双字段过渡期
3. **同步更新**：SDK 和 Cloud 必须同步发布，避免兼容性断裂
4. **保留历史迁移**：`db.py` 中的 `insight → trait(trend)` 数据迁移代码必须保留

## 3. 目标用户

- **主要用户**：SDK 开发者（直接调用 `digest()` 方法）
- **次要用户**：Cloud REST API / MCP 集成者（通过 Cloud 间接使用 `digest`）
- **内部用户**：Cloud Dashboard 用户（查看 digest 结果统计）

**用户痛点**：`digest()` 返回 `insights_generated` 字段，但实际生成的是 trait(trend)，文档中也已不再提 insight 概念。新用户会困惑于 insight 到底是什么。

## 4. MVP 范围

### 范围内

**SDK (`D:/CODE/NeuroMem/neuromem/`)**：
- ✅ `_core.py`: `digest()` 返回值 `insights_generated` → `traits_generated`，`insights` → `traits`
- ✅ `_core.py`: 内部变量 `all_insights` → `all_traits`，`existing_insights` → `existing_traits`，`batch_insights` → `batch_traits`
- ✅ `_core.py:861`: `elif memory_type == "insight"` 分支（调研确认后决定保留或移除）
- ✅ `_core.py:1154`: 注释中 "Facts/insights" 更新
- ✅ `services/reflection.py`: 函数重命名 `_generate_insights` → `_generate_traits`，`_build_insight_prompt` → `_build_trait_prompt`，`_parse_insight_result` → `_parse_trait_result`
- ✅ `services/reflection.py`: 常量 `_MIN_INSIGHT_IMPORTANCE` → `_MIN_TRAIT_IMPORTANCE`
- ✅ `services/reflection.py`: 所有内部变量 `insights` → `traits`，`valid_insights` → `valid_traits`，`insight` → `trait_item` 等
- ✅ `services/reflection.py`: LLM prompt 中 JSON key `"insights"` → `"traits"`
- ✅ `services/search.py:59`: `elif memory_type == "insight"` 分支（同上，调研确认后决定）
- ✅ `pyproject.toml`: bump minor version（0.9.5 → 0.10.0）

**Cloud 后端 (`D:/CODE/neuromem-cloud/server/src/neuromem_cloud/`)**：
- ✅ `core.py`: `insights_generated` → `traits_generated`（3 处透传）
- ✅ `schemas.py`: `insights_generated: int` → `traits_generated: int`
- ✅ `mcp/tools.py`: 返回文案中 `insights_generated` → `traits_generated`
- ✅ `reflection_worker.py`: `insights_generated` → `traits_generated`（2 处）

**Cloud 前端 (`D:/CODE/neuromem-cloud/web/src/`)**：
- ✅ `app/page.tsx:178`: "Digest insights" → "Digest traits"
- ✅ `app/admin/tasks/page.tsx:89-90`: "Insights Generated" → "Traits Generated"，`meta.insights_generated` → `meta.traits_generated`
- ✅ `lib/i18n/en.ts`: 所有 insight 文案更新为 trait 概念
- ✅ `lib/i18n/zh.ts:305`: "生成洞察" → "生成特质"
- ✅ `lib/i18n/zh.ts:322`: "洞察" → "特质"
- ✅ `components/trace-sequence-diagram.tsx`: `store_insights` → `store_traits`
- ✅ `components/trace-waterfall.tsx`: `llm_generate_insights` → `llm_generate_traits`，`embed_insights` → `embed_traits`
- ✅ `components/trace-timing-bar.tsx`: `llm_generate_insights` → `llm_generate_traits`

### 范围外

- ❌ Me2 的 insight 清理（单独 todo，后续处理）
- ❌ SDK `db.py` 中的数据迁移代码（`insight → trait` 迁移逻辑必须保留）
- ❌ 注释中解释历史演变的 insight 引用（可保留作为历史记录）
- ❌ 双字段兼容过渡期（直接重命名）
- ❌ 数据库中已有记录的 memory_type 字段值变更（已由之前的数据迁移完成）

## 5. 用户故事

1. **作为 SDK 开发者**，我调用 `digest()` 后获得 `traits_generated` 和 `traits` 字段，以便与 V2 文档中的 trait 概念保持一致
2. **作为 Cloud API 集成者**，我调用 `/api/v1/digest` 后获得 `traits_generated` 字段，以便理解 digest 操作实际生成了什么
3. **作为 Cloud Dashboard 用户**，我在任务列表中看到 "Traits Generated" 而非 "Insights Generated"，以便准确理解 digest 统计含义
4. **作为新开发者**，我阅读 SDK 源码时看到的函数名和变量名都使用 trait 术语，以便与设计文档对应理解代码

## 6. 核心架构与模式

本次变更是纯命名重构，不涉及架构变更。关键约束：

- **SDK 是上游**：先完成 SDK 重命名，再适配 Cloud（Cloud 依赖 SDK 的 `digest()` 返回值）
- **Cloud REST + MCP 共享 `core.py`**：`core.py` 中的字段名变更会同时影响 REST 和 MCP 两个协议
- **前端依赖后端 schema**：`schemas.py` 字段名变更后，前端必须同步更新所有引用

## 7. 重命名映射表

### SDK `_core.py`

| 位置 | 旧名称 | 新名称 |
|------|--------|--------|
| L861 | `memory_type == "insight"` | 调研确认后决定（可能移除整个分支） |
| L1154 | `Facts/insights` (注释) | `Facts/traits` |
| L1704 | `"""Generate insights...` (docstring) | `"""Generate traits...` |
| L1757 | `memory_type != 'insight'` | `memory_type != 'insight'`（保留，这是数据库查询过滤） |
| L1769 | `"insights_generated": 0` | `"traits_generated": 0` |
| L1770 | `"insights": []` | `"traits": []` |
| L1774 | `existing_insights` | `existing_traits` |
| L1784 | `existing_insights = [` | `existing_traits = [` |
| L1790 | `all_insights` | `all_traits` |
| L1833 | `existing_insights` (参数) | `existing_traits` |
| L1836 | `batch_insights` | `batch_traits` |
| L1837 | `all_insights.extend` | `all_traits.extend` |
| L1838-1839 | `batch_insights` 循环 | `batch_traits` |
| L1845-1846 | 日志中 `insights=` | `traits=` |
| L1869 | `"insights_generated"` | `"traits_generated"` |
| L1870 | `"insights"` | `"traits"` |

### SDK `services/reflection.py`

| 位置 | 旧名称 | 新名称 |
|------|--------|--------|
| L140 | 注释 `insight-based` | `insight-based`（历史说明，保留） |
| L751 | 参数 `existing_insights` | `existing_traits` |
| L755 | docstring `insights` | `traits` |
| L760 | `{"insights": []}` | `{"traits": []}` |
| L762 | `self._generate_insights` | `self._generate_traits` |
| L764 | `{"insights": insights}` | `{"traits": traits}` |
| L766 | `_generate_insights` | `_generate_traits` |
| L770 | `existing_insights` | `existing_traits` |
| L772 | docstring `insights` | `traits` |
| L773 | `_build_insight_prompt` | `_build_trait_prompt` |
| L781 | `_parse_insight_result` | `_parse_trait_result` |
| L783 | 日志 `Insight generation` | `Trait generation` |
| L787 | `_MIN_INSIGHT_IMPORTANCE` | `_MIN_TRAIT_IMPORTANCE` |
| L788-800 | `valid_insights` / `insights` / `insight` | `valid_traits` / `traits` / `trait_item` |
| L803 | 注释 `insights` | `traits` |
| L804 | 变量 `ins` | `item`（可选） |
| L808 | 日志 `insights batch` | `traits batch` |
| L812 | `insight, vector` | `trait_item, vector` |
| L826 | `stored.append(insight)` | `stored.append(trait_item)` |
| L833 | `_build_insight_prompt` | `_build_trait_prompt` |
| L836 | `existing_insights` | `existing_traits` |
| L838 | docstring `insights` | `traits` |
| L848-852 | `existing_insights` | `existing_traits` |
| L858 | prompt 中 `"insights"` key | `"traits"` |
| L881 | JSON 示例 `"insights"` | `"traits"` |
| L892 | `_parse_insight_result` | `_parse_trait_result` |
| L893 | docstring `insight` | `trait` |
| L911 | `result.get("insights")` | `result.get("traits")` |
| L927/930 | 日志 `insight` | `trait` |

### SDK `services/search.py`

| 位置 | 旧名称 | 新名称 |
|------|--------|--------|
| L59 | `memory_type == "insight"` | 调研确认后决定 |

### Cloud 后端

| 文件 | 旧名称 | 新名称 |
|------|--------|--------|
| `core.py:424,432,437` | `insights_generated` | `traits_generated` |
| `schemas.py:54` | `insights_generated: int` | `traits_generated: int` |
| `mcp/tools.py:208` | `result['insights_generated']` | `result['traits_generated']` |
| `reflection_worker.py:109-110` | `insights_generated` | `traits_generated` |

### Cloud 前端

| 文件 | 旧名称 | 新名称 |
|------|--------|--------|
| `app/page.tsx:178` | `Digest insights` | `Digest traits` |
| `app/admin/tasks/page.tsx:89` | `Insights Generated` | `Traits Generated` |
| `app/admin/tasks/page.tsx:90` | `meta.insights_generated` | `meta.traits_generated` |
| `lib/i18n/en.ts` 多处 | `insights` 文案 | `traits` 文案 |
| `lib/i18n/zh.ts:305` | `"生成洞察"` | `"生成特质"` |
| `lib/i18n/zh.ts:322` | `"洞察"` | `"特质"` |
| `components/trace-sequence-diagram.tsx:31,65` | `store_insights` | `store_traits` |
| `components/trace-waterfall.tsx:9,23` | `llm_generate_insights`, `embed_insights` | `llm_generate_traits`, `embed_traits` |
| `components/trace-timing-bar.tsx:9` | `llm_generate_insights` | `llm_generate_traits` |

## 8. 技术栈

无新增依赖。涉及的现有技术栈：
- **SDK**：Python 3.11+, SQLAlchemy async, asyncpg
- **Cloud 后端**：FastAPI, FastMCP 2.x, Pydantic v2
- **Cloud 前端**：Next.js 16, React 19, TypeScript

## 9. 安全与配置

本次变更不涉及安全配置变更。唯一的配置变更是 SDK `pyproject.toml` 的版本号 bump。

## 10. API 规范变更

### SDK `digest()` 返回值

**变更前**：
```python
{
    "insights_generated": 3,
    "insights": [{"content": "...", "category": "pattern", ...}, ...]
}
```

**变更后**：
```python
{
    "traits_generated": 3,
    "traits": [{"content": "...", "category": "pattern", ...}, ...]
}
```

### Cloud REST API `POST /api/v1/digest` 响应

**变更前**：
```json
{"traits_generated": 3, "insights_generated": 3}
```

**变更后**：
```json
{"traits_generated": 3}
```

注意：Cloud 响应中 `insights_generated` 字段完全移除，统一为 `traits_generated`。

### Cloud MCP digest tool 返回文案

**变更前**：`Generated {result['insights_generated']} trait trends`
**变更后**：`Generated {result['traits_generated']} trait trends`

## 11. 成功标准

- ✅ SDK 全部测试通过（`pytest tests/ -v`）
- ✅ Cloud 后端全部测试通过（`cd server && pytest tests/ -v`）
- ✅ Cloud 前端 TypeScript 编译通过（`cd web && npx tsc --noEmit`）
- ✅ 代码中搜索 `insight`（排除 `db.py` 迁移代码和历史说明注释）无残留
- ✅ `digest()` 返回值包含 `traits_generated` 和 `traits` 字段
- ✅ Cloud REST API 和 MCP 响应包含 `traits_generated` 字段

## 12. 实施阶段

### 阶段 1：SDK 重命名
- **目标**：完成 SDK 内部和公共 API 的 insight → trait 重命名
- **交付物**：
  - ✅ `_core.py` 所有 insight 命名重命名
  - ✅ `services/reflection.py` 所有函数/变量/prompt 重命名
  - ✅ `services/search.py` insight 分支处理
  - ✅ `pyproject.toml` version bump 到 0.10.0
- **验证**：`pytest tests/ -v` 全部通过

### 阶段 2：Cloud 适配
- **目标**：适配 SDK 新返回值字段名
- **交付物**：
  - ✅ 后端 `core.py`, `schemas.py`, `mcp/tools.py`, `reflection_worker.py` 字段名更新
  - ✅ 前端 i18n 文案、trace 组件、admin 页面更新
  - ✅ Cloud `pyproject.toml` 更新 neuromem 版本依赖
- **验证**：后端 `pytest tests/ -v`，前端 `npx tsc --noEmit`

### 阶段 3：验证与发布
- **目标**：全链路验证并发布
- **交付物**：
  - ✅ 跨项目 insight 搜索确认无残留
  - ✅ SDK 发布到 PyPI
  - ✅ Cloud 部署到 Railway
- **验证**：线上 digest API 调用返回 `traits_generated` 字段

## 13. 未来考虑

- Me2 项目的 insight 清理（独立 todo）
- 如果有第三方已集成 `insights_generated` 字段，需在变更日志中明确说明 breaking change

## 14. 风险与缓解措施

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| SDK 和 Cloud 部署不同步 | Cloud 解析 SDK 新返回值失败 | SDK 和 Cloud 同一时间窗口部署；Cloud 使用 `result.get()` 容错 |
| 第三方集成 breaking | 使用 `insights_generated` 的集成者代码报错 | 在 changelog 中标注 BREAKING CHANGE；版本号 minor bump 表明不兼容 |
| LLM prompt 中 JSON key 变更 | LLM 可能仍输出旧 key | `_parse_trait_result` 中同时兼容 `"insights"` 和 `"traits"` key |
| `search.py` 中 `insight` 分支移除后旧数据查询 | 旧数据库中可能仍有 `memory_type="insight"` 的记录 | 调研确认数据迁移是否覆盖所有记录；若有残留则保留兼容分支 |

## 15. 附录

### 相关文档
- V2 设计文档：`D:/CODE/NeuroMem/docs/design/memory-classification-v2.md`
- 数据迁移 commit：`f5813ff` (2026-03-01)
- 需求摘要：`D:/CODE/NeuroMem/rpiv/brainstorm-summary-cleanup-insight-naming.md`

### LLM Prompt 变更

`services/reflection.py` 中 `_build_trait_prompt` 的 JSON 输出格式变更：

**变更前**：
```json
{
  "insights": [
    {"content": "...", "category": "pattern|summary", "importance": 8, "source_ids": []}
  ]
}
```

**变更后**：
```json
{
  "traits": [
    {"content": "...", "category": "pattern|summary", "importance": 8, "source_ids": []}
  ]
}
```

`_parse_trait_result` 需同时兼容两种 key（`"traits"` 优先，fallback 到 `"insights"`），以避免 LLM 缓存或 few-shot 影响。
