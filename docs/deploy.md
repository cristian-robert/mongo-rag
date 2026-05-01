# Deployment Guide

Production deployment runbook for MongoRAG. Implements the stack chosen in `[[decision-deploy-fly-vercel]]`. The API/worker handoff via blobs is documented in `[[decision-blobstore-handoff]]`.

## Overview

| Layer | Service | Notes |
|---|---|---|
| Web (Next.js) | **Vercel** | `apps/web` — preview + prod, native Next.js |
| API (FastAPI) | **Fly Machines** (`mongorag-api`) | Always-on, `min_machines_running = 1` |
| Worker (Celery) | **Fly Machines** (`mongorag-worker`) | Stop-on-idle, autostart on inbound traffic (see "Worker autoscale gap") |
| Broker | **Upstash Redis** | TLS-only (`rediss://`), free tier OK for MVP |
| Blob storage | **Supabase Storage** | Private bucket `mongorag-uploads`, S3-compatible, 24h lifecycle |
| Postgres | **Supabase Postgres** | Existing — identity, billing, api_keys |
| Vector / Atlas Search | **MongoDB Atlas** | Existing — `documents`, `chunks` (1536-dim) |

API and worker run from a **single `apps/api/Dockerfile`**; `PROCESS_TYPE=api|worker` env var switches the entrypoint.

## First-Time Setup

Run from repo root. Assumes `fly auth login`, `vercel login`, and `apps/api/.env` populated.

```bash
# 1. Create both Fly apps
fly apps create mongorag-api
fly apps create mongorag-worker

# 2. Push secrets from apps/api/.env to both apps
./scripts/fly-secrets.sh both

# 3. Provision Supabase Storage bucket + lifecycle (24h auto-delete)
#    SUPABASE_S3_ACCESS_KEY / SUPABASE_S3_SECRET_KEY are minted under
#    Supabase dashboard → Project Settings → Storage → S3 Connection.
#    They are NOT the service-role SUPABASE_SECRET_KEY.
BLOB_STORE=supabase \
SUPABASE_URL=https://<project>.supabase.co \
SUPABASE_S3_ACCESS_KEY=<s3-access-key> \
SUPABASE_S3_SECRET_KEY=<s3-secret-key> \
SUPABASE_STORAGE_BUCKET=mongorag-uploads \
  uv run python scripts/setup_supabase_storage.py

# 4. Deploy both Fly machines from apps/api/
fly deploy -c apps/api/fly.api.toml
fly deploy -c apps/api/fly.worker.toml

# 5. Link Vercel to apps/web and set the API URL
cd apps/web && vercel link
vercel env add NEXT_PUBLIC_API_URL production
# value: https://mongorag-api.fly.dev
vercel deploy --prod
```

After step 4, verify:

```bash
fly status -a mongorag-api      # 1 machine started
fly status -a mongorag-worker   # 0 machines (auto-stopped)
fly logs -a mongorag-api | grep "Uvicorn running"
```

## Secrets

Managed by `scripts/fly-secrets.sh` (sourced from `apps/api/.env`, pushed to **both** Fly apps so the worker can mint tokens, decrypt JWTs, and reach all backends):

| Secret | Purpose |
|---|---|
| `MONGODB_URI` | Atlas connection string |
| `DATABASE_URL` | Supabase Postgres |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SECRET_KEY` | Service-role JWT-signing key (RLS bypass for Postgres / REST) |
| `SUPABASE_S3_ACCESS_KEY` | Storage S3 access key id (see callout below) |
| `SUPABASE_S3_SECRET_KEY` | Storage S3 secret (see callout below) |
| `SUPABASE_JWT_SECRET` | Dashboard JWT verification |
| `SUPABASE_STORAGE_BUCKET` | Bucket name (default `mongorag-uploads`) |
| `LLM_API_KEY` | LLM provider key (OpenRouter / OpenAI / Anthropic) |
| `EMBEDDING_API_KEY` | OpenAI key for `text-embedding-3-small` |
| `STRIPE_SECRET_KEY` | Stripe API |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing |
| `REDIS_URL` | Upstash `rediss://` (broker + result backend) |
| `BLOB_STORE` | `supabase` in prod, `filesystem` in local dev |
| `NEXTAUTH_SECRET` | Legacy NextAuth fallback (still wired) |

Rotate by editing `apps/api/.env` and re-running `./scripts/fly-secrets.sh both`. Fly restarts machines automatically on secret change.

> **Important — Storage S3 credentials are NOT the service-role key.**
> `SUPABASE_S3_ACCESS_KEY` and `SUPABASE_S3_SECRET_KEY` are a distinct
> access-key/secret pair that you must mint under Supabase dashboard →
> Project Settings → Storage → S3 Connection. The service-role
> `SUPABASE_SECRET_KEY` is a JWT-signing key for the Postgres / REST
> APIs and will be rejected by Storage's S3-compat layer with
> SignatureDoesNotMatch / 403. Both credentials live in the same
> Supabase project but are minted and rotated independently.

## Worker Autoscale Gap

Fly's `auto_start_machines = true` wakes a stopped Machine on **inbound network traffic**. Celery workers receive jobs via the **Redis broker** (outbound poll), not network — so a cold-stopped worker will not wake when the API dispatches a task.

**Mitigation (current):** worker `fly.worker.toml` keeps `min_machines_running = 0` to save money during idle hours, but operators should bump this to `1` if cold-start latency is unacceptable. Polled jobs sitting in Redis are still safe — Celery `acks_late = True` + `task_track_started = True` means a delayed worker eventually picks them up after autostop expires.

**Future tuning (out of scope for #79):** API process pings the Fly Machines API on `delay()` to force-start the worker, or run a 5-minute cron pinger. Documented here for the next operator who hits this.

## Smoke Test

After deploy, run from a workstation with `apps/api/.env`:

```bash
# 1. Mint a token (or use a real session cookie)
TOKEN=$(uv run python -c "from src.auth.api_keys import ...; print(...)")

# 2. Upload a real PDF
curl -X POST https://mongorag-api.fly.dev/api/v1/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@docs/sample.pdf"
# → returns { id, status: "pending" }

# 3. Poll status until ready (≤90s for a 1MB PDF)
curl https://mongorag-api.fly.dev/api/v1/documents/$DOC_ID/status \
  -H "Authorization: Bearer $TOKEN"
# → { status: "ready", chunk_count: 42 }

# 4. Verify chunks exist in Mongo and contain no [Error: placeholders
mongosh "$MONGODB_URI" --eval '
  db.chunks.find({ document_id: "<DOC_ID>" })
    .project({ content: 1 })
    .forEach(c => assert(!/^\[Error:/.test(c.content)))
'
```

A successful upload, ready status, `chunk_count > 1`, and zero `[Error:` strings = green.

## Rollback

Fly keeps the previous image tagged in its registry; rolling back is a single deploy:

```bash
fly releases list -a mongorag-api
fly deploy -c apps/api/fly.api.toml \
  --image registry.fly.io/mongorag-api:vN
```

Repeat for `mongorag-worker`. Vercel rollback is one click in the dashboard or `vercel rollback <deployment-url>`.

## Cost Table

| Stage | Vercel | Fly | Upstash | Atlas | Supabase | **Total** |
|---|---|---|---|---|---|---|
| Idle prod (no traffic) | $0 (Hobby) | $0 (free hours) | $0 (free) | $0 (M0) | $0 (free) | **~$5/mo** |
| First paying customer | $0 | ~$3 | $0 | $0 | $0 | **~$8/mo** |
| Steady SaaS (free tiers cap) | $20 (Pro) | $30-40 | $10 | $57 (M10) | $25 (Pro) | **$110-130/mo** |

The big jumps:
- Atlas M0 → M10 once vector index size or ops/sec exceed free tier (~$57/mo)
- Upstash free → paid past 10k commands/day (~$10/mo)
- Fly free → paid once the always-on API machine consumes more than 3 shared-cpu free hours (~$3/mo per machine)
- Vercel Hobby → Pro for team seats, analytics, longer logs (~$20/mo per seat)
