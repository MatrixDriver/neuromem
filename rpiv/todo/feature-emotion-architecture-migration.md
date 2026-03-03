---
title: "情绪架构迁移重构：废弃 EmotionProfile 表，迁移至动态聚合 + Trait 升级链"
type: feature
status: completed
priority: medium
created_at: 2026-03-03T20:00:00
updated_at: 2026-03-03T22:00:00
---

# 情绪架构迁移重构

## 动机与背景

当前 neuromem 的情绪系统存在架构冗余：

1. **微观层**（单条记忆的 `metadata_.emotion`）运行良好，LLM 提取时自动标注 valence/arousal/label，recall 时参与评分加成和 arousal 抗衰减
2. **中观层**（`emotion_profiles.latest_state`）和**宏观层**（`emotion_profiles.dominant_emotions` 等）存储在独立的 `emotion_profiles` 表中，但该表已标记为 **DEPRECATED**
3. 中观/宏观数据与微观标注之间存在**数据冗余和同步问题**——同一份情绪信息在两个地方维护

设计重构后的结论：
- **中观**（近期情感状态）可以从近期 episodic 记忆的 emotion 字段**动态聚合**，无需持久化
- **宏观**（长期情感特质）可以通过 **trait 升级链自然产生**（如"容易焦虑"是 behavior → preference 级别的特质）
- 独立的 EmotionProfile 表不再必要

## 期望行为

1. 删除 `emotion_profiles` 表及 `EmotionProfile` 模型
2. 中观情感状态改为调用时从近期记忆动态聚合（profile_view 或 recall 层面）
3. 宏观情感特质由 reflection 引擎自动归纳为 trait（当前已部分支持：reflection prompt 中已包含情绪模式检测指令）
4. 清理所有引用已弃用模型的导入和导出

## 用户场景

1. **应用层查询用户近期情绪**：调用 SDK 方法，从近期 episodic 记忆中动态聚合 valence/arousal 均值和情绪分布，而非读取静态表
2. **长期情感画像**：通过 recall trait 获取"容易焦虑"、"对技术话题兴奋"等情感特质，这些由 reflection 引擎自动从微观标注归纳产生
3. **emotion_triggers 映射**：话题→情绪的关联（如"工作→焦虑"）作为情境化 trait 存储，而非独立字段

## MVP 定义

### 必须完成

- [ ] 删除 `neuromem/models/emotion_profile.py`
- [ ] 删除 `__init__.py` 中的 `EmotionProfile` 导出
- [ ] 删除数据库中 `emotion_profiles` 表的创建/迁移逻辑
- [ ] 清理 `_core.py` 或其他 Facade 中对 EmotionProfile 的引用
- [ ] 确认 `digest()` 中更新 emotion_profiles 的逻辑已移除或替换

### 可选增强

- [ ] 新增 `nm.emotions.recent()` 方法，从近期记忆动态聚合中观情感状态
- [ ] 确认 reflection 引擎已能将情绪模式归纳为 trait（如 behavior:"讨论工作时总是焦虑" → preference:"工作场景下容易焦虑"）
- [ ] 数据库迁移：为已有 emotion_profiles 数据提供迁移脚本（转为 trait 或归档）

## 涉及文件

| 文件 | 操作 |
|------|------|
| `neuromem/models/emotion_profile.py` | 删除 |
| `neuromem/models/__init__.py` | 移除 EmotionProfile 导入 |
| `neuromem/__init__.py` | 移除 EmotionProfile 导出 |
| `neuromem/_core.py` | 清理 emotion_profiles 相关引用 |
| `neuromem/services/reflection.py` | 确认情绪模式→trait 归纳已覆盖宏观层需求 |
| `neuromem/services/search.py` | 微观层不变，确认无 EmotionProfile 依赖 |
| `neuromem-cloud` / `Me2` 调用点 | 检查是否有对 EmotionProfile 的调用 |

## 备选方案

1. **保留 EmotionProfile 作为缓存表**：定期从记忆聚合写入，避免每次查询都动态计算。缺点是仍有同步问题
2. **仅标记弃用但不删除**：当前状态，但长期会造成代码混淆

## 参考

- 三层情感架构设计：`D:/CODE/NeuroMem/docs/ARCHITECTURE.md` 第 612-623 行
- 情感标注理论：`D:/CODE/NeuroMem/docs/memory-architecture.md` 第 62-84 行（LeDoux 1996 + Russell 1980 Circumplex）
- EmotionProfile DEPRECATED 标记：`D:/CODE/NeuroMem/neuromem/models/emotion_profile.py`
- 反思中的情绪模式检测：`D:/CODE/NeuroMem/neuromem/services/reflection.py` 第 74-78 行
