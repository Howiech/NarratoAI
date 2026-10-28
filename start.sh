#!/bin/bash

# NarratoAI 快速啟動腳本（支援 Docker 與本地 uv 環境，啟動後自動顯示訪問地址）

set -e

export PATH="/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$HOME/.local/bin:$PATH"

cd "$(dirname "$0")"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PORT="${PORT:-8501}"

get_local_ip() {
    local ip
    ip=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
    if [ -z "$ip" ]; then
        ip="127.0.0.1"
    fi
    echo "$ip"
}

print_address_banner() {
    local local_ip
    local_ip=$(get_local_ip)
    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}  🚀 NarratoAI 已成功啟動！${NC}"
    echo -e ""
    echo -e "  🌐 請在瀏覽器打開以下地址："
    echo -e "     👉 本地訪問地址: ${CYAN}http://localhost:${PORT}${NC}"
    echo -e "     👉 備用本地地址: ${CYAN}http://127.0.0.1:${PORT}${NC}"
    echo -e "     👉 局域網訪問:   ${CYAN}http://${local_ip}:${PORT}${NC}"
    echo -e "${GREEN}============================================================${NC}"
    echo ""
}

# 確保 config.toml 存在且不是資料夾
if [ -d "config.toml" ]; then
    rm -rf config.toml
fi
if [ ! -f "config.toml" ] && [ -f "config.example.toml" ]; then
    echo -e "${YELLOW}[提示] 未檢測到 config.toml，已自動從 config.example.toml 複製生成。${NC}"
    cp config.example.toml config.toml
fi

MODE="${1:-auto}"

start_with_docker() {
    echo -e "${CYAN}[啟動] 正在透過 Docker Compose 啟動 NarratoAI...${NC}"
    if docker compose version &>/dev/null; then
        docker compose up -d
    else
        docker-compose up -d
    fi

    echo -e "${CYAN}[等待] 正在檢查服務就緒狀態...${NC}"
    local attempts=0
    while [ $attempts -lt 20 ]; do
        if curl -fs "http://localhost:${PORT}/_stcore/health" &>/dev/null; then
            break
        fi
        sleep 1
        ((attempts++))
    done

    print_address_banner
    echo -e "常用指令："
    echo -e "  查看即時日誌: ${YELLOW}docker compose logs -f${NC}"
    echo -e "  停止服務:     ${YELLOW}docker compose down${NC}"
    echo -e "  重啟服務:     ${YELLOW}docker compose restart${NC}"
}

start_with_local() {
    echo -e "${CYAN}[啟動] 正在透過本地 Python / uv 啟動 NarratoAI...${NC}"
    print_address_banner
    if command -v uv &>/dev/null; then
        exec uv run streamlit run webui.py \
            --server.port="${PORT}" \
            --server.maxUploadSize=2048 \
            --browser.serverAddress=localhost
    else
        exec streamlit run webui.py \
            --server.port="${PORT}" \
            --server.maxUploadSize=2048 \
            --browser.serverAddress=localhost
    fi
}

case "$MODE" in
    docker)
        start_with_docker
        ;;
    local)
        start_with_local
        ;;
    auto|*)
        if command -v docker &>/dev/null && docker info &>/dev/null; then
            start_with_docker
        else
            start_with_local
        fi
        ;;
esac
