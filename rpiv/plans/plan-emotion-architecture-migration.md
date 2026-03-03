---
description: "功能实施计划: emotion-architecture-migration"
status: pending
created_at: 2026-03-03T22:00:00
updated_at: 2026-03-03T22:00:00
archived_at: null
related_files:
  - rpiv/requirements/prd-emotion-architecture-migration.md
---

# 功能：情绪架构迁移 — 废弃 EmotionProfile 独立表

以下计划应该是完整的，但在开始实施之前，验证文档和代码库模式以及任务合理性非常重要。

特别注意现有工具、类型和模型的命名。从正确的文件导入等。

## 功能描述

完全清除 SDK、Cloud、Me2 三端中已废弃的 `EmotionProfile` 模型和 `emotion_profiles` 表相关代码。这是一次纯删除操作，不新增任何接口或功能。清理范围包括模型定义、导入导出、API 端点、前端页面、数据库迁移 SQL 以及数据清理引用。

## 用户故事

作为 neuromem 生态的开发者
我想要代码中不再存在废弃的 EmotionProfile 引用
以便理解情绪系统架构时不再混淆，维护成本降低

## 问题陈述

EmotionProfile 表已在记忆分类 V2 重构中被废弃（情绪系统改为三层架构：微观标注 + recall 评分 + trait 归纳），但残留代码仍存在于 SDK（模型/导入）、Cloud（端点/schema/前端页面）、Me2（迁移 SQL/查询/前端组件）中，造成理解混淆和无意义的运行时操作。

## 解决方案陈述

逐文件删除所有 EmotionProfile 相关代码。SDK 删除模型文件和导入；Cloud 删除端点、schema、前端页面和导航入口；Me2 删除迁移 SQL、查询端点和前端组件引用。数据可直接丢弃，无需迁移。

## 功能元数据

**功能类型**：重构
**估计复杂度**：中（跨三个项目 + 前后端，但每处改动都是简单删除）
**主要受影响的系统**：neuromem SDK, neuromem-cloud (后端+前端), Me2 (后端+前端)
**依赖项**：无新增外部依赖

---

## 上下文参考

### 相关代码库文件 重要：在实施之前必须阅读这些文件！

**SDK（D:/CODE/NeuroMem）**：
- `neuromem/models/emotion_profile.py` — 整个文件要删除（94 行）
- `neuromem/models/__init__.py` (第 12 行, 第 38 行) — EmotionProfile 导入和 `__all__` 导出
- `neuromem/__init__.py` (第 7 行, 第 28 行) — EmotionProfile 顶层导入和 `__all__` 导出

**Cloud 后端（D:/CODE/neuromem-cloud/server）**：
- `server/src/neuromem_cloud/schemas_memory.py` (第 117-130 行) — `EmotionProfileResponse` 类定义
- `server/src/neuromem_cloud/api/memory_mgmt.py` (第 12-13 行) — `EmotionProfileResponse` 导入
- `server/src/neuromem_cloud/api/memory_mgmt.py` (第 363-368 行) — clear_all_memories 中 `DELETE FROM emotion_profiles`
- `server/src/neuromem_cloud/api/memory_mgmt.py` (第 483-515 行) — `GET /emotion-profile` 端点（整个函数）

**Cloud 前端（D:/CODE/neuromem-cloud/web）**：
- `web/src/lib/memory-api.ts` (第 71-74 行) — `getEmotionProfile` 函数
- `web/src/components/emotion-chart.tsx` — 整个文件要删除（279 行）
- `web/src/app/api/spaces/[spaceId]/emotions/route.ts` — 整个文件要删除（14 行）
- `web/src/app/dashboard/spaces/[spaceId]/emotions/page.tsx` — 整个文件要删除（226 行）
- `web/src/components/space-sidebar.tsx` (第 73-76 行) — emotions 导航项
- `web/src/lib/i18n/en.ts` (第 307 行, 第 381-393 行) — emotions 相关翻译
- `web/src/lib/i18n/zh.ts` — emotions 相关翻译（对应行号）

**Me2 后端（D:/CODE/me2/backend）**：
- `backend/app/main.py` (第 62-72 行) — emotion_profiles 的 ALTER TABLE 迁移 SQL（10 行）
- `backend/app/api/v1/memories.py` (第 137-180 行) — `GET /emotion` 端点（整个函数，含 EmotionProfile 导入）
- `backend/app/services/admin_service.py` (第 376 行) — reset_all_data 中 tables 列表里的 `"emotion_profiles"`

**Me2 前端（D:/CODE/me2/frontend）**：
- `frontend/components/memories/EmotionSection.tsx` — 整个文件要删除（259 行）
- `frontend/app/memories/page.tsx` (第 17 行, 第 131 行) — EmotionSection 导入和使用

### 要删除的文件

- `D:/CODE/NeuroMem/neuromem/models/emotion_profile.py`
- `D:/CODE/neuromem-cloud/web/src/components/emotion-chart.tsx`
- `D:/CODE/neuromem-cloud/web/src/app/api/spaces/[spaceId]/emotions/route.ts`
- `D:/CODE/neuromem-cloud/web/src/app/dashboard/spaces/[spaceId]/emotions/page.tsx`
- `D:/CODE/me2/frontend/components/memories/EmotionSection.tsx`

### 不需要修改的文件（确认无影响）

- `neuromem/_core.py` — 无 EmotionProfile 引用（已确认 grep 零结果）
- `neuromem/services/` — 无 EmotionProfile 引用（已确认 grep 零结果）
- `neuromem/db.py` — 无 EmotionProfile 引用（已确认 grep 零结果）
- SDK 测试文件 — 不直接导入 EmotionProfile 模型，测试通过 raw SQL 或断言验证。删除模型后测试仍能正常运行（断言 emotion_profiles 不被更新的测试可能需要调整，因为表不再被创建）
- `web/src/components/trace-waterfall.tsx` — `llm_emotion_summary` 是 trace 标签颜色，与 EmotionProfile 无关
- `me2/frontend/app/analysis/page.tsx` — `emotion_expression` 是独立分析字段，与 EmotionProfile 无关

### 要遵循的模式

**删除操作**：纯删除行/文件，不添加替代代码

**导航项删除**：删除 sidebar 条目时保持数组结构完整（不留空对象）

**i18n 清理**：删除翻译 key 时保持 JSON 结构完整

---

## 实施计划

### 阶段 1：SDK 清理

删除 EmotionProfile 模型定义和所有导入导出。这是基础，必须首先完成。

### 阶段 2：Cloud 后端清理

删除 schema、端点和数据清理引用。

### 阶段 3：Cloud 前端清理

删除 emotions 页面、组件、API 路由、导航入口和 i18n 翻译。

### 阶段 4：Me2 后端清理

删除迁移 SQL、emotion 端点和 admin_service 表引用。

### 阶段 5：Me2 前端清理

删除 EmotionSection 组件和引用。

### 阶段 6：验证

全量 grep + 测试。

---

## 逐步任务

重要：按顺序从上到下执行每个任务。每个任务都是原子的且可独立测试。

### 任务 1: REMOVE `neuromem/models/emotion_profile.py`

- **IMPLEMENT**：删除整个文件 `D:/CODE/NeuroMem/neuromem/models/emotion_profile.py`
- **VALIDATE**：`ls D:/CODE/NeuroMem/neuromem/models/emotion_profile.py` 应报 "No such file"

### 任务 2: UPDATE `neuromem/models/__init__.py`

- **IMPLEMENT**：
  - 删除第 12 行：`from neuromem.models.emotion_profile import EmotionProfile`
  - 删除第 38 行（`__all__` 中）：`"EmotionProfile",`
- **PATTERN**：保持其他导入和 `__all__` 条目不变
- **修改后文件预期内容**：
  ```python
  # 第 12 行原为 emotion_profile 导入，删除后上下行直接相连：
  from neuromem.models.document import Document
  from neuromem.models.graph import EdgeType, GraphEdge, GraphNode, NodeType
  # ...
  # __all__ 中删除 "EmotionProfile", 保留其他所有条目
  ```
- **VALIDATE**：`uv run python -c "from neuromem.models import *; print('OK')"` 无报错

### 任务 3: UPDATE `neuromem/__init__.py`

- **IMPLEMENT**：
  - 删除第 7 行：`from neuromem.models.emotion_profile import EmotionProfile`
  - 删除第 28 行（`__all__` 中）：`"EmotionProfile",`
- **PATTERN**：保持其他导入和 `__all__` 条目不变
- **VALIDATE**：`uv run python -c "import neuromem; print(neuromem.__version__)"` 无报错

### 任务 4: UPDATE `server/src/neuromem_cloud/schemas_memory.py`

- **IMPLEMENT**：删除第 117-130 行的 `# --- Emotion ---` 区块和 `EmotionProfileResponse` 类定义：
  ```python
  # --- Emotion ---

  class EmotionProfileResponse(BaseModel):
      latest_state: str | None = None
      latest_state_period: str | None = None
      latest_state_valence: float | None = None
      latest_state_arousal: float | None = None
      valence_avg: float | None = None
      arousal_avg: float | None = None
      dominant_emotions: dict | None = None
      emotion_triggers: dict | None = None
      source_count: int | None = None
      last_reflected_at: str | None = None
  ```
- **VALIDATE**：`uv run python -c "from neuromem_cloud.schemas_memory import *; print('OK')"` 无报错

### 任务 5: UPDATE `server/src/neuromem_cloud/api/memory_mgmt.py`

- **IMPLEMENT**：
  1. 删除导入中的 `EmotionProfileResponse,`（第 13 行）
  2. 删除 `clear_all_memories` 函数中的 emotion_profiles 清理代码（第 363-368 行）：
     ```python
        # 3. Emotion profiles
        r = await session.execute(
            text("DELETE FROM emotion_profiles WHERE user_id = :uid"),
            {"uid": user_id},
        )
        result["emotion_profiles"] = r.rowcount
     ```
  3. 删除整个 `# ---------- 12. Emotion profile ----------` 区块（第 483-515 行）：
     ```python
     # ---------- 12. Emotion profile ----------

     @router.get(f"{PREFIX}/emotion-profile", response_model=EmotionProfileResponse)
     async def get_emotion_profile(
         tenant_id: UUID,
         space_id: UUID,
         request: Request,

     ):
         nm = await _get_nm(tenant_id, space_id, request)
         user_id = str(space_id)
         async with nm._db.session() as session:
             row = (await session.execute(
                 text("SELECT * FROM emotion_profiles WHERE user_id = :uid ORDER BY last_reflected_at DESC NULLS LAST LIMIT 1"),
                 {"uid": user_id},
             )).first()

         if not row:
             return EmotionProfileResponse()

         row_dict = row._mapping
         return EmotionProfileResponse(
             latest_state=row_dict.get("latest_state"),
             latest_state_period=row_dict.get("latest_state_period"),
             latest_state_valence=row_dict.get("latest_state_valence"),
             latest_state_arousal=row_dict.get("latest_state_arousal"),
             valence_avg=row_dict.get("valence_avg"),
             arousal_avg=row_dict.get("arousal_avg"),
             dominant_emotions=row_dict.get("dominant_emotions"),
             emotion_triggers=row_dict.get("emotion_triggers"),
             source_count=row_dict.get("source_count"),
             last_reflected_at=str(row_dict["last_reflected_at"]) if row_dict.get("last_reflected_at") else None,
         )
     ```
- **GOTCHA**：删除 `clear_all_memories` 中的 emotion_profiles 部分后，注释编号（`# 3.`→`# 4.`）会跳号，可选择重新编号或保持原样。建议保持原样（不影响功能）
- **VALIDATE**：`grep -r "EmotionProfile\|emotion_profile" D:/CODE/neuromem-cloud/server/src/` 返回零结果

### 任务 6: REMOVE Cloud 前端 emotions 相关文件

- **IMPLEMENT**：删除以下 3 个文件：
  1. `D:/CODE/neuromem-cloud/web/src/components/emotion-chart.tsx`
  2. `D:/CODE/neuromem-cloud/web/src/app/api/spaces/[spaceId]/emotions/route.ts`
  3. `D:/CODE/neuromem-cloud/web/src/app/dashboard/spaces/[spaceId]/emotions/page.tsx`
- **GOTCHA**：删除目录时注意只删文件，如果 `emotions/` 目录变空则可以整个删除
- **VALIDATE**：文件不存在

### 任务 7: UPDATE `web/src/lib/memory-api.ts`

- **IMPLEMENT**：删除第 71-74 行的 `getEmotionProfile` 函数：
  ```typescript
  // Emotion
  export async function getEmotionProfile(tenantId: string, spaceId: string) {
    return internalFetch(`/tenants/${tenantId}/spaces/${spaceId}/emotion-profile`);
  }
  ```
- **VALIDATE**：`grep -r "getEmotionProfile\|emotion-profile" D:/CODE/neuromem-cloud/web/src/lib/memory-api.ts` 零结果

### 任务 8: UPDATE `web/src/components/space-sidebar.tsx`

- **IMPLEMENT**：删除第 73-76 行的 emotions 导航项：
  ```typescript
        {
          href: `/dashboard/spaces/${selectedSpace}/emotions`,
          label: t("dashLayout.emotions"),
        },
  ```
- **VALIDATE**：`grep -r "emotions" D:/CODE/neuromem-cloud/web/src/components/space-sidebar.tsx` 零结果

### 任务 9: UPDATE Cloud 前端 i18n 文件

- **IMPLEMENT**：在 `web/src/lib/i18n/en.ts` 和 `web/src/lib/i18n/zh.ts` 中删除：
  - `"dashLayout.emotions"` 翻译项（en.ts 第 307 行）
  - 整个 `emotions.*` 翻译块（en.ts 第 381-393 行）：
    ```typescript
    "emotions.title": "Emotions",
    "emotions.currentState": "Current State",
    "emotions.valence": "Valence",
    "emotions.arousal": "Arousal",
    "emotions.positive": "Positive",
    "emotions.negative": "Negative",
    "emotions.calm": "Calm",
    "emotions.excited": "Excited",
    "emotions.dominant": "Dominant Emotions",
    "emotions.triggers": "Triggers",
    "emotions.topic": "Topic",
    "emotions.tendency": "Tendency",
    "emotions.noData": "No emotion data yet",
    ```
  - 同时更新 `memories.clearAllWarning` 翻译中的 "emotions" 描述（en.ts 第 338 行）：从 "memories, traits, knowledge graph, emotions, and conversation history" 改为 "memories, traits, knowledge graph, and conversation history"
- **GOTCHA**：zh.ts 中有对应的中文翻译也需要同步删除。需要先读取 zh.ts 确认行号
- **VALIDATE**：`grep -c "emotion" D:/CODE/neuromem-cloud/web/src/lib/i18n/en.ts` 应仅返回与 trace/其他无关引用的数量（不超过 3 行，来自 digest 描述中的 "emotional"）

### 任务 10: UPDATE `backend/app/main.py`

- **IMPLEMENT**：删除第 62-72 行的 emotion_profiles ALTER TABLE 迁移 SQL（10 行）：
  ```python
            # emotion_profiles 表 (neuromem 0.6.0+ 新增列)
            "ALTER TABLE emotion_profiles ADD COLUMN IF NOT EXISTS last_reflected_at TIMESTAMPTZ",
            "ALTER TABLE emotion_profiles ADD COLUMN IF NOT EXISTS latest_state_period VARCHAR(50)",
            "ALTER TABLE emotion_profiles ADD COLUMN IF NOT EXISTS latest_state_valence FLOAT",
            "ALTER TABLE emotion_profiles ADD COLUMN IF NOT EXISTS latest_state_arousal FLOAT",
            "ALTER TABLE emotion_profiles ADD COLUMN IF NOT EXISTS latest_state_updated_at TIMESTAMPTZ",
            "ALTER TABLE emotion_profiles ADD COLUMN IF NOT EXISTS valence_avg FLOAT",
            "ALTER TABLE emotion_profiles ADD COLUMN IF NOT EXISTS arousal_avg FLOAT",
            "ALTER TABLE emotion_profiles ADD COLUMN IF NOT EXISTS emotion_triggers JSONB",
            "ALTER TABLE emotion_profiles ADD COLUMN IF NOT EXISTS source_memory_ids UUID[]",
            "ALTER TABLE emotion_profiles ADD COLUMN IF NOT EXISTS source_count INTEGER",
  ```
- **VALIDATE**：`grep "emotion_profiles" D:/CODE/me2/backend/app/main.py` 零结果

### 任务 11: UPDATE `backend/app/api/v1/memories.py`

- **IMPLEMENT**：删除第 135-180 行的整个 `# -- Emotion --` 区块（`GET /emotion` 端点）：
  ```python
  # -- Emotion --

  @router.get("/emotion")
  async def get_emotion(current_user: User = Depends(get_current_user)):
      """获取情绪档案"""
      try:
          nm = _get_nm()
          from neuromem.models.emotion_profile import EmotionProfile
          from sqlalchemy import select

          async with nm._db.session() as session:
              result = await session.execute(
                  select(EmotionProfile).where(
                      EmotionProfile.user_id == current_user.id
                  )
              )
              profile = result.scalar_one_or_none()

              if not profile:
                  return {"emotion": None}

              return {
                  "emotion": {
                      "meso": {
                          "state": profile.latest_state,
                          "period": profile.latest_state_period,
                          "valence": profile.latest_state_valence,
                          "arousal": profile.latest_state_arousal,
                          "updated_at": (
                              profile.latest_state_updated_at.isoformat()
                              if profile.latest_state_updated_at
                              else None
                          ),
                      },
                      "macro": {
                          "valence_avg": profile.valence_avg,
                          "arousal_avg": profile.arousal_avg,
                          "dominant_emotions": profile.dominant_emotions,
                          "emotion_triggers": profile.emotion_triggers,
                      },
                      "source_count": profile.source_count,
                  }
              }
      except Exception as e:
          logger.error(f"获取情绪档案失败: {e}", exc_info=True)
          raise HTTPException(status_code=500, detail=str(e))
  ```
- **GOTCHA**：确保删除后 `# -- Graph --` 区块紧接在 `# -- Preferences --` 区块的 `delete_preference` 函数之后，注意空行
- **VALIDATE**：`grep "emotion_profile\|EmotionProfile" D:/CODE/me2/backend/app/api/v1/memories.py` 零结果

### 任务 12: UPDATE `backend/app/services/admin_service.py`

- **IMPLEMENT**：在 `reset_all_data` 方法的 `tables` 列表中（第 366-378 行），删除 `"emotion_profiles",` 条目（第 376 行）
- **修改前**：
  ```python
        tables = [
            "messages",
            "sessions",
            "conversation_sessions",
            "conversations",
            "embeddings",
            "documents",
            "graph_edges",
            "graph_nodes",
            "key_values",
            "emotion_profiles",
            "users",
        ]
  ```
- **修改后**：
  ```python
        tables = [
            "messages",
            "sessions",
            "conversation_sessions",
            "conversations",
            "embeddings",
            "documents",
            "graph_edges",
            "graph_nodes",
            "key_values",
            "users",
        ]
  ```
- **VALIDATE**：`grep "emotion_profiles" D:/CODE/me2/backend/app/services/admin_service.py` 零结果

### 任务 13: REMOVE Me2 前端 EmotionSection 组件

- **IMPLEMENT**：删除文件 `D:/CODE/me2/frontend/components/memories/EmotionSection.tsx`
- **VALIDATE**：文件不存在

### 任务 14: UPDATE `frontend/app/memories/page.tsx`

- **IMPLEMENT**：
  1. 删除第 17 行的导入：`import EmotionSection from '@/components/memories/EmotionSection';`
  2. 删除第 130-132 行的 EmotionSection 使用：
     ```tsx
                  <div className="border-t border-white/5">
                    <EmotionSection />
                  </div>
     ```
- **VALIDATE**：`grep "EmotionSection\|emotion" D:/CODE/me2/frontend/app/memories/page.tsx` 零结果

---

## 测试策略

### SDK 测试

SDK 测试中有若干测试文件引用 `emotion_profiles` 或 `EmotionProfile`：
- `tests/test_profile_unification.py` — 验证 digest 不再写入 emotion_profiles
- `tests/test_reflection.py` — 验证反思不再更新 emotion_profiles
- `tests/test_recall_emotion.py` — 验证 recall 不注入 EmotionProfile
- `tests/test_recall.py` — 验证 recall 结果不含 emotion_profile
- `tests/test_migration_profile.py` — emotion_profiles 数据迁移测试
- `tests/test_reflection_v2.py` — 验证 digest 结果不含 emotion_profile

**关键判断**：这些测试使用 raw SQL 操作 `emotion_profiles` 表（`INSERT INTO emotion_profiles`, `SELECT FROM emotion_profiles`），不依赖 Python 的 `EmotionProfile` 类导入。删除模型文件后：
- 表不再被 `create_all()` 创建 → 引用该表的测试可能因表不存在而失败
- 但这些测试本身就是在验证"EmotionProfile 已被废弃"，属于过渡期验证测试

**建议**：
- 运行完整测试套件，看哪些测试因表缺失而失败
- 对于专门验证"不再写入 emotion_profiles"的测试（如 `TestDigestNoEmotionProfile`），可以删除这些测试类/函数，因为模型和表都不存在了，验证已无意义
- 对于其他附带 `assert "emotion_profile" not in result` 的断言，保留即可（结果确实不含 emotion_profile）

### 前端验证

- Cloud 前端：`cd web && npm run build` 确认无编译错误
- Me2 前端：`cd frontend && npm run build` 确认无编译错误

### 集成测试

不做新增集成测试。验证方式为运行现有测试套件 + grep 零结果。

---

## 验证命令

执行每个命令以确保零回归和 100% 功能正确性。

### 级别 1：Grep 验证（三端零引用）

```bash
# SDK — 应返回零结果（排除 tests/ 和 scripts/）
grep -r "EmotionProfile\|emotion_profile" D:/CODE/NeuroMem/neuromem/

# Cloud 后端 — 应返回零结果
grep -r "EmotionProfile\|emotion_profile\|emotion_profiles" D:/CODE/neuromem-cloud/server/src/

# Cloud 前端 — 应返回零结果（排除 trace 组件中的 llm_emotion_summary）
grep -r "EmotionProfile\|emotion_profile\|getEmotionProfile\|emotion-profile" D:/CODE/neuromem-cloud/web/src/

# Me2 后端 — 应返回零结果
grep -r "EmotionProfile\|emotion_profile\|emotion_profiles" D:/CODE/me2/backend/app/

# Me2 前端 — 应返回零结果（排除 analysis/page.tsx 的 emotion_expression）
grep -r "EmotionProfile\|EmotionSection\|emotion_profile\|emotion-profile" D:/CODE/me2/frontend/
```

### 级别 2：SDK 测试

```bash
cd D:/CODE/NeuroMem
pytest tests/ -v -m "not slow" 2>&1 | tail -20
```

### 级别 3：Cloud 后端测试

```bash
cd D:/CODE/neuromem-cloud/server
pytest tests/ -v 2>&1 | tail -20
```

### 级别 4：前端构建验证

```bash
# Cloud 前端
cd D:/CODE/neuromem-cloud/web && npm run build

# Me2 前端
cd D:/CODE/me2/frontend && npm run build
```

### 级别 5：额外验证

```bash
# 确认被删除的文件确实不存在
ls D:/CODE/NeuroMem/neuromem/models/emotion_profile.py 2>&1
ls D:/CODE/neuromem-cloud/web/src/components/emotion-chart.tsx 2>&1
ls D:/CODE/neuromem-cloud/web/src/app/dashboard/spaces/*/emotions/ 2>&1
ls D:/CODE/me2/frontend/components/memories/EmotionSection.tsx 2>&1
```

---

## 验收标准

- [ ] `neuromem/models/emotion_profile.py` 文件已删除
- [ ] SDK 代码中 `grep -r "EmotionProfile" neuromem/` 返回零结果
- [ ] Cloud 后端代码中 `grep -r "EmotionProfile\|emotion_profiles" server/src/` 返回零结果
- [ ] Cloud 前端中 `emotion-chart.tsx`、`emotions/page.tsx`、`emotions/route.ts` 已删除
- [ ] Cloud 前端侧边栏不再有 Emotions 导航项
- [ ] Me2 后端代码中 `grep -r "EmotionProfile\|emotion_profiles" backend/app/` 返回零结果
- [ ] Me2 前端 `EmotionSection.tsx` 已删除
- [ ] Me2 前端 memories 页面不再引用 EmotionSection
- [ ] SDK 测试通过（`pytest tests/ -v -m "not slow"`）
- [ ] Cloud 前端构建通过（`npm run build`）
- [ ] Me2 前端构建通过（`npm run build`）
- [ ] 零新增代码行（纯删除操作）

---

## 完成检查清单

- [ ] 所有 14 个任务按顺序完成
- [ ] 每个任务验证立即通过
- [ ] 所有级别 1-5 验证命令成功执行
- [ ] 完整测试套件通过
- [ ] 所有验收标准均满足

---

## 备注

### 设计决策

1. **SDK 测试文件不主动修改**：测试中的 `assert "emotion_profile" not in result` 断言仍然有效（结果确实不含此 key），无需删除。仅当测试因 `emotion_profiles` 表不存在而实际失败时才做针对性修复。

2. **SDK scripts/ 目录不清理**：`scripts/migrate_profile_unification.py` 是一次性迁移脚本，已经完成使命，但不属于核心代码。保留不影响功能，后续可在代码审查阶段决定是否删除。

3. **Cloud 前端 i18n 中的 "emotional"**：`en.ts` 中 digest 描述包含 "emotional understanding" / "emotional profiles" 等措辞（第 21、27、164 行），这些是产品文案中的通用描述，不是 EmotionProfile 的引用。是否更新措辞由产品决定，不在本次重构范围内。

4. **数据库表不做 DROP**：代码不再创建/读写 emotion_profiles 表即可。已存在的表在生产数据库中保持不动，后续运维窗口手动处理。

5. **Cloud 前端 `clearAllWarning`**：从 warning 文案中移除 "emotions" 一词，因为 clear-all 不再删 emotion_profiles 数据。

### 信心分数

**9/10** — 所有改动都是明确的删除操作，无复杂逻辑变更。唯一风险是 SDK 测试中有些依赖 emotion_profiles 表存在的测试可能需要调整，但不影响核心功能。
