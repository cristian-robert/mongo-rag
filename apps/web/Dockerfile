# syntax=docker/dockerfile:1.7

# ─── Base ────────────────────────────────────────────────────────
# Debian slim (not alpine) — Next.js + sharp + transitive deps
# (React 19, base-ui, jose) ship glibc-only prebuilt binaries; alpine
# (musl) trips a "Cannot read properties of null (reading 'useContext')"
# during _global-error prerender because react-dom resolves to two
# instances under different musl-vs-glibc dependency trees.
FROM node:22.14.0-bookworm-slim AS base

ENV PNPM_HOME="/pnpm" \
    PATH="/pnpm:$PATH" \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

# corepack signature verification is unreliable for pnpm@10 with the
# Node 22.12 builtin corepack; install pnpm globally via npm instead.
RUN npm install --global --no-fund --no-audit pnpm@10.33.0

# ─── Dependencies ────────────────────────────────────────────────
FROM base AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
# Tailwind/TypeScript live in devDependencies but are required for the
# production Next.js build (PostCSS plugins). Override NODE_ENV here so
# pnpm installs the full dependency set; the runner stage uses only the
# standalone bundle and never sees node_modules.
ENV NODE_ENV=development
RUN --mount=type=cache,id=pnpm-store,target=/pnpm/store \
    pnpm config set store-dir /pnpm/store \
    && pnpm install --frozen-lockfile

# ─── Builder ─────────────────────────────────────────────────────
FROM base AS builder
WORKDIR /app
ENV NODE_ENV=development
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# next.config.ts must set `output: "standalone"` (verified).
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

# ─── Runner ──────────────────────────────────────────────────────
# Slim runtime: only Node + standalone bundle. Bookworm-slim for glibc
# parity with the builder.
FROM node:22.14.0-bookworm-slim AS runner

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3100 \
    HOSTNAME=0.0.0.0

RUN apt-get update \
    && apt-get install --no-install-recommends -y tini ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1001 nodejs \
    && useradd --system --uid 1001 --gid nodejs --home /app --shell /sbin/nologin nextjs

WORKDIR /app

# Standalone output + static assets + public assets.
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3100

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3100/api/health',r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))" \
    || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["node", "server.js"]
