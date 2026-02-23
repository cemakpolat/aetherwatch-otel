.PHONY: help build up down logs clean test validate docs

help:
	@echo "🔭 AetherWatch - Autonomous Drone Fleet Management"
	@echo ""
	@echo "Available commands:"
	@echo "  make build       - Build Docker images"
	@echo "  make up          - Start all services"
	@echo "  make down        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - Tail application logs"
	@echo "  make logs-all    - Tail all service logs"
	@echo "  make test        - Run basic tests"
	@echo "  make validate    - Validate configuration"
	@echo "  make clean       - Remove containers and volumes"
	@echo "  make status      - Show container status"
	@echo "  make urls        - Print service URLs"
	@echo ""

build:
	@echo "🔨 Building Docker images..."
	docker-compose build

up:
	@echo "🚀 Starting AetherWatch..."
	docker-compose up -d
	@sleep 10
	@echo ""
	@echo "✅ AetherWatch is starting up!"
	@echo ""
	@make urls

down:
	@echo "⛔ Stopping AetherWatch..."
	docker-compose down

restart:
	@echo "🔄 Restarting AetherWatch..."
	docker-compose restart

logs:
	@echo "📋 Tailing application logs..."
	docker-compose logs -f app

logs-all:
	@echo "📋 Tailing all service logs..."
	docker-compose logs -f

status:
	@echo "📊 Container Status:"
	@echo ""
	docker-compose ps

urls:
	@echo "🌐 Service URLs:"
	@echo ""
	@echo "  AetherWatch Dashboard:  http://localhost:5000"
	@echo "  Grafana:                http://localhost:3000 (admin/admin)"
	@echo "  Prometheus:             http://localhost:9090"
	@echo "  Jaeger UI:              http://localhost:16686"
	@echo ""

validate:
	@echo "✓ Validating configuration..."
	@docker-compose config > /dev/null && echo "✅ docker-compose.yml is valid" || echo "❌ Error in docker-compose.yml"
	@python3 -m py_compile app/app.py app/drone.py app/fleet_coordinator.py 2>/dev/null && echo "✅ Python files have valid syntax" || echo "❌ Syntax error in Python files"

test:
	@echo "🧪 Running basic tests..."
	@echo "  ✓ Checking container connectivity..."
	@docker-compose exec -T app curl -s http://localhost:5000/health > /dev/null && echo "✅ Application is healthy" || echo "⚠️  Application not ready yet"

clean:
	@echo "🧹 Cleaning up..."
	docker-compose down -v
	@echo "✅ Cleanup complete"

.DEFAULT_GOAL := help
