# MTEC Schedule Bot - Makefile

# Default target
help:
	@echo "MTEC Schedule Bot:"
	@echo "  install     - Установить зависимости"
	@echo "  run         - Запустить бота"
	@echo "  format      - Форматировать код"
	@echo "  lint        - Проверить код"
	@echo "  docker-build - Собрать Docker образ"
	@echo "  docker-run   - Запустить Docker контейнер"
	@echo "  docker-stop  - Остановить Docker контейнер"
	@echo "  docker-image - Создать и запустить Docker образ"
	@echo "  clean       - Очистить временные файлы"

# Development
install:
	pip install -r requirements.txt

run:
	python src/bot/main.py
format:
	black src/
	isort src/

lint:
	black --check src/
	isort --check-only src/

# Docker
docker-build:
	docker-compose build

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down

docker-image:
	docker build -t mtec-schedule-bot .
	docker run -d --name mtec-schedule-bot mtec-schedule-bot

# Utilities
clean:
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -exec rm -rf {} +
	find . -name "*.egg-info" -exec rm -rf {} +

# Aliases
deploy: docker-build docker-run
dev: install run
restart: docker-stop docker-run
