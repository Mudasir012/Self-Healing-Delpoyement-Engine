.PHONY: dev test lint build up down logs clean

dev:
	docker-compose up -d postgres redis
	@sleep 3
	cd engine && uvicorn app.main:app --reload --port 8000

test:
	cd engine && python -m pytest tests/ -v

test-cov:
	cd engine && python -m pytest tests/ -v --cov=app --cov-report=term-missing

lint:
	cd engine && ruff check app/ tests/

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	rm -rf engine/__pycache__ engine/app/__pycache__ engine/tests/__pycache__
	rm -rf engine/app/actions/__pycache__ engine/alembic/__pycache__

migrate:
	cd engine && alembic upgrade head

migration:
	cd engine && alembic revision --autogenerate -m "$(message)"

k8s-deploy:
	kubectl create secret generic postgres-secret \
		--namespace self-healing \
		--from-literal=POSTGRES_USER=remediator \
		--from-literal=POSTGRES_PASSWORD=remediator \
		--from-literal=POSTGRES_DB=self_healing \
		--dry-run=client -o yaml | kubectl apply -f -
	kubectl apply -k infra/k8s/

k8s-delete:
	kubectl delete -k infra/k8s/
	kubectl delete secret postgres-secret -n self-healing --ignore-not-found
