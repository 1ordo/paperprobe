.PHONY: up down build logs restart backend-logs celery-logs frontend-logs db-shell

up:
	docker compose up -d

up-build:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

restart:
	docker compose restart

backend-logs:
	docker compose logs -f backend

celery-logs:
	docker compose logs -f celery-worker

frontend-logs:
	docker compose logs -f frontend

db-shell:
	docker compose exec postgres psql -U cosmin -d cosmin_checker

backend-shell:
	docker compose exec backend bash

seed:
	docker compose exec backend python -c "from app.cosmin_data.seed import seed_cosmin_checklist; from sqlalchemy import create_engine; from sqlalchemy.orm import Session; e = create_engine('postgresql://cosmin:cosmin_secret@postgres:5432/cosmin_checker'); s = Session(e); seed_cosmin_checklist(s); s.close()"
