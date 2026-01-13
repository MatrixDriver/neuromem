# 快速开始

> 返回 [主架构文档](ARCHITECTURE.md)

---

## 环境要求

| 依赖 | 版本要求 | 说明 |
|------|----------|------|
| Python | >= 3.10 | 推荐 3.11+ |
| Docker | >= 20.0 | 用于运行数据库服务 |
| Docker Compose | >= 2.0 | 容器编排 |
| 内存 | >= 8GB | Neo4j + Qdrant 需要 |

---

## 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/NeuroMemory.git
cd NeuroMemory

# 2. 创建虚拟环境
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Linux/macOS
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
# 创建 .env 文件，填入 API 密钥
echo "DEEPSEEK_API_KEY=your-key-here" > .env
echo "GOOGLE_API_KEY=your-key-here" >> .env

# 5. 启动数据库服务
docker-compose up -d

# 6. 验证服务状态
docker-compose ps
# 确保 memory_graph_db 和 memory_vector_db 状态为 running
```

---

## 服务访问

| 服务 | 地址 | 凭证 |
|------|------|------|
| Neo4j Browser | http://localhost:7474 | neo4j / password123 |
| Qdrant API | http://localhost:6333 | 无需认证 |
| Qdrant Dashboard | http://localhost:6333/dashboard | 无需认证 |

---

## 运行演示

```bash
# 运行多跳推理演示
python main.py
```

预期输出：

```
==================================================
NeuroMemory 多跳推理演示
当前配置: LLM=deepseek, Embedding=local
==================================================

--- 正在构建初始记忆 ---
[输入] DeepMind 是 Google 的子公司。
[海马体] 激活记忆:
  - [vector] ...
[前额叶] 生成回答:
...
[后台] 知识图谱已更新。

... (更多输出)

--- 测试推理能力 ---
[输入] Demis Hassabis 和 Gemini 模型有什么关系？
[海马体] 激活记忆:
  - [graph] Demis Hassabis 是 DeepMind 的 CEO
  - [graph] Gemini 是 DeepMind 团队研发的
  - ...
[前额叶] 生成回答:
Demis Hassabis 作为 DeepMind 的 CEO，领导了 Gemini 模型的研发...
```

---

## 基础使用 (当前方式)

```python
from mem0 import Memory
from config import MEM0_CONFIG
from main import cognitive_process, create_brain

# 初始化
brain = create_brain()

# 添加记忆
cognitive_process(brain, "张三是李四的老板", user_id="test_user")
cognitive_process(brain, "李四负责人工智能项目", user_id="test_user")

# 查询推理
answer = cognitive_process(brain, "张三管理什么项目？", user_id="test_user")
```

---

## 使用 SDK (开发中)

```python
# [🚧 开发中] 目标使用方式

from neuromemory import NeuroMemory

# 初始化
memory = NeuroMemory()

# 添加记忆
memory.add("张三是李四的老板", user_id="test_user")
memory.add("李四负责人工智能项目", user_id="test_user")

# 检索
results = memory.search("张三管理什么", user_id="test_user")

# 问答 (完整认知流程)
answer = memory.ask("张三管理什么项目？", user_id="test_user")
print(answer)
```

---

## 下一步

- [配置参考](CONFIGURATION.md) - 了解模型切换和数据库配置
- [接口设计](API.md) - 查看完整 API 文档
- [部署架构](DEPLOYMENT.md) - 了解部署选项
