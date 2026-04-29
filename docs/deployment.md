# MongoRAG Deployment Runbook

This document covers how to take a green commit on `main` and ship it to
staging and production. The CI pipeline (`.github/workflows/ci.yml`) and
the build/publish pipeline (`.github/workflows/deploy.yml`) handle build
artifacts; promotion to runtime targets is described below.

---

## 1. Pipeline overview

```
push to main / git tag vX.Y.Z
   │
   ▼
ci.yml          ── lint, typecheck, unit tests, docker build smoke
   │
   ▼
deploy.yml      ── multi-arch build → GHCR push → Trivy scan → SBOM →
                   cosign sign → SLSA provenance attestation
   │
   ▼
runtime target  ── Railway / Fly.io / VPS+Compose / ECS / Cloud Run
```

`deploy.yml` only publishes images. **No runtime is auto-deployed** —
promotion is an explicit, human-approved step.

---

## 2. Image registry layout

All images are published to GitHub Container Registry under the repo
namespace:

| Service | Image |
|---------|-------|
| API     | `ghcr.io/<owner>/<repo>/api:<tag>` |
| Web     | `ghcr.io/<owner>/<repo>/web:<tag>` |
| Widget  | `ghcr.io/<owner>/<repo>/widget:<tag>` |

Tags produced for every push:

- `sha-<short>` — immutable, traceable to the exact commit (preferred for prod)
- `main` — moving tag for the latest main build (preview / staging only)
- `latest` — alias for `main`
- `vX.Y.Z`, `vX.Y` — for git tags

Always pin **production** to `sha-...` or `vX.Y.Z` — never `latest`.

---

## 3. Infrastructure targets

We support three deployment targets. Pick one per environment.

### Option A — Vercel (web) + Railway/Fly.io (api) + MongoDB Atlas (recommended)

- **Web**: Next.js standalone build deployed to Vercel via Git integration.
- **API**: GHCR image deployed to Railway or Fly.io.
- **Widget**: Static bundle uploaded to Cloudflare R2 / Vercel Edge,
  served from versioned URL `https://cdn.example.com/widget/v1/widget.js`.
- **MongoDB**: Atlas cluster (M10+ for prod; Vector Search requires Atlas).
- **Pros**: Lowest ops; managed TLS, autoscaling, global CDN.
- **Cons**: Three vendors to manage.

### Option B — Single VPS + Docker Compose + Caddy

- Single Linux host running `docker-compose.prod.yml`.
- Caddy reverse-proxy in front of the stack for TLS + HTTP/2.
- MongoDB Atlas (do **not** run mongo on the same VPS for prod — backups, IO).
- **Pros**: Simple, one box, easy to reason about.
- **Cons**: No autoscaling; single point of failure.

### Option C — AWS ECS Fargate or GCP Cloud Run

- Pull GHCR images via cross-registry replication or pull-through cache.
- Use ALB / Cloud Run HTTPS for ingress.
- Secrets via AWS Secrets Manager / GCP Secret Manager.
- **Pros**: Managed, autoscaling, zero-downtime rollouts.
- **Cons**: More ops surface, vendor lock-in.

---

## 4. Environments

| Env | Branch / Tag | Image tag | Purpose |
|-----|--------------|-----------|---------|
| dev | feature branches | (built locally) | Local `docker compose up` |
| staging | `main` | `sha-<short>` | Pre-prod smoke + integration |
| prod | git tags `v*` | `vX.Y.Z` | Customer traffic |

**Promotion**: a `sha-...` tag must run in staging for ≥ 24h with no
errors before being promoted (re-tagged) to a `vX.Y.Z` and rolled to
prod.

---

## 5. Required environment variables

Manage through the platform's secret manager — **never** commit `.env`.

### API

| Variable | Required | Notes |
|----------|----------|-------|
| `MONGODB_URI` | yes | Atlas SRV connection string |
| `LLM_API_KEY` | yes | Provider API key |
| `EMBEDDING_API_KEY` | yes | Usually same as LLM_API_KEY |
| `LLM_MODEL` | no | Default: `anthropic/claude-haiku-4.5` |
| `EMBEDDING_MODEL` | no | Default: `text-embedding-3-small` |
| `STRIPE_SECRET_KEY` | yes (prod) | `sk_live_...` |
| `STRIPE_WEBHOOK_SECRET` | yes (prod) | `whsec_...` |
| `LOG_LEVEL` | no | Default: `INFO` |

### Web

| Variable | Required | Notes |
|----------|----------|-------|
| `NEXT_PUBLIC_API_URL` | yes | Public origin of the API |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | yes (prod) | `pk_live_...` |
| `NEXTAUTH_SECRET` | yes | 32+ random bytes |
| `NEXTAUTH_URL` | yes | Public origin of the web app |

`NEXT_PUBLIC_*` values are baked into the Next.js client bundle at
build time. Rebuild + redeploy when they change.

---

## 6. Deployment procedures

### 6.1 Vercel (web)

1. Connect repo at `vercel.com/new`. Root: `apps/web`.
2. Set env vars in project settings (Production scope).
3. Each push to `main` deploys preview; promote in dashboard.

### 6.2 Railway / Fly.io (api) — recommended for FastAPI

```bash
# Fly.io example
fly launch --image ghcr.io/<owner>/<repo>/api:sha-<short> \
           --no-deploy --copy-config --name mongorag-api-staging
fly secrets set MONGODB_URI=... LLM_API_KEY=... NEXTAUTH_SECRET=...
fly deploy --image ghcr.io/<owner>/<repo>/api:sha-<short>
```

Fly.io uses rolling deploys with health-check gating (the image's
`HEALTHCHECK` plus `[checks]` in `fly.toml`).

### 6.3 VPS + Compose (Option B)

```bash
ssh deploy@vps.example.com
cd /opt/mongorag
# Pull pinned image tag from CI summary
export IMAGE_TAG=sha-abc1234
export MONGODB_URI=...
# secrets sourced from /etc/mongorag/env (chmod 600, root-owned)
set -a && . /etc/mongorag/env && set +a
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
```

`compose up -d` does not give zero-downtime by default. For VPS,
either accept ~5s of 502s or front the stack with two compose
projects behind Caddy and switch upstream after health.

### 6.4 Widget CDN

The widget ships as a static IIFE bundle. Two options:

1. **Container** (`packages/widget` image) — pin `widget:vX.Y.Z`
   behind Caddy/CloudFront with versioned paths `/widget/vX/widget.js`
   and `Cache-Control: public, max-age=31536000, immutable`.
2. **Object storage** — `pnpm --dir packages/widget build` then upload
   `dist/widget.js` to Cloudflare R2 or S3+CloudFront under
   `/widget/vX/widget.js`. Update the snippet docs to reference the
   new URL.

Either way, **never overwrite** an existing version path; always
publish a new one and let customers opt in.

---

## 7. Zero-downtime strategy

| Target | Strategy |
|--------|----------|
| Vercel | Atomic build switchover (built-in) |
| Fly.io | Rolling — Fly waits for health checks before shifting traffic |
| Railway | Rolling deploy with health-gated cutover |
| ECS Fargate | `minHealthyPercent=100` + `maximumPercent=200` (rolling) |
| Cloud Run | Revision-based traffic split (default 100% to new) |
| VPS Compose | Run two compose stacks behind Caddy `lb_policy first` and switch |

The image's `HEALTHCHECK` plus the platform's readiness gate is what
makes any of the above safe. Both are configured in this repo.

---

## 8. Rollback

1. Identify the last known-good tag from the GHCR UI or `gh run view`.
2. Roll back via the platform:
   - **Fly.io**: `fly deploy --image ghcr.io/.../api:sha-<prev>`
   - **Railway**: redeploy previous deployment from dashboard
   - **ECS**: `aws ecs update-service --task-definition <prev-revision>`
   - **Cloud Run**: shift 100% traffic to previous revision
   - **Vercel (web)**: "Promote to Production" on the previous deployment
   - **VPS**: `IMAGE_TAG=sha-<prev> docker compose -f docker-compose.prod.yml up -d`
3. Confirm `/health` returns 200 from the public origin.
4. Post-mortem within 24h. File a GitHub issue with label `incident`.

Rollback is the **first** action on any production incident — never
fix-forward in prod under pressure.

---

## 9. Verifying signatures (optional, recommended)

Images are cosign-signed (keyless via OIDC). Verify before prod pull:

```bash
cosign verify \
  --certificate-identity-regexp 'https://github.com/<owner>/<repo>/.github/workflows/deploy\.yml@refs/heads/main' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/<owner>/<repo>/api:sha-<short>
```

CI also produces SLSA provenance attestations and SPDX SBOMs (artifact
on each workflow run).

---

## 10. First-time setup checklist

- [ ] GHCR enabled — repo settings → Actions → Workflow permissions →
      "Read and write" + "Allow GitHub Actions to create / approve PRs"
- [ ] Required GitHub secrets configured (none required for `deploy.yml`
      itself; runtime secrets live on the deploy target)
- [ ] Atlas cluster provisioned with Vector Search enabled, network
      peering or 0.0.0.0/0 allowlist (latter only for managed PaaS)
- [ ] DNS records pointed at the runtime target with TLS terminated
      (Vercel/Fly/Caddy/CloudFront)
- [ ] Stripe webhooks pointed at `https://api.example.com/webhooks/stripe`
      with the matching `STRIPE_WEBHOOK_SECRET` set
- [ ] Sentry / observability DSN configured (when added)
