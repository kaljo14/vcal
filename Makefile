.PHONY: up down test backend-test frontend-test build
up:
	docker compose up --build -d --wait --wait-timeout 300
down:
	docker compose down
backend-test:
	cd backend && pytest -q
frontend-test:
	cd frontend && npm test && npm run build
test: backend-test frontend-test
build:
	docker compose build
