.PHONY: help install test lint format docker-build docker-run docker-compose-up docker-compose-down clean

IMAGE_NAME ?= perplexity-search2api
IMAGE_TAG ?= latest
PORT ?= 8000

help: ## 显示帮助信息
	@echo "Perplexity Search2API 实用命令:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## 安装本地开发环境依赖
	pip install -e ".[dev]"

test: ## 运行所有单元测试
	pytest -v

lint: ## 检查代码规范
	ruff check .

format: ## 自动格式化代码
	ruff format .

docker-build: ## 构建本地 Docker 镜像
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .

docker-run: ## 启动本地 Docker 容器并映射端口
	docker run --rm -it \
		-p $(PORT):8000 \
		--env-file .env \
		-v $(PWD)/data:/app/data \
		--name $(IMAGE_NAME) \
		$(IMAGE_NAME):$(IMAGE_TAG)

docker-compose-up: ## 使用 Docker Compose 在后台启动服务
	docker compose up -d --build

docker-compose-down: ## 停止并清理 Docker Compose 容器
	docker compose down

clean: ## 清理临时缓存文件
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
