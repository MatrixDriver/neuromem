# 接口设计

> 返回 [主架构文档](ARCHITECTURE.md)

---

## 目录

- [Python SDK 接口](#python-sdk-接口)
- [REST API 接口](#rest-api-接口)
- [CLI 接口](#cli-接口)

---

## Python SDK 接口 `[✅ 已实现]`

安装后使用：`uv pip install -e .` 或 `pip install -e .`

```python
from neuromemory import NeuroMemory

# 初始化
m = NeuroMemory()

# 添加记忆（返回 memory_id）
m.add("张三是李四的老板", user_id="test_user")

# 检索（返回 dict: memories, relations, metadata）
m.search("张三管理什么", user_id="test_user", limit=5)

# 问答（返回 answer 字符串）
m.ask("张三管理什么项目？", user_id="test_user")

# 获取知识图谱（返回 dict: status, nodes, edges, ...）
m.get_graph(user_id="test_user", depth=2)
```

接口定义（参考）：

```python
# 核心接口定义

class NeuroMemory:
    """神经符号混合记忆系统主接口"""

    def __init__(self, config: dict = None):
        """初始化记忆系统"""
        pass

    def add(
        self,
        content: str,
        user_id: str = "default",
        metadata: dict = None
    ) -> str:
        """
        添加记忆

        Args:
            content: 要记忆的文本内容
            user_id: 用户标识
            metadata: 可选元数据

        Returns:
            memory_id: 记忆唯一标识
        """
        pass

    def search(
        self,
        query: str,
        user_id: str = "default",
        limit: int = 10
    ) -> list[MemoryResult]:
        """
        混合检索记忆

        Args:
            query: 查询文本
            user_id: 用户标识
            limit: 返回结果数量上限

        Returns:
            检索结果列表，包含来源类型 (vector/graph)
        """
        pass

    def ask(
        self,
        question: str,
        user_id: str = "default"
    ) -> str:
        """
        基于记忆回答问题 (完整认知流程)

        Args:
            question: 用户问题
            user_id: 用户标识

        Returns:
            AI 生成的回答
        """
        pass

    def get_graph(
        self,
        user_id: str = "default",
        depth: int = 2
    ) -> dict:
        """
        获取用户的知识图谱

        Args:
            user_id: 用户标识
            depth: 遍历深度

        Returns:
            图谱数据 (nodes, edges)
        """
        pass
```

---

## REST API 接口 `[✅ 已实现]`

实现路径为 `/api/v1/*`，与根路径 `/process`、`/graph`、`/health` 等并存。详见 [REST API 文档](REST_API.md)。

```yaml
# OpenAPI 3.0 风格定义

POST /api/v1/memory  # 已实现
  description: 添加记忆
  request:
    body:
      content: string (required)
      user_id: string (default: "default")
      metadata: object
  response:
    memory_id: string

GET /api/v1/memory/search  # 已实现
  description: 混合检索
  parameters:
    query: string (required)
    user_id: string
    limit: integer (default: 10)
  response:
    results: array[MemoryResult]

POST /api/v1/ask  # 已实现
  description: 基于记忆回答问题
  request:
    body:
      question: string (required)
      user_id: string
  response:
    answer: string
    sources: array[MemoryResult]

GET /api/v1/graph  # 已实现
  description: 获取知识图谱
  parameters:
    user_id: string
    depth: integer (default: 2)
  response:
    nodes: array[Node]
    edges: array[Edge]

GET /api/v1/health  # 已实现
  description: 健康检查
  response:
    status: "healthy" | "unhealthy"
    components:
      neo4j: boolean
      qdrant: boolean
      llm: boolean
```

---

## CLI 接口 `[✅ 已实现]`

`uv pip install -e .` 或 `pip install -e .` 后使用 `neuromemory` 命令。

```bash
# 命令行示例

neuromemory status                                    # 检查 Neo4j、Qdrant、LLM 状态
neuromemory add "DeepMind 是 Google 的子公司" --user user_001
neuromemory search "Google 有哪些子公司" --user user_001 --limit 5
neuromemory ask "Demis 和 Gemini 有什么关系" --user user_001
neuromemory graph export --user user_001               # JSON 到 stdout
neuromemory graph export --user user_001 -o out.json  # 输出到文件
neuromemory graph visualize --user user_001 --open-browser
```

---

## 相关文档

- [数据模型](DATA_MODEL.md) - 了解数据结构
- [核心组件](COMPONENTS.md) - 了解内部实现
