---
description: "交付报告: cleanup-insight-naming"
status: archived
created_at: 2026-03-08T11:30:00
updated_at: 2026-03-08T11:30:00
archived_at: 2026-03-08T11:30:00
related_files:
  - rpiv/requirements/prd-cleanup-insight-naming.md
  - rpiv/plans/plan-cleanup-insight-naming.md
  - rpiv/validation/code-review-cleanup-insight-naming.md
  - rpiv/validation/test-strategy-cleanup-insight-naming.md
  - rpiv/validation/test-specs-cleanup-insight-naming.md
---

# 交付报告：清理 insight 命名残留

## 完成摘要

- PRD 文件：`rpiv/requirements/prd-cleanup-insight-naming.md`
- 实施计划：`rpiv/plans/plan-cleanup-insight-naming.md`
- 代码变更：

### SDK（D:/CODE/NeuroMem/neuromem/）
| 文件 | 变更内容 |
|------|----------|
| `services/reflection.py` | 函数重命名（_generate_insights→_generate_traits 等 3 个）、常量/变量/参数重命名、LLM prompt JSON key、_parse_trait_result 兼容旧 key fallback |
| `_core.py` | digest() 返回值 insights_generated→traits_generated / insights→traits、内部变量全面重命名、WHERE 条件 `!='insight'`→`!='trait'`（语义修正）、删除 insight 兼容分支 |
| `services/search.py` | 删除 `memory_type=="insight"` 兼容分支 |
| `pyproject.toml` | 版本号 0.9.5 → 0.10.0 |

### Cloud 后端（D:/CODE/neuromem-cloud/server/src/neuromem_cloud/）
| 文件 | 变更内容 |
|------|----------|
| `schemas.py` | `insights_generated: int` → `traits_generated: int` |
| `core.py` | 3 处 `insights_generated` → `traits_generated` 透传 |
| `mcp/tools.py` | `result['insights_generated']` → `result['traits_generated']` |
| `reflection_worker.py` | 2 处 `insights_generated` → `traits_generated` |

### Cloud 前端（D:/CODE/neuromem-cloud/web/src/）
| 文件 | 变更内容 |
|------|----------|
| `lib/i18n/en.ts` | 多处 insight 文案 → trait |
| `lib/i18n/zh.ts` | "生成洞察" → "生成特质"、"洞察" → "特质" |
| `app/page.tsx` | "Digest insights" → "Digest traits" |
| `app/admin/tasks/page.tsx` | "Insights Generated" → "Traits Generated"、`meta.insights_generated` → `meta.traits_generated` |
| `components/trace-sequence-diagram.tsx` | `store_insights` → `store_traits` |
| `components/trace-waterfall.tsx` | `llm_generate_insights` → `llm_generate_traits`、`embed_insights` → `embed_traits` |
| `components/trace-timing-bar.tsx` | `llm_generate_insights` → `llm_generate_traits` |

### 测试代码更新
- SDK：`test_reflection.py`（约 20 处）、`test_reflect_watermark.py`（3 处）、`test_profile_unification.py`（3 处）、`test_recall.py`（2 处）、`test_reflection_v2.py`（2 处）
- Cloud：`test_core.py`（3 处）、`test_core_extended.py`（2 处）、`test_reflection_worker.py`、`test_mcp_protocol.py`、`test_mcp_tools.py`、`test_memory_api.py`、`test_one_llm_mode.py`、`test_space_description.py`、`test_trace_integration.py`

- 测试覆盖：Cloud 后端所有 rename 相关测试通过（22/22）。SDK 测试待 Docker Desktop 启动后验证
- 代码审查：由 QA 和 Architect 完成对齐审查

## 关键决策记录

1. **digest() 返回值直接重命名**：不做双字段过渡期，SDK bump minor version 到 0.10.0 表示 breaking change
2. **WHERE 条件语义修正**：`memory_type != 'insight'` → `!= 'trait'`。原条件在数据迁移后已无实际过滤效果（CHECK 约束不允许 insight），改为 trait 语义更准确
3. **insight 兼容分支删除**：search.py 和 _core.py 中的 `memory_type=="insight"` 映射分支直接删除，不保留 deprecation warning
4. **LLM prompt fallback**：`_parse_trait_result` 同时接受 `"traits"` 和 `"insights"` key，防止 LLM 缓存返回旧 key
5. **保留合规引用**：db.py 迁移代码、L140 历史说明注释、L911 LLM fallback

## 遗留问题

1. **SDK 测试未运行**：Docker Desktop 未启动，PostgreSQL 5436 端口不可用。需启动后补充验证
2. **Me2 insight 清理**：已记录为独立 todo（`D:/CODE/me2/rpiv/todo/todo-cleanup-insight-remnants.md`），依赖 SDK 发布 0.10.0 后处理
3. **test_callback_mode.py 预存错误**：`do_ingest_with_extraction` 导入失败，与本次改动无关

## 建议后续步骤

1. 启动 Docker Desktop → 运行 SDK 测试 → 确认全部通过
2. SDK 提交并发布 0.10.0 到 PyPI
3. Cloud 提交并推送 → Railway 自动部署
4. 验证线上 digest API 返回 `traits_generated` 字段
5. 启动 Me2 insight 清理任务
