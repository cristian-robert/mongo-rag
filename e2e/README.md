# MongoRAG E2E

End-to-end Playwright harness covering the critical happy path:

1. Sign up a new tenant
2. Upload a document
3. Ask a question and receive an answer

## Run locally

```bash
# from repo root
docker compose up -d
cd e2e
pnpm install
pnpm install-browsers
E2E=1 pnpm test
```

Override targets via env vars:

| Variable           | Default                  | Purpose                          |
|--------------------|--------------------------|----------------------------------|
| `WEB_BASE_URL`     | `http://localhost:3100`  | Next.js dashboard URL            |
| `API_BASE_URL`     | `http://localhost:8100`  | FastAPI backend URL              |
| `TEST_USER_EMAIL`  | random `e2e+<ts>@…`      | Account email used for signup    |
| `TEST_USER_PASSWORD` | `supersecret-e2e-pw`   | Account password                 |
| `TEST_ORG_NAME`    | `E2E Org`                | Organisation name on signup form |

## CI

The `e2e` job in `.github/workflows/ci.yml` is skipped unless the workflow is
dispatched with `run_e2e=true` (or `E2E=1` is set in the environment). This
keeps the default PR pipeline fast and green even before the live stack is
provisioned in CI.
