---
description: "产品需求文档: emotion-architecture-migration"
status: completed
created_at: 2026-03-03T21:30:00
updated_at: 2026-03-03T22:15:00
archived_at: null
---

# 情绪架构迁移 — 废弃 EmotionProfile 独立表

## 1. 执行摘要

neuromem v0.9.x 已完成记忆分类 V2 重构，情绪系统从独立 `EmotionProfile` 表迁移到三层架构（微观情绪标注 + recall 评分 + trait 归纳）。但旧的 `EmotionProfile` 模型及 `emotion_profiles` 表相关代码仍残留在 SDK、Cloud、Me2 三端，造成：

- **代码冗余**：模型定义、导入导出、数据库建表/迁移逻辑仍然存在
- **维护混淆**：开发者不确定 EmotionProfile 是否仍在使用
- **数据同步隐患**：digest() 仍更新 emotion_profiles 表，但无消费端

本次重构目标是**完全清除** EmotionProfile 相关代码，使情绪系统回归简洁的三层架构。这是一次纯删除操作，不新增任何接口或功能。

## 2. 使命

**使命声明**：消除已弃用的 EmotionProfile 独立表残留代码，让 SDK 及下游应用的情绪架构保持简洁一致。

**核心原则**：

1. **只删不增**：仅删除废弃代码，不新增接口、模型或功能
2. **三端同步**：SDK、Cloud、Me2 在同一批次完成清理，避免运行时引用断裂
3. **数据可丢弃**：emotion_profiles 表数据已无业务价值，无需迁移脚本
4. **微观层不动**：metadata_.emotion 微观情绪标注保持现状（除非发现明显问题）
5. **最小影响**：不改动公共 API 签名，不影响现有功能的输入输出

## 3. 目标用户

**主要用户**：neuromem SDK 开发者

- 直接维护 SDK 代码库的开发者
- 需要理解情绪系统架构的贡献者

**次要用户**：下游应用开发者

- neuromem-cloud 后端维护者
- Me2 后端维护者

**痛点**：

- 代码中存在已废弃但未清理的 EmotionProfile 引用，造成理解困惑
- digest() 仍执行无意义的 emotion_profiles 表写入
- Cloud 暴露了无调用者的 emotion-profile 端点
- Me2 启动时执行无意义的 emotion_profiles 表迁移 SQL

## 4. MVP 范围

### 范围内

**SDK 清理**：
- ✅ 删除 `neuromem/models/emotion_profile.py` 模型文件
- ✅ 清理 `neuromem/models/__init__.py` 中 EmotionProfile 的导入和 `__all__` 导出
- ✅ 清理 `neuromem/__init__.py` 中 EmotionProfile 的顶层导出
- ✅ 清理 `neuromem/_core.py` 中对 EmotionProfile 的引用
- ✅ 删除 `digest()` 中更新 emotion_profiles 表的逻辑
- ✅ 删除 database setup 中 emotion_profiles 表的建表逻辑

**Cloud 清理**：
- ✅ 删除 `schemas_memory.py` 中的 `EmotionProfileResponse` schema
- ✅ 删除 `memory_mgmt.py` 中的 `GET /emotion-profile` 端点
- ✅ 删除用户数据清理中的 `DELETE FROM emotion_profiles` SQL

**Me2 清理**：
- ✅ 删除 `main.py` 中 emotion_profiles 的 ALTER TABLE 迁移 SQL
- ✅ 删除 `memories.py` 中 EmotionProfile 的导入和查询逻辑
- ✅ 删除 `admin_service.py` 中 emotion_profiles 表引用

**验证**：
- ✅ 确认 SDK 中无其他隐藏的 EmotionProfile 引用
- ✅ 确认 Cloud 前端无 emotion-profile 端点调用
- ✅ 确认微观层（metadata_.emotion）逻辑无明显问题

### 范围外

- ❌ 不新增 `nm.emotions` 子 Facade 或任何替代接口
- ❌ 不编写数据迁移脚本（表数据可直接丢弃）
- ❌ 不做 API 版本兼容（emotion-profile 端点直接删除）
- ❌ 不修改微观层核心逻辑（除非发现明显 bug）
- ❌ 不新增情绪聚合便利方法（后续版本单独评估）
- ❌ 不删除数据库中已存在的 emotion_profiles 表（代码不再创建/使用即可）

## 5. 用户故事

1. **作为 SDK 开发者**，我想要代码中不再有废弃的 EmotionProfile 模型，以便理解情绪系统时不再混淆
2. **作为 SDK 开发者**，我想要 digest() 不再执行无意义的表写入，以便反思流程更高效且逻辑清晰
3. **作为 Cloud 维护者**，我想要删除无调用者的 emotion-profile 端点，以便 API 表面积更精简
4. **作为 Me2 维护者**，我想要启动时不再执行 emotion_profiles 的迁移 SQL，以便启动逻辑更干净
5. **作为代码审查者**，我想要 grep EmotionProfile 在三端代码中返回零结果，以便确认清理彻底

## 6. 核心架构与模式

### 情绪系统三层架构（保留）

```
微观层：ingest 时 LLM 提取 → metadata_.emotion（记忆级情绪标注）
中观层：recall 时按 emotion 标签过滤/评分（检索增强）
宏观层：digest 时 trait 归纳引擎生成情绪相关 trait（反思产出）
```

### 被废弃的独立表层（删除目标）

```
EmotionProfile 模型 → emotion_profiles 表
  - 由 digest() 写入
  - Cloud 通过 GET /emotion-profile 暴露
  - Me2 通过 memories.py 查询
  - 已无业务消费端，数据与 trait 重复
```

### 清理策略

- **自下而上**：先删 SDK 模型定义 → 再清下游引用
- **编译验证**：每端清理后验证无 import 错误
- **测试驱动**：确保现有测试仍通过（删除的功能无对应测试则跳过）

## 7. 功能规范

### 7.1 SDK 模型清理

| 操作 | 文件 | 内容 |
|------|------|------|
| 删除文件 | `neuromem/models/emotion_profile.py` | 整个文件 |
| 删除导入 | `neuromem/models/__init__.py` | EmotionProfile 导入及 `__all__` 条目 |
| 删除导出 | `neuromem/__init__.py` | EmotionProfile 顶层导出 |
| 删除引用 | `neuromem/_core.py` | 对 EmotionProfile 的任何引用 |

### 7.2 SDK 数据库清理

| 操作 | 位置 | 内容 |
|------|------|------|
| 删除建表 | database setup 代码 | emotion_profiles 表创建逻辑 |
| 删除更新 | `digest()` 实现 | 更新 emotion_profiles 的代码段 |

### 7.3 Cloud 清理

| 操作 | 文件 | 内容 |
|------|------|------|
| 删除 schema | `server/src/neuromem_cloud/schemas_memory.py` | `EmotionProfileResponse` 类定义 |
| 删除端点 | `server/src/neuromem_cloud/api/memory_mgmt.py` | `GET /emotion-profile` 路由函数 |
| 删除 SQL | `server/src/neuromem_cloud/api/memory_mgmt.py` | 用户数据清理中 `DELETE FROM emotion_profiles` |

### 7.4 Me2 清理

| 操作 | 文件 | 内容 |
|------|------|------|
| 删除迁移 | `backend/app/main.py` | ~8 行 `ALTER TABLE emotion_profiles ADD COLUMN IF NOT EXISTS` |
| 删除导入+查询 | `backend/app/api/v1/memories.py` | `from neuromem.models.emotion_profile import EmotionProfile` + 查询代码 |
| 删除表引用 | `backend/app/services/admin_service.py` | 数据清理表列表中 `"emotion_profiles"` 条目 |

### 7.5 微观层检查

- 检查 `search.py` 和 `memory_extraction.py` 中 metadata_.emotion 的使用
- 如发现小问题顺手修复，不做架构改动

## 8. 技术栈

本次改动不引入新依赖，涉及的现有技术栈：

- **SDK**: Python 3.11+, SQLAlchemy 2.0 async, asyncpg
- **Cloud 后端**: FastAPI 0.115+, Pydantic v2
- **Me2 后端**: FastAPI 0.109, SQLAlchemy 2 async
- **数据库**: PostgreSQL + pgvector + pg_search

## 9. 安全与配置

**安全影响**：无。本次仅删除代码，不涉及认证、授权或配置变更。

**配置变更**：无。不新增/修改任何环境变量。

**部署考虑**：
- SDK 发布新版本后，Cloud 和 Me2 需同步更新 SDK 版本依赖
- Cloud 删除端点后无需 API 版本过渡（无外部调用者）

## 10. API 规范

### 被删除的端点

**Cloud: `GET /api/v1/memories/emotion-profile`**

此端点将被完全删除，不提供替代。情绪相关数据通过以下现有机制获取：
- 微观：`recall()` 返回的记忆中 `metadata_.emotion` 字段
- 宏观：`recall()` 中的 trait 类型记忆（category=trait）

### 保持不变的 API

- `ingest()` — 不变
- `recall()` — 不变
- `digest()` — 仅移除内部 emotion_profiles 更新逻辑，输入输出不变

## 11. 成功标准

### 功能要求

- ✅ SDK 代码中 `grep -r "EmotionProfile" neuromem/` 返回零结果
- ✅ SDK 代码中 `grep -r "emotion_profile" neuromem/` 返回零结果（排除 metadata_.emotion 上下文）
- ✅ Cloud 代码中 `grep -r "EmotionProfile\|emotion_profile" server/src/` 返回零结果
- ✅ Me2 代码中 `grep -r "EmotionProfile\|emotion_profile" backend/app/` 返回零结果
- ✅ `neuromem/models/emotion_profile.py` 文件不存在
- ✅ SDK 全部测试通过（`pytest tests/ -v`）
- ✅ Cloud 全部测试通过（`pytest tests/ -v`）
- ✅ Me2 全部测试通过（`pytest tests/ -v`）

### 质量指标

- 零新增代码行（纯删除操作）
- 不影响现有功能的输入输出行为
- digest() 执行时间不增加（应略减少，因为少了一次表写入）

## 12. 实施阶段

### 阶段 1：SDK 清理

- **目标**：完全移除 SDK 中的 EmotionProfile 相关代码
- **交付物**：
  - ✅ 删除模型文件、导入导出、Facade 引用
  - ✅ 删除 database setup 中的建表逻辑
  - ✅ 删除 digest() 中的更新逻辑
- **验证**：SDK 测试全部通过 + grep 零结果

### 阶段 2：Cloud 清理

- **目标**：移除 Cloud 中所有 EmotionProfile 引用
- **交付物**：
  - ✅ 删除 schema、端点、清理 SQL
- **验证**：Cloud 测试全部通过 + grep 零结果

### 阶段 3：Me2 清理

- **目标**：移除 Me2 中所有 EmotionProfile 引用
- **交付物**：
  - ✅ 删除迁移 SQL、导入查询、表引用
- **验证**：Me2 测试全部通过 + grep 零结果

### 阶段 4：微观层检查

- **目标**：确认微观层逻辑无明显问题
- **交付物**：
  - ✅ 检查报告（无问题则标记完成）
- **验证**：代码审查确认

## 13. 未来考虑

- **近期情绪聚合**：如应用层后续需要"最近 N 天的情绪分布"能力，可评估是否在 recall() 中新增便利参数或在 trait 系统中新增聚合方法
- **情绪可视化**：Me2 前端的情绪展示应改为基于 trait 数据，而非已废弃的 EmotionProfile
- **表清理**：生产数据库中已存在的 emotion_profiles 表可在后续运维窗口手动 DROP

## 14. 风险与缓解措施

| 风险 | 影响 | 缓解 |
|------|------|------|
| SDK 中存在未发现的隐藏引用 | 运行时 ImportError | 实施前全量 grep 扫描，清理后运行完整测试套件 |
| Cloud 前端有未记录的 emotion-profile 调用 | 前端功能异常 | 实施前在 Cloud web/ 目录搜索相关 API 路径 |
| Me2 memories.py 删除查询后端点行为变化 | API 返回格式变化 | 分析端点完整逻辑，必要时调整返回结构 |
| 三端未同步发布导致 import 断裂 | 部署期间服务异常 | 先合并 SDK 变更 → 再更新下游（Cloud/Me2 先本地测试再部署） |

## 15. 附录

### 相关文档

- 需求摘要：`D:/CODE/NeuroMem/rpiv/brainstorm-summary-emotion-architecture-migration.md`
- 记忆分类 V2 设计：`D:/CODE/NeuroMem/docs/design/memory-classification-v2.md`
- SDK 架构：`D:/CODE/NeuroMem/CLAUDE.md`

### 下游引用明细

#### neuromem-cloud（2 文件）

| 文件 | 引用内容 |
|------|---------|
| `server/src/neuromem_cloud/schemas_memory.py` | `EmotionProfileResponse` schema 定义 |
| `server/src/neuromem_cloud/api/memory_mgmt.py` | `GET /emotion-profile` 端点 + 用户数据删除中 `DELETE FROM emotion_profiles` |

#### Me2（3 文件）

| 文件 | 引用内容 |
|------|---------|
| `backend/app/main.py` | 启动时 ~8 行 `ALTER TABLE emotion_profiles ADD COLUMN IF NOT EXISTS ...` |
| `backend/app/api/v1/memories.py` | `from neuromem.models.emotion_profile import EmotionProfile` + 查询 |
| `backend/app/services/admin_service.py` | 数据清理表列表中包含 `"emotion_profiles"` |
