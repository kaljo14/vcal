# Workleave architecture

One organization, one modular FastAPI application, one PostgreSQL database, and a Vue 3 PWA. The API is the authority for permissions, calculations and transitions. The browser uses the official Clerk Vue provider. Clerk owns authentication cookies/session lifecycle; Workleave requests short-lived session tokens for bearer API calls. Internal roles are managed in the database, never accepted from client claims.

## Transaction boundaries

Every employee request mutation locks that employee row first, then the request row. All balance adjustments, holiday/schedule changes and policy changes use the same employee lock ordering. This serializes conflict checks, quotas and ledger debits for each employee under PostgreSQL READ COMMITTED. Approval checks current policy and funds, while request days are the durable accounting snapshot. Cancellation reverses the original ledger entries exactly once. Negative ledger entries have a unique request/year key. Pending leave is reserved for display only; approval is the point at which funds are consumed.

Annual balances are separate buckets per leave type/year. Cross-year requests debit the appropriate buckets. Carryover is a separately recorded credit with an optional expiry; consumption uses expiring credits first. No statutory entitlement is encoded. Half days use AM/PM slots, so complementary halves can coexist and identical halves cannot overlap.

## Data model

Departments → teams → employees; employees reference manager, schedule, leave and mobile policies. Schedules reference holiday calendars. Typed request detail tables, materialized request days, approval records, immutable balance ledger, audit events and notification outbox complete the model. Foreign keys, check constraints and unique keys enforce basic integrity. Alembic owns schema changes.

## Boundaries

Employees see their own requests and balances. Managers see direct reports. Calendar projections expose only names, dates and availability. HR manages employee/policy data and reports but does not receive request comments. Only the owner and assigned direct manager see private comments. HR exceptions require an explicit policy flag and mandatory justification; self-approval remains prohibited. Administrators assign roles and organization settings, without implicit access to private absence details.

## Deployment

Nginx serves the SPA and proxies `/api` to FastAPI. PostgreSQL has a persistent volume; Clerk hosts the identity provider. An independent worker polls a transactional email outbox; SMTP outages never roll back workflows. Delivery is at-least-once with stable Message-ID, retry backoff and row locking, not a claim of exactly-once SMTP delivery. Service worker caches static application assets only, never employee API data.

## Tradeoffs

SQLite is allowed for fast unit tests, not production or concurrency verification. PostgreSQL integration tests exercise real row locks. No distributed cache or queue is needed for this release. Accrual/carryover are explicit idempotent HR operations, with the same service callable by an external scheduler. No automatic inference of country compliance or public holiday substitutions. HR must review imported holidays.

## References

- https://clerk.com/docs/vue/getting-started/quickstart
- https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- https://fullcalendar.io/docs
