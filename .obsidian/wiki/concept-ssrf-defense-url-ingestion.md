---
title: "SSRF defense for tenant-supplied URLs"
type: concept
tags: [concept, security, ssrf, ingestion, webhooks]
sources:
  - "apps/api/src/services/ingestion/url_loader.py"
  - "apps/api/src/services/webhook.py (uses same url_loader defenses)"
  - "PR #52 (URL-based document ingestion with SSRF defense)"
related:
  - "[[feature-document-ingestion]]"
  - "[[concept-principal-tenant-isolation]]"
  - "[[concept-celery-ingestion-worker]]"
created: 2026-04-30
updated: 2026-04-30
status: compiled
---

## Overview

Tenants can hand us a URL we then fetch (URL ingestion of documents; outbound webhook delivery to a customer-supplied callback). Without defense this is textbook SSRF: the attacker can target our internal network, cloud metadata services, or other tenants' workloads. The defense is **block-listing** — pre-resolve DNS, refuse if any resolved IP is private/loopback/link-local/metadata, and re-validate every redirect hop. There is no resolved-IP allow-list (allow-listing public Internet would be infeasible).

## Content

### `validate_url(url, allow_private=False)` — `services/ingestion/url_loader.py`

Called twice in the request lifecycle:

1. Synchronously at the endpoint (before DB insert or task enqueue) — invalid URLs return 422 immediately
2. Inside `fetch_url()` for **every redirect hop** (re-validation prevents bait-and-switch)

Checks performed:

- **Scheme allow-list** (line 184–187): only `http`, `https`. No `file://`, `gopher://`, `dict://`, etc.
- **No URL credentials** (line 193–195): rejects `user:pass@host` patterns
- **Length cap** (line 176): URL > 2048 chars rejected
- **Hostname → IP resolution** via `_resolve_and_check_host()` (line 115–157):
  - `socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)` resolves all addresses
  - Every resolved IP runs through `_is_blocked_ip()`; **any single hit blocks**

### `_is_blocked_ip()` — block-list (line 103–112)

Refuses:

- `ip.is_private` — RFC1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)
- `ip.is_loopback` — `127.0.0.0/8`, `::1/128`
- `ip.is_link_local` — `169.254.0.0/16` (includes AWS/GCP/Azure IMDS), `fe80::/10`
- `ip.is_multicast` — `224.0.0.0/4`, `ff00::/8`
- `ip.is_reserved` — `240.0.0.0/4`, etc.
- `ip.is_unspecified` — `0.0.0.0/32`, `::/128`

### Explicit metadata host block-list (line 57–65)

```python
BLOCKED_METADATA_HOSTS = {
    "169.254.169.254",           # AWS / GCP / Azure / DigitalOcean / Alibaba IMDS
    "fd00:ec2::254",             # AWS IMDSv6
    "100.100.100.200",           # Alibaba ECS
    "metadata.google.internal",  # GCP
    "metadata.goog",             # GCP
}
```

These are matched before DNS resolution (so a CNAME to a public IP that *names* the metadata host still gets blocked).

### `allow_private` config flag

`settings.url_fetch_allow_private_ips` (default False). When True, only the private-IP checks are skipped; the metadata host block-list is **always** enforced. Test-only — never set in production.

### Content-Type and size enforcement

After connect:

- **Content-Type allow-list** (line 38–52, enforced line 276–281): `text/html`, `application/xhtml+xml`, `text/plain`, `text/markdown`, `application/pdf`, Word/Excel/PPT MIME variants. **Missing or unlisted MIME → reject.**
- **Pre-flight size check** via `Content-Length` header (line 272)
- **Streaming size cap** via `_read_capped()` (line 201–208) — `settings.url_fetch_max_size_mb * 1024 * 1024`
- **HTTP timeout** from settings (line 237)

### Redirect handling (line 254–266)

```python
if response.is_redirect:
    location = response.headers.get("location")
    next_url = str(httpx.URL(current).join(location))
    current = validate_url(next_url, allow_private=allow_private)  # full re-validation
    await response.aclose()
    continue
```

`settings.url_fetch_max_redirects` caps the chain.

### Documented residual risk (lines 13–17)

> **DNS rebinding TOCTOU:** Between `validate_url()` and the actual TCP connect, a malicious DNS server with low TTL could swap the resolved IP to a private one. Kernel resolver caches mitigate this in practice; deployments needing stronger isolation should use a network namespace that blocks RFC1918 egress.

The code acknowledges this is not a complete defense — defense in depth is the network layer.

### Where it's reused

- **URL document ingestion** — `services/ingestion/url_loader.py` (primary site)
- **Outbound webhooks** — `services/webhook.py` validates registered webhook URLs through the same checks before signing and POSTing

## Key Takeaways

- Block-list, not allow-list. Allow-listing public IPs is infeasible; we deny private ranges + metadata hosts.
- DNS resolution happens at the validation site, not the connect site — accept the documented TOCTOU caveat.
- Every redirect hop re-runs `validate_url`. There is no "trust the first response" path.
- Schemes are restricted to `http`/`https`; URL credentials are refused; URL length capped at 2048.
- Content-Type is an **allow-list**; missing MIME is a rejection.
- The same defenses guard outbound webhook delivery, not just URL document ingestion.

## See Also

- [[feature-document-ingestion]] — pipeline that consumes the URL loader
- [[concept-celery-ingestion-worker]] — the Celery task that performs the fetch after validation passes
- [[concept-principal-tenant-isolation]] — same defense-in-depth philosophy applied to authn data
