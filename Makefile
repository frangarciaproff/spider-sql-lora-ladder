.PHONY: install lint format typecheck test test-data check

install:
	uv sync --group dev

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy

test:
	uv run pytest

test-data:
	uv run --env-file .env pytest -m data -v

check: lint typecheck test
