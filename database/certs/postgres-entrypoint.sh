#!/bin/sh
# SPDX-License-Identifier: MIT
#
# Entrypoint wrapper for the PostgreSQL service (SRS NFR-SEC-001, Gateway R2).
# Copies the server certificate, server key, and CA certificate from the read-only mount
# /etc/biosync/tls-src into /var/lib/postgresql/tls with postgres ownership. The key is set to
# mode 0600, because PostgreSQL refuses a key that is readable by group or others, and Windows
# bind mounts report every file with those bits set. Then the official image entrypoint runs.
#
# Arguments are the PostgreSQL command line (for example: postgres -c ssl=on ...).

set -eu

SRC=/etc/biosync/tls-src
DST=/var/lib/postgresql/tls

mkdir -p "$DST"
install -m 0600 -o postgres -g postgres "$SRC/server.key" "$DST/server.key"
install -m 0644 -o postgres -g postgres "$SRC/server.crt" "$DST/server.crt"
install -m 0644 -o postgres -g postgres "$SRC/ca.crt" "$DST/ca.crt"
chown postgres:postgres "$DST"

exec docker-entrypoint.sh "$@"
