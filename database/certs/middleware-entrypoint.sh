#!/bin/sh
# SPDX-License-Identifier: MIT
#
# Entrypoint wrapper for the middleware service (SRS NFR-SEC-001, Gateway R2).
# libpq refuses a client key that is readable by group or others. Windows bind mounts report
# every file with those bits set, so the key is copied from the read-only mount
# /etc/biosync/db-tls/client.key into a private directory with mode 0600, and DB_SSLKEY points
# at the copy (/tmp/biosync-db-tls/client.key). The application then starts with the command
# given in docker-compose.yml.
#
# Arguments are the application command line (for example: uvicorn api.main:app ...).

set -eu

SRC=/etc/biosync/db-tls
DST=/tmp/biosync-db-tls

mkdir -p "$DST"
chmod 0700 "$DST"
install -m 0600 "$SRC/client.key" "$DST/client.key"

exec "$@"
