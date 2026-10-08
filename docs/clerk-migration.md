# Keycloak → Clerk migration

## What changed

The browser uses the official `@clerk/vue` provider, Clerk sign-in and sign-out, and fresh session tokens for API requests. FastAPI verifies RS256 signatures against the exact configured Clerk instance's public JWKS, issuer, expiry, not-before time and allowed `azp` application origins. It requires a user/session subject and rejects pending or impersonated sessions. Standard session tokens need no audience template; optional `CLERK_AUDIENCE` enables explicit audience enforcement if you customize the session token.

Permissions remain in role_assignments. Clerk metadata, organization roles and email addresses do not grant access or automatically link employees. An authenticated Clerk user must have an exact subject match to an active internal employee. The existing `identity_provider_subject` column is retained; no structural database migration is needed.

## New environment

- `VITE_CLERK_PUBLISHABLE_KEY`: public Clerk key, compiled into the frontend.
- `CLERK_ISSUER`: exact HTTPS Frontend API origin, e.g. `https://example.clerk.accounts.dev` or the production custom Clerk domain.
- `CLERK_AUTHORIZED_PARTIES`: JSON array of exact app origins, no wildcards/trailing slash.
- `CORS_ORIGINS`: JSON array of allowed browser app origins.
- `CLERK_AUDIENCE`: empty by default. If set, add the same `aud` to the standard Clerk session-token customization. Do not use a custom JWT template that omits session claims.

The JWKS URL is derived as `CLERK_ISSUER + /.well-known/jwks.json`; it is never selected from unverified token contents. The API does not need `CLERK_SECRET_KEY`. Only the optional E2E test runner needs a Clerk development secret key for official testing helpers. Never place a secret key in a VITE_ variable or source control.

The Keycloak container, realm import, database initialization and JS adapter are removed. Existing database volumes, including any legacy Keycloak database inside them, are not deleted by this migration. The old Keycloak role/database and backups can be retired separately after a verified cutover; this project does not execute that destructive cleanup.

## Preserve existing employee records

1. Back up the application database and the old identity provider. Stop app/worker writes for the cutover. Keep the PostgreSQL volume and employee IDs.
2. Create/import the users in your Clerk application using an authorized Clerk migration flow. Password hash/enterprise SSO migration is provider-side work; this command only links already-created identities. Do not email-match accounts automatically.
3. Prepare a private JSON mapping based on verified employee records:

   ```json
   [
     {
       "employee_number": "WL-002",
       "current_subject": "00000000-0000-4000-8000-000000000002",
       "clerk_user_id": "user_ACTUALCLERKID"
     }
   ]
   ```

   For a newly seeded unlinked employee, current_subject is `unlinked:employee` (similarly manager/hr/admin/colleague). For an existing installation, use the actual stored old subject. Map every required employee, including the administrator.
4. Run the dry-run against the existing application database using the trusted backend environment:

   ```sh
   cd backend
   python -m app.migrate_identities --mapping /absolute/private/path/identity-map.json
   python -m app.migrate_identities --mapping /absolute/private/path/identity-map.json --apply
   ```

   Container alternative (set Clerk environment first, with PostgreSQL already running):

   ```sh
   docker compose run --rm --no-deps \
     -v /absolute/private/path/identity-map.json:/run/identity-map.json:ro \
     api python -m app.migrate_identities --mapping /run/identity-map.json
   # Repeat with --apply after reviewing the dry-run.
   ```

   The command validates all current subjects and target uniqueness before mutating anything. The complete batch is transactional, uses employee locks, and records an audit event for each link. Reapplying the same mapping is a no-op. Employee primary keys, roles, reporting relationships, request ownership and ledger entries are preserved.
5. Set Clerk environment values, rebuild the frontend/API, and start the revised composition. Validate sign-in as employee, manager, HR and admin, then verify one complete approval and cancellation workflow and unchanged ledger totals.
6. Stop/remove the old Keycloak container only after successful cutover. Retain its database/backup for your approved rollback period. A rollback requires restoring the verified old identity mapping and old authentication deployment, not resetting the HR database.

For a **fresh production database**, use the existing explicit bootstrap command with a Clerk `user_…` subject instead. It refuses to run if any employee exists.

## Session and deployment notes

Clerk manages browser cookies and token refresh. Workleave sends only bearer authorization to its REST API; it does not authenticate API requests from Clerk cookies. Its session gate clears employee/server caches on sign-out/account changes and prevents stale token results being used after an account switch. Deactivating an internal employee blocks access immediately; provider-side revocation of an already-issued signed token takes effect no later than token expiry.

Use Clerk restricted/invitation-only sign-up as appropriate for the organization. Signing up at Clerk alone never creates an employee account. Configure organizational SSO/MFA in Clerk. Application permissions remain independent of Clerk organization roles. This deployment intentionally requires `azp`, even though Clerk can omit it for privacy-stripped Origin requests; such requests fail closed.

Nginx CSP permits the configured Clerk Frontend API, Clerk image/telemetry/protection endpoints and Cloudflare challenge endpoints required by the SDK. Update the exact configured Frontend API when switching development/production instances. PWA caches never include Clerk requests or application API responses.

## Verification limits

The migration CLI and local authorization/claim rules can be exercised without a Clerk account. Live Clerk sign-in requires your real publishable key, Frontend API URL and linked test users. Cryptographic JWT, PostgreSQL, Docker and browser integration tests remain release gates if unavailable in the local execution environment.

References: [Clerk Vue quickstart](https://clerk.com/docs/vue/getting-started/quickstart), [session token claims](https://clerk.com/docs/guides/sessions/session-tokens), [manual JWT verification](https://clerk.com/docs/guides/sessions/manual-jwt-verification), [CSP configuration](https://clerk.com/docs/guides/secure/best-practices/csp-headers), [Playwright helpers](https://clerk.com/docs/guides/development/testing/playwright/test-helpers).
