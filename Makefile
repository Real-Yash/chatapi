SHELL := /bin/bash
BACKEND := backend
FRONTEND := frontend
PY := cd $(BACKEND) && uv run

.PHONY: help install install-backend install-frontend lock lint fmt typecheck typecheck-backend typecheck-frontend test test-cov check precommit-install

help:
	@echo "Targets:"
	@echo "  install             Install backend (uv) and frontend (npm) dependencies"
	@echo "  lock                Regenerate uv.lock and pinned requirements files"
	@echo "  lint                Run ruff on the backend"
	@echo "  fmt                 Auto-fix and format backend code with ruff"
	@echo "  typecheck           Run mypy (backend) and tsc (frontend)"
	@echo "  test                Run the backend pytest suite"
	@echo "  test-cov            Run tests with coverage"
	@echo "  check               lint + typecheck + test"
	@echo "  precommit-install   Install the git pre-commit hooks"

install: install-backend install-frontend

install-backend:
	cd $(BACKEND) && uv sync --extra dev

install-frontend:
	cd $(FRONTEND) && npm install

lock:
	cd $(BACKEND) && uv lock
	cd $(BACKEND) && uv export --format requirements-txt --no-dev --no-hashes --no-emit-project -o requirements.txt
	cd $(BACKEND) && uv export --format requirements-txt --extra dev --no-hashes --no-emit-project -o requirements-dev.txt

lint:
	$(PY) ruff check app tests seed_demo.py

fmt:
	$(PY) ruff check --fix app tests seed_demo.py
	$(PY) ruff format app tests seed_demo.py

typecheck: typecheck-backend typecheck-frontend

typecheck-backend:
	$(PY) mypy app

typecheck-frontend:
	cd $(FRONTEND) && npx --no-install tsc --noEmit

test:
	$(PY) pytest

test-cov:
	$(PY) pytest --cov=app

check: lint typecheck test

precommit-install:
	cd $(BACKEND) && uv run pre-commit install
