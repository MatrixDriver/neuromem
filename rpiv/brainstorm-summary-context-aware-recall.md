---
description: "需求摘要: context-aware-recall"
status: pending
created_at: 2026-03-05T12:00:00
updated_at: 2026-03-05T12:00:00
archived_at: null
---

## 需求摘要

### 产品愿景
- **核心问题**：recall 不利用已有的 trait 情境标注，无法根据用户当前场景自动优先召回匹配的记忆
- **价值主张**：模拟人脑的情境依赖记忆（Tulving 编码特异性原则），让系统自主判断"什么情境下想起什么"，业界首创
- **目标用户**：neuromem SDK 开发者及其终端用户（无需感知此功能，自动生效）
- **产品形态**：SDK 内部优化，`recall()` 签名不变，返回值非破坏性扩展

### 核心场景（按优先级排序）
1. **工作情境召回**：用户讨论代码/项目时，工作相关的偏好 trait 自动排序靠前
2. **生活情境召回**：用户聊日常生活时，个人偏好 trait 自动排序靠前
3. **情境不明确时**：系统无法判断情境，所有记忆保持现有排序，零干扰
4. **跨情境通用 trait**：标注为 `general` 的 trait 在任何情境下都获得部分 boost

### 产品边界
- **MVP 范围内**：
  - embedding 原型匹配推断情境（中英双语原型句子）
  - 关键词兜底规则
  - context_match_bonus 0~0.10 × confidence
  - recall 返回 `inferred_context` + `context_confidence`
  - 对比实验验证排序质量
- **明确不做**：
  - fact/episodic 的情境标注和 boost（仅 trait）
  - LLM 推断情境（成本和延迟不可接受）
  - 自适应原型（从用户记忆中学习）
  - 可关闭开关
  - `context_hint` 参数（调用方显式传入情境）
- **后续版本考虑**：
  - 自适应原型向量（从用户实际记忆学习）
  - `context_hint` 可选参数
  - fact 层面的情境标注
  - A/B 线上观测

### 已知约束
- 必须零额外延迟（<1ms，复用 query_embedding）
- 必须零额外成本（不调用 LLM）
- 现有 API 签名不变（非破坏性）
- 现有测试全部通过

### 各场景功能要点

#### 场景1：情境推断
- 功能点：从 query_embedding 计算与 4 个情境原型的余弦相似度，取最强匹配
- 关键交互：margin（最高分 - 次高分）低于 0.05 时退化为 `("general", 0.0)`；关键词兜底处理强信号
- 异常处理：embedding 计算失败时返回 `("general", 0.0)`，不阻断 recall

#### 场景2：评分加成
- 功能点：`scored_search` SQL 增加 `context_match` 列，trait 情境完全匹配 +0.10×confidence，general +0.07×confidence
- 关键交互：与现有 recency/importance/trait_boost/emotion_match 叠加，不互斥
- 异常处理：confidence=0 时 boost 为零，等效于功能关闭

#### 场景3：原型向量生命周期
- 功能点：SDK 初始化时从预定义中英双语句子计算原型，缓存在内存
- 关键交互：embedding provider 变更时清除缓存重新计算
- 异常处理：缓存未就绪时跳过情境推断，graceful degradation

#### 场景4：验证
- 功能点：构造测试数据集（带情境标注的 trait + 不同情境的 query），对比开启/关闭 context_match 的排序质量
- 关键交互：使用 MRR（Mean Reciprocal Rank）衡量目标记忆的排名提升
- 异常处理：如果 MRR 无显著提升，需回调 boost 力度或 margin 阈值

### 关键设计决策（brainstorm 阶段确认）

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 作用范围 | 仅 trait | trait 已有 context 标注，改动最小 |
| 语言覆盖 | 中英双语原型 | 覆盖主流使用场景 |
| 多情境处理 | 取最强单情境 | 简单可靠，margin 不足时安全退化 |
| 自适应原型 | MVP 不做 | 避免冷启动问题，后续演进 |
| 透明度 | 暴露在返回结果中 | 支持调试和 Trait Transparency |
| 验证方式 | 对比实验 | 构造数据集，MRR 衡量 |
| 可关闭性 | 默认开启，不可关闭 | 单情境 Space 中 boost 均匀分配，等效无影响 |

### 关联文档

- 设计文档：`docs/design/context-aware-recall.md`
- Todo：`rpiv/todo/feature-context-aware-recall.md`
- V2 设计文档：`docs/design/memory-classification-v2.md` §3.2、§6
