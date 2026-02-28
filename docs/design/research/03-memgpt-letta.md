# 调研报告：MemGPT/Letta 及 OS-Inspired 记忆管理系统

> **调研日期**: 2026-02-28
> **调研范围**: MemGPT (UC Berkeley, 2023)、Letta 平台 (2024-2026)、A-MEM (NeurIPS 2025)、MemOS (MemTensor, 2025)
> **目标**: 评估 OS-inspired 记忆管理模式对 neuromem V2 设计的启发与改进方向

---

## 1. MemGPT 核心架构

### 1.1 OS 隐喻：虚拟内存分页

MemGPT（论文：*MemGPT: Towards LLMs as Operating Systems*, 2023）的核心创新是将操作系统的虚拟内存管理映射到 LLM 的上下文窗口管理：

| OS 概念 | MemGPT 对应 | 说明 |
|---------|------------|------|
| RAM（物理内存） | Main Context（上下文窗口） | LLM 当前可见的全部信息 |
| 虚拟内存/磁盘 | External Context（外部存储） | 上下文窗口外的持久化数据 |
| 页面调度 | Memory Paging | LLM 通过 function calling 在两层之间移动数据 |
| 页面置换算法 | Cognitive Triage | LLM 自主判断信息的保留价值 |

### 1.2 三层记忆结构

**Main Context（上下文内，始终可见）**:
- **Core Memory**: 固定大小的可编辑区域，存储关键信息。默认分为两个 block：
  - `Human` block：用户信息、偏好、事实
  - `Persona` block：agent 的自我概念、人格特征、行为准则
- **Conversation History**: FIFO 队列，存储对话历史（包含系统消息、用户消息、assistant 消息、function call 记录）

**External Context（上下文外，按需检索）**:
- **Recall Memory**: 完整对话历史的可搜索数据库，支持语义检索，即使不在当前上下文中也可召回
- **Archival Memory**: 长期存储，存放任意长度的文本对象，经过处理和索引

### 1.3 认知分诊（Cognitive Triage）

这是 MemGPT 最有价值的机制之一。当上下文占用率达到警告阈值（如 70%）时：

1. **内存压力信号**: 队列管理器向 LLM 发送 memory pressure 警告
2. **LLM 自主评估**: LLM 暂停当前推理，审视工作记忆内容
3. **分诊决策**: LLM 自主判断哪些内容最不关键，进行：
   - 摘要压缩（summarization）
   - 写入 archival storage（持久化）
   - 直接丢弃
4. **刷新阈值**: 当达到 100% 时，队列管理器强制刷新，驱逐消息并生成递归摘要

**关键原则**: 重要用户偏好、核心项目事实、关键个人详情获得更高保留优先级；临时对话元素和重复信息则是压缩或删除的候选。

### 1.4 语义化过程（Semantization）

MemGPT 观察到的一个重要现象：当信息跨多个上下文重复出现时，系统会逐渐将核心信息从特定语境中解耦。例如，用户多次提到偏好早晨开会，这一偏好从具体事件存储逐渐转变为一般性语义事实。

这与 V2 设计中 episodic → fact → trait 的流转路径有高度相似性。

---

## 2. Letta 平台演进（2024-2026）

### 2.1 从 MemGPT 到 Letta

MemGPT 从学术论文演进为 Letta 商业平台，核心变化：

| 阶段 | 时间 | 关键特性 |
|------|------|----------|
| MemGPT 论文 | 2023.10 | 虚拟内存分页概念验证 |
| Letta 平台化 | 2024 | 完整 agent 平台，server/client 架构 |
| 新 Agent 架构 | 2025.10 | 针对 frontier reasoning models 优化 |
| Conversations API | 2026.01 | 跨并行会话的共享记忆 |
| Context Repositories | 2026.02 | Git-based 记忆版本控制 |

### 2.2 Memory Blocks 机制

Letta 将 MemGPT 的 Core Memory 概念泛化为可配置的 Memory Blocks：

- **label**: 标识用途（如 "human"、"persona"、"knowledge"）
- **value**: block 内容的字符串表示
- **size limit**: 限制该 block 可占用的上下文窗口大小（字符或 token 数）
- **description**: 指导 LLM 如何使用该 block 的说明

Agent 通过 tool calling 读写这些 block，实现自编辑记忆。这种设计的优点是**高度可定制**——开发者可以根据应用场景定义任意数量和类型的 block。

### 2.3 Context Repositories（2026.02，最新）

Letta 最新推出的革命性特性，将 git 版本控制引入记忆管理：

- **MemFS**: agent 可通过 bash 工具像编辑文件一样编辑记忆
- **Git 版本控制**: 每次记忆变更自动生成带描述性 commit message 的版本
- **并行协作**: 多个 subagent 通过 git worktree 并发管理记忆，通过标准 git 操作处理分歧和冲突
- **遵循 Unix 哲学**: agent 可链式调用标准工具进行复杂记忆查询

### 2.4 AI Memory SDK 与 Learning SDK

Letta 将记忆能力拆分为两个独立 SDK：

**AI Memory SDK**（实验性）:
- 轻量级包装器，通过 "subconscious agent" 异步处理消息并更新 memory blocks
- 核心概念：Subjects（记忆主体）、Blocks（命名记忆区段）、Messages（输入）
- 适用于用户画像、对话摘要、领域知识库

**Learning SDK**（Drop-in）:
- 拦截 LLM API 调用，在 prompt 到达 LLM 前注入相关记忆上下文
- 支持 OpenAI、Anthropic、Gemini 等 API
- 实现持续学习而无需修改底层 agent 代码

---

## 3. A-MEM：基于 Zettelkasten 的自主记忆（NeurIPS 2025）

### 3.1 核心设计

A-MEM 从 Zettelkasten（卡片笔记法）汲取灵感，提出了一种 LLM agent 可以自主组织的记忆系统：

**记忆笔记结构**:
- 每条新记忆生成包含多种结构化属性的综合笔记
- 属性包括：上下文描述、关键词、标签
- 原子化笔记原则：每条记忆聚焦单一概念

**动态链接机制**:
- 系统分析历史记忆以识别相关连接
- 一条记忆可同时存在于多个 "box"（类别/分组）中
- 检索时，相关记忆的链接邻居也会被自动召回

### 3.2 自主演化

A-MEM 的独特之处在于记忆的**主动演化**：
- 新记忆的加入可触发已有记忆的上下文表示和属性更新
- 记忆网络持续自我优化理解
- LLM agent 自主决定何时创建、更新、链接、删除记忆

### 3.3 与 V2 的对比

| 维度 | A-MEM | neuromem V2 |
|------|-------|-------------|
| 记忆组织 | 网络图谱（Zettelkasten） | 分层分类（fact/episodic/trait/insight） |
| 演化方式 | 新记忆触发旧记忆更新 | reflection 引擎定期扫描归纳 |
| 链接机制 | 多对多的 box 分组 | trait 的 parent/child 层级引用 |
| 分类方式 | 标签 + 关键词（扁平） | 类型 + 子类（层级） |

---

## 4. MemOS：记忆操作系统（MemTensor, 2025）

### 4.1 三类记忆

MemOS 将记忆分为三种根本不同的表示形式：

| 类型 | 说明 | 对应 |
|------|------|------|
| **Parametric Memory** | 模型权重中编码的知识 | 预训练知识 |
| **Activation Memory** | 推理时的激活状态 | KV Cache、注意力模式 |
| **Plaintext Memory** | 文本形式的显式记忆 | 事实、偏好、文档 |

### 4.2 Memory Cube（MemCube）

三类记忆在 MemCube 中统一管理，支持：
- 跨类型调度和生命周期管理
- 记忆类型之间的转换路径（如 Plaintext → Parametric 通过微调）
- 异步调度器（MemScheduler）：毫秒级延迟，支持高并发

### 4.3 与 V2 的关联

MemOS 的视角更底层，关注记忆的**物理表示**（参数 vs 激活 vs 文本），而 V2 关注记忆的**语义分类**（事实 vs 情景 vs 特质）。两者是互补而非竞争关系。neuromem 目前仅处理 Plaintext Memory 层面，但 MemOS 的三层划分提醒我们：未来如果引入模型微调或 KV Cache 持久化，需要扩展记忆架构。

---

## 5. 关键发现总结

### 5.1 LLM 自主记忆管理是核心趋势

MemGPT/Letta、A-MEM 都将记忆管理权交给 LLM 自身，而非依赖预定义规则：

- **MemGPT**: LLM 通过 function calling 自主决定记忆的读写和迁移
- **A-MEM**: LLM 自主决定记忆的创建、链接、更新和删除
- **Letta 最新**: 甚至允许 LLM 用 bash 命令编辑记忆文件

**共同模式**: Tool-calling 驱动的记忆操作，LLM 既是记忆的消费者也是管理者。

### 5.2 记忆分层是共识，但分类维度不同

| 系统 | 分层维度 | 层级 |
|------|----------|------|
| MemGPT | 访问速度/位置 | Core（上下文内）→ Recall → Archival |
| V2 | 语义类型 + 抽象层级 | fact → episodic → trait(3层) → insight |
| A-MEM | 网络连接 | 扁平笔记 + 动态链接 |
| MemOS | 物理表示 | Parametric → Activation → Plaintext |

### 5.3 遗忘机制的不同实现

| 系统 | 遗忘方式 |
|------|----------|
| MemGPT | 内存压力触发主动淘汰 + 递归摘要 |
| V2 | 时间衰减 + 矛盾触发专项反思 + dissolved 归档 |
| A-MEM | LLM 自主删除（无显式衰减） |

### 5.4 Context Repositories 是前沿方向

Letta 的 git-based 记忆版本控制是一个值得关注的创新，特别是在多 agent 协作场景下的记忆一致性管理。

---

## 6. 对 V2 设计的审查意见

### 6.1 架构决策验证

**"工作记忆由应用层管理，SDK 只负责长期记忆"——这个决策是否合理？**

**结论：合理，但需要提供更好的接口支持。**

MemGPT 的经验表明：
- MemGPT 把工作记忆管理（Core Memory 的读写）和长期记忆管理（Archival/Recall 的存取）**紧密耦合**在同一个 agent loop 中
- 这种耦合带来了强大的自主性，但也意味着 MemGPT 是一个**完整的 agent 框架**而非可嵌入的 SDK
- Letta 后来拆分出 AI Memory SDK 和 Learning SDK，恰恰说明**解耦是更好的 SDK 设计**
- neuromem 作为 SDK 定位，将工作记忆交给应用层是正确的架构边界

**但需要改进**：V2 应提供明确的"工作记忆到长期记忆"的写入接口，让应用层（如 Me2）能在对话结束时或定期将工作记忆中的关键信息提交给 SDK 进行长期化处理。类似 Letta Learning SDK 的"拦截 → 提交"模式值得借鉴。

### 6.2 认知分诊机制的缺失

V2 的 reflection 引擎是**定期批处理**模式，缺少 MemGPT 的**实时分诊**能力：

- MemGPT: 每次对话交互都可能触发记忆读写决策
- V2: 记忆提取是被动的（LLM 提取 fact/episodic），reflection 是异步的

**建议**: 考虑在 LLM 提取阶段增加"重要性评分"（importance scoring），类似 Stanford Generative Agents 的做法。这不需要完全采用 MemGPT 的自主管理模式，但可以让提取层更智能地判断信息价值。

### 6.3 trait 机制的独特价值

在调研的所有系统中，**没有任何系统具备 V2 的 trait 三层子类（behavior → preference → core）及其渐进式升级机制**。

- MemGPT 的 Human block 存储偏好，但是扁平的文本，没有结构化的置信度和升级链
- A-MEM 的笔记可以相互链接，但没有从表层到深层的抽象层级
- Mem0（商业系统）有用户偏好提取，但没有 behavior → preference → core 的推断链

**这是 V2 设计的核心差异化优势**，应坚持并强化。

### 6.4 A-MEM 的启发：记忆间链接

V2 的 trait 有 parent/child 层级关系，但 fact 和 episodic 之间缺少显式链接。A-MEM 的 Zettelkasten 模式表明：

- 记忆之间的**横向关联**（而非仅纵向层级）有重要价值
- 例如：fact "在 Google 工作" 和 episodic "参加了 Python meetup" 之间可能存在有意义的关联
- 检索时，召回一条记忆同时带出其关联记忆，可以提供更丰富的上下文

**建议**: 在 metadata 中预留 `related_memories` 字段，允许 reflection 引擎或应用层建立 fact/episodic 之间的横向关联。不需要 A-MEM 那样复杂的动态链接，但基础的关联能力值得具备。

### 6.5 记忆版本控制

Letta 的 Context Repositories 提出了一个有趣的问题：记忆的修改历史是否有价值？

V2 目前使用 `valid_from / valid_until` 进行版本管理，fact 更新时旧版本标记失效。这已经是基本的版本控制。

**无需模仿 Letta 的 git 模式**（那是为多 agent 协作场景设计的），但 V2 的现有版本机制已经足够。

---

## 7. 具体改进建议

### 7.1 高优先级

**1. 增加"工作记忆提交"接口**

```python
# 新增 SDK 接口
async def commit_working_memory(
    user_id: str,
    session_context: str,  # 当前对话的关键上下文摘要
    flush: bool = False    # True 时对话结束的最终提交
) -> CommitResult:
    """
    应用层在对话过程中或结束时调用，
    将工作记忆中的关键信息提交给 SDK 进行长期化处理。
    SDK 对提交的内容执行标准的 fact/episodic 提取流程。
    """
```

这是 MemGPT "LLM 实时管理记忆"和 V2 "SDK 专注长期记忆"之间的**桥梁设计**。

**2. 提取阶段增加重要性预评分**

在 LLM 提取 fact/episodic 时，同时输出 importance score（1-10），指导后续 reflection 的优先级。MemGPT 和 Stanford Generative Agents 都证明了重要性评分对记忆质量的正面影响。

### 7.2 中优先级

**3. 记忆间横向关联**

在 metadata 中增加可选的 `related_memories: list[str]` 字段。reflection 引擎在扫描时，如果发现两条记忆语义高度相关但不构成 trait 升级关系，可以建立横向链接。recall 时可选择性地拉取关联记忆。

**4. 语义化检测**

借鉴 MemGPT 的 semantization 概念：当同一 fact 在 reflection 中被多次引用，考虑将其标记为"核心事实"（增加 `is_core_fact` 标记或提升 importance），类似 trait 的 established/core 阶段。

### 7.3 低优先级（远期）

**5. 记忆压力管理接口**

为应用层提供"记忆预算"概念：当某用户的活跃记忆数量超过阈值时，SDK 可以建议应用层触发 reflection 或返回精简的记忆集合。这是 MemGPT 内存压力机制的 SDK 化适配。

**6. 关注 MemOS 的多表示层**

当 neuromem 未来考虑引入 KV Cache 持久化或模型微调时，MemOS 的 Parametric/Activation/Plaintext 分类框架值得参考。

---

## 8. 结论

V2 的设计在以下方面处于业界领先位置：

1. **trait 三层子类 + 渐进式升级**: 独一无二的设计，无竞品具备
2. **矛盾处理 → 情境化双面 trait**: 心理学驱动的精细化处理
3. **SDK 定位的架构边界**: Letta 的演化路径（从框架到 SDK 拆分）验证了这个方向

需要补强的方面：

1. **实时性**: 缺少对话过程中的重要性判断，仅依赖事后 reflection
2. **互操作性**: 需要更好的"工作记忆 → 长期记忆"提交接口
3. **横向关联**: 记忆间只有纵向层级关系，缺少 fact-to-fact、episodic-to-episodic 的横向链接

总体评估：V2 设计的方向正确，核心机制（trait 体系）具有差异化优势。上述建议是锦上添花的增强，不需要改变整体架构。

---

## 参考资料

- Packer et al., "MemGPT: Towards LLMs as Operating Systems" (2023) — https://research.memgpt.ai/
- Letta Documentation — https://docs.letta.com/
- Letta Context Repositories Blog — https://www.letta.com/blog/context-repositories
- Letta Memory Blocks Blog — https://www.letta.com/blog/memory-blocks
- Letta AI Memory SDK — https://github.com/letta-ai/ai-memory-sdk
- Letta Learning SDK — https://github.com/letta-ai/learning-sdk
- Xu et al., "A-MEM: Agentic Memory for LLM Agents" (NeurIPS 2025) — https://arxiv.org/abs/2502.12110
- MemOS (MemTensor) — https://github.com/MemTensor/MemOS
- Letswalo, "MemGPT: Engineering Semantic Memory through Adaptive Retention and Context Summarization" (2025) — https://informationmatters.org/2025/10/memgpt-engineering-semantic-memory-through-adaptive-retention-and-context-summarization/
