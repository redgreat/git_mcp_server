FROM python:3.13-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY . .

# 构建参数：版本号（在 COPY 之后，确保 src 目录存在）
ARG APP_VERSION=v0.1.0
RUN echo "${APP_VERSION}" > /app/src/version.txt

# 创建存储目录
RUN mkdir -p /data/git_repos /app/logs

EXPOSE 3001

CMD ["python", "-m", "src.server"]
