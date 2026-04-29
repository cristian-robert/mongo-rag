-- ============================================================================
-- 20260429200000_stripe_events.sql
-- Idempotency log for Stripe webhook events.
--
-- The webhook handler MUST insert the Stripe event_id before processing it,
-- relying on the unique constraint to dedupe replays. Postgres is the source
-- of truth here so Mongo failures never corrupt webhook idempotency.
--
-- Rollback (manual):
--   drop table if exists public.stripe_events;
-- ============================================================================

create table if not exists public.stripe_events (
  event_id     text primary key,
  type         text not null,
  received_at  timestamptz not null default now(),
  processed_at timestamptz,
  payload      jsonb
);

create index if not exists stripe_events_received_at_idx
  on public.stripe_events(received_at desc);
create index if not exists stripe_events_type_idx
  on public.stripe_events(type);

-- Service-role only — no policies for `authenticated`. Tenant users never need
-- to read raw Stripe event payloads (PII risk). The backend writes via the
-- secret key which bypasses RLS.
alter table public.stripe_events enable row level security;
