---
title: "Decision: Vercel + Fly + Upstash + Supabase Storage deploy"
type: decision
tags: [decision, deploy, infrastructure, fly, vercel, upstash]
created: 2026-05-01
updated: 2026-05-01
related:
  - "[[decision-blobstore-handoff]]"
  - "[[concept-celery-ingestion-worker]]"
status: compiled
---

## Summary

Production deploy targets: **Vercel** for the Next.js dashboard, **Fly Machines** for both API and Celery worker (single Dockerfile, two `fly.toml` files, `PROCESS_TYPE` switch), **Upstash Redis** for the broker, **Supabase Storage** for blob handoff. Cost: ~$5/mo idle, $110-130/mo at steady SaaS load. Documented runbook lives in `docs/deploy.md`.

## Context

Issue #79 needed to take the API out of a single-host development setup and split the FastAPI app from the Celery worker so they could scale and fail independently. Constraints: must run two process groups from one container image, must have a free idle tier (this is pre-revenue), must keep ops surface low (no Kubernetes), must work with the existing Supabase Postgres and Atlas Mongo.

## Decision

Use four managed services, each chosen for a specific reason:

### Why Fly over Render / Railway

- **Two process groups, one image.** Fly's per-toml `processes` model lets `apps/api/fly.api.toml` and `apps/api/fly.worker.toml` reference the same `Dockerfile` from the same build context. Render and Railway both want one service per image; running a worker means duplicating the build pipeline.
- **Autostop billing.** Fly Machines bills per second; `auto_stop_machines = "stop"` on the worker means we pay zero when Redis has no jobs. Render's smallest paid worker is $7/mo always-on.
- **`PROCESS_TYPE` env switch.** A 10-line `entrypoint.sh` branches on `PROCESS_TYPE=api` (uvicorn) vs `PROCESS_TYPE=worker` (celery). Same image, two roles. No registry sprawl.
- **fly.toml co-location.** Both tomls live at `apps/api/`, so the toml's directory IS the Docker build context — no `build.context` overrides, no path gymnastics.

### Why Vercel for web

Next.js 16 is Vercel's native target. PPR, the App Router, the image optimizer, and the `output: standalone` self-host option all behave the same on Vercel as in `next dev` — moving to any other host requires re-validating each one. Vercel Hobby is $0; Pro is $20/seat once we need analytics or longer log retention.

### Why Upstash for Redis

- Generous free tier (10k commands/day), enough for MVP traffic.
- TLS-only `rediss://` endpoint — Celery 5 supports this directly.
- No-ops: serverless, multi-region replication available, no maintenance windows.
- Drop-in for any other Redis if we ever outgrow it.

### Why Supabase Storage for blobs

We already run on Supabase Postgres for identity/billing (see `[[decision-postgres-mongo-storage-split]]`). Storage is in the same project, billed under the same plan, shares the same service-role key. S3-compatible API means the SDK we wrote against `boto3` works against R2 / S3 / Backblaze if we ever migrate.

## Cost Analysis

| Stage | Vercel | Fly | Upstash | Atlas | Supabase | Total |
|---|---|---|---|---|---|---|
| Idle prod | $0 | $0 | $0 | $0 | $0 | **~$5/mo** (Vercel domain) |
| First customer | $0 | ~$3 | $0 | $0 | $0 | **~$8/mo** |
| Steady SaaS | $20 | $30-40 | $10 | $57 | $25 | **$110-130/mo** |

Inflection points:
- Atlas free (M0) → M10 once vector index size or read throughput exceeds free tier.
- Upstash free → paid past 10k commands/day.
- Fly free hours → paid once API machine runs continuously past the included shared-CPU budget.
- Vercel Hobby → Pro once team seats, analytics, or 7-day log retention are needed.

## Worker Autoscale Gap

Documented separately in `docs/deploy.md` ("Worker autoscale gap"). Fly autostarts machines on inbound network traffic; Celery jobs arrive via Redis poll, not network — so a stopped worker does not wake on `delay()`. Mitigation for now: keep `min_machines_running = 0` for cost, accept that the first job after idle waits up to one autostop interval for the worker to wake on its own (or set `min_machines_running = 1` if cold-start is unacceptable). Future tuning: API process pings Fly Machines API on dispatch — out of scope for #79.

## Key Takeaways

- Single Dockerfile + `PROCESS_TYPE` env switch = two Fly Machines from one image.
- `apps/api/fly.api.toml` (always-on) and `apps/api/fly.worker.toml` (autostop) live next to the Dockerfile; the toml's directory is the build context.
- Upstash + Supabase Storage are no-ops chosen specifically to avoid ops work pre-revenue.
- $5/mo idle, ~$120/mo at steady SaaS — cost ramps with usage, not provisioning.

## See Also

- [[decision-blobstore-handoff]] — why a separate worker forces a real handoff and what we picked
- [[concept-celery-ingestion-worker]] — the worker's task definitions
- `docs/deploy.md` — concrete runbook (commands, secrets, smoke test, rollback)
