FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

ENV http_proxy=http://192.168.244.188:7897
ENV https_proxy=http://192.168.244.188:7897

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements_fastapi.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements_fastapi.txt

# 复制应用代码
COPY *.py ./

# 创建非 root 用户
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# 暴露端口
EXPOSE 8003

# 健康检查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8003/api/health || exit 1

# 启动命令
CMD ["uvicorn", "fastapi_service:app", "--host", "0.0.0.0", "--port", "8003"]