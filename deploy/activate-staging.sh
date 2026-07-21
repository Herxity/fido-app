#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

if [[ ${EUID} -ne 0 || $# -ne 5 ]]; then
  echo "Usage: sudo activate-staging.sh <full-release-sha> <db-host> <origin-host> <edge-url> <image-tag>" >&2
  exit 2
fi

release_id=$1
db_host=$2
origin_host=$3
edge_url=$4
image_tag=$5
stage_dir=/home/ubuntu/fido-stage
release_dir=/opt/fido/releases/${release_id}
secret_dir=/root/fido-bootstrap

[[ ${release_id} =~ ^[a-f0-9]{40}$ ]] || exit 2
[[ ${image_tag} =~ ^fido-backend:[a-f0-9]{7}$ ]] || exit 2
for name in db-master db-migrator db-runtime lookup-key field-key origin-token clerk-webhook persona-webhook placeholder-provider; do
  [[ -s ${stage_dir}/fido-${name} ]] || { echo "Missing staged secret: ${name}" >&2; exit 1; }
done

install -d -m 0700 "${secret_dir}"
for source in "${stage_dir}"/fido-*; do
  [[ ${source} == *.tar.gz ]] || install -m 0600 "${source}" "${secret_dir}/$(basename "${source}")"
done

master_password=$(<"${secret_dir}/fido-db-master")
migrator_password=$(<"${secret_dir}/fido-db-migrator")
runtime_password=$(<"${secret_dir}/fido-db-runtime")

cat >"${secret_dir}/bootstrap-wrapper.sql" <<'SQL'
\set migrator_password `cat /root/fido-bootstrap/fido-db-migrator`
\set runtime_password `cat /root/fido-bootstrap/fido-db-runtime`
\i /home/ubuntu/fido-stage/bootstrap-db.sql
SQL

PGPASSWORD=${master_password} psql -h "${db_host}" -p 5432 -U fido_admin -d fido \
  -v ON_ERROR_STOP=1 -f "${secret_dir}/bootstrap-wrapper.sql"

gzip -dc "${stage_dir}/fido-backend-${release_id:0:7}.tar.gz" | docker load >/dev/null
cat >"${secret_dir}/migrator.env" <<EOF
FIDO_ENVIRONMENT=production
FIDO_PROVIDER_MODE=live
FIDO_DATABASE_URL=postgresql+psycopg://fido_migrator:${migrator_password}@${db_host}:5432/fido
FIDO_CLERK_AUTHORIZED_PARTIES=["${edge_url}"]
EOF
docker run --rm --env-file "${secret_dir}/migrator.env" "${image_tag}" alembic upgrade head

PGPASSWORD=${master_password} psql -h "${db_host}" -p 5432 -U fido_admin -d fido \
  -v ON_ERROR_STOP=1 -f "${secret_dir}/bootstrap-wrapper.sql"

install -d -m 0700 /etc/fido
cat >/etc/fido/fido.env <<EOF
CADDY_IMAGE=caddy@sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648
ORIGIN_HOSTNAME=${origin_host}
ACME_EMAIL=operations@fido.invalid
FIDO_ORIGIN_VERIFY_TOKEN=$(<"${secret_dir}/fido-origin-token")
FIDO_ENVIRONMENT=production
FIDO_PROVIDER_MODE=live
FIDO_DATABASE_URL=postgresql+psycopg://fido_runtime:${runtime_password}@${db_host}:5432/fido
FIDO_CORS_ORIGINS=["${edge_url}"]
FIDO_CLERK_ISSUER=https://unconfigured.invalid
FIDO_CLERK_AUDIENCE=fido-api
FIDO_CLERK_JWKS_URL=https://unconfigured.invalid/.well-known/jwks.json
FIDO_CLERK_AUTHORIZED_PARTIES=["${edge_url}"]
FIDO_CLERK_ALLOW_LEGACY_ORG_CLAIMS=false
FIDO_CLERK_WEBHOOK_SECRET=$(<"${secret_dir}/fido-clerk-webhook")
FIDO_PERSONA_API_BASE=https://api.withpersona.com/api/v1
FIDO_PERSONA_VERSION=2025-10-27
FIDO_PERSONA_API_KEY=$(<"${secret_dir}/fido-placeholder-provider")
FIDO_PERSONA_TEMPLATE_ID=itmpl_staging_not_configured
FIDO_PERSONA_WEBHOOK_SECRET=$(<"${secret_dir}/fido-persona-webhook")
FIDO_FIELD_ENCRYPTION_KEY=$(<"${secret_dir}/fido-field-key")
FIDO_LOOKUP_HASH_KEY=$(<"${secret_dir}/fido-lookup-key")
FIDO_WEBHOOK_TOLERANCE_SECONDS=300
FIDO_REQUEST_BODY_LIMIT=1048576
EOF
chown root:root /etc/fido/fido.env
chmod 0600 /etc/fido/fido.env

install -d -m 0755 "${release_dir}/frontend" "${release_dir}/deploy"
if tar -tzf "${stage_dir}/fido-frontend-${release_id:0:7}.tar.gz" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then
  echo "Frontend archive contains an unsafe path" >&2
  exit 1
fi
tar -xzf "${stage_dir}/fido-frontend-${release_id:0:7}.tar.gz" -C "${release_dir}/frontend"
install -m 0644 "${stage_dir}/docker-compose.prod.yml" "${release_dir}/docker-compose.prod.yml"
install -m 0644 "${stage_dir}/Caddyfile" "${release_dir}/deploy/Caddyfile"
install -m 0750 "${stage_dir}/run-retention.sh" /usr/local/sbin/fido-retention
install -m 0644 "${stage_dir}/fido-retention.service" /etc/systemd/system/fido-retention.service
install -m 0644 "${stage_dir}/fido-retention.timer" /etc/systemd/system/fido-retention.timer

export BACKEND_IMAGE=${image_tag} FIDO_RELEASE_DIR=${release_dir} FIDO_ENV_FILE=/etc/fido/fido.env
docker pull "$(sed -n 's/^CADDY_IMAGE=//p' /etc/fido/fido.env)" >/dev/null
docker compose --project-name fido --env-file /etc/fido/fido.env \
  -f "${release_dir}/docker-compose.prod.yml" config --quiet
docker compose --project-name fido --env-file /etc/fido/fido.env \
  -f "${release_dir}/docker-compose.prod.yml" up -d --remove-orphans

healthy=false
for _ in $(seq 1 36); do
  if docker compose --project-name fido --env-file /etc/fido/fido.env \
    -f "${release_dir}/docker-compose.prod.yml" exec -T backend python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready', timeout=5)" >/dev/null 2>&1; then
    healthy=true
    break
  fi
  sleep 5
done
[[ ${healthy} == true ]] || { docker compose --project-name fido --env-file /etc/fido/fido.env -f "${release_dir}/docker-compose.prod.yml" logs --tail 100 >&2; exit 1; }

printf 'BACKEND_IMAGE=%s\nFIDO_RELEASE_DIR=%s\n' "${image_tag}" "${release_dir}" >/opt/fido/current-release
chmod 0600 /opt/fido/current-release
systemctl daemon-reload
systemctl enable --now fido-retention.timer
rm -rf "${secret_dir}"
find "${stage_dir}" -maxdepth 1 -type f -name 'fido-*' -delete
echo "Synthetic staging release ${release_id} is healthy." >&2
