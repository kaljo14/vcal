# Implementation and verification record

A checked implementation item means the code exists and is connected. It does not assert that the deployment was verified in this environment.

## Phase 1 — foundation

- [x] Monorepo, FastAPI application, Vue shell and role-specific navigation
- [x] PostgreSQL schema, frozen initial Alembic revision and development seed
- [x] Clerk Vue session integration, JWT verification and internal role assignments
- [x] Persistent Compose database, Clerk configuration, API and worker containers
- [x] Employee, team, department, holiday calendar and schedule entities
- [ ] Live Clerk login and full container startup verification (Docker unavailable)

## Phase 2 — request workflows

- [x] Vacation/mobile forms, server previews, database persistence and history
- [x] Explicit state transitions, manager approval/rejection and no self-approval
- [x] Date conflicts, AM/PM slots, drafts, withdrawal and cancellation review
- [x] API-level vacation approval → ledger debit → calendar → cancellation reversal tested
- [ ] Browser-level Clerk workflow verification (scenario updated; needs Clerk test keys, linked users and available servers)

## Phase 3 — accounting and policy

- [x] Annual balance buckets, cross-year debit rollback and expiring credit allocations
- [x] Custom schedules, holidays, half days, unpaid and configurable leave categories
- [x] Quotas, weekday/location/country restrictions, notice and international HR review
- [x] HR employee/policy management, idempotent grants, adjustments and carryover
- [x] Monthly installments sum exactly to the annual allowance
- [x] Employee/request locking, immutable ledger/approval/audit database grants
- [ ] Real PostgreSQL concurrent approval verification (test written, requires test database)

## Phase 4 — dashboard, calendar and reports

- [x] API-backed employee dashboard and upcoming/pending/recent requests
- [x] Approval inbox, team roster and shared availability
- [x] FullCalendar month/week/day views, team/department/employee filters
- [x] Derived office presence, half-day availability and privacy-safe event details
- [x] Leave, mobile, balance, pending and availability reports; safe CSV export

## Phase 5 — notifications and UI

- [x] In-app notifications, read state and email preferences
- [x] SMTP transactional outbox, stable message IDs, backoff and delivery state
- [x] Responsive sidebar, accessible dialogs, feedback, loading/empty/error states
- [x] Static-asset PWA manifest/service worker; no employee API caching
- [ ] Live SMTP delivery and desktop/mobile visual verification (service ports blocked)
- [ ] Optional dark mode and calendar synchronization (outside the required first release)

## Phase 6 — operations and release verification

- [x] Backend, frontend and real-service Playwright test code
- [x] CI with PostgreSQL, migrations, lint, dependency audits, builds and browser workflows
- [x] Production Compose overlay, explicit first-admin provisioning, runtime database grants
- [x] Deployment, privacy/retention, monitoring, backup and restore documentation
- [ ] Full CI run, dependency vulnerability audit, image build and restore rehearsal
- [ ] Production identity-provider, TLS, SMTP and verified holiday configuration

## Tests executed in this environment

| Check | Result |
| --- | --- |
| Backend pytest against real ephemeral SQLite | **49 passed, 3 skips** |
| Frontend Vitest + Vue Test Utils | **18 passed** |
| Vue TypeScript check and Vite production build | **Passed** |
| Clean `npm ci` using committed lockfile | **Passed**, with offline dependency cache |
| Development Compose configuration validation | **Passed** |
| Production Compose configuration validation | **Passed** with example HTTPS environment |
| Python syntax compilation | **Passed** |
| OpenAPI generation | **Passed**, 43 operations |
| JWT signature suite | Skipped locally: PyJWT unavailable in offline cache |
| Alembic round-trip suite | Skipped locally: Alembic unavailable in offline cache |
| PostgreSQL concurrency suite | Skipped locally: test database unavailable |
| Ruff CLI | Not executed locally; configured in CI |
| Playwright / live Clerk / SMTP / containers | Not executed: Docker/socket/listening-port restrictions |

## Environment constraints and decisions

The repository was initially empty. Shell registry DNS/network access and Docker socket access were denied, and Vite could not bind a local listening port (`EPERM`). Dependencies available in existing local caches were used to execute tests; no sandbox permissions or authentication bypass was added to the application. The temporary Python test environment used Python 3.12, FastAPI 0.121.3, SQLAlchemy 2.0.44 and Pydantic 2.13.5. Production installs from `backend/pyproject.toml`; run CI to test the fully resolved dependency set.

Frontend dependencies are pinned in package-lock.json with integrity hashes. Some dependencies/overrides use official npm tarball URLs because package metadata was absent from the offline cache. This is reproducible through `npm ci`, but version/security review remains a release gate. TanStack Query Core is integrated through a small Vue composable instead of the separate Vue Query adapter package; this is the one intentional frontend library substitution.

No end-to-end, PostgreSQL locking, live SSO, SMTP or production readiness result is inferred from passing SQLite/component tests. The application must pass the remaining deployment checks before it is described as production-ready.

## Clerk migration

Keycloak frontend dependency, container, realm and database initialization removed. Official @clerk/vue installed with lockfile updates. API accepts only Clerk user sessions from the configured issuer and allowed app origins. Standard session tokens are supported without a custom audience. Employee identity mapping is explicit, atomic, audited and dry-run by default; schema/ledger/role changes are not required. Clerk account values and live-user mapping must be supplied for a real cutover. See clerk-migration.md.

Clerk migration verification: 49 backend tests passed (3 integration suites skipped), 18 frontend tests passed, TypeScript/Vite build passed, and development/production Compose configurations validated with placeholder public Clerk values. No live Clerk instance or employee mappings were supplied, so real account cutover and hosted sign-in have not been executed.
