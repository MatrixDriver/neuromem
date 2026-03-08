---
description: "测试策略: cleanup-insight-naming"
status: archived
created_at: 2026-03-08T10:30:00
updated_at: 2026-03-08T11:30:00
archived_at: 2026-03-08T11:30:00
---

# 测试策略：清理 insight 命名残留

## 1. 变更范围分析

本次变更属于**跨项目重命名**（SDK 公共 API 变更 + Cloud 适配），涉及：

| 层级 | 变更类型 | 风险等级 |
|------|----------|----------|
| SDK `reflection.py` | 内部函数/变量重命名 | 低（不影响外部） |
| SDK `_core.py` digest() | **公共 API 返回值字段重命名** | 高（破坏性变更） |
| SDK `_core.py` / `search.py` | insight 类型分支清理 | 中（需确认旧数据兼容） |
| Cloud `core.py` / `schemas.py` | 字段名适配 | 高（必须与 SDK 同步） |
| Cloud `reflection_worker.py` | 字段名透传 | 中 |
| Cloud `mcp/tools.py` | 字段名透传 | 中 |
| Cloud 前端 i18n / 组件 | 文案更新 | 低（纯 UI 文本） |

## 2. 测试策略

### 2.1 SDK 测试（D:/CODE/NeuroMem/tests/）

#### 已有测试需更新

| 测试文件 | 影响点 | 操作 |
|----------|--------|------|
| `test_reflection.py` | `insights` 变量名、mock 响应中的 `insights` 字段 | 更新为 `traits` |
| `test_reflection_v2.py` | 可能引用 `insights_generated` | 检查并更新 |
| `test_reflect_api.py` | digest() 返回值断言 | 更新字段名 |
| `test_reflect_watermark.py` | digest() 返回值断言 | 更新字段名 |
| `test_p2_two_stage_reflection.py` | 反思管道测试 | 检查是否引用 insight |
| `test_search.py` | `memory_type == "insight"` 分支测试 | 视实现决定保留或更新 |
| `test_e2e_three_features.py` | 端到端流程中 digest 返回值 | 更新字段名 |

#### 新增测试用例

1. **digest() 返回值字段验证**
   - 断言返回 dict 包含 `traits_generated` 而非 `insights_generated`
   - 断言返回 dict 包含 `traits` 而非 `insights`
   - 断言不存在任何 `insight` 开头的键

2. **reflection.py 内部函数可调用性**
   - 验证 `_generate_traits`（原 `_generate_insights`）正常工作
   - 验证 `_build_trait_prompt`（原 `_build_insight_prompt`）正常工作
   - 验证 `_parse_trait_result`（原 `_parse_insight_result`）正常工作

3. **search.py 类型分支**（如清理 insight 分支）
   - 验证 `memory_type="trait"` 检索正常
   - 验证不再支持 `memory_type="insight"` 或提供兼容映射

### 2.2 Cloud 后端测试（D:/CODE/neuromem-cloud/server/tests/）

#### 已有测试需更新

| 测试文件 | 影响点 | 操作 |
|----------|--------|------|
| `test_core.py` | `test_do_digest` 断言 `insights_generated` | 更新为 `traits_generated` |
| `test_schemas.py` | DigestResponse schema 字段 | 更新字段名 |
| `test_reflection_worker.py` | digest 返回值透传 | 更新字段名 |
| `test_api.py` | digest API 响应断言 | 更新字段名 |
| `test_mcp_tools.py` | MCP digest 工具返回 | 更新字段名 |

#### 新增测试用例

1. **API 响应字段验证**
   - `POST /api/v1/digest` 响应包含 `traits_generated`
   - MCP digest 工具返回包含 `traits_generated`

2. **Schema 验证**
   - DigestResponse 有 `traits_generated` 字段
   - 旧字段 `insights_generated` 不存在

### 2.3 Cloud 前端测试

- **类型检查**：`npx tsc --noEmit` 确保 TypeScript 编译通过
- **文案验证**：手动确认 i18n 文件中 insight 已替换为 trait
- **组件渲染**：trace 组件中的标识符更新不影响构建

## 3. 测试执行计划

### 阶段 A：单元测试（自动化）

```bash
# SDK 快速测试（跳过慢测试）
cd D:/CODE/NeuroMem && uv run pytest tests/ -v -m "not slow"

# Cloud 后端测试
cd D:/CODE/neuromem-cloud/server && uv run pytest tests/ -v

# Cloud 前端类型检查
cd D:/CODE/neuromem-cloud/web && npx tsc --noEmit
```

### 阶段 B：回归验证

- 确认所有现有测试通过（无因重命名导致的断言失败）
- 关键路径：ingest → recall → digest 端到端流程

### 阶段 C：静态分析

```bash
# 确认代码中无 insight 残留（排除注释、db 迁移代码、历史说明）
grep -rn "insight" D:/CODE/NeuroMem/neuromem/ --include="*.py" | grep -v "# " | grep -v "db.py" | grep -v "__pycache__"
grep -rn "insight" D:/CODE/neuromem-cloud/server/src/ --include="*.py" | grep -v "# " | grep -v "__pycache__"
grep -rn "insight" D:/CODE/neuromem-cloud/web/src/ --include="*.ts" --include="*.tsx" | grep -v "// "
```

## 4. 通过标准

| 项目 | 通过条件 |
|------|----------|
| SDK | `pytest tests/ -m "not slow"` 全部通过 |
| Cloud 后端 | `pytest tests/ -v` 全部通过 |
| Cloud 前端 | `tsc --noEmit` 零错误 |
| 静态分析 | 代码中无非注释/非迁移的 insight 残留 |
| 兼容性 | `db.py` 迁移代码中 insight 引用保留不变 |

## 5. 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| SDK 和 Cloud 部署不同步导致线上 break | Cloud 必须在 SDK 发版后立即适配部署 |
| 旧数据库中 `memory_type="insight"` 的记忆无法检索 | 确认 search.py 是否需要保留兼容分支（调研确认） |
| Me2 未同步适配 | 本次 MVP 明确不含 Me2，后续单独处理 |
| 测试 mock 返回旧字段名导致测试假通过 | 新增断言检查返回值中不含 `insight` 前缀键 |
