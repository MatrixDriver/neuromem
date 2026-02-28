# 记忆分类与流转全景图

> 本文档为 `memory-classification-v2.md` 的可视化补充，便于快速理解记忆系统的完整流转过程。

---

## 1. 全景流转图

![记忆分类与流转全景图](memory-flow-diagram.svg)

<details>
<summary>Mermaid 源码</summary>

```mermaid
flowchart TB
    %% ============ 输入层 ============
    subgraph INPUT["<b>输入层</b> — 对话"]
        direction LR
        CONV["用户对话"]
        DOC["文件上传"]
    end

    subgraph EXTRACT["<b>提取层</b> — LLM 实时提取"]
        direction LR
        LLM["LLM 记忆提取<br/><i>分类 + 情感标注 + 实体抽取</i>"]
    end

    CONV --> LLM
    DOC --> DOC_MEM

    %% ============ 存储层 ============
    subgraph STORAGE["<b>存储层</b> — 4 种记忆类型"]
        direction TB

        subgraph DIRECT["直接产出"]
            direction LR
            FACT["<b>fact</b><br/>事实记忆<br/><i>离散·客观·可验证</i><br/>━━━━━━━━━━━━<br/>在 Google 工作<br/>养了猫叫 Mimi"]
            EPIS["<b>episodic</b><br/>情景记忆<br/><i>事件·时间·地点·人物</i><br/>━━━━━━━━━━━━<br/>2/15 参加 Python meetup<br/>昨天和老板谈了晋升"]
            DOC_MEM["<b>document</b><br/>文档记忆<br/><i>RAG 场景</i>"]
        end

        subgraph TRAIT_BOX["<b>trait</b> — 特质记忆（仅由 reflection 产生）"]
            direction TB

            subgraph LIFECYCLE["生命周期阶段"]
                direction LR
                TREND["<b>trend</b><br/><i>近期趋势</i><br/>valid_window 管理<br/>不参与 recall"]
                CAND["<b>candidate</b><br/><i>初步模式</i><br/>conf &lt; 0.3<br/>不参与 recall"]
                EMER["<b>emerging</b><br/><i>渐成模式</i><br/>conf 0.3~0.6<br/>低权重 recall"]
                ESTAB["<b>established</b><br/><i>可信特质</i><br/>conf 0.6~0.85<br/>正常 recall"]
                CORE_S["<b>core</b><br/><i>核心特质</i><br/>conf &gt; 0.85<br/>高权重 recall"]

                TREND -->|"窗口内≥2次强化"| CAND
                CAND -->|"证据累积"| EMER
                EMER -->|"持续强化"| ESTAB
                ESTAB -->|"高度稳定"| CORE_S
            end

            subgraph SUBTYPES["子类层级（可升级）"]
                direction LR
                BEH["<b>behavior</b><br/><i>可观测行为模式</i><br/>深夜活跃<br/>决策前查数据"]
                PREF["<b>preference</b><br/><i>偏好倾向</i><br/>数据驱动决策<br/>喜欢极简设计"]
                CORE_T["<b>core</b><br/><i>核心人格/价值观</i><br/>高尽责性<br/>重视自由"]

                BEH -->|"≥2 behavior<br/>同一倾向"| PREF
                PREF -->|"≥2 preference<br/>同一维度"| CORE_T
            end
        end
    end

    LLM --> FACT
    LLM --> EPIS

    %% ============ 反思引擎 ============
    subgraph REFLECT["<b>Reflection 引擎</b> — 异步批处理"]
        direction TB
        TRIGGER["触发条件<br/>━━━━━━━━━━━━<br/>① 重要度累积 ≥ 30<br/>② 距上次 ≥ 24h<br/>③ 会话结束"]
        SCAN["扫描新增 fact / episodic"]
        DETECT_TREND["检测短期趋势<br/>→ 生成 trend trait"]
        DETECT_PATTERN["检测行为模式<br/>→ 生成/强化 behavior"]
        UPGRADE["检测聚类<br/>→ 升级 behavior→pref→core"]
        CONTRADICT["矛盾检测<br/>→ 专项反思"]
        DECAY["时间衰减<br/>→ 降级 / dissolved"]

        TRIGGER --> SCAN
        SCAN --> DETECT_TREND
        DETECT_TREND --> DETECT_PATTERN
        DETECT_PATTERN --> UPGRADE
        UPGRADE --> CONTRADICT
        CONTRADICT --> DECAY
    end

    FACT -.->|"被扫描"| SCAN
    EPIS -.->|"被扫描"| SCAN
    DETECT_TREND -.->|"产出"| TREND
    DETECT_PATTERN -.->|"产出"| BEH
    UPGRADE -.->|"升级"| PREF
    UPGRADE -.->|"升级"| CORE_T

    %% ============ 终态 ============
    DISSOLVED["<b>dissolved</b><br/>归档·不参与 recall"]

    TREND -->|"窗口过期<br/>无强化"| DISSOLVED
    CAND -->|"矛盾/衰减"| DISSOLVED
    EMER -->|"矛盾/衰减"| DISSOLVED
    ESTAB -->|"矛盾/衰减"| DISSOLVED
    CORE_S -->|"矛盾/衰减"| DISSOLVED

    CONTRADICT -.->|"废弃"| DISSOLVED

    %% ============ 样式 ============
    classDef input fill:#E3F2FD,stroke:#1565C0,color:#000
    classDef extract fill:#FFF3E0,stroke:#E65100,color:#000
    classDef fact fill:#E8F5E9,stroke:#2E7D32,color:#000
    classDef episodic fill:#F3E5F5,stroke:#6A1B9A,color:#000
    classDef doc fill:#ECEFF1,stroke:#546E7A,color:#000
    classDef trait fill:#FFF8E1,stroke:#F57F17,color:#000
    classDef trend fill:#FFF8E1,stroke:#F57F17,color:#000,stroke-dasharray: 5 5
    classDef reflect fill:#FCE4EC,stroke:#C62828,color:#000
    classDef dissolved fill:#F5F5F5,stroke:#9E9E9E,color:#666

    class CONV,DOC input
    class LLM extract
    class FACT fact
    class EPIS episodic
    class DOC_MEM doc
    class BEH,PREF,CORE_T,CAND,EMER,ESTAB,CORE_S trait
    class TREND trend
    class TRIGGER,SCAN,DETECT_TREND,DETECT_PATTERN,UPGRADE,CONTRADICT,DECAY reflect
    class DISSOLVED dissolved
```

</details>

---

## 2. 置信度与证据质量速查

```
证据质量分级                          置信度阶段
━━━━━━━━━━━━━━━━━━━━━              ━━━━━━━━━━━━━━━━━━━━━
A 级 (0.25) 跨情境一致                trend    [valid_window]  ── 不参与 recall
B 级 (0.20) 显式陈述                  candidate [< 0.3]       ── 不参与 recall
C 级 (0.15) 跨对话行为                emerging  [0.3 ~ 0.6]   ── 低权重
D 级 (0.05) 同对话/隐式               established [0.6 ~ 0.85] ── 正常
                                      core      [> 0.85]      ── 高权重优先

衰减公式（间隔效应）
━━━━━━━━━━━━━━━━━━━━━
effective_λ = base_λ / (1 + 0.1 × reinforcement_count)

base_λ:  behavior=0.005  preference=0.002  core=0.001
```

## 3. 矛盾处理流程

```
新证据与已有 trait 矛盾
         │
    矛盾比 > 0.3 ?
    ╱            ╲
  否              是
  │               │
置信度微降     触发专项 reflection
  │               │
  │          ┌────┼────┐
  │          │    │    │
  │        修正  分裂  废弃
  │          │    │    │
  │       更新   情境化  dissolved
  │      content 双面trait
  │          │    │
  └──────────┴────┘
```

## 4. 子类升级条件速查

```
fact/episodic ──────────────────────► behavior (trait)
  条件: ≥3 条呈现相同模式              初始 confidence = 0.4
  短期趋势: → trend (valid_window)
  有积累:   → candidate (conf=0.3)

behavior ──────────────────────────► preference
  条件: ≥2 behavior 同一倾向
        各自 confidence ≥ 0.5

preference ────────────────────────► core
  条件: ≥2 preference 同一人格维度
        各自 confidence ≥ 0.6

trend ─────────────────────────────► candidate
  条件: valid_window 内 ≥2 次强化

trend (过期) ──────────────────────► dissolved
  条件: valid_window 结束, 无强化
```

## 5. 情境标签体系

```
                    ┌─── work      (工作/专业)
                    ├─── personal  (私人/生活)
context 标签 ───────├─── social    (社交)
(behavior 层即附带) ├─── learning  (学习/成长)
                    ├─── general   (跨情境通用 — 升级加成最大)
                    └─── contextual(情境化双面 — 用 contexts 字段)
```
