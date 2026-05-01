# Next Steps — After Issue #79

Practical guide for what shipped, what you need to register before going to prod, and how to run everything locally.

---

## 1. What Changed (in one minute)

Issue #79 fixed a **silent ingestion-pipeline bug** and shipped the **production deploy story**. Before #79, the API and Celery worker shared a `/tmp` filesystem assumption — when they ran in different containers, the worker couldn't read the file the API wrote, ingestion silently fell back to a placeholder string `[Error: Could not read file …]`, and that string got chunked, embedded, and stored as RAG content. Documents looked successful with `chunk_count=1` while polluting search results.

### What replaced it

| Concern | Before | After |
|---|---|---|
| API ↔ Worker file handoff | Filesystem path passed via Celery (broken when not co-hosted) | **Blob URI** passed via Celery; both ends speak `BlobStore.put` / `BlobStore.open` |
| Local dev blob backend | n/a | `BLOB_STORE=fs` → `file://` URIs under `./.tmp/uploads/` (no cloud needed) |
| Prod blob backend | n/a | `BLOB_STORE=supabase` → `supabase://<bucket>/<key>` via S3-compatible API, 24h auto-expire lifecycle |
| Read-error handling | Silent string fallback | Raises loudly; Celery autoretries on `BlobAccessError` |
| Tenant isolation on blobs | n/a | Every URI checked via `assert_tenant_owns_uri(uri, principal.tenant_id)` (percent-decoded, no `..`/`%`/`/`/`\x00` in tenant segment) |
| Upload size cap | Only checked when client set Content-Length | Stream-counted during upload; aborts + cleans up partial blob on overflow → 413 |
| Deploy target | Not defined | **Vercel** (web) + **Fly Machines** (api + worker, single Dockerfile, `PROCESS_TYPE` switch) + **Upstash Redis** (broker) + **Supabase Storage** (blobs) |

### Files added (high-level)

- `apps/api/src/services/blobstore/` — Protocol + 2 impls (`filesystem.py`, `supabase.py`) + URI parser + factory
- `apps/api/Dockerfile` (single image), `apps/api/scripts/entrypoint.sh` (`PROCESS_TYPE` switch), `apps/api/fly.api.toml`, `apps/api/fly.worker.toml`
- `scripts/fly-secrets.sh` — push `apps/api/.env` to both Fly apps
- `scripts/setup_supabase_storage.py` — provision the Supabase bucket + lifecycle (exits **2** if lifecycle fails — bucket is usable but you must set the 1-day expiry manually in the dashboard before going live)
- `docs/deploy.md` — full prod runbook

22 reviewer findings closed across 5 review waves (2 Crit + 4 High + 5 Med + 4 Low + 7 Copilot + 4 residual). 30+ new tests. PR #83, merge commit `b39e657`.

---

## 2. Accounts You Need to Register for Production

You can already run the app locally with **only MongoDB Atlas + an LLM key**. Everything else is for prod.

### Already required (assume you have these)

| Service | Why | Where to sign up |
|---|---|---|
| **MongoDB Atlas** | RAG content (`documents`, `chunks`, `conversations`, `bots`). Vector + Atlas Search indexes. | [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas) — free M0 cluster works for MVP |
| **OpenAI** *(or OpenRouter)* | LLM completions + `text-embedding-3-small` embeddings | [platform.openai.com](https://platform.openai.com) or [openrouter.ai](https://openrouter.ai) |
| **Supabase** | Postgres (identity, billing, api_keys), Auth (dashboard login), Storage (blobs in prod) | [supabase.com](https://supabase.com) — free tier OK for MVP. Project ref: `vmuybfmxermgwhmhevou` (already provisioned) |

### New for prod after #79

| Service | Why | Where to sign up | Env vars it produces |
|---|---|---|---|
| **Fly.io** | Hosts the FastAPI API process (always-on) + Celery worker process (autostop when idle) | [fly.io/app/sign-up](https://fly.io/app/sign-up) — install the CLI: `brew install flyctl` then `fly auth login` | None directly; deploy via `fly deploy -c apps/api/fly.api.toml` and `fly deploy -c apps/api/fly.worker.toml` |
| **Upstash Redis** | Celery broker + result backend (TLS-only, `rediss://`) | [upstash.com](https://upstash.com) → create a Redis database, **enable TLS** | `REDIS_URL=rediss://default:<token>@<host>:6379` |
| **Supabase Storage S3 credentials** | Blob backend in prod. Distinct from your `SUPABASE_SECRET_KEY` (service-role JWT) — must be minted separately. | Supabase dashboard → your project → **Project Settings → Storage → S3 Connection** → "New access key" | `SUPABASE_S3_ACCESS_KEY`, `SUPABASE_S3_SECRET_KEY`, plus you choose a bucket name (default `mongorag-uploads`) for `SUPABASE_STORAGE_BUCKET` |
| **Vercel** | Hosts the Next.js web dashboard (`apps/web`). Native preview + production deploys. | [vercel.com/signup](https://vercel.com/signup) — install the CLI: `npm i -g vercel` then `vercel login` | None directly; project settings store `NEXT_PUBLIC_API_URL=https://mongorag-api.fly.dev` etc. |

### Already wired but optional in prod

| Service | Why | Action |
|---|---|---|
| **Stripe** | Billing / subscriptions / webhooks | If you're not selling yet, leave the test keys (`sk_test_…`) in place. The webhook handler runs but no events arrive. |
| **Resend** | Password-reset / invitation emails | `RESEND_API_KEY=re_...` — sign up at [resend.com](https://resend.com). Skip until you have real users. |
| **Sentry** | Error tracking | `SENTRY_DSN=` — leave empty to disable. Add when traffic justifies it. |

### Critical gotcha — Supabase Storage S3 keys are NOT the service-role key

Every other Supabase API auths with `SUPABASE_SECRET_KEY` (the service-role JWT). Storage's S3-compat endpoint **rejects that key** with `SignatureDoesNotMatch / 403`. You must mint a separate access-key/secret pair under **Project Settings → Storage → S3 Connection**. Both belong to the same Supabase project but rotate independently. The `apps/api/.env.example` keeps them on different lines as a reminder.

---

## 3. Running It Locally

This is the fast path — no cloud blob storage required.

### Prerequisites

```bash
# Python 3.10+ + uv (Python package manager)
brew install uv

# Node 20+ + pnpm (frontend package manager)
brew install pnpm

# Docker (for local Postgres + Redis)
brew install --cask docker

# MongoDB Atlas account (free M0 tier is enough)
# — or run Mongo locally; uri then becomes mongodb://localhost:27017
```

### Step 1 — clone and install

```bash
git clone https://github.com/cristian-robert/mongo-rag.git
cd mongo-rag

# Backend deps
cd apps/api && uv sync && cd ../..

# Frontend deps
cd apps/web && pnpm install && cd ../..
```

### Step 2 — populate env

```bash
cp apps/api/.env.example apps/api/.env
```

Edit `apps/api/.env`. **Mandatory for local dev:**

| Var | Value | Notes |
|---|---|---|
| `MONGODB_URI` | `mongodb+srv://…` (your Atlas cluster) | Must have Atlas Search + Vector Search indexes — see step 5 |
| `LLM_API_KEY` | OpenAI or OpenRouter key | |
| `EMBEDDING_API_KEY` | OpenAI key | Embeddings always go through OpenAI |
| `BLOB_STORE` | `fs` *(already the default in `.env.example`)* | No cloud blob store needed locally |
| `REDIS_URL` | `redis://localhost:6379/0` *(already the default)* | Comes from docker-compose |
| `SUPABASE_URL` / `SUPABASE_SECRET_KEY` / `SUPABASE_PUBLISHABLE_KEY` | from your Supabase project | Required for auth even in dev |
| `NEXTAUTH_SECRET` | `openssl rand -hex 32` | Must match the same value in `apps/web/.env.local` |
| `APP_ENV` | `development` | |

Everything else (Stripe, Resend, Supabase S3 keys, Sentry, Fly stuff) **leave as the example or empty** for local dev.

For the frontend: `cp apps/web/.env.local.example apps/web/.env.local` and fill `NEXT_PUBLIC_API_URL=http://localhost:8100`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, and the same `NEXTAUTH_SECRET` from above.

### Step 3 — start Mongo + Redis (and Postgres if you don't use Supabase)

```bash
docker-compose -f docker-compose.dev.yml up -d
```

This brings up Redis on `:6379` (broker) and any other dev services the compose file declares. Mongo is expected to be Atlas (cloud) — set `MONGODB_URI` accordingly. If you'd rather run Mongo locally, point `MONGODB_URI=mongodb://localhost:27017` and add a `mongo` service to the compose file.

### Step 4 — run the migrations + index setup

```bash
cd apps/api
uv run python -m src.migrations.cli migrate    # Mongo collection indexes
uv run python scripts/setup_indexes.py         # Atlas Vector Search + Atlas Search indexes
```

> **Atlas Vector / Atlas Search indexes can NOT be created programmatically.** `setup_indexes.py` prints the JSON definitions; you must paste them into the Atlas UI under your cluster → Search → Create Search Index. This is a one-time per-cluster step.

### Step 5 — run the stack

Open three terminals.

```bash
# Terminal 1 — API (FastAPI on :8100)
cd apps/api && uv run uvicorn src.main:app --reload --port 8100

# Terminal 2 — Celery worker
cd apps/api && uv run celery -A src.worker worker --loglevel=info

# Terminal 3 — Next.js web (on :3100)
cd apps/web && pnpm dev
```

Or use the wrapper:

```bash
./scripts/dev.sh
```

It validates the required env vars (including the BlobStore + S3 vars when you set `BLOB_STORE=supabase`), then starts api + worker + web together.

### Step 6 — verify it works

1. Open [http://localhost:3100](http://localhost:3100), register a tenant, log in.
2. Upload a small PDF/MD file via the dashboard.
3. Watch the worker terminal — you should see structured logs like `ingestion_complete source_kind=upload chunks=N`.
4. Confirm chunks landed in Mongo without `[Error:` placeholders:

```bash
mongosh "$MONGODB_URI" --eval '
  db.chunks.find({}, { content: 1 }).limit(5).forEach(c =>
    console.log(c.content.slice(0, 80))
  )
'
```

5. Ask a question in the chat UI — answers should cite chunks from your uploaded doc.

### Useful local commands

```bash
# Backend
cd apps/api
uv run pytest -m "not integration" -q     # Unit tests (~11 min, 618 should pass)
uv run pytest -m integration              # Integration tests (needs MONGODB_TEST_URI)
uv run ruff check . && uv run ruff format --check .   # Lint

# Frontend
cd apps/web
pnpm test                                 # Vitest
pnpm lint                                 # ESLint + Prettier
pnpm build                                # Prod build smoke

# CLI agent (no UI needed)
cd apps/api && uv run python -m src.cli
```

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `BlobNotFoundError` during ingestion | Worker can't see the file the API wrote | You're probably running api on host but worker in Docker with separate `/tmp`. Use `BLOB_STORE=fs` and the bind-mounted upload dir from `docker-compose.dev.yml`, or run both api+worker on the same side. |
| `BLOB_STORE=supabase` but ingestion 401/403 | Using service-role key for S3 | Mint dedicated S3 access/secret under Supabase → Project Settings → Storage → S3 Connection (see §2 gotcha) |
| `LLM_API_KEY` validation error at startup | `.env` not loaded or var name wrong | Check `apps/api/.env` exists and is in the same dir as `pyproject.toml`; vars are uppercase |
| Vector search returns 0 results | Atlas Search indexes not created | Re-run `setup_indexes.py` and create the indexes in Atlas UI |
| Worker doesn't pick up tasks | Redis URL mismatch | `redis-cli -u "$REDIS_URL" ping` from both api and worker terminals — both must say PONG |

---

## 4. Going to Production (high-level checklist)

Full runbook is `docs/deploy.md`. The condensed version:

1. **Sign up for Fly + Upstash + Vercel** (see §2). Mint Supabase Storage S3 keys.
2. Populate `apps/api/.env` with **prod values**: `BLOB_STORE=supabase`, `REDIS_URL=rediss://…`, real `STRIPE_SECRET_KEY`, real `SUPABASE_S3_ACCESS_KEY` etc.
3. `fly apps create mongorag-api && fly apps create mongorag-worker`
4. `./scripts/fly-secrets.sh both` — pushes every secret from `.env` to both Fly apps
5. `BLOB_STORE=supabase SUPABASE_URL=… SUPABASE_S3_ACCESS_KEY=… SUPABASE_S3_SECRET_KEY=… SUPABASE_STORAGE_BUCKET=mongorag-uploads uv run python scripts/setup_supabase_storage.py` — creates the bucket + 24h lifecycle. **If it exits 2**, the bucket exists but the lifecycle rule failed; set the 1-day expiration manually in the Supabase dashboard before going live.
6. `fly deploy -c apps/api/fly.api.toml` and `fly deploy -c apps/api/fly.worker.toml`
7. `cd apps/web && vercel link && vercel env add NEXT_PUBLIC_API_URL production` (value: `https://mongorag-api.fly.dev`) → `vercel deploy --prod`
8. Run the smoke test in `docs/deploy.md` §"Smoke Test".

### Worker cold-start gotcha

Fly only auto-wakes machines on **inbound network traffic**. Celery workers poll Redis (outbound), so a stopped worker won't auto-wake. Two options:
- Bump `min_machines_running = 1` in `apps/api/fly.worker.toml` (small extra cost; immediate task pickup)
- Leave at `0`, accept ~30-60s first-task latency after idle (Celery `acks_late = True` makes it safe)

### Idle prod cost target

~$5/mo on Vercel Hobby + Fly free hours + Upstash free tier + Atlas M0 + Supabase free tier. First paying customer ~$8/mo. Steady SaaS once free tiers cap: $110-130/mo.

---

## 5. Known Tech Debt (inherited on main, not from #79)

The CI on `main` has been red for several days due to issues unrelated to #79. Worth cleaning up in a separate hygiene PR:

- `ruff format --check .` flags 4 files: `apps/api/src/auth/api_keys.py`, `apps/api/src/routers/keys.py`, `apps/api/tests/test_api_key_router.py`, `apps/api/tests/test_api_keys_pg.py` (mechanical fix: `uv run ruff format .`)
- `mypy src/ --ignore-missing-imports` reports ~30 errors across `services/rerank.py`, `core/dependencies.py`, `services/ingestion/url_loader.py`, `services/stripe_webhook.py`, `migrations/cli.py`, `core/settings.py`, `services/blobstore/supabase.py:48`. Most are pre-existing.
- `tests/test_tenant_filter_audit.py::test_every_mongo_call_in_apps_api_is_tenant_scoped` fails on `services/webhook_delivery.py:176` — an `update_one()` lacking a `tenant_id` filter. **Real bug** worth fixing — outbound-webhook delivery must be tenant-scoped (see `concept-principal-tenant-isolation` in `.obsidian/wiki/`).

---

## TL;DR

- **Local dev:** clone, `cp .env.example .env`, fill Mongo + LLM key, leave `BLOB_STORE=fs`, `docker-compose -f docker-compose.dev.yml up -d`, `uvicorn` + `celery` + `pnpm dev`.
- **For prod:** sign up for **Fly.io**, **Upstash Redis**, **Vercel**, mint **Supabase Storage S3 keys** (separate from service-role). Then follow `docs/deploy.md`.
- **Don't reuse** `SUPABASE_SECRET_KEY` for Storage — it'll fail with 403.
