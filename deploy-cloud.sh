#!/bin/bash
# LLM-Wiki 一键部署脚本 (Ubuntu/Debian)
# 在服务器上运行: bash deploy-cloud.sh

set -e

echo "============================"
echo "  LLM-Wiki Cloud Deploy"
echo "============================"
echo ""

# 0. Version bump
VERSION_FILE="VERSION"
if [ -f "$VERSION_FILE" ]; then
    OLD_VER=$(cat "$VERSION_FILE" | tr -d '[:space:]')
    # Increment patch version (e.g. 0.10 -> 0.11)
    MAJOR=$(echo "$OLD_VER" | cut -d. -f1)
    MINOR=$(echo "$OLD_VER" | cut -d. -f2)
    NEW_VER="$MAJOR.$(($MINOR + 1))"
else
    OLD_VER="unknown"
    NEW_VER="0.10"
fi

echo "[0/5] Version: $OLD_VER -> $NEW_VER"
echo ""
echo "请输入本次部署说明（1-2句话，直接回车跳过）:"
read -r DEPLOY_DESC
if [ -z "$DEPLOY_DESC" ]; then
    DEPLOY_DESC="常规更新部署"
fi

# Update VERSION file
echo "$NEW_VER" > "$VERSION_FILE"

# Update DEPLOY_LOG.md
DEPLOY_DATE=$(date +%Y-%m-%d)
LOG_FILE="DEPLOY_LOG.md"
if [ ! -f "$LOG_FILE" ]; then
    cat > "$LOG_FILE" << 'LOGEOF'
# 维护日志

| 版本 | 日期 | 说明 |
|------|------|------|
LOGEOF
fi
# Insert new entry after the table header (line 5)
sed -i "4a\\| $NEW_VER | $DEPLOY_DATE | $DEPLOY_DESC |" "$LOG_FILE"
echo "  -> VERSION updated to $NEW_VER, DEPLOY_LOG.md updated"
echo ""

# 1. Install Python
if ! command -v python3 &> /dev/null; then
    echo "[1/5] Installing Python..."
    sudo apt update && sudo apt install -y python3 python3-venv python3-pip
else
    echo "[1/5] Python OK: $(python3 --version)"
fi

# 2. Create venv and install deps
echo "[2/5] Setting up virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[web]" --quiet

# 3. Check .env
if [ ! -f ".env" ]; then
    echo "[3/5] .env not found! Creating template..."
    cat > .env << 'ENVEOF'
# GLM API
ZAI_API_KEY=
ZAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
ZAI_MODEL_FLASH=glm-4-flash
ZAI_MODEL_PRO=gear-01

# DeepSeek API
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# Kimi API (optional)
KIMI_API_KEY=
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2.0711

# JWT Secret (change this!)
JWT_SECRET_KEY=change-me-to-random-string
ENVEOF
    echo "  -> Please edit .env and fill in your API keys"
    echo "  -> nano .env"
    exit 1
else
    echo "[3/5] .env OK"
fi

# 4. Install systemd service
echo "[4/5] Installing systemd service..."
CURRENT_DIR=$(pwd)
cat > /tmp/llmwiki.service << SRVEOF
[Unit]
Description=LLM-Wiki Knowledge Base v$NEW_VER
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/.venv/bin/python -m llmwiki web --host 0.0.0.0 --port 8765
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SRVEOF

sudo cp /tmp/llmwiki.service /etc/systemd/system/llmwiki.service
sudo systemctl daemon-reload
sudo systemctl enable llmwiki
sudo systemctl restart llmwiki

echo "[5/5] Done!"
echo ""
echo "============================"
echo "  v${NEW_VER} deployed!"
echo "============================"
echo ""
echo "  URL:  http://$(curl -s ifconfig.me):8765"
echo ""
echo "  Manage service:"
echo "    sudo systemctl status llmwiki"
echo "    sudo systemctl restart llmwiki"
echo "    sudo systemctl stop llmwiki"
echo "    journalctl -u llmwiki -f    # view logs"
echo ""
echo "  REMINDER: Open port 8765 in Tencent Cloud Security Group!"
