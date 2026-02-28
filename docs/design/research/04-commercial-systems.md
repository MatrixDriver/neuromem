# 商业级/开源 AI 记忆系统调研报告

> **调研日期**: 2026-02-28
> **调研范围**: Mem0、Zep AI (Graphiti)、Cognee、LangChain Memory、LlamaIndex Memory、Second Me、OpenMemory MCP
> **目的**: 对比商业系统的记忆分类和架构设计，审查 neuromem V2 设计方案

---

## 1. 各系统架构概览

### 1.1 Mem0

**定位**: 生产就绪的 AI Agent 通用记忆层（Y Combinator 投资）

**架构**: 向量 + 图 + KV 混合存储

- **基础版 (Mem0)**: 以向量数据库为核心，LLM 从对话中提取记忆事实，存储为自然语言文本 + embedding
- **图增强版 (Mem0^g)**: 在向量基础上叠加有向标签图 G=(V,E,L)，节点为实体（含类型、embedding、元数据），边为关系三元组 (source, relation, destination)

**记忆分类**: Mem0 采用**按时间/组织范围**分层，而非按心理学类型分类：

| 层级 | 名称 | 生命周期 | 示例 |
|------|------|----------|------|
| L1 | Conversation Memory | 单轮对话 | 当前 tool call 的中间状态 |
| L2 | Session Memory | 会话级 (分钟~小时) | 多步调试任务上下文 |
| L3 | User Memory | 长期 (周~永久) | 用户偏好、账户状态 |
| L4 | Organizational Memory | 全局共享 | 团队 FAQ、产品目录 |

同时引用了认知心理学分类（factual / episodic / semantic），但仅作为概念说明，实际 API 不区分。

**核心处理流水线**: 两阶段 Extraction + Update

1. **提取阶段**: 输入三要素 — 最新对话 (m_{t-1}, m_t)、滚动摘要 S、最近 m=10 条消息窗口。LLM 提取候选记忆集 {w1, w2, ..., wn}
2. **更新阶段**: 对每条提取的事实，检索向量库中最相似的 s=10 条记忆，LLM 决定执行四种操作之一：
   - **ADD**: 创建新记忆（无语义等价项时）
   - **UPDATE**: 补充/修改已有记忆（信息互补时）
   - **DELETE**: 删除被新信息否定的旧记忆
   - **NOOP**: 无需修改

**遗忘机制**: **无显式衰减**。通过 DELETE 操作在冲突时删除旧记忆，图版本中将冲突关系标记为 "invalid" 而非物理删除（保留历史推理能力）。检索时依赖相关性排序天然降低旧记忆的权重。

**性能**: 在 LOCOMO 基准上准确率 66.9%，相比 OpenAI Memory 提升 26%；p95 延迟降低 91%，token 成本节省 90%+。

---

### 1.2 Zep AI (Graphiti)

**定位**: 基于时态知识图谱的 Agent 记忆平台

**核心引擎**: Graphiti — 时态感知的动态知识图谱引擎

**三层子图架构** G = (N, E, phi):

| 层级 | 名称 | 功能 | 类比 |
|------|------|------|------|
| 第一层 | Episode Subgraph | 存储原始输入（消息、JSON、文本），作为无损数据仓库 | 类似人类情景记忆 |
| 第二层 | Semantic Entity Subgraph | 从 episode 中提取的实体和关系，经过实体解析和合并 | 类似人类语义记忆 |
| 第三层 | Community Subgraph | 强连接实体的聚类，包含高层摘要 | 类似概念层抽象 |

**双时间线模型 (Bi-Temporal)**:

- **Timeline T**: 事件实际发生的时间顺序（"Alan Turing 1912 年出生"）
- **Timeline T'**: Zep 系统摄入数据的事务顺序

每条边（事实）追踪四个时间戳：
- `t'_created` / `t'_expired` (系统时间线): 记录创建和失效
- `t_valid` / `t_invalid` (事件时间线): 事实成立的时间范围

**实体提取和解析流程**:

1. 当前消息 + 前 n=4 条上下文 -> LLM 实体识别
2. 实体名称 embedding 到 1024 维向量空间，余弦相似度搜索已有节点
3. 并行 BM25 全文搜索找候选
4. LLM 实体解析 prompt 判断是否为已有实体的别名/变体
5. 通过预定义 Cypher 查询（非 LLM 生成）写入 Neo4j

**边失效 (Edge Invalidation)**: Zep 的核心差异化能力

当新信息与已有边语义冲突时，LLM 比较新旧边，检测到时间重叠的矛盾后，将旧边的 `t_invalid` 设为新事实的 `t_valid`，**不物理删除**，保留完整历史。

**社区检测**: 使用 Label Propagation 算法（而非 Leiden），因其支持增量更新，延迟全量重建。

**检索**: 三阶段 f(a) = X(p(phi(a)))
1. **搜索 (phi)**: 余弦相似度 + BM25 + BFS（n-hop 图遍历）
2. **重排 (p)**: RRF / MMR / episode 提及频率 / 图距离 / cross-encoder
3. **构造 (X)**: 拼接节点和边信息，含事实有效期

**遗忘机制**: 边失效即"软遗忘"，旧事实保留但标记为过期。无显式时间衰减函数。

**性能**: DMR 基准准确率 94.8%（vs MemGPT 93.4%），延迟降低 90%。

---

### 1.3 Cognee

**定位**: AI Agent 的开源知识引擎（图 + 向量混合）

**架构**: Extract-Cognify-Load 流水线

1. **Ingestion**: 支持 30+ 数据源接入
2. **Cognify**: 内容分块 -> 实体和关系提取（三元组: subject-relation-object）-> 时间上下文标注 -> 写入图结构和 embedding
3. **Retrieval**: 时间过滤 + 图遍历 + 向量相似度混合检索

**记忆类型**: 借用认知心理学框架但不做严格分类：

- 显式（陈述性）: 情景记忆 + 语义记忆
- 隐式（程序性）: 技能和学习到的任务

Cognee 认为严格的短期/长期记忆分类对 AI 系统而言"过于简化"，主张用**多层网络视角**（关系、频率、上下文）替代刚性分类。

**后处理**: Memify Pipeline — 对知识图谱的持续优化（enrichment、optimization、persistence），无需全量重建。

**遗忘机制**: 无显式遗忘或衰减机制。

---

### 1.4 LangChain Memory

**定位**: LLM 应用开发框架中的对话记忆模块

**记忆类型** (按技术实现分类，非心理学分类):

| 类型 | 机制 | 适用场景 |
|------|------|----------|
| ConversationBufferMemory | 完整保留对话历史 | 短对话 |
| ConversationBufferWindowMemory | 滑动窗口保留最近 k 轮 | 中等长度对话 |
| ConversationSummaryMemory | LLM 生成摘要替代原文 | 长对话 |
| ConversationSummaryBufferMemory | 近期原文 + 远期摘要 | 混合需求 |
| ConversationEntityMemory | 跟踪对话中提及的实体及其属性 | 实体密集对话 |
| VectorStoreRetrieverMemory | 向量检索历史消息 | RAG 场景 |

**关键局限**:
- 本质上是**对话历史管理工具**，不是长期记忆系统
- 无记忆分类（fact/episodic/trait 等概念不存在）
- 无遗忘机制（BufferWindow 是物理截断，不是语义遗忘）
- 无人格建模或特质提取
- 已标记部分类为 deprecated，推荐迁移到 LangGraph 的 checkpoint 机制

---

### 1.5 LlamaIndex Memory

**定位**: 数据框架中的 Agent 记忆模块

**记忆组件**:

- **ChatMemoryBuffer**: FIFO 队列存储最近消息（已 deprecated）
- **ChatSummaryMemoryBuffer**: 近期原文 + 远期摘要
- **VectorMemory**: 向量检索历史消息，可与上述 Buffer 组合
- **Memory (新 API)**: 统一的短期 + 长期记忆接口

**关键局限**: 与 LangChain 类似，本质是对话上下文管理。无记忆分类体系，无遗忘机制，无人格建模。

---

### 1.6 Second Me

**定位**: 开源 AI 身份系统（数字分身），Apache 2.0 许可

**架构**: 三层分级记忆建模 (Hierarchical Memory Modeling, HMM)

| 层级 | 名称 | 内容 |
|------|------|------|
| L0 | Raw Data Layer | 非结构化原始数据（RAG/RALM） |
| L1 | Natural Language Memory | 结构化摘要：用户传记、关键句子、偏好标签 |
| L2 | AI-Native Memory | **神经网络参数化记忆**——不以自然语言描述，而是通过模型参数学习和组织 |

**人格建模**: Second Me 是调研中**唯一显式做人格建模**的系统
- 通过 SFT (Supervised Fine-Tuning) 训练用户个性化数据
- 通过 DPO (Direct Preference Optimization) 对齐用户偏好（约占 SFT 数据的 20%）
- 使用 GraphRAG 进行实体提取、关系映射和社区检测
- Me-alignment 架构：内循环（L0/L1/L2 集成）+ 外循环（协调外部 LLM 和互联网资源）

**差异化**: 不是记忆检索系统，而是**模型级人格化**——将用户身份"烧入"模型参数。

---

### 1.7 OpenMemory MCP

**定位**: Mem0 推出的开源 MCP 记忆服务器，本地优先

**架构**: Docker + PostgreSQL + Qdrant 向量库，完全本地运行
- 自动捕获编码偏好、模式和设置
- 与所有 MCP 兼容客户端互通（Claude、Cursor、VS Code 等）
- 跨工具上下文传递

**记忆分类**: 继承 Mem0 的扁平事实存储，无显式分类体系。

---

## 2. 关键维度对比

### 2.1 记忆分类方案对比

| 系统 | 分类维度 | 是否区分 fact/episodic | 是否有 trait 概念 | 是否有层级升级 |
|------|----------|----------------------|------------------|---------------|
| **neuromem V2** | 心理学类型 (fact/episodic/trait/insight/document) | 是 | **是 (三层子类)** | **是 (behavior->preference->core)** |
| **Mem0** | 时间/组织范围 (conversation/session/user/org) | 否 (扁平事实) | 否 | 否 |
| **Zep/Graphiti** | 三层子图 (episode/entity/community) | 部分 (episode vs entity) | 否 | 否 (但 community 是一种抽象) |
| **Cognee** | 心理学框架 (episodic/semantic/procedural) | 概念上区分 | 否 | 否 |
| **LangChain** | 技术实现 (buffer/summary/entity) | 否 | 否 | 否 |
| **LlamaIndex** | 技术实现 (buffer/vector/summary) | 否 | 否 | 否 |
| **Second Me** | 抽象层级 (raw/NL/AI-native) | 否 | **模型级人格化** | 否 (训练级) |

**关键发现**: neuromem V2 的 trait 三层子类设计在所有调研系统中**独一无二**。没有任何商业系统实现了从行为观测到人格特质的结构化升级链。

### 2.2 遗忘/衰减机制对比

| 系统 | 遗忘方式 | 衰减函数 | 矛盾处理 |
|------|----------|----------|----------|
| **neuromem V2** | 指数衰减 + 矛盾反思 + dissolved 归档 | `conf * exp(-lambda * days)` | LLM 专项反思 (修正/分裂/废弃) |
| **Mem0** | DELETE 操作（硬删除） | 无 | LLM 决定 UPDATE 或 DELETE |
| **Zep/Graphiti** | Edge invalidation（软失效） | 无 | 时间戳标记旧边为 invalid |
| **Cognee** | 无 | 无 | 未提及 |
| **LangChain** | 滑动窗口截断 | 无 | 不处理 |
| **LlamaIndex** | 滑动窗口截断 | 无 | 不处理 |
| **Second Me** | 模型参数自然遗忘 | 无显式机制 | 通过 DPO 隐式处理 |

**关键发现**: V2 的三重遗忘机制（时间衰减 + 矛盾反思 + dissolved 归档）是所有系统中最完善的。Zep 的 edge invalidation 最优雅但仅处理冲突，不处理时间衰减。Mem0 最粗暴（直接删除）。

### 2.3 存储架构对比

| 系统 | 向量 | 图 | KV | 全文 |
|------|------|----|----|------|
| neuromem | pgvector | graph_nodes/edges | key_values | BM25 |
| Mem0 | Qdrant/等 | Neo4j/等 (可选) | - | - |
| Zep/Graphiti | embedding (Neo4j) | Neo4j (核心) | - | BM25 |
| Cognee | LanceDB/等 | Neo4j/FalkorDB/NetworkX | - | - |

### 2.4 检索方法对比

| 系统 | 向量检索 | 全文检索 | 图遍历 | 重排 |
|------|----------|----------|--------|------|
| neuromem V2 | 余弦相似度 | BM25 | 图关系 | RRF |
| Mem0 | 余弦相似度 | - | 实体邻域探索 | 相似度排序 |
| Zep/Graphiti | 余弦相似度 | BM25 | BFS n-hop | RRF/MMR/cross-encoder |
| Cognee | 向量相似度 | - | 三元组搜索 | - |

---

## 3. 对 V2 设计的审查意见

### 3.1 V2 的独特优势（应坚持的设计）

**1. trait 三层子类是真正的创新**

在所有调研系统中，没有一个实现了从行为观测 (behavior) 到偏好倾向 (preference) 到核心人格 (core) 的结构化升级链。这是 neuromem 最具差异化的特性。

- Mem0 将所有信息扁平存储为"事实"，不区分层次
- Zep 有三层子图但按**数据抽象度**分层（原始/实体/社区），不是按**人格深度**分层
- Second Me 做人格建模但在模型参数级别，无法解释和追溯

V2 的 trait 设计同时具备**可解释性**（证据链可追溯）和**渐进性**（从表层到内核逐步积累），这是独一无二的。

**2. 置信度模型设计合理**

V2 的三因素置信度模型（强化/矛盾/时间衰减）比任何商业系统都更精细：
- Mem0 无置信度概念，事实要么存在要么删除
- Zep 有时间戳但无置信度连续值
- 没有系统实现了按子类差异化衰减率的设计

**3. 矛盾处理的"专项反思"是最佳实践**

V2 的矛盾处理（修正/分裂/废弃三选一）比 Mem0 的硬删除和 Zep 的直接失效都更合理。"情境化双面 trait" 的设计特别有价值——Zep 的 edge invalidation 只能判定新旧哪个对，无法表达"两个都对但在不同情境下"。

**4. reflection 引擎作为 trait 唯一来源**

V2 要求 trait 只能由 reflection 产生，不能从单次对话直接提取。这在所有系统中是最严谨的：
- Mem0 的提取是即时的、逐轮的
- Zep 的实体提取也是即时的
- 只有 Stanford Generative Agents 有类似的"反思"概念，但其反思产物不区分类型

### 3.2 值得借鉴的商业系统设计

**1. Zep 的双时间线模型 (Bi-Temporal)**

V2 的 trait 有 `first_observed` 和 `last_reinforced` 时间字段，但缺少 Zep 那样的**系统时间 vs 事件时间**区分。

建议：为 fact/episodic 增加类似的双时间线概念：
- `event_time`: 事件实际发生时间（"两周前开始新工作"）
- `ingest_time`: 系统记录时间

这在处理回忆性叙述时（用户说"去年我曾..."）非常关键。

**2. Zep 的 Community Subgraph 概念**

Zep 在实体子图之上构建社区子图，通过社区检测算法聚合强连接实体。V2 的 trait 升级链（behavior -> preference -> core）在概念上类似但限于个人特质维度。

建议：考虑在图存储层面引入类似 community 的聚合，将相关的 fact + trait 聚成"主题群"（如"职业"、"兴趣"、"社交"），为 recall 提供主题级检索入口。

**3. Mem0 的四操作模式 (ADD/UPDATE/DELETE/NOOP)**

Mem0 将记忆更新统一为四种原子操作，由 LLM 通过 function calling 接口决定。这个设计模式简洁且工程化程度高。

V2 的 fact 更新（supersede）和 trait 更新（置信度升降）可以借鉴此模式，统一为明确的操作类型枚举。

**4. Second Me 的 L2 AI-Native Memory 概念**

Second Me 的"参数化记忆"概念很前沿——将用户偏好编码进模型参数而非自然语言描述。虽然 V2 的近期实施不需要，但值得作为远期方向关注。

### 3.3 需要注意的风险和改进建议

**1. trait 升级阈值可能需要自适应**

V2 当前设定了固定阈值（>=3 条证据触发 behavior，>=2 条 behavior 触发 preference 等）。Mem0 和 Zep 都不做这种固定阈值判断，而是依赖 LLM 综合判断。

建议：保留阈值作为**必要条件**（防止过早升级），但在满足阈值后，由 LLM 判断证据的**质量和一致性**再决定是否真正升级。避免纯计数升级导致低质量 trait。

**2. 缺少对"沉默证据"的考虑**

V2 的 trait 升级依赖正向证据积累（观测到 N 次相同行为）。但在实际对话中，**用户没有展现某行为**也是信息（沉默证据）。

例如：用户在 10 次对话中**从未**讨论过社交活动 -> 这可能暗示内向特质，但当前设计无法捕获。

建议：在 reflection 引擎的 prompt 中明确要求考虑"用户长期未展现的行为模式"，作为 trait 推断的辅助信号。

**3. fact 的 supersede 机制需要保留历史**

V2 中 fact 的更新方式是"新事实覆盖旧版本 (supersede)"。参考 Zep 的 edge invalidation 设计，旧事实不应物理删除，而应保留为历史版本。

原因：
- Zep 的实践证明保留历史版本对时间推理很重要（"用户以前在 A 公司，现在在 B 公司"）
- 支持 trait 的证据回溯——如果某个 trait 基于已被 supersede 的 fact，需要知道原始事实是什么

建议：为 fact 增加 `valid_from` / `valid_until` 时间窗口（V2 的 embeddings 表已有这些字段），supersede 时设置旧记录的 `valid_until` 而非删除。

**4. 考虑组织级记忆 (Organizational Memory)**

Mem0 的四层分类中，"组织级记忆"是 V2 未覆盖的维度。在 neuromem-cloud 的多用户场景下，可能存在跨用户共享的记忆需求（如团队知识库、产品文档摘要）。

建议：在 V2 设计中预留 `scope` 字段（user / org / global），即使近期只实现 user 级别。

**5. 性能基准需要关注**

Mem0 论文提供了详细的延迟和 token 成本数据。V2 的 reflection 引擎是异步的（不影响在线延迟），但 trait 参与 recall 的权重加成计算应确保不增加检索延迟。

---

## 4. 总结

### 4.1 neuromem V2 在生态中的定位

```
抽象度（高→低）
    │
    │  Second Me ─── 模型参数级人格化（最抽象，不可解释）
    │
    │  neuromem V2 ── trait 三层子类 + 证据链（可解释的人格建模）  <-- 独特定位
    │
    │  Zep/Graphiti ─ 时态知识图谱（实体+关系+时间）
    │
    │  Mem0 ───────── 向量+图混合（扁平事实存储）
    │
    │  Cognee ──────── 知识图谱引擎（三元组提取）
    │
    │  LangChain/LlamaIndex ── 对话历史管理（最底层）
    │
    └──────────────────────────────────────────────────
```

neuromem V2 占据了一个独特的位置：它比 Mem0/Zep 更深（有人格建模），比 Second Me 更可解释（不依赖黑盒模型参数），比 LangChain 等更完整（有长期记忆和遗忘机制）。

### 4.2 核心建议

| 优先级 | 建议 | 理由 |
|--------|------|------|
| P0 | 坚持 trait 三层子类和 reflection 引擎设计 | 这是最核心的差异化，无商业系统有类似实现 |
| P0 | 坚持置信度模型和三重遗忘机制 | 比所有商业系统都更完善 |
| P1 | 为 fact 引入 Zep 风格的双时间线和软失效 | 利用已有 valid_from/valid_until 字段，增强时间推理 |
| P1 | trait 升级增加 LLM 质量判断（不仅数量） | 防止低质量证据堆积触发不合理升级 |
| P2 | reflection prompt 增加"沉默证据"考量 | 增强 trait 推断的全面性 |
| P2 | 预留组织级记忆的 scope 字段 | 为 cloud 多用户场景做准备 |
| P3 | 关注 Second Me 的参数化记忆方向 | 远期演进参考 |

### 4.3 一句话总结

**V2 的 trait 设计在商业生态中没有直接竞品，是 neuromem 最强的差异化优势。建议坚持核心设计不动摇，同时吸收 Zep 的时间模型和 Mem0 的工程模式来完善细节。**

---

## 参考资料

- Mem0 论文: "Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory" (arXiv:2504.19413, 2025)
- Zep 论文: "Zep: A Temporal Knowledge Graph Architecture for Agent Memory" (arXiv:2501.13956, 2025)
- Second Me 论文: "AI-Native Memory 2.0: Second Me" (arXiv:2503.08102, 2025)
- Mem0 文档: https://docs.mem0.ai/
- Zep/Graphiti: https://github.com/getzep/graphiti
- Cognee: https://github.com/topoteretes/cognee
- OpenMemory MCP: https://mem0.ai/openmemory
