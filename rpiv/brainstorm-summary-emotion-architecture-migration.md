---
description: "需求摘要: 情绪架构迁移重构（废弃 EmotionProfile）"
status: pending
created_at: 2026-03-03T21:00:00
updated_at: 2026-03-03T21:00:00
archived_at: null
---

## 需求摘要

### 产品愿景
- **核心问题**：EmotionProfile 表已弃用但未清理，造成 SDK/Cloud/Me2 三端代码冗余和维护混淆
- **价值主张**：删除弃用的情绪独立表，让情绪系统回归简洁的三层架构（微观标注 + recall 评分 + trait 归纳），消除数据同步问题
- **目标用户**：neuromem SDK 开发者及下游应用（cloud/Me2）开发者
- **产品形态**：SDK 内部重构 + 下游代码同步清理，无新增 API

### 核心场景（按优先级排序）
1. **SDK 模型清理**：删除 EmotionProfile 模型、导入导出、Facade 引用
2. **SDK 数据库清理**：删除 emotion_profiles 表的创建/迁移逻辑，digest() 中的更新逻辑
3. **Cloud 清理**：删除 GET /emotion-profile 端点、EmotionProfileResponse schema、数据清理中的 emotion_profiles 引用
4. **Me2 清理**：删除启动时的 ALTER TABLE 迁移 SQL、memories.py 中的 EmotionProfile 查询、admin_service 中的表引用
5. **微观层检查**：清理过程中如发现微观层（metadata_.emotion）有可优化之处，顺手修复

### 产品边界
- **MVP 范围内**：
  - 删除 EmotionProfile 模型和 emotion_profiles 表相关所有代码（SDK + Cloud + Me2）
  - 数据可直接丢弃，无需迁移脚本
  - 微观层保持不变（除非发现明显问题）
- **明确不做**：
  - 不新增 `nm.emotions` 子 Facade 或任何替代接口
  - 不写数据迁移脚本（数据可丢弃）
  - 不做 API 版本兼容（端点直接删除）
- **后续版本考虑**：
  - 如应用层后续需要"近期情绪聚合"能力，可单独评估是否新增便利方法

### 已知约束
- 三端代码需同步清理，避免 SDK 删了模型但下游仍有引用导致运行时报错
- Cloud 的 emotion-profile 端点无外部调用者，可直接删除
- Me2 的 emotion_profiles ALTER TABLE 迁移 SQL 在表不存在时不会报错（IF NOT EXISTS），但仍应清除以保持代码整洁

### 各场景功能要点

#### 场景 1：SDK 模型清理
- 删除 `neuromem/models/emotion_profile.py`
- 清理 `neuromem/models/__init__.py` 和 `neuromem/__init__.py` 中的导入/导出
- 清理 `_core.py` 中对 EmotionProfile 的引用
- 关键交互：无，纯代码删除
- 异常处理：确认无其他 SDK 内部模块引用此模型

#### 场景 2：SDK 数据库清理
- 删除 emotion_profiles 表的建表逻辑（在 database setup 中）
- 删除 `digest()` 中更新 emotion_profiles 的逻辑
- 关键交互：无
- 异常处理：确认 digest() 清理后不影响其他功能（反思、trait 归纳等）

#### 场景 3：Cloud 清理
- 删除 `schemas_memory.py` 中的 `EmotionProfileResponse`
- 删除 `memory_mgmt.py` 中的 `GET /emotion-profile` 端点
- 删除用户数据清理中的 `DELETE FROM emotion_profiles` SQL
- 异常处理：检查 Web 前端是否调用了此端点，如有则一并清理

#### 场景 4：Me2 清理
- 删除 `main.py` 中约 8 行 ALTER TABLE emotion_profiles 的迁移 SQL
- 删除 `memories.py` 中 import 和查询 EmotionProfile 的代码
- 删除 `admin_service.py` 中 emotion_profiles 表引用
- 异常处理：memories.py 中删除查询后，确认该 API 端点是否还有其他用途或应整体删除

#### 场景 5：微观层检查
- 清理过程中顺便检查 `search.py` 和 `memory_extraction.py` 中的微观情绪逻辑
- 如发现小问题顺手修复，无大改
- 异常处理：无

### 下游引用明细（头脑风暴中扫描确认）

#### neuromem-cloud（2 文件）
| 文件 | 引用内容 |
|------|---------|
| `server/src/neuromem_cloud/schemas_memory.py` | `EmotionProfileResponse` schema 定义 |
| `server/src/neuromem_cloud/api/memory_mgmt.py` | `GET /emotion-profile` 端点 + 用户数据删除中 `DELETE FROM emotion_profiles` |

#### Me2（3 文件）
| 文件 | 引用内容 |
|------|---------|
| `backend/app/main.py` | 启动时 8 行 `ALTER TABLE emotion_profiles ADD COLUMN IF NOT EXISTS ...` |
| `backend/app/api/v1/memories.py` | `from neuromem.models.emotion_profile import EmotionProfile` + 查询 |
| `backend/app/services/admin_service.py` | 数据清理表列表中包含 `"emotion_profiles"` |
