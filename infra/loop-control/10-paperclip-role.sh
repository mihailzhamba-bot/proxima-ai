#!/bin/sh
set -eu
# Secret never enters argv or logs. psql quotes the env value as an SQL literal.
IFS= read -r LOOP_PAPERCLIP_PASSWORD < /run/secrets/paperclip_postgres || [ -n "${LOOP_PAPERCLIP_PASSWORD:-}" ]
export LOOP_PAPERCLIP_PASSWORD
psql -v ON_ERROR_STOP=1 --username postgres --dbname postgres <<'SQL'
\getenv loop_password LOOP_PAPERCLIP_PASSWORD
CREATE ROLE paperclip_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'loop_password';
CREATE DATABASE paperclip OWNER paperclip_runtime;
SQL
unset LOOP_PAPERCLIP_PASSWORD
