#!/bin/bash
# OpenManus Web 部署脚本
# 用法: bash deploy/deploy.sh

set -e

echo "=== OpenManus Web 部署 ==="

# 0. 检查 Python
python3 --version

# 1. 安装依赖
echo "[1/5] 安装 Python 依赖..."
pip install -r requirements.txt

# 2. 拉取 Docker 镜像
echo "[2/5] 拉取 Sandbox 镜像..."
docker pull python:3.12-slim

# 3. 创建数据目录
echo "[3/5] 创建数据目录..."
sudo mkdir -p /data/openmanus
sudo chown -R $USER:$USER /data/openmanus

# 4. 检查 config.toml
echo "[4/5] 检查配置..."
if [ ! -f config/config.toml ]; then
    echo "⚠️  请先创建 config/config.toml 并填入 [web] 段配置（MySQL 真实凭据等）"
    exit 1
fi
grep -q "\[web\]" config/config.toml || {
    echo "⚠️  config.toml 中缺少 [web] 段，请参考 config/config.example.toml"
    exit 1
}
echo "配置 OK"

# 5. 安装 systemd 服务
echo "[5/5] 安装 systemd 服务..."
sudo cp deploy/openmanus-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable openmanus-web
sudo systemctl restart openmanus-web

echo ""
echo "=== 部署完成 ==="
echo "查看状态: sudo systemctl status openmanus-web"
echo "查看日志: sudo journalctl -u openmanus-web -f"
echo "访问地址: http://$(hostname -I | awk '{print $1}'):8080"
