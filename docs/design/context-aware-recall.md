# 情境感知自动召回（Context-Aware Recall）

> **状态**: 设计完成，待实施
> **创建日期**: 2026-03-05
> **参与者**: Jacky + Claude
> **关联**: `docs/design/memory-classification-v2.md` §3.2（情境标注前置）、§6（Recall 中的 Trait 使用）

---

## 1. 设计动机

### 1.1 问题

V2 的 trait 系统从 behavior 层就附带情境标注（`context: work/personal/social/learning/general`），reflection 引擎自动推断情境。但 **recall 端完全没有利用这些情境信息**——当前的召回纯靠语义相似度 + recency + importance + trait_boost + emotion_match 排序，不感知用户当前所处的情境。

结果：用户问"帮我写个 Python 脚本"时，工作相关的代码风格偏好（`trait[work]: "偏好函数式编程"`）和生活偏好（`trait[personal]: "喜欢极简风格"`）在召回排序中没有区分——全靠语义碰运气。

### 1.2 认知心理学基础

**编码特异性原则**（Encoding Specificity Principle, Tulving & Thomson 1973）：

记忆的提取效果取决于提取线索与编码时情境的匹配程度。在咖啡店学的东西，回到咖啡店更容易想起来。这被称为**情境依赖记忆**（Context-Dependent Memory）。

人脑不需要手动设置"现在是工作模式"——坐在办公桌前、打开 IDE 这些环境线索自动激活工作相关的记忆。

### 1.3 设计原则

- **模拟人脑，减少人为配置**：情境推断完全自动化，不需要用户设置或调用方传参
- **soft boost，不是 hard filter**：情境不匹配的记忆不会被排除，只是排名靠后。人脑也是这样——工作时也能想起家里的事，只是需要更强的触发
- **graceful degradation**：推断不出情境时退化为现有行为，零副作用

### 1.4 业界调研支撑

对 Mem0、Zep、ChatGPT、Letta、Cursor/Claude Code、Memoria 等产品/框架的调研显示：

- **没有任何产品在 recall 时做自动情境推断** — neuromem 将是首个实现此能力的系统
- Letta 通过多 Memory Block 手动分离情境（需要开发者显式创建 work/personal 块）
- Cursor 通过 glob 模式匹配实现文件级"情境"（编辑 `.tsx` 时加载 `frontend.mdc`）
- ChatGPT 将所有记忆混合存储，不做情境区分
- neuromem V2 已有的情境标注基础设施（`trait_context` 字段）使得这个功能水到渠成

---

## 2. 方案设计

### 2.1 整体流程

```
当前 recall 流程:
  query → embed → 向量检索 + BM25 → RRF 融合 → bonus 加成 → 排序

增加情境感知后:
  query → embed → 向量检索 + BM25 → RRF 融合 → bonus 加成 → 【+ context_match_bonus】→ 排序
                                                                        ↑
                                                                从 query 自动推断情境
```

### 2.2 情境推断方案

**选型决策：embedding 原型匹配 + 关键词兜底**

| 方案 | 优劣 | 延迟 | 成本 |
|------|------|------|------|
| A. 关键词规则 | 覆盖不全，硬编码 | ~0ms | 零 |
| **B. embedding 原型匹配** | **语义级、可扩展** | **~0ms（复用已有 query_embedding）** | **零** |
| C. LLM 推断 | 最准确 | +200-500ms | 每次 recall 一次 LLM 调用 |

**选择方案 B 的理由**：

1. **模拟人脑**：人脑的情境判断是模式匹配，不是查字典（方案 A）也不是深度推理（方案 C）
2. **零额外延迟**：recall 已经计算了 `query_embedding`，情境推断只需要计算 5 个余弦相似度（<0.1ms）
3. **零额外成本**：不需要 LLM 调用
4. **recall 是高频操作**：每次对话可能多次 recall，不应增加延迟

**关键词规则作为兜底**：处理特别明确的信号（如 query 中包含"代码"、"项目"、"做饭"、"周末"等强信号词）。

#### 2.2.1 情境原型向量

为每个情境标签准备 20-30 个典型句子，计算其 embedding 均值作为"原型向量"：

```python
CONTEXT_PROTOTYPES = {
    "work": mean_embedding([
        # 中文
        "帮我写一个 Python 函数",
        "这个 API 接口怎么设计",
        "代码审查发现了一个 bug",
        "明天有个技术评审会议",
        "部署到生产环境",
        "项目架构需要重构",
        # 英文
        "Help me write a Python function",
        "How should I design this API endpoint",
        "Found a bug during code review",
        "I have a technical review meeting tomorrow",
        "Deploy to production",
        "The project architecture needs refactoring",
        # ... 每个情境中英各 15 句，共约 30 句
    ]),
    "personal": mean_embedding([
        # 中文
        "周末去哪里玩",
        "晚饭吃什么",
        "最近在看一部电视剧",
        "我妈妈生日快到了",
        # 英文
        "Where should I go this weekend",
        "What should I have for dinner",
        "I've been watching a TV series lately",
        "My mom's birthday is coming up",
        # ...
    ]),
    "social": mean_embedding([
        # 中文
        "朋友聚会怎么安排",
        "同事关系处理",
        "社交场合穿什么",
        # 英文
        "How to plan a friends gathering",
        "Dealing with colleague relationships",
        "What to wear for social occasions",
        # ...
    ]),
    "learning": mean_embedding([
        # 中文
        "这个概念的原理是什么",
        "推荐一些学习资源",
        "怎么入门机器学习",
        # 英文
        "What's the principle behind this concept",
        "Recommend some learning resources",
        "How to get started with machine learning",
        # ...
    ]),
}
```

**语言覆盖**：每个情境包含中英文典型句子各约 15 句，取混合均值。这确保原型向量在中英文 query 上都能有效匹配。

**初始化时机**：SDK 实例化时计算并缓存在内存中。原型向量随 embedding 模型变化需要重新计算。

#### 2.2.2 情境推断算法

```python
def infer_context(query_embedding: list[float], prototypes: dict[str, list[float]]) -> tuple[str, float]:
    """从 query embedding 推断最可能的情境。

    Returns:
        (context_label, confidence)
        confidence < threshold 时返回 ("general", 0.0)，表示无法确定情境
    """
    similarities = {
        ctx: cosine_similarity(query_embedding, proto)
        for ctx, proto in prototypes.items()
    }
    best_ctx = max(similarities, key=similarities.get)
    best_score = similarities[best_ctx]

    # 置信度 = 最高分与次高分的差距（越大越确信）
    sorted_scores = sorted(similarities.values(), reverse=True)
    margin = sorted_scores[0] - sorted_scores[1] if len(sorted_scores) > 1 else sorted_scores[0]

    # 阈值：差距太小说明情境不明确
    MARGIN_THRESHOLD = 0.05
    if margin < MARGIN_THRESHOLD:
        return ("general", 0.0)

    return (best_ctx, min(margin / 0.15, 1.0))  # 归一化到 0~1
```

### 2.3 评分公式扩展

在 `scored_search` 的 final score 中增加 `context_boost`：

```sql
-- 情境匹配加成：0~0.10
-- 仅对有 trait_context 的记忆生效
CASE
    WHEN memory_type = 'trait'
         AND metadata->>'context' = :query_context
    THEN 0.10 * :context_confidence
    WHEN memory_type = 'trait'
         AND metadata->>'context' = 'general'
    THEN 0.07 * :context_confidence     -- general 跨情境通用，部分匹配
    ELSE 0
END AS context_match
```

**最终评分公式**：

```
score = prospective_penalty
        × base_relevance
        × (1 + recency + importance + trait_boost + emotion_match + context_match)
```

### 2.4 加成力度设计

recall 的完整评分公式中，每个 bonus 都是一个**乘法加成因子**，叠加在一起放大 base_relevance：

```
score = prospective_penalty × base_relevance × (1 + recency + importance + trait_boost + emotion_match + context_match)
```

| bonus 类型 | 范围 | 模拟的人脑机制 |
|-----------|------|--------------|
| recency | 0~0.15 | 越近的事越容易想起（遗忘曲线） |
| importance | 0~0.15 | 越重要的事越不容易忘（情绪编码增强） |
| trait_boost | 0~0.25 | 核心人格记忆最容易浮现（自我图式效应） |
| emotion_match | 0~0.10 | 心情相似时更容易想起相关记忆（心境一致性效应） |
| **context_match** | **0~0.10** | **在相同情境下更容易想起相关记忆（情境依赖记忆）** |

context_match 设为 0.10 的理由：
- 不应超过 trait_boost（trait 的阶段验证比情境匹配更重要）
- 与 emotion_match 同级（都是辅助性的情境线索）
- 足以将同等语义相关度的记忆区分开（0.10 的差距在排序中有明显效果）

#### 完整计算示例

**场景**：用户问 "帮我优化这段 Python 代码"，系统推断 `context = "work"`，`confidence = 0.8`。

有两条 trait 记忆语义相关度差不多：

**记忆 A**：`trait[work]: "偏好函数式编程风格"` (established)

```
base_relevance = 0.72
recency        = 0.08
importance     = 0.12
trait_boost    = 0.15  (established)
emotion_match  = 0.02
context_match  = 0.10 × 0.8 = 0.08  ← 情境匹配！confidence 作为衰减因子

score = 0.72 × (1 + 0.08 + 0.12 + 0.15 + 0.02 + 0.08) = 0.72 × 1.45 = 1.044
```

**记忆 B**：`trait[personal]: "喜欢极简风格"` (established)

```
base_relevance = 0.70
recency        = 0.10
importance     = 0.12
trait_boost    = 0.15  (established)
emotion_match  = 0.02
context_match  = 0     ← 情境不匹配，不惩罚，只是没有加成

score = 0.70 × (1 + 0.10 + 0.12 + 0.15 + 0.02 + 0) = 0.70 × 1.39 = 0.973
```

**结果**：记忆 A（1.044）排在记忆 B（0.973）前面。没有 context_match 时两者分数非常接近，排序可能反过来。context_match 在此起到了"决胜局"的作用。

**关键行为**：
- **soft boost**：情境不匹配的记忆 B **不会被过滤掉**，只是得分少一点。就像你在办公室也能想起家里的事，只是不那么容易
- **confidence 调节**：如果系统不确定当前情境（confidence 低），boost 自动缩小（`0.10 × confidence`），趋近于零
- **graceful degradation**：完全无法判断情境时 `confidence = 0.0`，context_match 对所有记忆都是 0，退化为现有行为

### 2.5 设计决策记录

#### 作用范围：仅 trait

context_match_bonus **仅作用于 trait 类型记忆**，不影响 fact 和 episodic。

理由：
- trait 是唯一在存储时带有 `trait_context` 标注的记忆类型（由 reflection 引擎推断）
- fact 本身没有情境标注，强行推断会增加 ingest 的复杂度，与 MVP 目标冲突
- 保持改动最小化，仅消费已有的 trait_context 字段

#### 语言覆盖：中英双语原型

每个情境的原型句子**同时包含中文和英文典型句子**，取混合均值作为原型向量。

理由：
- neuromem 用户可能用中文或英文与 AI 对话
- 主流 embedding 模型（如 OpenAI text-embedding-3）对中英文都有较好的语义表示
- 混合原型向量在跨语言 query 上表现更稳健

#### 多情境处理：取最强单情境

当 query 同时包含多个情境信号（如 "我想在工作中学习 Rust" 含 work + learning）时，**只取最强匹配的单个情境**。

理由：
- 简单可靠，避免多情境加权的复杂度
- margin 不够大时自动退化为 `("general", 0.0)`，安全兜底
- 实际场景中单情境覆盖绝大多数 query

#### 自适应原型：MVP 不做，后续演进

MVP 使用预定义句子的静态原型向量。未来可以从用户实际记忆中学习更精确的情境原型（用 `context=work` 的 trait embedding 均值替代预定义原型），但这需要用户积累足够多的带情境标注的 trait，新用户体验会有冷启动问题。

#### 情境信息透明度：暴露在返回结果中

recall 返回值增加 `inferred_context` 和 `context_confidence` 字段，便于调用方观测和调试。

理由：
- 支持 Trait Transparency（P1 已实现的特质透明化功能）
- 调用方可选择在 UI 中展示"当前识别的情境"
- 不影响现有消费方（新增字段，非破坏性变更）

---

## 3. 实施要点

### 3.1 涉及文件

| 文件 | 改动 |
|------|------|
| `neuromem/services/context.py` | **新增** — 情境推断服务（原型向量管理 + 推断算法） |
| `neuromem/services/search.py` | `scored_search` 增加 `context_match` bonus |
| `neuromem/_core.py` | `recall` 方法中调用情境推断，将结果传入 `scored_search` |

### 3.2 API 变化

**`recall()` 签名不变**，情境推断在内部自动完成。

**返回值扩展**（非破坏性）：recall 返回的 dict 增加两个字段：

```python
{
    "vector_results": [...],
    "graph_results": [...],
    "merged": [...],
    "inferred_context": "work",      # 新增：推断出的情境标签
    "context_confidence": 0.82,       # 新增：推断置信度 (0~1)
}
```

调用方可以选择使用这些信息（如在 UI 中展示"当前识别的情境"），也可以忽略。

如果未来需要，可以增加可选参数 `context_hint: str | None = None` 允许调用方显式传入情境（覆盖自动推断），但 MVP 不需要。

### 3.3 原型向量的生命周期

- **初始化**：SDK 实例化时，如果缓存不存在，用预定义句子列表计算原型向量
- **缓存**：原型向量缓存在内存中（dict），不需要持久化（计算成本低）
- **更新**：当 embedding provider 变更时，清除缓存重新计算
- **可扩展**：未来可以从用户的实际记忆中学习更精确的情境原型（而非预定义句子）

### 3.4 关键词兜底规则

```python
CONTEXT_KEYWORDS = {
    "work": {"代码", "项目", "API", "部署", "会议", "deadline", "code", "debug",
             "重构", "测试", "review", "上线", "需求", "sprint", "issue"},
    "personal": {"周末", "家里", "旅行", "做饭", "朋友", "家人", "生日", "假期",
                 "看电影", "运动", "健身", "宠物"},
    "social": {"聚会", "社交", "团建", "聊天", "约会", "关系"},
    "learning": {"学习", "教程", "原理", "论文", "课程", "入门", "理解", "概念"},
}
```

当 embedding 原型匹配的 margin 低于阈值时，检查关键词兜底。如果关键词也无法判断，返回 `("general", 0.0)`，不加任何 boost。

---

## 4. 对设置页的影响

### 4.1 短期（本功能）

**无影响**。这是 SDK 层纯内部优化，不改变任何外部 API 或 UI。

### 4.2 中期展望

设置页的三个工具描述（`ingest_description` / `recall_description` / `digest_description`）可以逐步简化。随着情境感知能力增强，手动指令的价值递减。

长期方向：设置页从"指令式配置"变为"记忆空间用途描述"——不是告诉系统"如何操作"，而是告诉系统"这个空间用于什么场景"，这本身可以成为情境推断的一个全局先验信号。

---

## 5. 与 V2 设计的关系

本功能是 V2 情境标注系统的**消费端补全**：

- V2 §3.2 `[P0-调研] 情境标注前置`：解决了"如何在存储时标注情境"（生产端）
- 本文档：解决了"如何在召回时利用情境"（消费端）

两者合在一起，形成完整的**情境依赖记忆**闭环：

```
编码时：reflection 自动推断情境 → 标注 trait_context
提取时：recall 自动推断情境 → context_match_bonus
```

这对应人脑的 Tulving 编码特异性原则——编码和提取的情境匹配越好，记忆效果越好。

---

## 附录 A：与现有 bonus 的交互示例

**场景**：用户问"帮我用 Python 写个数据清洗脚本"

| 记忆 | 语义相关 | trait_boost | context_match | 最终效果 |
|------|---------|-------------|---------------|----------|
| `trait[work]: "偏好函数式编程风格"` (established) | 高 | +0.15 | +0.10 | 高优先 |
| `trait[work]: "习惯先写测试再写实现"` (emerging) | 中 | +0.05 | +0.10 | 中优先 |
| `fact: "用户在 Google 工作"` | 低 | 0 | 0 | 低优先 |
| `trait[personal]: "喜欢极简风格"` (established) | 中 | +0.15 | 0 | 中优先（语义相关但情境不匹配） |

`trait[work]: "偏好函数式编程风格"` 在当前系统可能排在 `trait[personal]: "喜欢极简风格"` 后面（语义相关度可能差不多），但加了 context_match 后会被正确地提升到前面。
