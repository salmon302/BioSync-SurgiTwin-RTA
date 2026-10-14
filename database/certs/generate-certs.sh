#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
#
# Generates the PostgreSQL client-certificate TLS material (SRS NFR-SEC-001, Gateway R2).
# Origin: BioSync-Gateway nginx/generate-certs.sh (adapted). The nginx server certificate is
# not part of this repository and is not generated here.
#
# Produces in database/certs/out/ (gitignored):
#   ca.crt, ca.key             BioSync CA. Signs the server and client certificates.
#   server.crt, server.key     PostgreSQL server certificate. SAN: localhost, postgres, 127.0.0.1.
#   client.crt, client.key     Client certificate for the middleware. CN is the database user.
#
# The CN of the client certificate must equal the PostgreSQL role it connects as. With
# clientcert=verify-full in pg_hba.conf, PostgreSQL compares the CN with the user name.
#
# Environment:
#   PG_CLIENT_CN   Database user written as the client CN (default: surgitwin, the POSTGRES_USER default).
#   CERT_DAYS      Validity in days for every certificate (default: 365).
#   FORCE=1        Regenerate even when out/ca.key already exists. Existing keys are replaced.
#
# Usage (Windows, Git for Windows bash):
#   & "C:\Program Files\Git\bin\bash.exe" database/certs/generate-certs.sh
# Usage (Linux or macOS):
#   ./database/certs/generate-certs.sh
#
# For production, issue the server and client certificates from an enterprise CA and inject them
# through a secrets manager. Never commit the private keys.

set -euo pipefail

# Git for Windows bash rewrites arguments that start with "/" (the -subj values). Disable that.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${SCRIPT_DIR}/out"
DB_USER="${PG_CLIENT_CN:-surgitwin}"
DAYS="${CERT_DAYS:-365}"
SUBJ_BASE="/C=US/ST=State/L=City/O=BioSync"

if [[ -f "${OUT_DIR}/ca.key" && "${FORCE:-0}" != "1" ]]; then
    echo "Certificates already exist in ${OUT_DIR}. Set FORCE=1 to replace them." >&2
    exit 1
fi

mkdir -p "${OUT_DIR}"
# Relative file names only. The MinGW openssl on Git for Windows cannot resolve the POSIX
# absolute paths that bash produces, so the work runs inside out/.
cd "${OUT_DIR}"
rm -f ./*.csr ./*.srl ./*.ext

# The CA extensions come from this file, not from the host openssl.cnf. Adding them with -addext
# duplicates the basicConstraints extension that the host default already writes, and the
# duplicate makes the CA fail verification.
cat > ca.cnf <<EOF
[req]
distinguished_name = dn
prompt = no

[dn]

[ca_ext]
basicConstraints = critical,CA:TRUE
keyUsage = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always
EOF

echo "==> Generating BioSync CA"
openssl req -x509 -new -nodes -sha256 -newkey rsa:2048 -days "${DAYS}" \
    -config ca.cnf -extensions ca_ext \
    -keyout ca.key \
    -out ca.crt \
    -subj "${SUBJ_BASE}/CN=biosync-ca"

cat > server.ext <<EOF
basicConstraints=CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
subjectAltName=DNS:localhost,DNS:postgres,IP:127.0.0.1
EOF

cat > client.ext <<EOF
basicConstraints=CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=clientAuth
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
EOF

echo "==> Issuing PostgreSQL server certificate (signed by CA)"
openssl req -new -nodes -newkey rsa:2048 \
    -keyout server.key \
    -out server.csr \
    -subj "${SUBJ_BASE}/CN=biosync-db"
openssl x509 -req -in server.csr \
    -CA ca.crt -CAkey ca.key -CAcreateserial \
    -days "${DAYS}" -extfile server.ext \
    -out server.crt

echo "==> Issuing client certificate for database user ${DB_USER} (signed by CA)"
openssl req -new -nodes -newkey rsa:2048 \
    -keyout client.key \
    -out client.csr \
    -subj "${SUBJ_BASE}/CN=${DB_USER}"
openssl x509 -req -in client.csr \
    -CA ca.crt -CAkey ca.key -CAcreateserial \
    -days "${DAYS}" -extfile client.ext \
    -out client.crt

rm -f ./*.csr ./*.ext ./*.srl ./ca.cnf

chmod 600 ca.key server.key client.key
chmod 644 ca.crt server.crt client.crt

echo "==> Verifying chains"
openssl verify -CAfile ca.crt server.crt client.crt

echo "Done. Certificates written to ${OUT_DIR}."
echo "  ca.{crt,key}                 BioSync CA"
echo "  server.{crt,key}             PostgreSQL server certificate"
echo "  client.{crt,key}             middleware client certificate (CN=${DB_USER})"
