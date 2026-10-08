# Security and privacy

## Authorization model

Clerk bearer session tokens are validated for RS256 signature, exact issuer, required session claims, expiration/not-before time and permitted application origins (`azp`). Audience is validated when CLERK_AUDIENCE is configured; standard Clerk session tokens have no audience by default. Pending and impersonated sessions are rejected. The Clerk user ID must map to an active employee. Database roles are authoritative; Clerk metadata and organization roles never grant HR permissions. Clerk manages its browser session cookies; Workleave does not persist bearer tokens. The REST API authenticates only Authorization headers, not cookies, so cookie-session CSRF tokens are not required by these endpoints. Account linking is explicit, never based solely on email.

Owners access their own requests and balances. Managers approve direct reports, never themselves. HR sees organization reports and operational employee fields; private employee comments are omitted unless HR is also the assigned manager. International mobile work can require HR. Other HR approval overrides require a policy flag and mandatory reason. Administrators assign roles and configure the organization without implicit access to private leave comments or organization-wide balances.

Team calendar output contains generic availability, without comments, leave category, city/country or ledger data. Query filters only narrow the server-authorized population. CSV exports escape formula-leading cells. Validation errors omit submitted input values. Audit listing strips free-text reasons; HR ledger entries preserve documented adjustment reasons under restricted access.

## Personal-data handling

General request notes explicitly discourage medical details. Avoid putting diagnoses or medical attachments in this application; it has no medical-document workflow. Limit employee data to fields required for scheduling, identity, communication and accounting. Local accounts, seed holidays and policy values are examples, not legal or compliance advice.

Organization retention_years records the policy; it does not autonomously destroy accounting data. The following reviewed operations procedure is required because employment-record retention and legal holds vary:

1. An authorized data owner identifies an employee or completed retention period and checks applicable obligations/holds with the organization’s responsible reviewer.
2. Deactivate the internal account and identity provider login immediately when access should end. Reassign direct reports and resolve open requests. Clerk session tokens are short-lived; the API additionally checks active employee status on every request.
3. Export approved subject-access data through a restricted operations environment. Include the employee profile, their own ledger, requests, decisions and notifications; redact unrelated employees’ information. Never send a whole database dump as a subject export.
4. For an approved erasure/minimization request, take an encrypted recovery backup and document the scope, authority and execution plan. Remove or anonymize personal profile fields, identity subject, request comments, approval comments, old notifications/outbox and free-text reasons. Preserve only the minimum required pseudonymous ledger/audit references where retention is necessary. Use owner credentials because the application role cannot rewrite financial/audit history.
5. Run the operation first against a restored test copy. Verify foreign keys, retained ledger totals, access revocation and reports. Execute the reviewed transaction in a maintenance window, record a non-sensitive operational audit event, and test sign-in denial afterwards.
6. Apply the same approved lifecycle to exports, logs, identity-provider records and backups. Expire backups according to policy; restore procedures must reapply later erasure decisions.

This release deliberately provides no one-click irreversible purge. Retention configuration does not imply statutory compliance. Authentication system credentials, issuer and trusted origins are deployment settings, not editable through an administrator browser form.

## Known operational limits

No external penetration test or legal compliance certification is implied. Production TLS, verified holiday imports, provider MFA, SMTP credentials, scheduled entitlement invocation, off-host backup storage and alert routing are deployment responsibilities. Dependency audit gates require registry connectivity. FullCalendar office days are derived planning data, not a time clock or proof of attendance.
