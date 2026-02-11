# 高层 API 未实现功能

> 来源：`docs/HIGH_LEVEL_API_DESIGN.md` 和 `docs/HIGH_LEVEL_API_EXAMPLES.md`
>
> 以下功能在设计文档中已规划但尚未实现。

---

## 1. URL 自动下载

```python
client.files.add_url(
    user_id="user123",
    url="https://example.com/article",
    category="reading",
    auto_extract=True,
    format="markdown"
)
```

**需要**：URL 抓取 → 正文提取 → 转 Markdown → 上传 OBS → 生成 embedding

---

## 2. 文件内容语义搜索

```python
results = client.files.search(
    user_id="user123",
    query="后端开发经验",
    file_types=["pdf", "md"]
)
```

**需要**：基于 embedding 的文件内容检索，支持按文件类型过滤

---

## 3. 用户画像

```python
profile = client.memory.get_user_profile(user_id="user123")
# => {
#   "preferences": {...},
#   "facts": {...},
#   "recent_episodes": [...],
#   "documents_count": 15,
#   "knowledge_graph": {...}
# }
```

**需要**：聚合 KV(preferences) + embedding(facts/episodes) + documents + graph 数据

---

## 4. 全局配置管理

```python
client.config.set(
    extraction_strategy="aggressive",
    llm_provider="claude",
    auto_extract=True,
    extract_trigger="message_count",
    extract_threshold=10,
)
```

**需要**：租户级别配置持久化（可复用 KV `_system` namespace）

---

## 5. 后台任务系统

```python
status = client.tasks.get_status(task_id="task_123")
tasks = client.tasks.list(user_id="user123", status="processing")
```

**需要**：异步任务队列（Celery 或内置），任务状态追踪，进度报告

---

## 6. 学习进度追踪（Echo Feature 5）

```python
client.progress.update(
    user_id="alice",
    skill_id="ai_programming",
    stage_id="stage_2",
    status="completed",
    metadata={"quality_score": 85}
)
progress = client.progress.get(user_id="alice", skill_id="ai_programming")
```

**需要**：`learning_progress` 表 + API + SDK

---

## 7. 配额管理（Phase 2）

- API 调用限流
- 租户存储配额
- 用量统计和报表

---

## 优先级建议

| 功能 | 优先级 | 依赖 |
|------|--------|------|
| 学习进度追踪 | 高 | Echo 需要 |
| 配额管理 | 高 | 生产部署需要 |
| 用户画像 | 中 | 聚合现有数据 |
| 文件语义搜索 | 中 | embedding 已有 |
| URL 自动下载 | 低 | 需要爬虫/解析 |
| 全局配置 | 低 | 可复用 KV |
| 后台任务系统 | 低 | 需要任务队列 |
