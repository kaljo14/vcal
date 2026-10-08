#!/bin/sh
set -eu

psql -h postgres -U workleave_owner -d workleave \
  -v ON_ERROR_STOP=1 -v runtime_password="$APP_DB_PASSWORD" \
  -f /grants.sql
