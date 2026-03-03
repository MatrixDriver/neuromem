---
description: "测试规格: 情绪架构迁移（废弃 EmotionProfile）— 具体测试用例"
status: completed
created_at: 2026-03-03T21:35:00
updated_at: 2026-03-03T22:10:00
archived_at: null
---

# 测试规格：情绪架构迁移 — 具体测试用例

> 基于 PRD `prd-emotion-architecture-migration.md` 和测试策略 `test-strategy-emotion-architecture-migration.md`

## TC-1: 文件存在性验证

**优先级**: P0 | **类型**: 静态检查

| 用例 ID | 检查项 | 预期结果 | 命令 |
|---------|--------|---------|------|
| TC-1.1 | `neuromem/models/emotion_profile.py` 已删除 | 文件不存在 | `test ! -f D:/CODE/NeuroMem/neuromem/models/emotion_profile.py && echo PASS \|\| echo FAIL` |

## TC-2: Grep 零残留验证

**优先级**: P0 | **类型**: 静态检查

对三端源码目录搜索以下模式，期望零匹配（豁免项除外）。

**搜索模式**：`EmotionProfile`、`emotion_profile`、`emotion_profiles`、`EmotionProfileResponse`

### TC-2.1: SDK 零残留

| 用例 ID | 搜索范围 | 模式 | 预期 | 豁免 |
|---------|---------|------|------|------|
| TC-2.1a | `D:/CODE/NeuroMem/neuromem/**/*.py` | `EmotionProfile` | 0 匹配 | 无 |
| TC-2.1b | `D:/CODE/NeuroMem/neuromem/**/*.py` | `emotion_profile` | 0 匹配 | `metadata_.emotion` 上下文中的非相关匹配可忽略 |
| TC-2.1c | `D:/CODE/NeuroMem/neuromem/**/*.py` | `emotion_profiles` | 0 匹配 | 无 |

### TC-2.2: Cloud 零残留

| 用例 ID | 搜索范围 | 模式 | 预期 | 豁免 |
|---------|---------|------|------|------|
| TC-2.2a | `D:/CODE/neuromem-cloud/server/src/**/*.py` | `EmotionProfile` | 0 匹配 | 无 |
| TC-2.2b | `D:/CODE/neuromem-cloud/server/src/**/*.py` | `emotion_profile` | 0 匹配 | 无 |
| TC-2.2c | `D:/CODE/neuromem-cloud/server/src/**/*.py` | `EmotionProfileResponse` | 0 匹配 | 无 |

### TC-2.3: Me2 零残留

| 用例 ID | 搜索范围 | 模式 | 预期 | 豁免 |
|---------|---------|------|------|------|
| TC-2.3a | `D:/CODE/me2/backend/app/**/*.py` | `EmotionProfile` | 0 匹配 | 无 |
| TC-2.3b | `D:/CODE/me2/backend/app/**/*.py` | `emotion_profile` | 0 匹配 | 无 |
| TC-2.3c | `D:/CODE/me2/backend/app/**/*.py` | `emotion_profiles` | 0 匹配 | 无 |

### TC-2.4: Cloud 前端零残留

| 用例 ID | 搜索范围 | 模式 | 预期 |
|---------|---------|------|------|
| TC-2.4a | `D:/CODE/neuromem-cloud/web/src/**/*.{ts,tsx}` | `emotion-profile` | 0 匹配 |
| TC-2.4b | `D:/CODE/neuromem-cloud/web/src/**/*.{ts,tsx}` | `emotion_profile` | 0 匹配 |

## TC-3: SDK Import 链完整性

**优先级**: P0 | **类型**: 运行时验证

每个用例通过 `uv run python -c "..."` 在 SDK 目录下执行。

| 用例 ID | 导入语句 | 预期 | 说明 |
|---------|---------|------|------|
| TC-3.1 | `from neuromem import NeuroMemory` | 无异常 | 顶层 Facade 可导入 |
| TC-3.2 | `import neuromem; print(dir(neuromem))` | 无异常，输出不含 `EmotionProfile` | 顶层命名空间已清理 |
| TC-3.3 | `from neuromem.models import Memory, Conversation` | 无异常 | models 包可导入且不含废弃模型 |
| TC-3.4 | `from neuromem.models import EmotionProfile` | 抛出 `ImportError` | 确认模型已被移除 |
| TC-3.5 | `from neuromem._core import NeuroMemory` | 无异常 | Facade 内部无断裂引用 |
| TC-3.6 | `from neuromem.services.reflection import ReflectionService` | 无异常 | 反思服务 import 链完整 |

**执行命令模板**：
```bash
cd D:/CODE/NeuroMem && uv run python -c "<import_statement>"
```

## TC-4: Cloud Import 链完整性

**优先级**: P0 | **类型**: 运行时验证

| 用例 ID | 导入语句 | 预期 | 说明 |
|---------|---------|------|------|
| TC-4.1 | `from neuromem_cloud.app import app` | 无异常 | 应用入口可导入 |
| TC-4.2 | `from neuromem_cloud.api.memory_mgmt import router` | 无异常 | 路由模块可导入 |
| TC-4.3 | `from neuromem_cloud.schemas_memory import *; assert 'EmotionProfileResponse' not in dir()` | 断言通过 | schema 已清理 |

**执行命令模板**：
```bash
cd D:/CODE/neuromem-cloud/server && uv run python -c "<import_statement>"
```

## TC-5: Me2 Import 链完整性

**优先级**: P0 | **类型**: 运行时验证

| 用例 ID | 导入语句 | 预期 | 说明 |
|---------|---------|------|------|
| TC-5.1 | `import sys; sys.path.insert(0, '.'); from app.api.v1.memories import router` | 无异常 | memories 路由不再 import EmotionProfile |
| TC-5.2 | `import sys; sys.path.insert(0, '.'); from app.services.admin_service import AdminService` | 无异常 | admin_service 不含废弃引用 |

**执行命令模板**：
```bash
cd D:/CODE/me2/backend && uv run python -c "<import_statement>"
```

**注意**：Me2 import 可能依赖数据库连接等运行时条件，如 import 因非 EmotionProfile 原因失败，记录为"非本次改动导致"。

## TC-6: SDK 测试套件回归

**优先级**: P0 | **类型**: 自动化测试 | **依赖**: PostgreSQL 5436

| 用例 ID | 命令 | 预期 | 失败处理 |
|---------|------|------|---------|
| TC-6.1 | `cd D:/CODE/NeuroMem && uv run pytest tests/ -v --timeout=60` | 全部通过，0 failures | 任何失败需分析是否由本次改动导致 |
| TC-6.2 | `cd D:/CODE/NeuroMem && uv run pytest tests/ -v --timeout=60 -k "emotion or digest or reflect"` | 全部通过 | 重点关注情绪/反思相关测试 |

**数据库不可用时**：记录为"PostgreSQL 5436 不可用，TC-6 待手动验证"，不阻塞。

## TC-7: Cloud 测试套件回归

**优先级**: P0 | **类型**: 自动化测试 | **依赖**: PostgreSQL 5435

| 用例 ID | 命令 | 预期 |
|---------|------|------|
| TC-7.1 | `cd D:/CODE/neuromem-cloud/server && uv run pytest tests/ -v` | 全部通过 |

**数据库不可用时**：记录为"PostgreSQL 5435 不可用，TC-7 待手动验证"。

## TC-8: Me2 测试套件回归

**优先级**: P0 | **类型**: 自动化测试

| 用例 ID | 命令 | 预期 |
|---------|------|------|
| TC-8.1 | `cd D:/CODE/me2/backend && uv run pytest tests/ -m unit -v` | 全部通过 |

## TC-9: PRD 用户故事验收

**优先级**: P0 | **类型**: 验收测试

逐条验证 PRD 第 5 节用户故事：

| 用户故事 | 验证方式 | 对应 TC |
|----------|---------|---------|
| US-1: 代码中不再有 EmotionProfile 模型 | grep 零残留 + 文件删除 | TC-1, TC-2.1 |
| US-2: digest() 不再执行无意义的表写入 | grep reflection.py 无 emotion_profiles 引用 + 测试套件 | TC-2.1c, TC-6.2 |
| US-3: Cloud 无 emotion-profile 端点 | grep Cloud 零残留 | TC-2.2 |
| US-4: Me2 启动不执行 emotion_profiles 迁移 SQL | grep Me2 零残留 | TC-2.3 |
| US-5: grep EmotionProfile 返回零结果 | 三端全量 grep | TC-2.1~2.4 |

## TC-10: PRD 成功标准对照

**优先级**: P0 | **类型**: 综合验证

PRD 第 11 节功能要求逐条映射：

| PRD 成功标准 | 对应 TC | 自动化 |
|-------------|---------|--------|
| SDK grep EmotionProfile 零结果 | TC-2.1a | 是 |
| SDK grep emotion_profile 零结果 | TC-2.1b | 是 |
| Cloud grep 零结果 | TC-2.2a~c | 是 |
| Me2 grep 零结果 | TC-2.3a~c | 是 |
| emotion_profile.py 文件不存在 | TC-1.1 | 是 |
| SDK 全部测试通过 | TC-6.1 | 是（需 DB） |
| Cloud 全部测试通过 | TC-7.1 | 是（需 DB） |
| Me2 全部测试通过 | TC-8.1 | 是 |

PRD 质量指标：

| 指标 | 验证方式 |
|------|---------|
| 零新增代码行（纯删除） | 代码审查阶段 git diff --stat 验证 |
| 不影响现有功能 I/O | TC-6~8 测试套件 |

## TC-11: 端点删除验证

**优先级**: P1 | **类型**: API 验证 | **依赖**: Cloud 服务运行中

| 用例 ID | 操作 | 预期 |
|---------|------|------|
| TC-11.1 | Cloud 路由表中搜索 `/emotion-profile` | 不存在此路由 |

**静态验证替代**：如 Cloud 服务未运行，通过 grep `memory_mgmt.py` 确认无 `@router.get` 装饰器包含 `emotion-profile`。

## TC-12: Me2 memories.py 端点行为验证

**优先级**: P1 | **类型**: 代码审查

| 用例 ID | 检查项 | 预期 |
|---------|--------|------|
| TC-12.1 | `memories.py` 删除 EmotionProfile 查询后，相关端点是否仍有完整功能 | 端点逻辑完整，或整个端点被移除 |
| TC-12.2 | `memories.py` 中是否有其他 import 因 EmotionProfile 删除而失效 | 无其他依赖断裂 |

## 验收清单汇总

### Gate 1：代码实现完成后（阻塞审查）

- [ ] TC-1.1: emotion_profile.py 文件已删除
- [ ] TC-2.1a~c: SDK grep 零残留
- [ ] TC-2.2a~c: Cloud grep 零残留
- [ ] TC-2.3a~c: Me2 grep 零残留
- [ ] TC-2.4a~b: Cloud 前端零残留
- [ ] TC-3.1~3.6: SDK import 链完整
- [ ] TC-4.1~4.3: Cloud import 链完整
- [ ] TC-5.1~5.2: Me2 import 链完整
- [ ] TC-6.1~6.2: SDK 测试通过（或 DB 不可用标记）
- [ ] TC-7.1: Cloud 测试通过（或 DB 不可用标记）
- [ ] TC-8.1: Me2 单元测试通过
- [ ] TC-9: 全部用户故事验收通过
- [ ] TC-10: 全部 PRD 成功标准达成

### Gate 2：代码审查阶段（阻塞合并）

- [ ] `git diff --stat` 确认零新增代码行（纯删除）
- [ ] 变更文件列表与 PRD 第 7 节完全吻合
- [ ] 无意外的附带修改（scope creep）

### Gate 3：P1 跟踪项（不阻塞但需记录）

- [ ] TC-11.1: Cloud emotion-profile 端点已移除
- [ ] TC-12.1~12.2: Me2 memories.py 端点行为正常

---

## 补充：前端清理测试用例（基于实施计划扩展）

实施计划确认清理范围扩展到 Cloud 前端和 Me2 前端，补充以下测试用例。

### TC-13: Cloud 前端文件删除验证

**优先级**: P0 | **类型**: 静态检查

| 用例 ID | 检查项 | 预期 |
|---------|--------|------|
| TC-13.1 | `web/src/components/emotion-chart.tsx` 已删除 | 文件不存在 |
| TC-13.2 | `web/src/app/api/spaces/[spaceId]/emotions/route.ts` 已删除 | 文件不存在 |
| TC-13.3 | `web/src/app/dashboard/spaces/[spaceId]/emotions/page.tsx` 已删除 | 文件不存在 |

### TC-14: Cloud 前端 Grep 零残留

**优先级**: P0 | **类型**: 静态检查

| 用例 ID | 搜索范围 | 模式 | 预期 | 豁免 |
|---------|---------|------|------|------|
| TC-14.1 | `web/src/**/*.{ts,tsx}` | `emotion-profile` | 0 匹配 | `llm_emotion_summary` 相关（trace 标签） |
| TC-14.2 | `web/src/**/*.{ts,tsx}` | `getEmotionProfile` | 0 匹配 | 无 |
| TC-14.3 | `web/src/**/*.{ts,tsx}` | `EmotionChart\|emotion-chart` | 0 匹配 | 无 |

### TC-15: Me2 前端文件删除验证

**优先级**: P0 | **类型**: 静态检查

| 用例 ID | 检查项 | 预期 |
|---------|--------|------|
| TC-15.1 | `frontend/components/memories/EmotionSection.tsx` 已删除 | 文件不存在 |

### TC-16: Me2 前端 Grep 零残留

**优先级**: P0 | **类型**: 静态检查

| 用例 ID | 搜索范围 | 模式 | 预期 | 豁免 |
|---------|---------|------|------|------|
| TC-16.1 | `frontend/**/*.{ts,tsx}` | `EmotionSection` | 0 匹配 | 无 |
| TC-16.2 | `frontend/**/*.{ts,tsx}` | `emotion_profile` | 0 匹配 | `emotion_expression`（分析页面，无关） |

### TC-17: 前端构建验证

**优先级**: P0 | **类型**: 构建测试

| 用例 ID | 命令 | 预期 |
|---------|------|------|
| TC-17.1 | `cd D:/CODE/neuromem-cloud/web && npm run build` | 构建成功 |
| TC-17.2 | `cd D:/CODE/me2/frontend && npm run build` | 构建成功 |

---

## 自动化验证脚本

所有测试用例已整合为自动化验证脚本：

```
D:/CODE/NeuroMem/rpiv/validation/verify-emotion-migration.sh
```

执行方式：`bash D:/CODE/NeuroMem/rpiv/validation/verify-emotion-migration.sh`

脚本覆盖：TC-1 ~ TC-8 + TC-13 ~ TC-17，共 35+ 个自动化检查项，输出彩色结果和汇总报告。
