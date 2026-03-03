---
description: "测试策略: 情绪架构迁移（废弃 EmotionProfile）"
status: completed
created_at: 2026-03-03T21:10:00
updated_at: 2026-03-03T21:10:00
archived_at: null
---

# 测试策略：情绪架构迁移（废弃 EmotionProfile）

## 1. 测试目标

本次变更为**纯删除型重构**——移除已弃用的 EmotionProfile 模型及 emotion_profiles 表在三端（SDK/Cloud/Me2）的所有代码引用。测试策略聚焦于：

1. **删除完整性**：确认所有 EmotionProfile 相关代码已从三端完全清除
2. **无回归**：微观情绪功能（metadata_.emotion 标注、recall 评分加成、arousal 抗衰减）不受影响
3. **import 链完整性**：三端 import 不因模型删除而报错
4. **运行时验证**：三端现有测试套件均能通过
5. **grep 零残留**：清理后三端代码中搜索 EmotionProfile/emotion_profile/emotion_profiles 无残留引用（测试代码和注释除外）

## 2. 测试范围

### 2.1 受影响的代码清单

#### neuromem SDK（主要改动）

| 文件 | 预期操作 | 验证方式 |
|------|---------|---------|
| `neuromem/models/emotion_profile.py` | 整文件删除 | 文件不存在检查 |
| `neuromem/models/__init__.py` | 移除 EmotionProfile 导入/导出 | import 验证 + grep |
| `neuromem/__init__.py` | 移除 EmotionProfile 公共导出 | import 验证 + grep |
| `neuromem/_core.py` | 移除 EmotionProfile 引用 | grep + 功能测试 |
| 数据库 setup 逻辑 | 移除 emotion_profiles 建表 | grep + DB 初始化测试 |
| `services/reflection.py` | 移除 digest() 中更新 emotion_profiles 的逻辑 | grep + digest 功能测试 |

#### neuromem-cloud（2 文件）

| 文件 | 预期操作 | 验证方式 |
|------|---------|---------|
| `server/src/neuromem_cloud/schemas_memory.py` | 删除 EmotionProfileResponse | import 验证 + grep |
| `server/src/neuromem_cloud/api/memory_mgmt.py` | 删除 GET /emotion-profile 端点 + DELETE SQL 引用 | API 路由验证 + grep |

#### Me2（3 文件）

| 文件 | 预期操作 | 验证方式 |
|------|---------|---------|
| `backend/app/main.py` | 删除 ~8 行 ALTER TABLE emotion_profiles SQL | grep + 启动验证 |
| `backend/app/api/v1/memories.py` | 删除 EmotionProfile import 和查询 | import 验证 + grep |
| `backend/app/services/admin_service.py` | 移除 emotion_profiles 表引用 | grep |

### 2.2 不受影响（需验证无回归）

| 功能 | 位置 | 验证方式 |
|------|------|---------|
| 微观情绪标注（metadata_.emotion） | `services/memory_extraction.py` | 现有测试 |
| recall 情绪评分加成 | `services/search.py` | 现有测试 |
| arousal 抗衰减 | `services/search.py` | 现有测试 |
| trait 反思管道 | `services/reflection.py`, `services/trait_engine.py` | 现有测试 |
| 图谱功能 | `services/graph*.py` | 现有测试 |

## 3. 测试层级

### 3.1 Level 1：静态验证（grep 零残留）

**优先级：P0 - 必须通过**

在三端代码目录中执行全局搜索，确认以下关键词无残留：

```
搜索模式（区分大小写和不区分大小写两轮）：
- EmotionProfile
- emotion_profile
- emotion_profiles
- EmotionProfileResponse
```

**搜索范围**：
- SDK: `D:/CODE/NeuroMem/neuromem/`（排除 `__pycache__`）
- Cloud: `D:/CODE/neuromem-cloud/server/src/`（排除 `__pycache__`）
- Me2: `D:/CODE/me2/backend/app/`（排除 `__pycache__`）

**豁免条件**：
- 测试文件中的断言（如 "assert EmotionProfile not in ..."）
- 注释中的变更说明（如 "# Removed EmotionProfile in v0.9.x"）
- git 历史和 changelog
- rpiv/ 过程文件

### 3.2 Level 2：Import 链完整性

**优先级：P0 - 必须通过**

验证删除模型后 import 链不断裂：

```python
# SDK import 验证
from neuromem import NeuroMemory
from neuromem.models import Memory, Conversation  # 不应包含 EmotionProfile
import neuromem  # 顶层 __init__.py 不报错

# Cloud import 验证
from neuromem_cloud.app import app
from neuromem_cloud.schemas_memory import *  # 不应包含 EmotionProfileResponse
from neuromem_cloud.api.memory_mgmt import router

# Me2 import 验证
from app.main import app  # 启动不报错
from app.api.v1.memories import router
from app.services.admin_service import AdminService
```

### 3.3 Level 3：现有测试套件回归

**优先级：P0 - 必须通过**

| 项目 | 命令 | 依赖 | 预期 |
|------|------|------|------|
| SDK | `cd D:/CODE/NeuroMem && uv run pytest tests/ -v --timeout=60` | PostgreSQL 5436 | 全部通过 |
| Cloud | `cd D:/CODE/neuromem-cloud/server && uv run pytest tests/ -v` | PostgreSQL 5435 | 全部通过 |
| Me2 | `cd D:/CODE/me2/backend && uv run pytest tests/ -m unit -v` | 无外部依赖 | 全部通过 |

**注意**：如果数据库未启动，记录为"数据库不可用，需手动验证"，不阻塞流程。

### 3.4 Level 4：文件存在性检查

**优先级：P0 - 必须通过**

```
确认已删除的文件不存在：
- D:/CODE/NeuroMem/neuromem/models/emotion_profile.py → 不应存在
```

### 3.5 Level 5：功能无回归抽样

**优先级：P1 - 应当通过**

如果数据库可用，执行以下功能验证：
- `nm.ingest()` 正常工作（不报 EmotionProfile 相关错误）
- `nm.recall()` 正常工作（情绪评分加成仍生效）
- `nm.digest()` 正常工作（反思管道不尝试更新 emotion_profiles 表）

## 4. 验收标准

### 必须满足（P0）

- [ ] grep 搜索三端源码无 EmotionProfile/emotion_profile/emotion_profiles 残留（豁免条件除外）
- [ ] `neuromem/models/emotion_profile.py` 文件已删除
- [ ] SDK `neuromem/__init__.py` 和 `neuromem/models/__init__.py` 中无 EmotionProfile 导出
- [ ] SDK import `from neuromem import NeuroMemory` 不报错
- [ ] Cloud import `from neuromem_cloud.api.memory_mgmt import router` 不报错
- [ ] Me2 import `from app.main import app` 不报错
- [ ] SDK 测试套件全部通过（或因数据库不可用标记为待验证）
- [ ] Cloud 测试套件全部通过（或因数据库不可用标记为待验证）
- [ ] Me2 单元测试全部通过

### 应当满足（P1）

- [ ] digest() 功能正常，不尝试访问 emotion_profiles 表
- [ ] recall() 的微观情绪评分加成不受影响
- [ ] Cloud GET /emotion-profile 端点已不存在（404）

### 不应发生

- [ ] 任何现有测试因本次改动而失败（非预期失败）
- [ ] 任何 import 因模型删除而报 ImportError/ModuleNotFoundError
- [ ] digest() 因缺少 EmotionProfile 而抛出运行时异常

## 5. 测试执行流程

```
Phase 1: 代码实现完成后
  ├── Step 1: Level 4 - 文件存在性检查
  ├── Step 2: Level 1 - grep 零残留验证（三端并行）
  ├── Step 3: Level 2 - import 链验证（三端并行）
  └── Step 4: Level 3 - 测试套件回归（按依赖情况执行）

Phase 2: 测试结果审查
  ├── P0 全部通过 → 进入代码审查
  ├── 有 P0 失败 → 立即通知 team-lead，阻塞流程
  └── P1 失败 → 记录问题，不阻塞但需跟踪
```

## 6. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 测试数据库未启动 | Level 3 无法执行 | 记录为"待验证"，不阻塞流程 |
| SDK 内部模块间接引用 EmotionProfile | import 报错 | grep 搜索覆盖所有 .py 文件 |
| Me2 memories.py 删除查询后端点功能不完整 | API 返回异常 | 审查端点剩余逻辑是否仍有意义 |
| digest() 清理不彻底仍访问旧表 | 运行时异常 | 重点审查 reflection.py 变更 |
