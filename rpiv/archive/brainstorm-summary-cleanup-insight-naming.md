---
description: "需求摘要: cleanup-insight-naming"
status: archived
created_at: 2026-03-08T10:00:00
updated_at: 2026-03-08T11:30:00
archived_at: 2026-03-08T11:30:00
---

# 需求摘要：清理 insight 命名残留

## 产品愿景
- 核心问题：V2 设计已将 insight 降级为 trait 的 trend 阶段，数据迁移已完成，但代码中的函数名/变量名/API 返回值字段名仍大量使用 insight，导致概念不一致
- 价值主张：统一代码命名与 V2 设计文档一致，消除概念混乱
- 目标用户：SDK 开发者、Cloud 集成者
- 产品形态：SDK 内部重命名 + 公共 API 返回值重命名 + Cloud 适配

## 核心场景（按优先级）
1. SDK `digest()` 返回值字段从 `insights_generated`/`insights` 改为 `traits_generated`/`traits`
2. SDK `reflection.py` 内部函数/变量全面重命名（`_generate_insights` → `_generate_traits` 等）
3. SDK `_core.py` 中 insight 相关分支和变量清理
4. Cloud 后端适配 SDK 新返回值字段名
5. Cloud 前端 i18n/trace 组件中的 insight 文案更新

## 产品边界
- MVP 范围内：
  - SDK：`reflection.py` 全面重命名、`_core.py` digest() 返回值和内部变量、`search.py` insight 分支
  - Cloud 后端：`core.py`、`schemas.py`、`reflection_worker.py`、`mcp/tools.py` 适配新字段名
  - Cloud 前端：i18n 文案、trace 组件中的 insight 引用更新
- 明确不做：
  - Me2 的 insight 清理（单独 todo，后续处理）
  - SDK `db.py` 中的迁移代码（`insight → trait` 迁移逻辑保留，是历史迁移路径）
  - 注释中解释历史演变的 insight 引用可保留

## 约束条件
- SDK `digest()` 返回值是公共 API，直接重命名（不做双字段过渡期），bump minor version
- Cloud 必须同步适配，否则部署后会 break
- 保留 `db.py` 中 `insight → trait(trend)` 的数据迁移代码（仍需支持旧数据库升级）
- `search.py` 中 `memory_type == "insight"` 的兼容分支：考虑是否保留（旧数据可能仍有 insight 类型？需调研确认）

## 已知残留清单

### SDK（D:/CODE/NeuroMem/neuromem/）
- `_core.py:861` — `elif memory_type == "insight"` 分支
- `_core.py:1704-1870` — digest() 返回值 `insights_generated`/`insights`，内部变量 `all_insights`/`existing_insights`/`batch_insights`
- `services/reflection.py:751-930` — `_generate_insights`、`_build_insight_prompt`、`_parse_insight_result`、`_MIN_INSIGHT_IMPORTANCE`、所有 insight 变量名
- `services/search.py:59` — `elif memory_type == "insight"` 分支

### Cloud 后端（D:/CODE/neuromem-cloud/server/src/neuromem_cloud/）
- `core.py:424-437` — `insights_generated` 字段透传
- `schemas.py:54` — `insights_generated: int` 字段
- `mcp/tools.py:208` — 文案已修正为 "trait trends"，但字段名仍用 `insights_generated`
- `reflection_worker.py:109-110` — `insights_generated` 透传

### Cloud 前端（D:/CODE/neuromem-cloud/web/src/）
- `app/page.tsx:178` — "Digest insights" 文案
- `app/admin/tasks/page.tsx:89-90` — "Insights Generated" 显示
- `lib/i18n/en.ts` — 多处 insight 文案（digest 描述、admin 标签）
- `lib/i18n/zh.ts:305` — "生成洞察" 标签
- `components/trace-*.tsx` — `store_insights`、`llm_generate_insights`、`embed_insights` 标识

## 参考
- V2 设计文档 insight 降级决策：`D:/CODE/NeuroMem/docs/design/memory-classification-v2.md` §2.1/§4.1
- MEMORY.md："insight 已降级为 trait 的 trend 阶段"
- 数据迁移 commit：`f5813ff` (2026-03-01)
