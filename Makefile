.PHONY: dev api web install lint test test-unit test-integration test-web test-e2e widget-build clean

# Run both API and web dev servers concurrently
dev:
	@echo "Starting API and Web dev servers..."
	@make -j2 api web

# Run FastAPI dev server
api:
	cd apps/api && uv run uvicorn src.main:app --reload --port 8100

# Run Next.js dev server
web:
	cd apps/web && pnpm dev

# Install all dependencies
install:
	cd apps/api && uv sync
	cd apps/web && pnpm install
	cd packages/widget && pnpm install

# Run all linters
lint:
	cd apps/api && uv run ruff check .
	cd apps/web && pnpm lint

# Run all default tests (api unit + web). Integration and e2e are opt-in.
test: test-unit test-web

# API unit tests (no external deps required)
test-unit:
	cd apps/api && uv run pytest -m unit

# API integration tests against a real MongoDB.
# Requires MONGODB_TEST_URI in the environment.
test-integration:
	cd apps/api && uv run pytest -m integration

# Web unit tests (vitest)
test-web:
	cd apps/web && pnpm test

# Playwright e2e suite. Requires the local stack to be running
# (`docker compose up`) and E2E=1 in the environment.
test-e2e:
	cd e2e && pnpm install && E2E=1 pnpm test

# Build widget
widget-build:
	cd packages/widget && pnpm build

# Clean build artifacts
clean:
	rm -rf apps/api/.venv apps/api/build apps/api/dist
	rm -rf apps/web/.next apps/web/node_modules
	rm -rf packages/widget/dist packages/widget/node_modules
