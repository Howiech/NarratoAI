# NarratoAI Docker Makefile

.PHONY: help build up down restart logs shell clean deploy

# 默认目标
.DEFAULT_GOAL := help

# 变量定义
SERVICE_NAME := narratoai-webui

# 颜色定义
GREEN := \033[32m
YELLOW := \033[33m
BLUE := \033[34m
RESET := \033[0m

help: ## 显示帮助信息
	@echo "$(GREEN)NarratoAI Docker 管理命令$(RESET)"
	@echo ""
	@echo "$(YELLOW)可用命令:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(BLUE)%-15s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

deploy: ## 一键部署
	@echo "$(GREEN)执行一键部署...$(RESET)"
	./docker-deploy.sh

DOCKER_COMPOSE := $(shell if docker compose version >/dev/null 2>&1; then echo "docker compose"; else echo "docker-compose"; fi)
LOCAL_IP := $(shell ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $$1}' || echo "127.0.0.1")

build: ## 构建 Docker 镜像
	@echo "$(GREEN)构建 Docker 镜像...$(RESET)"
	$(DOCKER_COMPOSE) build

up: ## 启动服务
	@echo "$(GREEN)启动服务...$(RESET)"
	$(DOCKER_COMPOSE) up -d
	@echo ""
	@echo "$(GREEN)============================================================$(RESET)"
	@echo "$(GREEN)  🚀 NarratoAI 服務已啟動！$(RESET)"
	@echo "$(GREEN)  🌐 本地訪問地址: http://localhost:8501$(RESET)"
	@echo "$(GREEN)  🌐 備用本地地址: http://127.0.0.1:8501$(RESET)"
	@echo "$(GREEN)  🌐 局域網訪問:   http://$(LOCAL_IP):8501$(RESET)"
	@echo "$(GREEN)============================================================$(RESET)"

down: ## 停止服务
	@echo "$(YELLOW)停止服务...$(RESET)"
	$(DOCKER_COMPOSE) down

restart: ## 重启服务
	@echo "$(YELLOW)重启服务...$(RESET)"
	$(DOCKER_COMPOSE) restart
	@echo ""
	@echo "$(GREEN)============================================================$(RESET)"
	@echo "$(GREEN)  🚀 NarratoAI 服務已重啟！$(RESET)"
	@echo "$(GREEN)  🌐 本地訪問地址: http://localhost:8501$(RESET)"
	@echo "$(GREEN)  🌐 局域網訪問:   http://$(LOCAL_IP):8501$(RESET)"
	@echo "$(GREEN)============================================================$(RESET)"

logs: ## 查看日志
	docker-compose logs -f

shell: ## 进入容器
	docker-compose exec $(SERVICE_NAME) bash

ps: ## 查看服务状态
	docker-compose ps

clean: ## 清理未使用的资源
	@echo "$(YELLOW)清理未使用的资源...$(RESET)"
	docker system prune -f

config: ## 检查配置文件
	@if [ -f "config.toml" ]; then \
		echo "$(GREEN)config.toml 存在$(RESET)"; \
	else \
		echo "$(YELLOW)复制示例配置...$(RESET)"; \
		cp config.example.toml config.toml; \
	fi
