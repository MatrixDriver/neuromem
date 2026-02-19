# NeuroMemory LoCoMo 优化历程

## 成绩总览

| 轮次 | 日期 | 改进项 | Overall Judge | 提升 |
|:---:|:---:|------|:---:|:---:|
| 1 | 02-15 | Baseline（无优化） | 0.125 | — |
| 2 | 02-16 | 独立评测DB、后台任务+embedding缓存、只提取user消息、多用户隔离修复、事务原子性、图谱批量去重、embed_batch批量调用 | 0.274 | +119% |
| 3 | 02-17 | Conv 8-9 数据完整性修复 | 0.431 | +57% |
| 4 | 02-17 | 时间戳提取系统、pg_search BM25、情感感知衰减、RRF混合排序、PostgreSQL 18升级 | 0.610 | +42% |
| 5 | 02-18 | 移除emotion profile/2-hop graph、Answer prompt优化、图谱context注入 | 0.585 | -4% |
| 6 | 02-18 | 评测pipeline移除reflect | 0.580 | -1% |
| 7 | 02-19 | 用户画像提取注入(6 KV键)、Recall Limit 10→20、Graph实体匹配(无LLM) | **0.704** | **+15%** |

> 累计提升：0.125 → 0.704（**+463%**）

## 分类成绩对比

| 轮次 | Single-Hop | Multi-Hop | Open-Dom | Temporal | Overall |
|:---:|:---:|:---:|:---:|:---:|:---:|
| 4 (BM25) | 0.645 | 0.612 | 0.417 | 0.574 | 0.610 |
| 7 (最终) | **0.749** | **0.737** | **0.573** | **0.596** | **0.704** |
| 变化 | +0.104 | +0.125 | +0.156 | +0.022 | +0.094 |

## 与其他框架对比

| 框架 | Single-Hop | Multi-Hop | Open-Dom | Temporal | Overall | Judge LLM |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| Backboard | 89.4% | 75.0% | 91.2% | 91.9% | 90.0% | GPT-4.1 |
| Memobase v0.0.37 | 70.9% | 46.9% | 77.2% | 85.1% | 75.8% | ? |
| Zep | 74.1% | 66.0% | 67.7% | 79.8% | 75.1% | ? |
| Letta (GPT-4o-mini) | — | — | — | — | 74.0% | GPT-4o-mini |
| **NeuroMemory** | **74.9%** | **73.7%** | **57.3%** | **59.6%** | **70.4%** | **DeepSeek** |
| Mem0-Graph | 65.7% | 47.2% | 75.7% | 58.1% | 68.4% | GPT-4o-mini |
| Mem0 | 67.1% | 51.2% | 72.9% | 55.5% | 66.9% | GPT-4o-mini |
| LangMem | 62.2% | 47.9% | 71.1% | 23.4% | 58.1% | GPT-4o-mini |
| OpenAI Memory | 63.8% | 42.9% | 62.3% | 21.7% | 52.9% | GPT-4o-mini |

> 注：各框架使用不同的 Judge LLM，分数不完全可比。NeuroMemory 使用成本较低的 DeepSeek-chat。

## 各轮改进详情

### 第2轮：基础设施与性能（02-16）

| 改进 | 说明 |
|------|------|
| 独立评测数据库 | neuromemory_eval 隔离，避免污染开发数据 |
| 后台任务 + embedding 缓存 | recall 性能优化，避免重复计算 |
| 只对 user 消息提取记忆 | assistant 消息不提取，减少噪音 |
| 多用户隔离修复 | 图谱 user_id 隔离 bug 修复 |
| 事务原子性 | 记忆提取失败不留脏数据 |
| 图谱批量去重 | 避免重复 triple 写入 |
| embed_batch 批量调用 | facts/episodes 一次性批量 embedding |

### 第3轮：数据完整性（02-17）

修复评测框架 bug，确保 10 个 conv 全部完整入库。

### 第4轮：检索引擎升级（02-17）

| 改进 | 说明 |
|------|------|
| 时间戳提取系统 | TemporalExtractor 纯 Python 规则引擎，3 级解析（LLM ISO → LLM 文本 regex → 内容提取） |
| pg_search BM25 | ParadeDB Tantivy 替代 PostgreSQL tsvector，关键词匹配更精准 |
| 情感感知衰减 | arousal 值减缓 recency 衰减，高情感记忆保持更久 |
| RRF 混合排序 | 向量相似度 + BM25 通过 Reciprocal Rank Fusion 融合 |
| PostgreSQL 18 升级 | ParadeDB PG18 + pgvector 0.8.1 + AGE 1.7.0 |

### 第5-6轮：Pipeline 简化（02-18）

移除 emotion profile 注入、2-hop graph 遍历、reflect 阶段。单独看为负优化，但简化了 pipeline，减少了噪音干扰，为第7轮奠定基础。

### 第7轮：画像 + 图谱 + 扩容（02-19）

| 改进 | 说明 |
|------|------|
| 用户画像提取注入 | 6 个 KV 键（identity/occupation/interests/values/relationships/personality），写时提取，读时注入 answer prompt |
| Recall Limit 10→20 | 提供更多上下文，全面提升各类别 |
| Graph 实体匹配 | 子串匹配已知 graph_nodes 实体，无 LLM 依赖，multi-hop +0.125，仅 +25ms 开销 |

## 尝试但回退的实验

| 实验 | 测试结果 | 回退原因 |
|------|---------|---------|
| 规则化 Query 分类 | Judge -0.013 | Open-domain BM25 权重 0.3 过激 |
| 读时记忆去重 (cosine>0.92) | Judge -0.033 | 丢失重复 fact 的"投票"信号，single-hop 下降 |

## 待优化方向

- **Open-domain (57.3%)** 和 **Temporal (59.6%)** 是当前弱项
- 写时记忆去重（解决 93.4% 冗余率，每条仅增加 ~10ms）
- 换用 GPT-4o-mini 作为 Judge 进行公平对比
- 提升 extraction 质量（更精确的 fact/episode 提取）
