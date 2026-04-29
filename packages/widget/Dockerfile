# syntax=docker/dockerfile:1.7
# Builds the embeddable widget bundle and serves it via a tiny nginx.
# Alternative: copy the built artifact into the api/web image, or push to CDN.

FROM node:22.12.0-alpine AS builder

WORKDIR /build
COPY package.json ./
RUN npm install --no-audit --no-fund

COPY src/ ./src/
COPY tsconfig.json ./
RUN npm run build

# ─── Runtime: nginx serving static assets ────────────────────────
FROM nginx:1.27.3-alpine AS runtime

RUN apk add --no-cache tini \
    && addgroup -g 1001 -S widget \
    && adduser -u 1001 -S widget -G widget

# Custom nginx config — non-privileged port + permissive caching.
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
    listen 8080;
    server_name _;
    root /usr/share/nginx/html;

    # Versioned bundle path: /v1/widget.js — set Cache-Control: immutable
    # at the CDN, not here.
    location / {
        add_header Cache-Control "public, max-age=300" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Access-Control-Allow-Origin "*" always;
        try_files $uri =404;
    }

    location = /healthz {
        access_log off;
        return 200 "ok";
        add_header Content-Type text/plain;
    }
}
EOF

COPY --from=builder /build/dist /usr/share/nginx/html

# nginx upstream image runs as root by default to bind 80; we use 8080 + non-root.
RUN chown -R widget:widget /var/cache/nginx /var/log/nginx /etc/nginx/conf.d /usr/share/nginx/html \
    && touch /var/run/nginx.pid \
    && chown widget:widget /var/run/nginx.pid

USER widget

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:8080/healthz || exit 1

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["nginx", "-g", "daemon off;"]
