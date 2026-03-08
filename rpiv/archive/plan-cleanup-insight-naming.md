---
description: "功能实施计划: cleanup-insight-naming"
status: archived
created_at: 2026-03-08T10:30:00
updated_at: 2026-03-08T11:30:00
archived_at: 2026-03-08T11:30:00
related_files:
  - rpiv/requirements/prd-cleanup-insight-naming.md
  - rpiv/research-cleanup-insight-naming.md
---

# 功能：清理 insight 命名残留

以下计划应该是完整的，但在开始实施之前，验证文档和代码库模式以及任务合理性非常重要。

特别注意现有工具、类型和模型的命名。从正确的文件导入等。

## 功能描述

将 SDK 和 Cloud 代码中所有 `insight` 命名残留重命名为 `trait`，使代码与 V2 记忆分类设计文档一致。这是一次纯重命名操作，不涉及逻辑变更（除了两处 WHERE 条件从 `!= 'insight'` 改为 `!= 'trait'`，这是语义修正）。

## 用户故事

作为 SDK 开发者
我想要 `digest()` 返回 `traits_generated` 和 `traits` 字段
以便代码中的命名与 V2 设计文档中的 trait 概念完全一致

## 问题陈述

V2 设计将 insight 降级为 trait 的 trend 阶段，数据迁移已完成，但代码中的函数名/变量名/API 返回值字段名仍大量使用 `insight`，导致概念不一致。

## 解决方案陈述

对所有 insight 命名进行系统性重命名为 trait，分两个阶段：先 SDK（上游），再 Cloud（下游）。SDK `digest()` 返回值直接重命名，不做双字段过渡期。

## 功能元数据

**功能类型**：重构
**估计复杂度**：低
**主要受影响的系统**：SDK reflection/digest 模块、Cloud 后端 digest API、Cloud 前端 i18n/trace
**依赖项**：无新增依赖

---

## 上下文参考

### 相关代码库文件 重要：在实施之前必须阅读这些文件！

**SDK：**
- `D:/CODE/NeuroMem/neuromem/_core.py` (L855-862) - `_add_memory()` insight→trait 兼容分支，需删除
- `D:/CODE/NeuroMem/neuromem/_core.py` (L1154) - 注释 "Facts/insights"，需更新
- `D:/CODE/NeuroMem/neuromem/_core.py` (L1698-1871) - `digest()` 和 `_digest_impl()` 完整实现，所有 insight 变量和返回值
- `D:/CODE/NeuroMem/neuromem/services/reflection.py` (L745-931) - `digest()`、`_generate_insights()`、`_build_insight_prompt()`、`_parse_insight_result()` 全部需要重命名
- `D:/CODE/NeuroMem/neuromem/services/search.py` (L59-60) - `memory_type == "insight"` 兼容分支，需删除

**Cloud 后端：**
- `D:/CODE/neuromem-cloud/server/src/neuromem_cloud/core.py` (L424, 432, 437) - `insights_generated` 透传
- `D:/CODE/neuromem-cloud/server/src/neuromem_cloud/schemas.py` (L54) - `insights_generated: int` 字段定义
- `D:/CODE/neuromem-cloud/server/src/neuromem_cloud/mcp/tools.py` (L208) - `result['insights_generated']` 引用
- `D:/CODE/neuromem-cloud/server/src/neuromem_cloud/reflection_worker.py` (L109-110) - `insights_generated` 透传

**Cloud 前端：**
- `D:/CODE/neuromem-cloud/web/src/app/page.tsx` (L178) - "Digest insights" 文案
- `D:/CODE/neuromem-cloud/web/src/app/admin/tasks/page.tsx` (L89-90) - "Insights Generated" 显示
- `D:/CODE/neuromem-cloud/web/src/lib/i18n/en.ts` - 多处 insight 文案
- `D:/CODE/neuromem-cloud/web/src/lib/i18n/zh.ts` (L305, 322) - 中文 insight 文案
- `D:/CODE/neuromem-cloud/web/src/components/trace-sequence-diagram.tsx` (L31, 65) - `store_insights`
- `D:/CODE/neuromem-cloud/web/src/components/trace-waterfall.tsx` (L9, 23) - `llm_generate_insights`, `embed_insights`
- `D:/CODE/neuromem-cloud/web/src/components/trace-timing-bar.tsx` (L9) - `llm_generate_insights`

### 要创建的新文件

无。本次变更仅修改现有文件。

### 要遵循的模式

**命名约定**：
- 函数名使用 `_generate_traits` 而非 `_generate_insights`
- 变量名使用 `existing_traits` / `all_traits` / `batch_traits` / `valid_traits`
- 返回值 key 使用 `"traits_generated"` / `"traits"`
- LLM prompt 中 JSON key 使用 `"traits"`

**兼容性模式**：
- `_parse_trait_result` 中同时兼容 `"traits"` 和 `"insights"` key（LLM 可能仍输出旧 key）
- `db.py` 中的 `insight → trait` 数据迁移代码**不动**

---

## 实施计划

### 阶段 1：SDK 重命名

SDK 是上游，必须先完成。Cloud 依赖 SDK `digest()` 的返回值结构。

### 阶段 2：Cloud 后端适配

适配 SDK 新返回值字段名 `traits_generated` / `traits`。

### 阶段 3：Cloud 前端更新

更新 i18n 文案、trace 组件标识符、admin 页面字段名。

### 阶段 4：验证

SDK 测试、Cloud 后端测试、Cloud 前端 TypeScript 编译、insight 残留搜索。

---

## 逐步任务

重要：按顺序从上到下执行每个任务。每个任务都是原子的且可独立测试。

### 任务 1: UPDATE `D:/CODE/NeuroMem/neuromem/services/reflection.py` — 函数和变量重命名

这是最核心的文件，包含所有 insight 生成逻辑。

- **IMPLEMENT**：以下重命名映射（使用 replace_all 批量替换）：

  **函数名重命名：**
  | 旧名称 | 新名称 |
  |--------|--------|
  | `_generate_insights` | `_generate_traits` |
  | `_build_insight_prompt` | `_build_trait_prompt` |
  | `_parse_insight_result` | `_parse_trait_result` |

  **参数名重命名：**
  | 旧名称 | 新名称 |
  |--------|--------|
  | `existing_insights` (L751, 770, 836, 848, 849, 852) | `existing_traits` |

  **常量重命名：**
  | 旧名称 | 新名称 |
  |--------|--------|
  | `_MIN_INSIGHT_IMPORTANCE` (L787) | `_MIN_TRAIT_IMPORTANCE` |

  **变量名重命名（L762-831）：**
  | 旧名称 | 新名称 |
  |--------|--------|
  | `insights = await self._generate_insights(...)` (L762) | `traits = await self._generate_traits(...)` |
  | `insights = self._parse_insight_result(...)` (L781) | `traits = self._parse_trait_result(...)` |
  | `valid_insights` (L788, 798, 800, 804, 812) | `valid_traits` |
  | `for insight in insights:` (L789) | `for trait_item in traits:` |
  | `insight.get(...)` (L790-792, 820-822) | `trait_item.get(...)` |
  | `valid_insights.append(insight)` (L798) | `valid_traits.append(trait_item)` |
  | `ins["content"]` (L804) | `item["content"]` |
  | `for insight, vector in zip(...)` (L812) | `for trait_item, vector in zip(...)` |
  | `stored.append(insight)` (L826) | `stored.append(trait_item)` |

  **返回值 key 重命名：**
  | 旧名称 | 新名称 |
  |--------|--------|
  | `{"insights": []}` (L760) | `{"traits": []}` |
  | `{"insights": insights}` (L764) | `{"traits": traits}` |

  **Docstring 和日志更新：**
  | 行号 | 旧文本 | 新文本 |
  |------|--------|--------|
  | L755 | `Generates pattern/summary insights` | `Generates pattern/summary traits` |
  | L772 | `Generate pattern and summary insights` | `Generate pattern and summary traits` |
  | L783 | `Insight generation LLM call failed` | `Trait generation LLM call failed` |
  | L796 | `Skipping low-importance insight` | `Skipping low-importance trait` |
  | L803 | `Embed all insights in batch` | `Embed all traits in batch` |
  | L808 | `Failed to embed insights batch` | `Failed to embed traits batch` |
  | L838 | `Build prompt for generating pattern and summary insights` | `Build prompt for generating pattern and summary traits` |
  | L893 | `Parse LLM insight generation output` | `Parse LLM trait generation output` |
  | L927 | `Failed to parse insight JSON` | `Failed to parse trait JSON` |
  | L930 | `Error parsing insight result` | `Error parsing trait result` |

  **LLM Prompt 中的 JSON key（L858-889）：**
  - L858: `{{"insights": []}}` → `{{"traits": []}}`
  - L881: `"insights": [` → `"traits": [`
  - L861: prompt 文本中"洞察"可保留（这是给 LLM 的中文指令，语义上"洞察"仍然合适）

  **_parse_trait_result 兼容处理（L911）：**
  ```python
  # 旧代码
  insights = result.get("insights", [])
  # 新代码（兼容两种 key）
  traits = result.get("traits") or result.get("insights", [])
  ```

- **GOTCHA**：L140 注释 "Replaces the original insight-based reflection" 是历史说明，保留不动
- **VALIDATE**：`cd D:/CODE/NeuroMem && uv run python -c "from neuromem.services.reflection import ReflectionService; print('import ok')"`

### 任务 2: UPDATE `D:/CODE/NeuroMem/neuromem/_core.py` — digest() 返回值和内部变量

- **IMPLEMENT**：以下重命名映射：

  **删除兼容分支（L861-862）：**
  ```python
  # 删除这两行
  elif memory_type == "insight":
      memory_type = "trait"
  ```

  **注释更新（L1154）：**
  `# Facts/insights: timeless attributes` → `# Facts/traits: timeless attributes`

  **Docstring 更新（L1704）：**
  `"""Generate insights from un-digested memories.` → `"""Generate traits from un-digested memories.`

  **WHERE 条件修正（L1757, L1800）：**
  `memory_type != 'insight'` → `memory_type != 'trait'`
  - 语义修正：排除 trait 类型记忆，避免 trait 对自身反思（调研报告已确认语义正确）

  **返回值 key 重命名（L1769-1770, L1869-1870）：**
  | 旧名称 | 新名称 |
  |--------|--------|
  | `"insights_generated": 0` | `"traits_generated": 0` |
  | `"insights": []` | `"traits": []` |
  | `"insights_generated": len(all_insights)` | `"traits_generated": len(all_traits)` |
  | `"insights": all_insights` | `"traits": all_traits` |

  **变量重命名（L1774-1846）：**
  | 旧名称 | 新名称 |
  |--------|--------|
  | `existing_insights` (L1774, 1784, 1833, 1839) | `existing_traits` |
  | `all_insights` (L1790, 1837, 1846, 1869) | `all_traits` |
  | `batch_insights` (L1836, 1837, 1838, 1845) | `batch_traits` |
  | `ins` (L1838, 1840, 1841) | `item` |

  **`batch_result.get()` key（L1836）：**
  `batch_result.get("insights", [])` → `batch_result.get("traits", [])`

  **日志文本（L1845）：**
  `insights=%d (total=%d/%d)` → `traits=%d (total=%d/%d)`

  **注释（L1773）：**
  `# --- Seed existing insights for dedup ---` → `# --- Seed existing traits for dedup ---`

- **GOTCHA**：L1757 和 L1800 的 WHERE 条件从 `!= 'insight'` 改为 `!= 'trait'` 是**语义变更**，不是纯文本替换。这确保 digest 不会将 trait 类型记忆作为输入来反思自身。数据库中已无 `insight` 类型记录（CHECK 约束保证），所以旧条件实际上不过滤任何东西。
- **VALIDATE**：`cd D:/CODE/NeuroMem && uv run python -c "from neuromem._core import NeuroMemory; print('import ok')"`

### 任务 3: UPDATE `D:/CODE/NeuroMem/neuromem/services/search.py` — 删除 insight 兼容分支

- **IMPLEMENT**：删除 L59-60 的兼容分支：
  ```python
  # 删除这两行
  elif memory_type == "insight":
      memory_type = "trait"
  ```
- **PATTERN**：参考调研报告结论"推荐方案 A：直接删除"
- **VALIDATE**：`cd D:/CODE/NeuroMem && uv run python -c "from neuromem.services.search import SearchService; print('import ok')"`

### 任务 4: UPDATE `D:/CODE/NeuroMem/pyproject.toml` — 版本号 bump

- **IMPLEMENT**：version 从 `0.9.5` → `0.10.0`（minor bump，表示 API breaking change）
- **VALIDATE**：`cd D:/CODE/NeuroMem && uv run python -c "import neuromem; print(neuromem.__version__ if hasattr(neuromem, '__version__') else 'no version attr')"`

### 任务 5: VALIDATE SDK — 运行全部测试

- **VALIDATE**：`cd D:/CODE/NeuroMem && uv run pytest tests/ -v --tb=short 2>&1 | tail -30`
- **GOTCHA**：需要 PostgreSQL 在端口 5436 运行。如果测试失败，检查是否有测试硬编码了 `insights_generated` 或 `insights` 作为预期返回值

### 任务 6: UPDATE `D:/CODE/neuromem-cloud/server/src/neuromem_cloud/schemas.py` — Pydantic 模型字段

- **IMPLEMENT**：L54 `insights_generated: int` → `traits_generated: int`
- **VALIDATE**：`cd D:/CODE/neuromem-cloud/server && uv run python -c "from neuromem_cloud.schemas import DigestResponse; print(DigestResponse.model_fields.keys())"`

### 任务 7: UPDATE `D:/CODE/neuromem-cloud/server/src/neuromem_cloud/core.py` — 字段透传

- **IMPLEMENT**：3 处 `insights_generated` → `traits_generated`（L424, 432, 437）
  ```python
  # L424: trace span metadata
  "traits_generated": result.get("traits_generated", 0),
  # L432: task metadata
  "traits_generated": result.get("traits_generated", 0),
  # L437: API 返回值
  "traits_generated": result.get("traits_generated", 0),
  ```
- **VALIDATE**：`cd D:/CODE/neuromem-cloud/server && grep -n "insights_generated" src/neuromem_cloud/core.py`（应返回空）

### 任务 8: UPDATE `D:/CODE/neuromem-cloud/server/src/neuromem_cloud/mcp/tools.py` — MCP 返回文案

- **IMPLEMENT**：L208 `result['insights_generated']` → `result['traits_generated']`
- **VALIDATE**：`cd D:/CODE/neuromem-cloud/server && grep -n "insights_generated" src/neuromem_cloud/mcp/tools.py`（应返回空）

### 任务 9: UPDATE `D:/CODE/neuromem-cloud/server/src/neuromem_cloud/reflection_worker.py` — 字段透传

- **IMPLEMENT**：L109-110 `insights_generated` → `traits_generated`
- **VALIDATE**：`cd D:/CODE/neuromem-cloud/server && grep -n "insights_generated" src/neuromem_cloud/reflection_worker.py`（应返回空）

### 任务 10: VALIDATE Cloud 后端 — 运行测试

- **VALIDATE**：`cd D:/CODE/neuromem-cloud/server && uv run pytest tests/ -v --tb=short 2>&1 | tail -30`
- **GOTCHA**：检查测试中是否有断言预期 `insights_generated` 字段

### 任务 11: UPDATE Cloud 前端 i18n — `D:/CODE/neuromem-cloud/web/src/lib/i18n/en.ts`

- **IMPLEMENT**：以下文案替换（注意 i18n 是面向用户的文案，需要语义合理）：
  | 行号 | 旧文案 | 新文案 |
  |------|--------|--------|
  | L11 | `digest insights` | `digest traits` |
  | L21 | `Synthesize memories into insights and user profiles` | `Synthesize memories into traits and user profiles` |
  | L27 | `produce structured insights: behavioral patterns` | `produce structured traits: behavioral patterns` |
  | L112 | `insight synthesis` | `trait synthesis` |
  | L311 | `"admin.tasks.insightsGenerated": "Insights generated"` | `"admin.tasks.traitsGenerated": "Traits generated"` |
  | L328 | `"dashLayout.group.insights": "Insights"` | `"dashLayout.group.traits": "Traits"` |
- **GOTCHA**：i18n key 也需要重命名（`insightsGenerated` → `traitsGenerated`，`group.insights` → `group.traits`），同时需要更新所有引用这些 key 的组件

### 任务 12: UPDATE Cloud 前端 i18n — `D:/CODE/neuromem-cloud/web/src/lib/i18n/zh.ts`

- **IMPLEMENT**：
  | 行号 | 旧文案 | 新文案 |
  |------|--------|--------|
  | L305 | `"admin.tasks.insightsGenerated": "生成洞察"` | `"admin.tasks.traitsGenerated": "生成特质"` |
  | L322 | `"dashLayout.group.insights": "洞察"` | `"dashLayout.group.traits": "特质"` |

### 任务 13: UPDATE Cloud 前端页面 — `D:/CODE/neuromem-cloud/web/src/app/page.tsx`

- **IMPLEMENT**：L178 `Digest insights` → `Digest traits`

### 任务 14: UPDATE Cloud 前端 admin — `D:/CODE/neuromem-cloud/web/src/app/admin/tasks/page.tsx`

- **IMPLEMENT**：
  - L89: `Insights Generated` → `Traits Generated`（或使用 i18n key `traitsGenerated`）
  - L90: `meta.insights_generated` → `meta.traits_generated`

### 任务 15: UPDATE Cloud 前端 trace 组件

- **IMPLEMENT**：3 个文件中的标识符替换：

  **`trace-sequence-diagram.tsx`：**
  - L31: `"store_insights"` → `"store_traits"`
  - L65: `"store_insights": "store insights"` → `"store_traits": "store traits"`

  **`trace-waterfall.tsx`：**
  - L9: `"llm_generate_insights"` → `"llm_generate_traits"`
  - L23: `"embed_insights"` → `"embed_traits"`

  **`trace-timing-bar.tsx`：**
  - L9: `"llm_generate_insights"` → `"llm_generate_traits"`

- **GOTCHA**：这些是前端硬编码标识符，与后端无耦合（后端当前不产生这些 span name），但命名应保持一致

### 任务 16: UPDATE Cloud 前端 — i18n key 引用检查

- **IMPLEMENT**：搜索 `insightsGenerated` 和 `group.insights` 在前端代码中的所有引用，全部更新为新 key 名
- **VALIDATE**：`cd D:/CODE/neuromem-cloud/web && grep -rn "insightsGenerated\|group\.insights" src/ --include="*.tsx" --include="*.ts"`（应仅在 i18n 定义文件中出现，或返回空）

### 任务 17: VALIDATE Cloud 前端 — TypeScript 编译

- **VALIDATE**：`cd D:/CODE/neuromem-cloud/web && npx tsc --noEmit 2>&1 | tail -20`

### 任务 18: VALIDATE 全局 — insight 残留搜索

- **VALIDATE**：在 SDK 和 Cloud 源码中搜索 insight 残留：
  ```bash
  # SDK（排除 db.py 迁移代码）
  cd D:/CODE/NeuroMem && grep -rn "insight" neuromem/ --include="*.py" | grep -v "db.py" | grep -v "# .*insight"

  # Cloud 后端
  cd D:/CODE/neuromem-cloud && grep -rn "insight" server/src/ --include="*.py"

  # Cloud 前端
  cd D:/CODE/neuromem-cloud && grep -rn "insight" web/src/ --include="*.ts" --include="*.tsx"
  ```
  所有搜索应返回空或仅包含历史说明注释。

---

## 测试策略

### 单元测试

SDK 现有测试覆盖 `digest()` 返回值。测试中若有断言检查 `insights_generated` / `insights` 字段，需同步更新为 `traits_generated` / `traits`。

### 集成测试

Cloud 后端测试中若有 `insights_generated` 断言，需同步更新。

### 边缘情况

1. **LLM 返回旧 JSON key**：`_parse_trait_result` 兼容 `"insights"` 和 `"traits"` 两种 key
2. **数据库无 insight 记录**：CHECK 约束保证，WHERE `!= 'trait'` 语义正确
3. **空记忆列表**：返回 `{"traits_generated": 0, "traits": []}`

---

## 验证命令

### 级别 1：语法检查

```bash
cd D:/CODE/NeuroMem && uv run python -c "from neuromem._core import NeuroMemory; from neuromem.services.reflection import ReflectionService; from neuromem.services.search import SearchService; print('all imports ok')"
```

### 级别 2：SDK 测试

```bash
cd D:/CODE/NeuroMem && uv run pytest tests/ -v --tb=short
```

### 级别 3：Cloud 后端测试

```bash
cd D:/CODE/neuromem-cloud/server && uv run pytest tests/ -v --tb=short
```

### 级别 4：Cloud 前端编译

```bash
cd D:/CODE/neuromem-cloud/web && npx tsc --noEmit
```

### 级别 5：insight 残留搜索

```bash
grep -rn "insight" D:/CODE/NeuroMem/neuromem/ --include="*.py" | grep -v "db.py"
grep -rn "insight" D:/CODE/neuromem-cloud/server/src/ --include="*.py"
grep -rn "insight" D:/CODE/neuromem-cloud/web/src/ --include="*.ts" --include="*.tsx"
```

---

## 验收标准

- [ ] SDK `digest()` 返回 `{"traits_generated": N, "traits": [...]}` 而非 `insights_*`
- [ ] SDK 所有测试通过
- [ ] Cloud 后端所有测试通过
- [ ] Cloud 前端 TypeScript 编译通过
- [ ] SDK 源码搜索 `insight` 仅在 `db.py` 迁移代码和历史说明注释中出现
- [ ] Cloud 源码搜索 `insight` 返回空
- [ ] `_parse_trait_result` 兼容 LLM 输出的 `"insights"` 和 `"traits"` 两种 key
- [ ] SDK version 为 0.10.0

---

## 完成检查清单

- [ ] 所有任务按顺序完成
- [ ] 每个任务验证立即通过
- [ ] 所有验证命令成功执行
- [ ] 完整测试套件通过（SDK + Cloud 后端 + Cloud 前端 tsc）
- [ ] 无 insight 命名残留（排除 db.py 和历史注释）
- [ ] 所有验收标准均满足

---

## 备注

1. **部署顺序**：SDK 先发布到 PyPI，Cloud 再更新依赖并部署。两者之间有短暂窗口期，Cloud 的 `result.get()` 容错可覆盖。
2. **Me2 不在范围内**：Me2 仍使用 neuromem 0.9.4，不受影响。后续独立 todo 处理。
3. **信心分数**：9/10 — 纯命名重构，逻辑无变更，风险极低。唯一的不确定性是 Cloud 测试中是否有硬编码 `insights_generated` 断言。
