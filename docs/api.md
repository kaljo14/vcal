# API contract

All business routes use `/api/v1`, JSON, ISO dates and bearer authentication. OpenAPI at `/docs` is the executable contract. Lists use `offset` and `limit` (maximum 200). Errors have `error.code` and `error.message`; field validation returns `error.details`.

`GET /me`, `/me/dashboard`, `/me/balances`, `/me/ledger`; `PATCH /me/preferences`.

`POST /requests/preview` calculates working days and returns policy violations without persisting. `POST /requests` creates DRAFT or submits immediately with `submit=true`. Request fields: kind (`LEAVE`, `MOBILE`), start_date, end_date, portion (`FULL`, `AM`, `PM`), leave_type_id, location_type (`HOME`, `OTHER`, `ABROAD`), city, country, comment. Half-day ranges must be one date. `GET /requests` accepts status and scope (`mine`, `approvals`); `GET /requests/{id}`; `POST /requests/{id}/{submit,withdraw,cancel,approve,reject}` accept comment and override_reason. Approve/reject also resolve cancellation requests.

State machine: DRAFT → PENDING → APPROVED / REJECTED; DRAFT/PENDING → CANCELLED; APPROVED → CANCELLATION_REQUESTED → CANCELLED / APPROVED. Each transition is audited. Manager-required policies are default; no-approval policies pass through the same approval accounting service with a SYSTEM approval record.

`GET /calendar` and `/calendar/team/{id}` accept start, end, team_id, department_id, employee_id. Responses contain authorized availability only, holidays and daily statistics. Reports use start/end and optional `format=csv`.

Management endpoints: employees, departments, teams, schedules, holiday-calendars, holidays, leave-types, policies. `GET /employees` accepts `status=ACTIVE` or `status=INACTIVE`. Removing an employee sets their status to `INACTIVE`, blocking sign-in while retaining requests, balances and audit history; the Employees page can restore them. Active direct reports must be reassigned before a manager can be removed. Policies have kind (`leave`/`mobile`) and typed configuration. `POST /employees/{id}/adjustments`, `/employees/{id}/entitlements`, `/employees/{id}/carryover` mutate the auditable ledger with mandatory reason and idempotency key. `GET /employees/{id}/ledger` is restricted to HR or the employee. `GET /notifications`, `POST /notifications/{id}/read`, `GET /audit`, `GET/PATCH /settings` complete operations.
