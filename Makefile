.PHONY: help run build dev clean docker-up docker-down docker-up-local docker-down-local docker-build setup up down

help: ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ============ 本地开发 ============

run: ## 直接运行服务（不构建前端）
	python -m src.server

build: ## 构建前端
	cd frontend && npm install && npm run build

dev: ## 构建前端并启动开发服务
	cd frontend && npm install && npm run build && cd ..
	python -m src.server

clean: ## 清理编译产物
	-find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
	-rm -rf frontend/build frontend/.svelte-kit frontend/node_modules
	-rm -rf src/static

setup: ## 初始化项目（创建配置 + 安装依赖）
	@test -f config/config.yml || cp config/config.yml.example config/config.yml
	@echo "请编辑 config/config.yml 修改密钥和数据库密码"
	@echo ""
	pip install -r requirements.txt
	cd frontend && npm install

# ============ Docker (生产模式 - 带 PostgreSQL) ============

docker-up: up ## 启动完整 Docker 环境
up: ## 启动完整 Docker 环境 (PostgreSQL + 服务)
	docker compose up -d --build

docker-down: down ## 停止完整 Docker 环境
down: ## 停止完整 Docker 环境
	docker compose down

# ============ Docker (本地模式 - 单镜像) ============

docker-up-local: ## 启动本地 Docker（单镜像，含 PostgreSQL）
	docker compose -f docker/docker-compose-local.yml up -d --build

docker-rebuild: ## 清理并重建本地 Docker 镜像
	powershell -ExecutionPolicy Bypass -File script/dockerrebuid.ps1

docker-down-local: ## 停止本地 Docker
	docker compose -f docker/docker-compose-local.yml down

docker-build: ## 只构建本地 Docker 镜像（不启动）
	docker compose -f docker/docker-compose-local.yml build

docker-logs: ## 查看本地 Docker 日志
	docker compose -f docker/docker-compose-local.yml logs -f

docker-shell: ## 进入本地 Docker 容器
	docker compose -f docker/docker-compose-local.yml exec git-mcp-server bash

# ============ 测试 ============

test: ## 运行全部测试
	.venv/Scripts/python test/run_all.py

test-config: ## 测试配置加载
	.venv/Scripts/python test/test_config.py

test-db: ## 测试数据库
	.venv/Scripts/python test/test_db.py

test-auth: ## 测试认证
	.venv/Scripts/python test/test_auth.py

test-git: ## 测试 Git 操作
	.venv/Scripts/python test/test_git_ops.py

test-api: ## 测试 API（需先启动服务）
	.venv/Scripts/python test/test_api.py
