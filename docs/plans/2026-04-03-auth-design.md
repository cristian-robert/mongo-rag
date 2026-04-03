# User Authentication Design — Issue #7

## Summary

Auth system for MongoRAG SaaS dashboard. Users sign up with email/password + organization name, creating a tenant automatically. Auth.js v5 handles sessions (JWT strategy, 15-min access tokens with refresh rotation). FastAPI validates JWTs via shared secret. Password reset uses Resend for transactional emails.

## Architecture

```
Browser → Auth Pages (/login, /signup, /forgot-password, /reset-password)
       → Next.js Middleware (protects /dashboard/*)
       → Auth.js v5 (Credentials provider, JWT strategy)
       → FastAPI (JWT validation via shared NEXTAUTH_SECRET)
       → MongoDB Atlas (users, tenants, password_reset_tokens)
```

### Key Flows

**Signup:** Form (email, password, org name) → FastAPI `POST /auth/signup` → creates tenant + user (bcrypt hash) → Auth.js auto-login → JWT issued → redirect to `/dashboard`.

**Login:** Form → Auth.js Credentials `authorize` → FastAPI `POST /auth/login` (validates bcrypt) → returns user with `tenant_id`, `role` → Auth.js packages into JWT (15-min, HTTP-only cookie).

**Authenticated FastAPI request:** Next.js middleware validates session → forwards JWT in `Authorization: Bearer` header → FastAPI decodes with shared `NEXTAUTH_SECRET` → extracts `tenant_id` from claims → replaces current `X-Tenant-ID` stub.

**Token refresh:** Auth.js handles automatically via JWT callback, rotates before expiry.

**Password reset:** Forgot form → FastAPI generates `secrets.token_urlsafe(32)` → stores SHA256 hash in `password_reset_tokens` → Resend sends email with link → reset form validates token → updates bcrypt hash → marks token used.

## Data Models

### `users` collection (existing model, no changes)

```python
{
  "_id": ObjectId,
  "tenant_id": str,
  "email": str,               # unique index
  "hashed_password": str,     # bcrypt
  "name": str,
  "role": "owner" | "admin" | "member",
  "is_active": bool,
  "email_verified": bool,
  "created_at": datetime,
  "updated_at": datetime
}
```

### `tenants` collection (existing, no changes)

### `password_reset_tokens` collection (new)

```python
{
  "_id": ObjectId,
  "user_id": str,
  "token_hash": str,          # SHA256 of raw token
  "expires_at": datetime,     # created_at + 1 hour
  "used": bool,
  "created_at": datetime
}
# Indexes: unique on token_hash, TTL on expires_at
```

### JWT Claims

```json
{
  "sub": "<user_id>",
  "email": "user@example.com",
  "tenant_id": "<tenant_id>",
  "role": "owner",
  "iat": 1234567890,
  "exp": 1234568790
}
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/auth/signup` | POST | Create tenant + user |
| `/api/v1/auth/login` | POST | Validate credentials, return user data |
| `/api/v1/auth/forgot-password` | POST | Generate reset token, send email |
| `/api/v1/auth/reset-password` | POST | Validate token, update password |

## Frontend Pages

| Route | Group | Purpose |
|-------|-------|---------|
| `/(auth)/login` | Public | Email + password login |
| `/(auth)/signup` | Public | Email, password, org name |
| `/(auth)/forgot-password` | Public | Email input for reset |
| `/(auth)/reset-password` | Public | New password form (token from URL) |
| `/(dashboard)/` | Protected | Dashboard placeholder |

### Middleware (`middleware.ts`)

- `/dashboard/*` → redirect to `/login` if no session
- `/login`, `/signup` → redirect to `/dashboard` if authenticated
- Public routes (`/`, `/api/auth/*`) → pass through

### Validation

- Email: valid format (Zod)
- Password: min 8 characters
- Org name: 2-100 characters

## Password Reset Security

- Constant-time response regardless of email existence (no enumeration)
- Raw token never stored — only SHA256 hash in DB
- 1-hour expiry + TTL index for auto-cleanup
- Single use — marked `used` after consumption
- Previous tokens invalidated on new request
- Rate limiting: max 3 requests per email per hour (MongoDB count check)
- Resend: plain transactional email, configurable from address

## New Dependencies

**Python (backend):**
- `bcrypt` — password hashing
- `python-jose[cryptography]` — JWT decode/verify
- `resend` — email sending

**Node (frontend):**
- `next-auth` (v5) — Auth.js
- `react-hook-form` — form state
- `zod` — validation
- `@hookform/resolvers` — Zod resolver for RHF

## Configuration

**New environment variables:**

Backend (`apps/api/.env`):
- `NEXTAUTH_SECRET` — shared JWT signing key
- `RESEND_API_KEY` — Resend API key
- `APP_URL` — frontend URL for reset links (default: `http://localhost:3100`)
- `RESET_EMAIL_FROM` — from address for reset emails

Frontend (`apps/web/.env.local`):
- `NEXTAUTH_SECRET` — same shared key
- `NEXTAUTH_URL` — app URL
- `NEXT_PUBLIC_API_URL` — FastAPI URL

## Backend Changes

**`get_tenant_id` dependency update:** Replace `X-Tenant-ID` header stub with JWT decode. Extract `tenant_id` from verified JWT claims. Maintain backward compatibility for API key auth (stub for Issue #8).

## Testing

**Backend unit tests:** Auth router (signup/login/reset endpoints), auth service (hashing, tokens, user creation), JWT tenant extraction.

**Frontend unit tests:** Page rendering, Zod form validation, middleware redirects.

**Integration tests:** Full signup → login → authenticated request flow, password reset token lifecycle.

**Mocks:** MongoDB collections (existing conftest pattern), Resend API, bcrypt in unit tests.

## Decisions

- **Auth.js v5** over custom JWT — production-grade, built-in rotation and CSRF
- **FastAPI owns user/tenant creation** — single source of truth for MongoDB writes
- **Shared NEXTAUTH_SECRET** — simplest JWT validation between Next.js and FastAPI
- **Resend** for transactional email — simple API, good DX
- **No Google OAuth** — deferred, email/password only for MVP
- **No email verification** — field exists (`email_verified`) but flow deferred
