#!/bin/bash
# Git MCP Server 启动脚本
set -e

echo "=== Git MCP Server ==="

# 检查配置文件
if [ ! -f config/config.yml ]; then
    echo "[+] 创建配置文件 config/config.yml"
    cp config/config.yml.example config/config.yml
    echo "[!] 请编辑 config/config.yml 修改密钥和数据库密码！"
fi

# 检查 Python 依赖
if ! python -c "import fastapi" 2>/dev/null; then
    echo "[+] 安装 Python 依赖..."
    pip install -r requirements.txt
fi

# 检查前端构建
if [ ! -d frontend/build ]; then
    echo "[+] 构建前端..."
    cd frontend && npm install && npm run build && cd ..
fi

echo "[+] 启动服务..."
python -m src.server
