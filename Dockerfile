# NeuroMemory Dockerfile for ZeaBur Deployment
# 多阶段构建优化镜像大小
FROM python:3.13-slim as builder

WORKDIR /app

# 安装 uv（更快的依赖安装工具）
RUN pip install --no-cache-dir uv

# 复制依赖文件
COPY pyproject.toml uv.lock ./

# 安装依赖（不包含 dev 依赖，减小镜像体积）
RUN uv pip install --no-cache-dir -e .

# 运行阶段
FROM python:3.13-slim

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制 Python 环境
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制源代码
COPY neuromemory/ ./neuromemory/
COPY config.py private_brain.py session_manager.py coreference.py consolidator.py privacy_filter.py health_checks.py http_server.py mcp_server.py main.py ./

# 创建非 root 用户（安全最佳实践）
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# 暴露端口
EXPOSE 8765

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8765/health || exit 1

# 启动命令（使用多进程模式提高并发性能）
CMD ["uvicorn", "http_server:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "2"]
