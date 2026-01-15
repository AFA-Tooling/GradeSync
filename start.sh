#!/bin/bash
# GradeSync 快速启动脚本

set -e

echo "🚀 GradeSync 服务启动脚本"
echo "================================"
echo ""

# 检查是否在正确的目录
if [ ! -f "api/app.py" ]; then
    echo "❌ 错误：请在 GradeSync 根目录运行此脚本"
    exit 1
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚠️  警告：未找到 .env 文件"
    echo "   请创建 .env 并配置以下环境变量："
    echo "   - GRADESCOPE_EMAIL"
    echo "   - GRADESCOPE_PASSWORD"
    echo "   - PL_API_TOKEN"
    echo "   - ICLICKER_USERNAME"
    echo "   - ICLICKER_PASSWORD"
    echo "   - SERVICE_ACCOUNT_CREDENTIALS"
    echo "   - DATABASE_URL"
    echo ""
fi

# 检查数据库
echo "📦 检查数据库连接..."
python3 <<EOF
import os
from dotenv import load_dotenv
load_dotenv()

db_url = os.getenv('DATABASE_URL', 'postgresql://gradesync:changeme@localhost:5432/gradesync')
print(f"   数据库: {db_url}")
EOF

echo ""

# 启动 FastAPI
echo "🌐 启动 FastAPI 服务..."
echo "   访问 http://localhost:8000/docs 查看 API 文档"
echo ""
echo "按 Ctrl+C 停止服务"
echo "================================"
echo ""

# 使用 uvicorn 启动，支持自动重载
exec uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
