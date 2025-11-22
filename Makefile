# Egypt Voter API - Production Makefile
# Use this Makefile to manage Docker deployment on production server

.PHONY: help build run stop restart logs status health clean shell deploy update

# Configuration
IMAGE_NAME := egypt-voter-api
CONTAINER_NAME := egypt-voter-api
PORT := 8000
SHM_SIZE := 4gb
MEMORY_LIMIT := 4g
CPU_LIMIT := 2

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
BLUE := \033[0;34m
NC := \033[0m # No Color

# Default target
help: ## Show this help message
	@echo -e "${BLUE}Egypt Voter API - Production Makefile${NC}"
	@echo ""
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  ${GREEN}%-15s${NC} %s\n", $$1, $$2}'

build: ## Build the Docker image
	@echo -e "${BLUE}Building Docker image: ${IMAGE_NAME}${NC}"
	docker build -t $(IMAGE_NAME) .
	@echo -e "${GREEN}✅ Build completed successfully${NC}"

run: ## Run the container in production mode
	@echo -e "${BLUE}Starting container: $(CONTAINER_NAME)${NC}"
	docker run -d \
		--name $(CONTAINER_NAME) \
		--restart unless-stopped \
		--network assembly-election_assembly-network \
		-p $(PORT):8000 \
		-e PYTHONUNBUFFERED=1 \
		-e DD_TRACE_ENABLED=false \
		--shm-size=$(SHM_SIZE) \
		--memory=$(MEMORY_LIMIT) \
		--cpus=$(CPU_LIMIT) \
		--security-opt no-new-privileges:true \
		--tmpfs /tmp \
		-v webdriver-cache:/app/.wdm \
		$(IMAGE_NAME)
	@echo -e "${GREEN}✅ Container started. Waiting for health check...${NC}"
	@sleep 10
	@make health

stop: ## Stop the running container
	@echo -e "${YELLOW}Stopping container: $(CONTAINER_NAME)${NC}"
	docker stop $(CONTAINER_NAME) || echo -e "${RED}Container not running${NC}"
	docker rm $(CONTAINER_NAME) || echo -e "${RED}Container not found${NC}"
	@echo -e "${GREEN}✅ Container stopped${NC}"

restart: ## Restart the container
	@echo -e "${BLUE}Restarting container: $(CONTAINER_NAME)${NC}"
	docker restart $(CONTAINER_NAME)
	@echo -e "${GREEN}✅ Container restarted${NC}"

logs: ## View container logs
	docker logs -f $(CONTAINER_NAME)

logs-tail: ## View last 50 lines of logs
	docker logs --tail 50 $(CONTAINER_NAME)

status: ## Check container status
	@echo -e "${BLUE}Container Status:${NC}"
	@docker ps -f name=$(CONTAINER_NAME) --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo -e "${BLUE}Container Resources:${NC}"
	@docker stats --no-stream $(CONTAINER_NAME) 2>/dev/null || echo -e "${RED}Container not running${NC}"

health: ## Test health endpoint
	@echo -e "${BLUE}Testing health endpoint...${NC}"
	@curl -s http://localhost:$(PORT)/health | python3 -m json.tool || echo -e "${RED}❌ Health check failed${NC}"

shell: ## Get a shell into the running container (for debugging)
	docker exec -it $(CONTAINER_NAME) /bin/bash

deploy: ## Build and deploy (stop old, build new, start)
	@echo -e "${BLUE}🚀 Starting deployment process...${NC}"
	@echo -e "${YELLOW}⚠️  This will stop the current container if running${NC}"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	@make stop || true
	@make build
	@make run
	@echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"

update: ## Pull latest code and redeploy (for git-based deployments)
	@echo -e "${BLUE}Updating and redeploying...${NC}"
	@echo -e "${YELLOW}⚠️  This will stop the current container${NC}"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	git pull origin main || echo -e "${YELLOW}No git repository found, skipping pull${NC}"
	@make deploy

clean: ## Remove stopped containers and unused images
	@echo -e "${YELLOW}🧹 Cleaning up Docker resources...${NC}"
	@echo -e "${RED}⚠️  This will remove stopped containers and unused images${NC}"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	docker container prune -f
	docker image prune -f
	docker volume prune -f
	@echo -e "${GREEN}✅ Cleanup completed${NC}"

clean-all: ## Remove ALL containers and images (dangerous!)
	@echo -e "${RED}💀 DANGER: This will remove ALL Docker containers and images!${NC}"
	@echo -e "${RED}⚠️  Make sure you have backups and understand the consequences${NC}"
	@read -p "Are you absolutely sure? Type 'YES' to confirm: " confirm && [ "$$confirm" = "YES" ] || exit 1
	docker stop $$(docker ps -aq) 2>/dev/null || true
	docker rm $$(docker ps -aq) 2>/dev/null || true
	docker rmi $$(docker images -q) 2>/dev/null || true
	@echo -e "${GREEN}✅ All Docker resources removed${NC}"

backup-logs: ## Backup container logs to a file
	@echo -e "${BLUE}Backing up logs...${NC}"
	@mkdir -p backups
	docker logs $(CONTAINER_NAME) > backups/logs-$(shell date +%Y%m%d-%H%M%S).txt 2>&1 || echo -e "${RED}❌ Failed to backup logs${NC}"
	@echo -e "${GREEN}✅ Logs backed up${NC}"

test-api: ## Test API endpoints
	@echo -e "${BLUE}Testing API endpoints...${NC}"
	@echo "Health check:"
	@make health
	@echo ""
	@echo "API info:"
	@curl -s http://localhost:$(PORT)/ | python3 -m json.tool || echo -e "${RED}❌ API info failed${NC}"

monitor: ## Monitor container resources in real-time
	@echo -e "${BLUE}Monitoring container resources (Ctrl+C to stop)...${NC}"
	docker stats $(CONTAINER_NAME)

# Development helpers
dev-build: ## Build with development settings (with volume mounts)
	@echo -e "${BLUE}Building development image...${NC}"
	docker build -t $(IMAGE_NAME)-dev -f Dockerfile.dev . 2>/dev/null || \
	docker build -t $(IMAGE_NAME)-dev .
	@echo -e "${GREEN}✅ Dev build completed${NC}"

dev-run: ## Run in development mode (with hot reload)
	@echo -e "${BLUE}Starting development container...${NC}"
	docker run -d \
		--name $(CONTAINER_NAME)-dev \
		-p $(PORT):8000 \
		-v $(PWD):/app \
		-e PYTHONUNBUFFERED=1 \
		-e DD_TRACE_ENABLED=false \
		--shm-size=$(SHM_SIZE) \
		$(IMAGE_NAME)-dev \
		uvicorn api:app --host 0.0.0.0 --port 8000 --reload
	@echo -e "${GREEN}✅ Dev container started on port $(PORT)${NC}"
