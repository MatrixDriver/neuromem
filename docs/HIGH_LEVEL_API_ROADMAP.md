# NeuroMemory 高层 API 实施路线图

## 🎯 目标

将 NeuroMemory 从"底层记忆 API"升级为"智能记忆管理平台"，让用户：
- 无需手动提取和分类记忆
- 只需提交对话，系统自动处理
- 获得跨类型的智能检索能力

---

## 📅 分阶段实施计划

### Phase 1: 会话存储 + 基础记忆提取 （4-6 周）

#### 1.1 会话存储 (1-2 周)

**后端实现：**
- [ ] 设计会话数据模型 (KV 存储)
  ```sql
  CREATE TABLE conversations (
      id UUID PRIMARY KEY,
      tenant_id UUID,
      user_id VARCHAR,
      session_id VARCHAR,
      role VARCHAR,  -- user/assistant/system
      content TEXT,
      metadata JSONB,
      created_at TIMESTAMP
  );

  CREATE INDEX idx_conversations_session ON conversations(tenant_id, user_id, session_id);
  ```

- [ ] 实现会话 API 端点
  - `POST /v1/conversations/messages` - 添加单条消息
  - `POST /v1/conversations/batch` - 批量添加
  - `GET /v1/conversations/sessions/{session_id}` - 获取会话历史
  - `GET /v1/conversations/sessions` - 列出所有会话

**Python SDK：**
- [x] `conversations.py` 模块（已创建示例）
- [ ] 集成到主 Client
- [ ] 单元测试

**预计工时：** 1-2 周

---

#### 1.2 LLM Classifier 集成 (2-3 周)

**核心功能：**
- [ ] LLM Classifier 服务
  ```python
  class MemoryClassifier:
      def classify_message(self, message: str) -> Dict:
          """分类单条消息，识别记忆类型"""
          prompt = f"""
          分析以下对话，提取记忆信息：

          消息: {message}

          请提取：
          1. 用户偏好（喜好、习惯）
          2. 事实信息（工作、技能、爱好）
          3. 情景记忆（事件、经历）

          以 JSON 格式返回。
          """
          # 调用 Claude/GPT
          return parse_llm_response(...)

      def batch_extract(self, session_id: str) -> ExtractionResult:
          """批量提取会话中的记忆"""
          messages = get_session_messages(session_id)
          # 分批处理，避免上下文过长
          ...
  ```

- [ ] 记忆提取任务队列
  - 使用 Celery 或类似工具
  - 支持异步和定时触发

- [ ] 提取策略配置
  - `realtime` - 实时提取（每条消息）
  - `batch` - 批量提取（每 N 条消息）
  - `scheduled` - 定时提取（每小时/每天）

**API 端点：**
- [ ] `POST /v1/conversations/auto-extract` - 配置自动提取
- [ ] `POST /v1/conversations/extract` - 手动触发提取
- [ ] `GET /v1/tasks/{task_id}` - 查询任务状态

**预计工时：** 2-3 周

---

#### 1.3 记忆分类存储 (1 周)

**存储映射：**
- [ ] 偏好 → `preferences` 表
- [ ] 事实 → `embeddings` 表（带 fact 标签）
- [ ] 情景 → `embeddings` 表（带 episodic 标签 + 时间戳）

**数据模型增强：**
```sql
ALTER TABLE embeddings
ADD COLUMN memory_type VARCHAR,  -- fact/episodic/semantic
ADD COLUMN extracted_from VARCHAR,  -- conversation/document/url
ADD COLUMN confidence FLOAT,  -- LLM 置信度
ADD COLUMN source_session_id VARCHAR;  -- 来源会话
```

**预计工时：** 1 周

---

### Phase 2: 文件系统 + URL 管理 （3-4 周）

#### 2.1 对象存储集成 (1-2 周)

**技术选型：**
- 华为云 OBS
- MinIO（开源替代）
- AWS S3 兼容

**实现：**
- [ ] OBS 客户端封装
- [ ] 文件上传/下载 API
- [ ] 文件元数据管理

```python
class OBSService:
    def upload_file(self, file_path: str, user_id: str) -> str:
        """上传文件到 OBS，返回 URL"""
        bucket = f"neuromemory-{tenant_id}"
        key = f"{user_id}/{uuid4()}/{filename}"
        # 上传到 OBS
        return obs_url

    def download_url(self, url: str) -> bytes:
        """下载 URL 内容"""
        # 支持 HTTP/HTTPS
        ...
```

**数据模型：**
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    tenant_id UUID,
    user_id VARCHAR,
    filename VARCHAR,
    file_type VARCHAR,  -- pdf/md/txt/html
    file_size BIGINT,
    obs_url TEXT,  -- OBS 存储位置
    original_url TEXT,  -- 如果来自 URL
    category VARCHAR,
    tags TEXT[],
    created_at TIMESTAMP
);

CREATE INDEX idx_documents_user ON documents(tenant_id, user_id);
```

**预计工时：** 1-2 周

---

#### 2.2 文本提取 + Embedding (1 周)

**文本提取：**
- [ ] PDF → pypdf2 / pdfplumber
- [ ] Word → python-docx
- [ ] HTML → BeautifulSoup / Readability

**Embedding 生成：**
- [ ] 分块策略（Chunk）
  - 固定长度（512 token）
  - 滑动窗口（overlap 50 token）
  - 语义分块（按段落）

- [ ] 批量生成 embedding
  ```python
  def process_document(doc_id: str):
      content = extract_text(doc_id)
      chunks = split_into_chunks(content, size=512)

      for chunk in chunks:
          embedding = generate_embedding(chunk)
          save_to_db(
              content=chunk,
              embedding=embedding,
              document_id=doc_id,
              memory_type="document"
          )
  ```

**API 端点：**
- [ ] `POST /v1/files/documents` - 上传文档
- [ ] `POST /v1/files/text` - 从文本创建
- [ ] `POST /v1/files/urls` - 添加 URL（自动下载）
- [ ] `GET /v1/files` - 列出文件
- [ ] `GET /v1/files/{file_id}/content` - 获取内容
- [ ] `POST /v1/files/search` - 搜索文件
- [ ] `DELETE /v1/files/{file_id}` - 删除文件

**预计工时：** 1 周

---

#### 2.3 URL 自动下载 (1 周)

**网页抓取：**
- [ ] 使用 Playwright / Selenium 渲染动态页面
- [ ] 提取正文（Readability.js）
- [ ] 转换为 Markdown

```python
class URLProcessor:
    def process_url(self, url: str, user_id: str, format: str = "markdown"):
        """处理 URL：下载、提取、存储"""
        # 1. 下载页面
        html = download_page(url)

        # 2. 提取正文
        article = extract_article(html)

        # 3. 转换格式
        if format == "markdown":
            content = html_to_markdown(article.html)
        elif format == "pdf":
            content = html_to_pdf(article.html)

        # 4. 上传到 OBS
        obs_url = upload_to_obs(content, user_id)

        # 5. 生成 embedding
        process_document(doc_id)

        return {
            "file_id": doc_id,
            "title": article.title,
            "url": obs_url
        }
```

**预计工时：** 1 周

---

### Phase 3: 高级检索 + 记忆画像 （2-3 周）

#### 3.1 跨类型统一检索 (1 周)

**实现：**
```python
class UnifiedSearch:
    def search(
        self,
        user_id: str,
        query: str,
        memory_types: List[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """跨类型检索"""
        results = []

        # 1. 偏好匹配（关键词）
        if not memory_types or "preference" in memory_types:
            prefs = search_preferences(user_id, query)
            results.extend(format_results(prefs, type="preference"))

        # 2. 向量检索（事实、情景、文档）
        if not memory_types or any(t in memory_types for t in ["fact", "episodic", "document"]):
            embedding = generate_embedding(query)
            vectors = vector_search(user_id, embedding, memory_types)
            results.extend(format_results(vectors, type="semantic"))

        # 3. 图查询（关系、规则）
        if not memory_types or "graph" in memory_types:
            graph_results = graph_search(user_id, query)
            results.extend(format_results(graph_results, type="graph"))

        # 4. 合并和排序
        return merge_and_rank(results, limit)
```

**API 端点：**
- [ ] `POST /v1/memory/search` - 统一检索
- [ ] `GET /v1/memory/preferences` - 获取所有偏好
- [ ] `GET /v1/memory/facts` - 获取事实
- [ ] `GET /v1/memory/episodes` - 获取情景记忆

**预计工时：** 1 周

---

#### 3.2 用户记忆画像 (1-2 周)

**画像生成：**
```python
class UserProfile:
    def generate_profile(self, user_id: str) -> Dict:
        """生成用户完整画像"""
        return {
            "basic_info": {
                "preferences_count": count_preferences(user_id),
                "facts_count": count_facts(user_id),
                "documents_count": count_documents(user_id),
            },
            "preferences": get_all_preferences(user_id),
            "top_facts": get_top_facts(user_id, limit=10),
            "recent_episodes": get_recent_episodes(user_id, days=7),
            "knowledge_graph": generate_knowledge_graph(user_id),
            "timeline": generate_timeline(user_id),
        }
```

**可视化：**
- [ ] 记忆时间轴
- [ ] 知识图谱可视化
- [ ] 偏好雷达图

**API 端点：**
- [ ] `GET /v1/memory/users/{user_id}/profile` - 用户画像
- [ ] `GET /v1/memory/timeline` - 记忆时间轴

**预计工时：** 1-2 周

---

### Phase 4: 优化和扩展 （2-3 周）

#### 4.1 性能优化

- [ ] 缓存层（Redis）
  - 缓存高频查询结果
  - 缓存 embedding 向量

- [ ] 批量操作优化
  - 批量生成 embedding
  - 批量插入数据库

- [ ] 异步任务优化
  - 优先级队列
  - 任务重试机制

**预计工时：** 1 周

---

#### 4.2 高级特性

- [ ] 记忆遗忘策略
  - 按时间衰减
  - 按访问频率
  - 手动归档

- [ ] 记忆冲突检测
  - 检测矛盾信息
  - 提示用户确认

- [ ] 多模态支持
  - 图片记忆（OCR + 图像 embedding）
  - 音频记忆（语音转文本）

**预计工时：** 1-2 周

---

## 🔧 技术栈

### 后端
- **Web 框架**: FastAPI (Python) 或 Spring Boot (Java)
- **任务队列**: Celery + Redis
- **对象存储**: 华为云 OBS / MinIO
- **LLM**: Claude API / OpenAI API
- **文本提取**: pypdf2, python-docx, BeautifulSoup
- **网页渲染**: Playwright

### 数据库
- **会话存储**: PostgreSQL (JSONB)
- **向量检索**: pgvector
- **文档元数据**: PostgreSQL
- **缓存**: Redis

---

## 📊 预估工时和人力

| 阶段 | 工作内容 | 预估工时 | 人力需求 |
|------|---------|---------|---------|
| Phase 1 | 会话存储 + 记忆提取 | 4-6 周 | 2 后端 + 1 LLM |
| Phase 2 | 文件系统 + URL | 3-4 周 | 2 后端 |
| Phase 3 | 高级检索 + 画像 | 2-3 周 | 2 后端 |
| Phase 4 | 优化和扩展 | 2-3 周 | 2 后端 + 1 前端 |
| **总计** | | **11-16 周** | **2-3 人** |

---

## 🎯 里程碑

### M1: MVP（6 周）
- ✅ 会话存储
- ✅ 基础 LLM 提取（偏好 + 事实）
- ✅ 统一检索 API
- ✅ Python SDK

### M2: 文件系统（9 周）
- ✅ 文档上传和管理
- ✅ URL 自动下载
- ✅ 全文检索

### M3: 完整版（12 周）
- ✅ 用户画像
- ✅ 记忆时间轴
- ✅ 性能优化

### M4: 高级特性（16 周）
- ✅ 多模态支持
- ✅ 记忆管理策略
- ✅ 可视化界面

---

## 🚀 快速启动（最小可行方案）

如果要快速验证，可以先实现核心功能：

**Week 1-2:**
- [ ] 会话存储（简化版，单表）
- [ ] 手动调用 LLM 提取（无队列）
- [ ] 存入 preferences 和 embeddings

**Week 3-4:**
- [ ] 统一检索 API
- [ ] Python SDK 集成
- [ ] 基础测试

这样 4 周就能出 Demo，验证产品方向！

---

## 📝 后续规划

### 企业级功能
- 记忆权限管理
- 多租户资源隔离
- 记忆审计日志
- 合规和隐私控制

### 开发者工具
- 记忆调试工具
- 性能分析仪表板
- 记忆质量评分

### 生态建设
- LangChain 插件
- AutoGPT 集成
- Semantic Kernel 适配器

---

**让我们开始构建下一代智能记忆管理平台！** 🚀
