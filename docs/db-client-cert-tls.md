# SPDX-License-Identifier: MIT
# Database client-certificate TLS (SRS NFR-SEC-001, Gateway R2)

Origin: BioSync-Gateway docs/db-client-cert-tls.md and nginx/generate-certs.sh (adapted).
Deliverable for DEVELOPMENT_PLAN.md Phase 1 task 1.4. The change record is
SNDEV/docs/impl-2026-10-14-r2-tls.md.

The middleware connects to PostgreSQL over TLS and presents a client certificate. The server
accepts network connections only over TLS and only with a client certificate signed by the
BioSync CA. The role password is still required.

## 1. Defaults

| Setting | Value | Where it is set |
|---------|-------|-----------------|
| `DB_SSLMODE` when unset or empty | `verify-full` in every `ENVIRONMENT` | `middleware/database.py` |
| `DB_SSLMODE` in the compose stack | `verify-full`, fixed in the file | `docker-compose.yml`, middleware service |
| Server rule | `hostssl ... clientcert=verify-full` | `database/postgres/pg_hba.conf` |
| Server TLS | `ssl=on`, certificate, key, and CA set | `docker-compose.yml`, postgres service |

`middleware/database.py` passes `sslmode` to libpq on every connection, including `disable`
and `prefer`. An explicit `DB_SSLMODE` overrides the default. A value that is not a libpq
sslmode stops the module at import. An empty value is treated as unset.

Test runs set `DB_SSLMODE=prefer` in `middleware/tests/conftest.py` and `vv/tests/conftest.py`
with `setdefault`, so an exported value still wins.

## 2. Generate the certificates

Run the generator once per environment before the first `docker compose up`.

Windows (Git for Windows bash, which provides OpenSSL):

```
& "C:\Program Files\Git\bin\bash.exe" database/certs/generate-certs.sh
```

Linux or macOS:

```
./database/certs/generate-certs.sh
```

The generator writes these files to `database/certs/out/`. The directory is gitignored by
`database/certs/.gitignore`.

| File | Purpose |
|------|---------|
| `ca.crt`, `ca.key` | BioSync CA. Signs the server and client certificates. |
| `server.crt`, `server.key` | PostgreSQL server certificate. SAN: `localhost`, `postgres`, `127.0.0.1`. |
| `client.crt`, `client.key` | Middleware client certificate. CN is the database role. |

Environment variables for the generator:

* `PG_CLIENT_CN` sets the client CN. The default is `surgitwin`, which matches the
  `POSTGRES_USER` default. Set it to the role the middleware connects as.
* `CERT_DAYS` sets the validity in days. The default is 365.
* `FORCE=1` replaces existing keys. Without it, the generator stops when `ca.key` exists.

The client CN must equal the role name. PostgreSQL with `clientcert=verify-full` compares the
certificate CN with the user name. The Gateway document described this rule as chain-only
verification. It is not. Chain-only verification is `clientcert=verify-ca`.

The CA key stays on the host. The compose stack mounts `ca.crt`, `server.crt`, and `server.key`
into the postgres container, and `ca.crt`, `client.crt`, and `client.key` into the middleware
container. `ca.key` is not mounted into any container.

Private keys are never committed. Regenerate the files per environment.

## 3. Server enforcement (`pg_hba.conf`)

`database/postgres/pg_hba.conf` contains these rules:

```
local      all       all                  trust
hostssl    all       all   0.0.0.0/0      scram-sha-256  clientcert=verify-full
hostssl    all       all   ::/0           scram-sha-256  clientcert=verify-full
```

A plaintext TCP connection matches no rule and is rejected with `no pg_hba.conf entry ... no
encryption`. A TLS connection without a client certificate is rejected with `connection requires
a valid client certificate`. A TLS connection with a valid certificate whose CN differs from the
role is rejected. The server log reports that case as `password authentication failed`, because
the CN check runs under the password method.

The `local` row is trust for administration over the Unix socket inside the container, for
example `docker exec ... psql` for migrations and test database creation. Network clients do not
reach the socket.

## 4. Compose wiring

The postgres service runs `database/certs/postgres-entrypoint.sh` before the official image
entrypoint. The script copies the server key, server certificate, and CA into
`/var/lib/postgresql/tls` with postgres ownership and mode 0600 for the key. PostgreSQL refuses a
key that is readable by group or others, and Windows bind mounts report every file with those
bits set. The server command sets `ssl=on`, `ssl_cert_file`, `ssl_key_file`, `ssl_ca_file`, and
`hba_file=/opt/biosync/pg_hba.conf`.

The middleware service runs `database/certs/middleware-entrypoint.sh`. The script copies the
client key to `/tmp/biosync-db-tls/client.key` with mode 0600, and `DB_SSLKEY` points there. The
environment sets:

```
DB_SSLMODE=verify-full
DB_SSLROOTCERT=/etc/biosync/db-tls/ca.crt
DB_SSLCERT=/etc/biosync/db-tls/client.crt
DB_SSLKEY=/tmp/biosync-db-tls/client.key
```

The compose publish for postgres is still `127.0.0.1:5432:5432`.

If a mounted certificate file is missing, Docker creates an empty directory at that path, and the
wrapper stops with an error. Run the generator before `docker compose up`.

## 5. Running the stack

```
docker compose config -q
docker compose up -d postgres middleware
```

`docker compose up` recreates a container when its configuration changes. A postgres container
that predates this change keeps its plaintext configuration until it is recreated. Recreate it
only after the other users of that database are finished.

## 6. Host-side connections and test overrides

The 5432 container used by the host qualification tests is a plaintext server and does not load
this configuration. Its `ssl` setting is `off`. The DB-gated tests keep working because the test
conftest sets `DB_SSLMODE=prefer`. Set `BIOSYNC_TEST_DATABASE_URL` to a plaintext URL and leave
`DB_SSLMODE` unset in the shell, or keep the conftest default.

To run the DB-gated tests against the TLS server, put the TLS options in the URL. Forward slashes
keep the paths valid in the URL on Windows:

```
BIOSYNC_TEST_DATABASE_URL=postgresql+psycopg2://surgitwin:PASSWORD@127.0.0.1:5433/surgitwin_tls_test?sslmode=verify-full&sslrootcert=I:/path/to/database/certs/out/ca.crt&sslcert=I:/path/to/database/certs/out/client.crt&sslkey=I:/path/to/database/certs/out/client.key
```

Replace `PASSWORD` and the path with local values. Do not commit the URL.

## 7. Live TLS tests

`middleware/tests/test_db_ssl_config.py` contains three live tests. They connect to the server
named by `BIOSYNC_TLS_TEST_DATABASE_URL` and skip with a reason when the variable is unset.

* `test_tls_server_accepts_verified_client_certificate` checks that the connection uses TLS.
* `test_tls_server_rejects_connection_without_client_certificate` checks the rejection message.
* `test_tls_server_rejects_plaintext_connection` checks the no-encryption rejection message.

Set `BIOSYNC_TLS_TEST_CERT_DIR` when the certificates are not in `database/certs/out/`.

The live tests need a server with the same entrypoint, `pg_hba.conf`, and certificate mounts as
the compose service. The scratch server used for verification is started like this, with a
password from the environment:

```
docker run -d --name srta-postgres-tls -p 127.0.0.1:5433:5432 `
  -e POSTGRES_DB=surgitwin_tls_test -e POSTGRES_USER=surgitwin -e POSTGRES_PASSWORD=$env:SRTA_TLS_PW `
  -v "$PWD\database\certs\postgres-entrypoint.sh:/opt/biosync/postgres-entrypoint.sh:ro" `
  -v "$PWD\database\postgres\pg_hba.conf:/opt/biosync/pg_hba.conf:ro" `
  -v "$PWD\database\certs\out\server.crt:/etc/biosync/tls-src/server.crt:ro" `
  -v "$PWD\database\certs\out\server.key:/etc/biosync/tls-src/server.key:ro" `
  -v "$PWD\database\certs\out\ca.crt:/etc/biosync/tls-src/ca.crt:ro" `
  --entrypoint sh postgres:15 /opt/biosync/postgres-entrypoint.sh postgres `
  -c ssl=on -c ssl_cert_file=/var/lib/postgresql/tls/server.crt `
  -c ssl_key_file=/var/lib/postgresql/tls/server.key `
  -c ssl_ca_file=/var/lib/postgresql/tls/ca.crt -c hba_file=/opt/biosync/pg_hba.conf
```

`SNDEV/scripts/tls-connection-matrix.py` runs three connection attempts against that server:
a verified client certificate, no client certificate, and plaintext.

## 8. Limits

* The certificates are self-signed by the BioSync CA. Production deployments issue the server
  and client certificates from an enterprise CA.
* The client CN must match the role. A service that connects as a different role needs its own
  client certificate with that CN.
* The `pg_hba.conf` rules apply to all roles. A test that creates its own login role cannot use
  a client certificate whose CN names a different role.
* Private keys are copied into containers at start. Rotate them by regenerating the files and
  recreating the containers.
