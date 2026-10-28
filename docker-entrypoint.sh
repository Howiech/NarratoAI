#!/bin/bash
set -e

# 函数：打印日志
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# 函数：安装运行时依赖
install_runtime_dependencies() {
    log "检查运行环境依赖..."
    
    # 如果构建阶段的虚拟环境 /opt/venv 已经包含核心依赖，直接跳过耗时的 pip 重装
    if python -c "import streamlit, yt_dlp, tencentcloud, requests" >/dev/null 2>&1; then
        log "虚拟环境依赖已就绪 (streamlit, yt-dlp, tencentcloud 等均已安装)，跳过重复安装"
        return 0
    fi

    local requirements_file="requirements.txt"
    local installed_packages_file="/tmp/installed_packages.txt"
    
    # 如果requirements.txt存在且比已安装包列表新，则重新安装
    if [ -f "$requirements_file" ]; then
        if [ ! -f "$installed_packages_file" ] || [ "$requirements_file" -nt "$installed_packages_file" ]; then
            log "发现新的依赖需求，开始安装..."
            pip install --user --no-cache-dir -r "$requirements_file" 2>&1 | while read line; do
                log "pip: $line"
            done
            export PATH="$HOME/.local/bin:$PATH"
            touch "$installed_packages_file"
            log "依赖安装完成"
        else
            log "依赖已是最新版本，跳过安装"
        fi
    else
        log "未找到 requirements.txt 文件"
    fi
}

# 函数：检查必要的文件和目录
check_requirements() {
    log "检查应用环境..."

    # 检查配置文件
    if [ ! -f "config.toml" ]; then
        if [ -f "config.example.toml" ]; then
            log "复制示例配置文件..."
            cp config.example.toml config.toml
        else
            log "警告: 未找到配置文件"
        fi
    fi

    # 检查必要的目录
    for dir in "storage/temp" "storage/tasks" "storage/json" "storage/narration_scripts" "storage/drama_analysis"; do
        if [ ! -d "$dir" ]; then
            log "创建目录: $dir"
            mkdir -p "$dir"
        fi
    done
    
    # 安装运行时依赖
    install_runtime_dependencies

    log "环境检查完成"
}

# 函数：启动 WebUI
start_webui() {
    log "启动 NarratoAI WebUI..."

    # 检查端口是否可用
    if command -v netstat >/dev/null 2>&1; then
        if netstat -tuln | grep -q ":8501 "; then
            log "警告: 端口 8501 已被占用"
        fi
    fi

    echo "============================================================"
    echo "  🚀 NarratoAI WebUI 正在啟動..."
    echo "  🌐 請在瀏覽器中打開以下地址訪問："
    echo "     👉 本地訪問地址: http://localhost:8501"
    echo "     👉 備用本地地址: http://127.0.0.1:8501"
    echo "============================================================"

    # 启动 Streamlit 应用
    exec streamlit run webui.py \
        --server.address=0.0.0.0 \
        --server.port=8501 \
        --server.enableCORS=true \
        --server.maxUploadSize=2048 \
        --server.enableXsrfProtection=false \
        --browser.gatherUsageStats=false \
        --browser.serverAddress=localhost \
        --logger.level=info
}

# 主逻辑
log "NarratoAI Docker 容器启动中..."

# 检查环境
check_requirements

# 根据参数执行不同的命令
case "$1" in
    "webui"|"")
        start_webui
        ;;
    "bash"|"sh")
        log "启动交互式 shell..."
        exec /bin/bash
        ;;
    "health")
        # 健康检查命令
        log "执行健康检查..."
        if curl -f http://localhost:8501/_stcore/health >/dev/null 2>&1; then
            log "健康检查通过"
            exit 0
        else
            log "健康检查失败"
            exit 1
        fi
        ;;
    *)
        log "执行自定义命令: $*"
        exec "$@"
        ;;
esac