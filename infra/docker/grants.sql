-- The init script only runs for a brand-new PostgreSQL data directory.
-- Reconcile the runtime role here as well so an existing volume can start.
SELECT 'CREATE ROLE workleave_app LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'workleave_app')
\gexec
ALTER ROLE workleave_app PASSWORD :'runtime_password';
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE workleave TO workleave_app;
GRANT USAGE ON SCHEMA public TO workleave_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO workleave_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO workleave_app;
REVOKE UPDATE, DELETE ON leave_balance_ledger, ledger_allocations, approvals, audit_logs FROM workleave_app;
REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM workleave_app;
