#!/bin/bash
# GradeSync 快速部署脚本（Ubuntu/Debian）

set -e

echo "🚀 GradeSync 部署脚本"
echo "===================="

# 检查是否为root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ 请使用sudo运行此脚本"
    exit 1
fi

# 1. 安装系统依赖
echo "📦 安装系统依赖..."
apt-get update
apt-get install -y python3 python3-pip python3-venv postgresql nginx git curl

# 2. 创建用户
echo "👤 创建gradesync用户..."
if ! id "gradesync" &>/dev/null; then
    useradd -m -s /bin/bash gradesync
    usermod -aG www-data gradesync
fi

# 3. 设置项目目录
PROJECT_DIR="/opt/GradeSync"
echo "📁 设置项目目录: $PROJECT_DIR"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "请先将代码放到 $PROJECT_DIR"
    echo "运行: sudo cp -r /path/to/GradeSync $PROJECT_DIR"
    exit 1
fi

cd $PROJECT_DIR
chown -R gradesync:gradesync $PROJECT_DIR

# 4. 设置Python环境
echo "🐍 配置Python环境..."
sudo -u gradesync python3 -m venv venv
sudo -u gradesync $PROJECT_DIR/venv/bin/pip install --upgrade pip
sudo -u gradesync $PROJECT_DIR/venv/bin/pip install -r requirements.txt
sudo -u gradesync $PROJECT_DIR/venv/bin/pip install -r requirements_db.txt
sudo -u gradesync $PROJECT_DIR/venv/bin/pip install fastapi uvicorn gunicorn

# 5. 配置数据库
echo "🗄️  配置PostgreSQL..."
sudo -u postgres psql << EOF
CREATE USER gradesync WITH PASSWORD 'changeme_in_production';
CREATE DATABASE gradesync OWNER gradesync;
GRANT ALL PRIVILEGES ON DATABASE gradesync TO gradesync;
\q
EOF

echo "⚠️  请修改数据库密码！"
echo "   sudo -u postgres psql -c \"ALTER USER gradesync WITH PASSWORD 'your_secure_password';\""

# 6. 配置环境变量
echo "⚙️  配置环境变量..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "❌ .env文件不存在！"
    echo "请创建 $PROJECT_DIR/.env 文件并填入凭证"
    exit 1
fi

chmod 600 $PROJECT_DIR/.env
chown gradesync:gradesync $PROJECT_DIR/.env

# 7. 创建日志目录
echo "📝 创建日志目录..."
mkdir -p /var/log/gradesync
chown gradesync:gradesync /var/log/gradesync

# 8. 配置systemd服务
echo "⚡ 配置systemd服务..."
cat > /etc/systemd/system/gradesync-api.service << 'EOFSVC'
[Unit]
Description=GradeSync API Service
After=network.target postgresql.service

[Service]
Type=simple
User=gradesync
Group=gradesync
WorkingDirectory=/opt/GradeSync/api
Environment="PATH=/opt/GradeSync/venv/bin"
EnvironmentFile=/opt/GradeSync/.env
ExecStart=/opt/GradeSync/venv/bin/gunicorn \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --access-logfile /var/log/gradesync/access.log \
    --error-logfile /var/log/gradesync/error.log \
    app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOFSVC

systemctl daemon-reload
systemctl enable gradesync-api

# 9. 配置Nginx
echo "🌐 配置Nginx..."
cp $PROJECT_DIR/deployment/nginx.conf /etc/nginx/sites-available/gradesync
ln -sf /etc/nginx/sites-available/gradesync /etc/nginx/sites-enabled/
nginx -t

# 10. 启动服务
echo "🚀 启动服务..."
systemctl start gradesync-api
systemctl reload nginx

# 11. 检查状态
echo ""
echo "✅ 部署完成！"
echo ""
echo "检查服务状态:"
echo "  sudo systemctl status gradesync-api"
echo ""
echo "查看日志:"
echo "  sudo journalctl -u gradesync-api -f"
echo ""
echo "测试API:"
echo "  curl http://localhost:8000/"
echo ""
echo "⚠️  重要后续步骤:"
echo "1. 修改数据库密码"
echo "2. 配置SSL证书 (certbot)"
echo "3. 更新 /etc/nginx/sites-available/gradesync 中的域名"
echo "4. 在 .env 中填入所有凭证"
echo "5. 配置 config.json"
echo ""
