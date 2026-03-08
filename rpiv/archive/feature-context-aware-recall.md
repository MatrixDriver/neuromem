---
title: "情境感知自动召回（Context-Aware Recall）"
type: feature
status: archived
priority: high
created_at: 2026-03-05T11:00:00
updated_at: 2026-03-07T13:30:00
archived_at: 2026-03-07T13:30:00
---

# 情境感知自动召回（Context-Aware Recall）

## 概述

recall 时自动从 query 推断用户当前情境（work/personal/social/learning），对匹配情境的 trait 记忆给予 soft boost，实现情境依赖记忆（Context-Dependent Memory）。

## 动机

- V2 的 trait 已有情境标注（`trait_context` 字段），但 recall 完全没有利用
- 人脑通过编码特异性原则（Tulving 1973）自动在匹配情境下优先召回相关记忆
- 业界无产品实现此能力，neuromem 将是首个
- 减少对手动配置（设置页工具描述）的依赖，让系统自主学会"什么时候想起什么"

## 设计文档

`docs/design/context-aware-recall.md`

## 核心方案

1. **情境推断**：embedding 原型匹配（预计算 4 个情境的中英双语原型向量）+ 关键词兜底
2. **评分加成**：`context_match_bonus` 0~0.10，与 `emotion_match` 同级，乘以推断 confidence
3. **零延迟**：复用已有 query_embedding，仅需 4 次余弦相似度计算（<0.1ms）
4. **recall 签名不变**：返回值新增 `inferred_context` + `context_confidence`（非破坏性）

## 设计决策

- **作用范围**：仅 trait（已有 trait_context 标注），不影响 fact/episodic
- **语言覆盖**：中英双语原型句子混合均值
- **多情境处理**：取最强单情境，margin 不足时退化为 general
- **自适应原型**：MVP 不做，后续可从用户实际记忆中学习
- **透明度**：recall 返回推断结果，支持调试和 UI 展示

## 涉及文件

- `neuromem/services/context.py` — 新增，情境推断服务（原型向量管理 + 推断算法 + 关键词兜底）
- `neuromem/services/search.py` — `scored_search` 增加 context_match bonus
- `neuromem/_core.py` — `recall` 调用情境推断，结果传入 search 并写入返回值

## 验收标准

- [ ] 情境原型向量（中英双语）在 SDK 初始化时自动计算并缓存
- [ ] recall 自动推断情境，无需调用方传参
- [ ] 情境匹配的 trait 获得 0~0.10 × confidence 的 boost
- [ ] context="general" 的 trait 获得 0.07 × confidence 的部分匹配 boost
- [ ] 情境不确定时 graceful degradation（confidence=0，退化为现有行为）
- [ ] recall 返回值包含 `inferred_context` 和 `context_confidence` 字段
- [ ] 不增加 recall 可感知的延迟（<1ms 额外开销）
- [ ] 现有测试全部通过（无破坏性变更）
- [ ] 新增测试：情境推断准确性、评分排序正确性、graceful degradation
