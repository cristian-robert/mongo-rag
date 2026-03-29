.PHONY: dev api web install lint test widget-build clean

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

# Run all tests
test:
	cd apps/api && uv run pytest
	cd apps/web && pnpm test

# Build widget
widget-build:
	cd packages/widget && pnpm build

# Clean build artifacts
clean:
	rm -rf apps/api/.venv apps/api/build apps/api/dist
	rm -rf apps/web/.next apps/web/node_modules
	rm -rf packages/widget/dist packages/widget/node_modules
