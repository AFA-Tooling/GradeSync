FROM python:3.11-slim

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt requirements_db.txt ./

# 安装Python依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements_db.txt && \
    pip install --no-cache-dir fastapi uvicorn[standard] gunicorn

# 复制应用代码
COPY . .

# 创建日志目录
RUN mkdir -p /app/logs && chmod 777 /app/logs

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# 启动命令
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "/app/logs/access.log", \
     "--error-logfile", "/app/logs/error.log", \
     "--log-level", "info", \
     "api.app:app"]
