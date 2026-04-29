-- ============================================================================
-- 20260429190107_init_tenancy.sql
-- Initial Postgres tenancy + identity + billing schema for MongoRAG.
--
-- Postgres owns: tenants, profiles (1:1 with auth.users), api_keys, subscriptions.
-- MongoDB still owns: documents, chunks, embeddings, conversations.
--
-- Rollback (manual, run in this order):
--   drop trigger if exists on_auth_user_created on auth.users;
--   drop function if exists public.handle_new_user();
--   drop function if exists public.set_updated_at();
--   drop function if exists public.current_tenant_id();
--   drop function if exists public.current_user_role();
--   drop table if exists public.subscriptions;
--   drop table if exists public.api_keys;
--   drop table if exists public.profiles;
--   drop table if exists public.tenants;
--   drop type if exists public.subscription_status;
--   drop type if exists public.user_role;
--   drop type if exists public.tenant_plan;
-- ============================================================================

-- Extensions ------------------------------------------------------------------
create extension if not exists citext;
create extension if not exists pgcrypto;

-- Enums -----------------------------------------------------------------------
create type public.tenant_plan as enum ('free', 'starter', 'pro', 'enterprise');
create type public.user_role as enum ('owner', 'admin', 'member', 'viewer');
create type public.subscription_status as enum (
  'trialing',
  'active',
  'past_due',
  'canceled',
  'incomplete',
  'incomplete_expired',
  'unpaid',
  'paused'
);

-- Tables ----------------------------------------------------------------------
create table public.tenants (
  id          uuid primary key default gen_random_uuid(),
  slug        citext not null unique,
  name        text not null,
  plan        public.tenant_plan not null default 'free',
  settings    jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table public.profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  tenant_id   uuid not null references public.tenants(id) on delete cascade,
  email       citext not null,
  role        public.user_role not null default 'member',
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index profiles_tenant_id_idx on public.profiles(tenant_id);
create unique index profiles_email_per_tenant_idx on public.profiles(tenant_id, email);

create table public.api_keys (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references public.tenants(id) on delete cascade,
  created_by    uuid references public.profiles(id) on delete set null,
  name          text not null,
  prefix        text not null,
  key_hash      text not null unique,
  last_used_at  timestamptz,
  revoked_at    timestamptz,
  created_at    timestamptz not null default now()
);
create index api_keys_tenant_id_idx on public.api_keys(tenant_id);
create index api_keys_prefix_idx on public.api_keys(prefix);
create index api_keys_active_idx on public.api_keys(tenant_id) where revoked_at is null;

create table public.subscriptions (
  tenant_id              uuid primary key references public.tenants(id) on delete cascade,
  stripe_customer_id     text unique,
  stripe_subscription_id text unique,
  plan                   public.tenant_plan not null default 'free',
  status                 public.subscription_status not null default 'active',
  current_period_end     timestamptz,
  usage                  jsonb not null default '{}'::jsonb,
  updated_at             timestamptz not null default now()
);
create index subscriptions_status_idx on public.subscriptions(status);

-- Helper functions ------------------------------------------------------------
-- SECURITY DEFINER so they read profiles regardless of RLS, but they only
-- return data scoped to the calling auth.uid() — safe by construction.

create or replace function public.current_tenant_id()
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select tenant_id from public.profiles where id = (select auth.uid())
$$;

create or replace function public.current_user_role()
returns public.user_role
language sql
stable
security definer
set search_path = public
as $$
  select role from public.profiles where id = (select auth.uid())
$$;

revoke all on function public.current_tenant_id() from public;
revoke all on function public.current_user_role() from public;
grant execute on function public.current_tenant_id() to authenticated;
grant execute on function public.current_user_role() to authenticated;

-- updated_at trigger ----------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create trigger tenants_updated_at
  before update on public.tenants
  for each row execute function public.set_updated_at();

create trigger profiles_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

create trigger subscriptions_updated_at
  before update on public.subscriptions
  for each row execute function public.set_updated_at();

-- Auth signup trigger: provision tenant + profile + free subscription ---------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_tenant_id uuid;
  v_slug      citext;
  v_attempt   int := 0;
begin
  loop
    v_slug := lower(regexp_replace(split_part(new.email, '@', 1), '[^a-z0-9]+', '-', 'g'))
              || '-' || substring(replace(new.id::text, '-', ''), 1, 6 + v_attempt);
    begin
      insert into public.tenants (slug, name)
      values (v_slug, coalesce(new.raw_user_meta_data->>'name', new.email))
      returning id into v_tenant_id;
      exit;
    exception when unique_violation then
      v_attempt := v_attempt + 1;
      if v_attempt > 4 then raise; end if;
    end;
  end loop;

  insert into public.profiles (id, tenant_id, email, role)
  values (new.id, v_tenant_id, new.email, 'owner');

  insert into public.subscriptions (tenant_id, plan, status)
  values (v_tenant_id, 'free', 'active');

  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Row Level Security ----------------------------------------------------------
alter table public.tenants       enable row level security;
alter table public.profiles      enable row level security;
alter table public.api_keys      enable row level security;
alter table public.subscriptions enable row level security;

-- tenants: members read own tenant; owners/admins update
create policy tenants_select on public.tenants
  for select to authenticated
  using (id = (select public.current_tenant_id()));

create policy tenants_update on public.tenants
  for update to authenticated
  using (
    id = (select public.current_tenant_id())
    and (select public.current_user_role()) in ('owner', 'admin')
  )
  with check (
    id = (select public.current_tenant_id())
    and (select public.current_user_role()) in ('owner', 'admin')
  );

-- profiles: see same-tenant peers; users update only their own profile
create policy profiles_select on public.profiles
  for select to authenticated
  using (tenant_id = (select public.current_tenant_id()));

create policy profiles_update_self on public.profiles
  for update to authenticated
  using (id = (select auth.uid()))
  with check (
    id = (select auth.uid())
    and tenant_id = (select public.current_tenant_id())
  );

-- api_keys: same-tenant members read; owners/admins write
create policy api_keys_select on public.api_keys
  for select to authenticated
  using (tenant_id = (select public.current_tenant_id()));

create policy api_keys_insert on public.api_keys
  for insert to authenticated
  with check (
    tenant_id = (select public.current_tenant_id())
    and (select public.current_user_role()) in ('owner', 'admin')
  );

create policy api_keys_update on public.api_keys
  for update to authenticated
  using (
    tenant_id = (select public.current_tenant_id())
    and (select public.current_user_role()) in ('owner', 'admin')
  )
  with check (
    tenant_id = (select public.current_tenant_id())
    and (select public.current_user_role()) in ('owner', 'admin')
  );

create policy api_keys_delete on public.api_keys
  for delete to authenticated
  using (
    tenant_id = (select public.current_tenant_id())
    and (select public.current_user_role()) in ('owner', 'admin')
  );

-- subscriptions: tenant members read. Writes go through service_role only
-- (Stripe webhooks); service_role bypasses RLS.
create policy subscriptions_select on public.subscriptions
  for select to authenticated
  using (tenant_id = (select public.current_tenant_id()));

-- Grants ----------------------------------------------------------------------
-- Authenticated role gets table-level rights; RLS does the actual gating.
grant usage on schema public to authenticated;
grant select, insert, update, delete on public.tenants       to authenticated;
grant select, insert, update, delete on public.profiles      to authenticated;
grant select, insert, update, delete on public.api_keys      to authenticated;
grant select                         on public.subscriptions to authenticated;
