# Workleave

Employee self-service for vacation, mobile work, approvals and HR administration. Vue 3 + TypeScript, FastAPI, PostgreSQL and **Clerk** authentication in a modular monolith. All screens use the backend; there is no demo-login bypass or browser-local employee database.

## Configure Clerk and start

1. Create a Clerk development application. Copy its **publishable key** and **Frontend API URL** from the API Keys page.
2. Copy `.env.example` to `.env` and set:

   ```dotenv
   VITE_CLERK_PUBLISHABLE_KEY=pk_test_YOUR_PUBLIC_KEY
   CLERK_ISSUER=https://YOUR_INSTANCE.clerk.accounts.dev
   CLERK_AUTHORIZED_PARTIES=["http://localhost:3000","http://localhost:5173"]
   ```

   Both values must belong to the same Clerk instance. Keep `CLERK_AUDIENCE` empty for standard Clerk session tokens. No Clerk secret key is needed by the application API or frontend.
3. Create your test accounts in Clerk. For a fresh development database, optionally populate `CLERK_SEED_EMPLOYEE_ID`, `CLERK_SEED_MANAGER_ID`, `CLERK_SEED_HR_ID`, `CLERK_SEED_ADMIN_ID`, and `CLERK_SEED_COLLEAGUE_ID` with their `user_…` identifiers. These identities receive the corresponding sample employee roles. Configure the allowed application origins and sign-in methods in Clerk.
4. Run:

   ```sh
   docker compose up --build -d --wait --wait-timeout 300
   ```

Open **http://localhost:3000** and select **Sign in with your company** to open Clerk. The sample employee is Jamie Parker (`WL-002`), manager is Alex Morgan (`WL-001`), HR is Sam Rivera (`WL-003`), administrator is Taylor Chen (`WL-004`). Accounts without supplied Clerk IDs remain unlinked and cannot log in. Passwords and SSO are managed in Clerk; there are no bundled login credentials.

**Existing database:** follow [the Clerk migration guide](docs/clerk-migration.md). Changing seed environment variables does not relink existing employees. The explicit mapping command preserves employee IDs, balances, policies and history. Do not reset the database or its volume.

Requires Docker with Compose v2, roughly 3 GB memory, and registry access. Startup applies Alembic migrations, seeds the development organization if empty, grants restricted database permissions, and starts API, worker and frontend. PostgreSQL persists in `postgres_data`. `docker compose down` preserves data; `down -v` destroys it.

- API docs: http://localhost:8000/docs
- Liveness/readiness: http://localhost:8000/health and http://localhost:8000/ready
- Troubleshooting: `docker compose ps` and `docker compose logs api migrate grants web`

## First workflow

Sign in with the linked employee account and submit a future vacation request. In a separate browser profile, sign in with the linked manager and approve it through **Approval inbox**. The employee’s balance and shared calendar update transactionally. Mobile requests use the same workflow, with policy quotas and HR review for international work. Approved requests need cancellation approval before their balance/quota is restored.

HR can maintain employees, policies, holidays, grants, adjustments, carryover and reports. Administrators assign internal roles and manage teams and settings. Clerk authenticates the user; database roles remain the sole source of HR permissions. Clerk users without a linked active employee get no application access.

## Local development

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e './backend[dev]'
docker compose up -d postgres
# Export backend DATABASE_URL, CLERK_ISSUER and allowed origins, or use backend/.env.
cd backend
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

In another terminal:

```sh
cd frontend
cp .env.example .env.local
# Set VITE_CLERK_PUBLISHABLE_KEY in .env.local.
npm ci
npm run dev
```

Vite serves http://localhost:5173 and proxies `/api` to port 8000. Backend settings load from environment or `.env` in the current working directory. Frontend environment changes require a restart/rebuild.

## Verification

```sh
cd backend
DATABASE_URL=sqlite:// pytest -q
TEST_DATABASE_URL=postgresql+psycopg://test:test@localhost:5432/workleave_test pytest -q -m postgres
cd ../frontend
npm ci
npm test
npm run build
```

For real Clerk browser tests, use a disposable development Clerk instance, linked employee/manager/HR users and an isolated application database. Set `CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY` (test-only runner secret), `E2E_EMPLOYEE_EMAIL`, `E2E_MANAGER_EMAIL`, `E2E_HR_EMAIL`, then:

```sh
cd e2e
npm install
npx playwright install chromium
npm test
```

Clerk’s official testing helper establishes real Clerk sessions; requests, policies, approvals, accounting and calendars use the actual API and database. No application API responses are mocked. Browser tests reject production Clerk keys. In GitHub Actions, configure the corresponding variables and `CLERK_TEST_SECRET_KEY` secret, then set `CLERK_E2E_ENABLED=true`. The hosted-auth E2E job is explicitly skipped until configured; other tests/builds still run.

## Docker Hub releases

GitHub Actions publishes `kaljo14/vcal-api` and `kaljo14/vcal-web` for tags such as `v1.2.3`, using the image tag `1.2.3`. Configure repository secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`, plus repository variable `VITE_CLERK_PUBLISHABLE_KEY` for the web build. The Docker Hub account must be able to push both repositories.

## Accounting and operational decisions

- Vacation is charged on approval, separately by year. Pending leave is displayed separately. Credit lots expire and are consumed in expiry order. Cancellation restores original credits without extending expiry.
- AM/PM half days can coexist only in complementary slots. Working days derive from assigned schedules and holiday calendars.
- Pending mobile work reserves quota. PostgreSQL employee locks serialize conflict checks, quotas and balance changes.
- Entitlements/carryover are explicit idempotent HR operations, also callable by an external scheduler. Monthly installments sum to the annual allowance. No statutory entitlement/proration is hardcoded.
- Approved day snapshots remain fixed after schedule/holiday changes; pending requests are recalculated on approval.
- Bulgarian seed holidays are illustrative fixed dates, not a statutory calculator. HR must verify/add movable and substitute holidays.
- Team calendars omit private leave reasons. HR and administrators do not automatically receive private request comments.
- TanStack Query Core is wrapped by a small Vue composable; Pinia owns UI/session state, FullCalendar provides calendar views, and Headless UI supplies accessible dialogs.
- SMTP uses a transactional outbox with backoff and stable Message-ID. Delivery is at-least-once; in-app notifications remain authoritative.
- The PWA caches only static application assets. Clerk manages its authentication cookies/session lifecycle; Workleave never persists bearer tokens or employee API responses in its service worker. Account changes cancel queries and clear the in-memory employee cache.

See [implementation status](docs/implementation.md) for exact checks and remaining environment limits. Docker, live Clerk, PostgreSQL concurrency and full browser verification must pass before production use.

## Documentation

- [Clerk setup and existing-account migration](docs/clerk-migration.md)
- [Architecture](docs/architecture.md)
- [API contracts](docs/api.md) and [generated OpenAPI](docs/openapi.json)
- [Implementation status](docs/implementation.md)
- [Deployment, monitoring and backup/restore](docs/operations.md)
- [Security and retention procedures](docs/security.md)
