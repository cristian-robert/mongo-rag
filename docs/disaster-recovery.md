# Disaster Recovery Plan

This runbook covers backup, restore, and incident-response procedures for the
MongoRAG production stack: **MongoDB Atlas** (RAG data plane: documents,
chunks, conversations, usage) and **Supabase Postgres** (control plane:
tenancy, identity, billing).

## 1. Objectives

| Tier | RPO (data loss) | RTO (time to recover) | Notes |
|------|-----------------|----------------------|-------|
| Customer documents / chunks (MongoDB) | <= 60 min | <= 4 h | Atlas continuous backup; PITR enabled |
| Tenancy / identity / billing (Postgres) | <= 60 min | <= 2 h | Supabase managed daily + WAL |
| Conversation history (MongoDB)         | <= 24 h  | <= 8 h | Lower tier; can be replayed |
| Object storage (uploads)               | <= 24 h  | <= 8 h | Versioned bucket |

RPO is the *maximum* acceptable data loss measured from the last successful
backup. RTO is the *maximum* acceptable time from incident declaration to
restored service.

## 2. Backup Architecture

### 2.1 MongoDB Atlas

- **Continuous Cloud Backup** enabled on the production cluster (M10+).
- **Point-in-time restore** window: 7 days.
- **Snapshot retention**: hourly for 24 h, daily for 7 d, weekly for 4 w,
  monthly for 12 m. Configure under *Atlas > Backup > Policy*.
- **Off-platform copy**: nightly `scripts/backup/mongo_backup.sh` runs from
  GitHub Actions (`.github/workflows/backup.yml`) and writes an encrypted
  `mongodump` archive to S3 (when `BACKUP_S3_BUCKET` is set) plus a 14-day
  GitHub Actions artifact.
- **Vector / Atlas Search indexes** are NOT included in `mongodump`. Index
  definitions live in `apps/api/scripts/setup_indexes.py` and are recreated
  via that script after restore. Vector index definitions must be applied
  via the Atlas UI / Atlas CLI.

### 2.2 Supabase Postgres

- **Supabase managed daily backups**: 7-day retention on Pro plan, 14-day on
  Team. Configure under *Project > Database > Backups*.
- **Off-platform copy**: nightly `scripts/backup/postgres_backup.sh` runs
  from GitHub Actions and writes a `pg_dump --format=custom` archive.
- **Migrations**: Postgres schema lives under `supabase/migrations/`.
  Applied with `supabase db push` from CI.

### 2.3 Backup integrity

- Each backup script verifies the archive is non-empty before exit and
  applies a local retention policy (`RETENTION_DAYS`, default 30 days).
- Quarterly: download the most recent backup and run a full restore drill
  into the staging cluster (see Section 4.3). Track outcome in
  `docs/runbooks/restore-drills.md` (create on first run).

## 3. Migration Strategy

### 3.1 MongoDB

- Versioned migrations under `apps/api/src/migrations/versions/NNNN_<name>.py`.
- Runner: `apps/api/src/migrations/runner.py`. CLI:

  ```bash
  uv run python -m src.migrations.cli status
  uv run python -m src.migrations.cli up
  uv run python -m src.migrations.cli up --target 0003
  uv run python -m src.migrations.cli down --steps 1
  ```

- Tracking collection: `_migrations` (one document per applied version).
- Each migration must be **idempotent** (re-running `up` is a no-op) and
  must include a working `down`.
- Vector / Atlas Search indexes are NOT created by migrations — those must
  be applied via the Atlas UI or Atlas CLI per `apps/api/scripts/setup_indexes.py`.
- The CLI refuses to run against a URI that contains `prod` / `production`
  unless `MONGORAG_ALLOW_PROD=1` is exported. Production migrations run
  from CI inside the deployment job, after the backup has succeeded.

### 3.2 Postgres

- Migrations live under `supabase/migrations/` and run via the Supabase
  CLI in CI: `supabase db push --linked --include-all`.
- Never edit a previously applied migration. Always add a new file.

## 4. Recovery Procedures

For every scenario: **declare the incident first**, set up an incident
channel, and assign an Incident Commander before touching production.

### 4.1 Database corruption (MongoDB)

1. Pause writes by scaling the API to zero or enabling maintenance mode.
2. Identify the last good point-in-time from Atlas monitoring + app logs.
3. *Atlas > Backup > Restore* — select PITR, enter timestamp, restore into
   a NEW cluster (`mongorag-restore-YYYYMMDD`).
4. Validate the restore in the new cluster: row counts, recent docs,
   tenant counts. Cross-check `tenants` collection size against expected.
5. Update `MONGODB_URI` in production secrets to point at the restored
   cluster (or use Atlas live migration). Rotate the original cluster
   credentials before bringing the API back up.
6. Re-run `apps/api/scripts/setup_indexes.py` and recreate Atlas Vector /
   Search indexes from saved definitions (see `setup_indexes.py` footer).
7. Resume traffic. Post-incident review within 5 business days.

### 4.2 Accidental data deletion

Two scenarios depending on scope:

- **Single tenant, recent**: use Atlas PITR to restore into a scratch
  cluster, then export only that tenant's data
  (`mongoexport --query='{"tenant_id":"<id>"}'`) and re-import. **Never**
  `--drop` collections during restore — that wipes other tenants. Verify
  `tenant_id` filtering on every export and import command.
- **Cross-tenant or schema-wide**: full PITR per Section 4.1.

### 4.3 Service outage (control plane / Supabase)

1. Confirm outage via Supabase status page.
2. If outage > RTO, fail over: spin up a replacement Postgres (Supabase
   project clone, or temporary RDS) and `pg_restore` from latest archive.
3. Update `DATABASE_URL` in production secrets. Run `supabase db push`
   to verify schema.
4. Resume traffic.

### 4.4 Compromised API keys / leaked credentials

1. **Within 15 minutes**: rotate the affected secret(s) in Vercel + Atlas
   + Supabase. Old keys revoked immediately.
2. Audit: search Atlas + Supabase logs for the key's request signature,
   compute blast radius, list affected tenants.
3. If customer API keys are involved (`api_keys` collection): force-rotate
   per-tenant keys, notify affected tenants within 24 h.
4. If a backup credential was leaked: rotate `MONGODB_BACKUP_URI`,
   `POSTGRES_BACKUP_URL`, and any S3 IAM keys. Verify backup workflow
   still succeeds on the next manual run.
5. File a SEC-* incident issue with timeline, scope, and remediation.

## 5. Restore Drill (quarterly)

1. Trigger `Database Backup` workflow manually with `target=all`.
2. Download the latest artifact (or pull from S3).
3. Provision a STAGING-tagged cluster:
   - Mongo: `mongorag-restore-YYYYMMDD`
   - Postgres: `mongorag-restore-YYYYMMDD` Supabase project
4. Run:

   ```bash
   MONGODB_URI=<staging-restore-uri> ARCHIVE_PATH=./mongo-...archive.gz \
     ./scripts/backup/mongo_restore.sh

   DATABASE_URL=<staging-restore-url> ARCHIVE_PATH=./postgres-...dump \
     ./scripts/backup/postgres_restore.sh
   ```

5. Validate: tenant counts match production, sample queries return
   expected rows, indexes present, sample auth flow succeeds.
6. Tear down restore cluster. Record drill outcome (date, duration,
   issues, fixes) in `docs/runbooks/restore-drills.md`.

## 6. Incident Response Checklist

- [ ] Incident declared in #incidents (or chosen channel)
- [ ] Incident Commander assigned
- [ ] Status page updated
- [ ] Severity classified (SEV-1/2/3)
- [ ] Recovery procedure (Section 4) selected and started
- [ ] Backups verified before any destructive recovery action
- [ ] All recovery actions logged in incident channel
- [ ] Resolution announced; status page updated
- [ ] Post-incident review scheduled within 5 business days
- [ ] PIR doc created with: timeline, root cause, contributing factors,
      what went well, what went wrong, action items with owners + dates

## 7. Escalation Chain (Template)

Replace placeholders before going to production. Keep this section
synchronized with the on-call rota.

1. **Primary on-call engineer** — first responder, owns triage
2. **Secondary on-call engineer** — backup, takes over if primary
   unavailable within 15 minutes
3. **Engineering lead** — escalation point for SEV-1
4. **CTO / founder** — customer-impacting SEV-1 > 1 hour
5. **Atlas / Supabase support** — open a P1 ticket for SEV-1 platform
   issues; include cluster ID and incident timeline

## 8. Post-Incident Review Checklist

- [ ] Timeline reconstructed (UTC) from logs and chat
- [ ] Root cause identified (5 Whys minimum)
- [ ] Customer impact quantified (tenants affected, data lost, downtime)
- [ ] Was RPO met? Was RTO met?
- [ ] Action items: each has an owner and a due date
- [ ] Runbook updated with anything missing or wrong
- [ ] Tests added that would have caught the failure mode
