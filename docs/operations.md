# Production deployment and operations

## Release gate

Run the complete CI pipeline and a restore rehearsal before handling employee data. The local execution sandbox could not run containers, PostgreSQL, Alembic, live Clerk, SMTP or Playwright. Passing the local unit/component tests is not a substitute for those deployment checks. Review current advisories and update pinned dependencies/container images before a production release; registry access was unavailable during implementation.

## Configuration

Use Docker Compose >=2.24.4. Provision an empty PostgreSQL volume and a TLS reverse proxy. Keep ports 3000 and 8080 bound to loopback and expose them only through that proxy. Use HTTPS app/identity origins, strong independent credentials, encrypted storage/backups and a managed secret store. Database passwords embedded in URLs must be URL-safe or encoded. Do not reuse the example passwords.

Apply `compose.production.yaml` over the base composition. It disables development seeding, removes exposed database/API ports and validates HTTPS Clerk configuration. Clerk is hosted; no identity-provider container is needed. Configure TLS/DNS separately.

```dotenv
ENVIRONMENT=production
VITE_CLERK_PUBLISHABLE_KEY=pk_live_YOUR_PUBLIC_KEY
CLERK_ISSUER=https://clerk.example.com
CLERK_AUTHORIZED_PARTIES=["https://people.example.com"]
CORS_ORIGINS=["https://people.example.com"]
CLERK_AUDIENCE=
```

The publishable key and Frontend API URL must be from the same Clerk instance. No Clerk secret key belongs in the runtime frontend/API. Rebuild the frontend when changing its publishable key. Configure allowed app origins, restricted sign-up, SSO and MFA in the Clerk Dashboard. Refer to [the Clerk migration guide](clerk-migration.md) before switching an existing database.

```sh
docker compose -f compose.yaml -f compose.production.yaml up --build -d --wait --wait-timeout 300
```

For an empty production database, explicitly provision the first employee administrator using the corresponding Clerk user ID:

```sh
docker compose -f compose.yaml -f compose.production.yaml run --rm api \
  python -m app.bootstrap --subject user_ACTUALCLERKID \
  --email admin@example.com --first-name First --last-name Last \
  --organization 'Your Company'
```

This refuses to run once any employee exists. It assigns EMPLOYEE, HR and ADMIN to the initial provisioning account. Separate those responsibilities after onboarding designated owners. Review policies, schedules, verified holidays and employee entitlements before accepting requests. Existing databases use the atomic identity-mapping CLI, never reseeding or volume resets.

Configure the TLS proxy to set HSTS, preserve Host, limit request sizes and restrict administrative access. Nginx CSP includes the configured Clerk Frontend API and the SDK's required protection/image hosts. Configure shared ingress rate limiting before scaling beyond the single API process.

## Database permissions and upgrades

`workleave_owner` is the migration/provisioning database owner. The API/worker use `workleave_app`, which cannot create schema objects, alter migrations, or update/delete ledger, allocation, approval or audit history. Clerk identity storage is managed by Clerk. Keep owner credentials out of the runtime API environment.

Before each upgrade: back up the application database, build reviewed images, stop API/worker writes, run the migration service with owner credentials, reapply `infra/docker/grants.sql` for new tables, then restart services and test readiness. The initial revision contains a frozen schema independent of current application models; future migrations must describe explicit incremental changes. `alembic check` in CI detects uncommitted model changes. For rollback, prefer a reviewed forward fix; a destructive downgrade is not an operational backup strategy.

## Backups

Use owner credentials only in the trusted operations environment. Restrict the backup directory to its operator; encrypt files before copying them off-host. Backup retention is an organizational choice.

```sh
umask 077
mkdir -p backups
docker compose exec -T postgres pg_dump -U workleave_owner -d workleave -Fc > backups/workleave.dump
```

A restore rehearsal must use an isolated empty PostgreSQL instance. Create the required database roles first, then restore the application archive with their ownership/privileges preserved. Example for an isolated instance that already has initialized roles and empty target databases:

```sh
# RESTORE TARGET ONLY — overwrites objects in that isolated target database.
docker compose exec -T postgres pg_restore -U workleave_owner -d workleave --clean --if-exists < backups/workleave.dump
```

Verify migration version, row counts, employee sign-in, representative ledger totals and a reversible request workflow. Record restore duration, recovery point and checks. Never test a restore over your only production database.

## Monitoring and email

- `/health`: process liveness. `/ready`: database reachability and migration table availability. Neither claims that external Clerk or SMTP is reachable.
- JSON HTTP logs include request ID, method, status and duration, without tokens, URLs, bodies or personal details. Alert on elevated 5xx, latency, disk usage, failed backups and database connection exhaustion.
- Inspect email_deliveries for old PENDING/RETRY rows and FAILED rows. After repairing SMTP configuration, a trusted operator can reset FAILED deliveries to RETRY; stable Message-ID helps downstream deduplication. Do not log recipient addresses or message bodies.
- Worker holds a row lock while sending one message (15-second SMTP timeout). Multiple workers safely claim different rows with SKIP LOCKED. SMTP failure commits retry state separately from the approval transaction.
- The built-in write limiter is process-local. Keep the documented single API process or add shared ingress rate limiting before scaling horizontally. A reverse-proxy rate limit also protects endpoints against arbitrary invalid tokens.
- Workflows lock an employee then a request. Global policy edits lock employees in ID order; use the same ordering for future ledger/schedule operations.
