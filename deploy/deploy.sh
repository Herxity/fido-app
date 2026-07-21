#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ENV_FILE=/etc/fido/fido.env
STATE_FILE=/opt/fido/current-release
RELEASES_DIR=/opt/fido/releases
BACKEND_IMAGE_INPUT=
RELEASE_ID=
FRONTEND_ARCHIVE=
COMPOSE_SOURCE=
CADDY_SOURCE=

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-image) BACKEND_IMAGE_INPUT=$2; shift 2 ;;
    --release-id) RELEASE_ID=$2; shift 2 ;;
    --frontend-archive) FRONTEND_ARCHIVE=$2; shift 2 ;;
    --compose-file) COMPOSE_SOURCE=$2; shift 2 ;;
    --caddyfile) CADDY_SOURCE=$2; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "deploy.sh must run as root" >&2
  exit 1
fi
if [[ ! ${BACKEND_IMAGE_INPUT} =~ @sha256:[a-f0-9]{64}$ ]]; then
  echo "Backend image must be pinned by sha256 digest" >&2
  exit 1
fi
if [[ ! ${RELEASE_ID} =~ ^[a-f0-9]{40}$ ]]; then
  echo "Release ID must be a full Git commit SHA" >&2
  exit 1
fi
for required_file in "${ENV_FILE}" "${FRONTEND_ARCHIVE}" "${COMPOSE_SOURCE}" "${CADDY_SOURCE}"; do
  [[ -f ${required_file} ]] || { echo "Missing required file: ${required_file}" >&2; exit 1; }
done
[[ $(stat -c '%U:%G:%a' "${ENV_FILE}") == root:root:600 ]] || {
  echo "${ENV_FILE} must be root:root mode 0600" >&2
  exit 1
}

read_env() {
  local key=$1
  local value
  value=$(sed -n "s/^${key}=//p" "${ENV_FILE}" | tail -n 1)
  [[ -n ${value} ]] || { echo "${key} is required in ${ENV_FILE}" >&2; exit 1; }
  printf '%s' "${value}"
}
CADDY_IMAGE=$(read_env CADDY_IMAGE)
read_env ORIGIN_HOSTNAME >/dev/null
read_env FIDO_ORIGIN_VERIFY_TOKEN >/dev/null
read_env ACME_EMAIL >/dev/null
[[ ${CADDY_IMAGE} =~ @sha256:[a-f0-9]{64}$ ]] || {
  echo "Caddy image must be pinned by sha256 digest" >&2
  exit 1
}

release_dir=${RELEASES_DIR}/${RELEASE_ID}
install -d -m 0755 "${release_dir}/frontend" "${release_dir}/deploy"
if tar -tzf "${FRONTEND_ARCHIVE}" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then
  echo "Frontend archive contains an unsafe path" >&2
  exit 1
fi
tar -xzf "${FRONTEND_ARCHIVE}" -C "${release_dir}/frontend"
install -m 0644 "${COMPOSE_SOURCE}" "${release_dir}/docker-compose.prod.yml"
install -m 0644 "${CADDY_SOURCE}" "${release_dir}/deploy/Caddyfile"

deploy_source_dir=$(dirname "${CADDY_SOURCE}")
if [[ -f ${deploy_source_dir}/run-retention.sh && -f ${deploy_source_dir}/fido-retention.service && -f ${deploy_source_dir}/fido-retention.timer ]]; then
  install -m 0750 "${deploy_source_dir}/run-retention.sh" /usr/local/sbin/fido-retention
  install -m 0644 "${deploy_source_dir}/fido-retention.service" /etc/systemd/system/fido-retention.service
  install -m 0644 "${deploy_source_dir}/fido-retention.timer" /etc/systemd/system/fido-retention.timer
  systemctl daemon-reload
  systemctl enable --now fido-retention.timer
fi

previous_image=
previous_dir=
if [[ -f ${STATE_FILE} ]]; then
  previous_image=$(sed -n 's/^BACKEND_IMAGE=//p' "${STATE_FILE}")
  previous_dir=$(sed -n 's/^FIDO_RELEASE_DIR=//p' "${STATE_FILE}")
fi

export BACKEND_IMAGE=${BACKEND_IMAGE_INPUT}
export FIDO_RELEASE_DIR=${release_dir}
compose=(docker compose --project-name fido --env-file "${ENV_FILE}" -f "${release_dir}/docker-compose.prod.yml")

"${compose[@]}" config --quiet
"${compose[@]}" pull --quiet
"${compose[@]}" run --rm --no-deps backend alembic upgrade head
"${compose[@]}" up -d --remove-orphans

healthy=false
for _ in $(seq 1 24); do
  if "${compose[@]}" exec -T backend python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready', timeout=5)" >/dev/null 2>&1; then
    healthy=true
    break
  fi
  sleep 5
done

if [[ ${healthy} != true ]]; then
  echo "New release failed readiness checks; restoring the previous application containers." >&2
  "${compose[@]}" logs --tail 100 >&2 || true
  if [[ ${previous_image} =~ @sha256:[a-f0-9]{64}$ && -d ${previous_dir} ]]; then
    export BACKEND_IMAGE=${previous_image}
    export FIDO_RELEASE_DIR=${previous_dir}
    rollback_compose=(docker compose --project-name fido --env-file "${ENV_FILE}" -f "${previous_dir}/docker-compose.prod.yml")
    "${rollback_compose[@]}" up -d --remove-orphans
  fi
  echo "Database migrations are not reversed; every migration must remain backward-compatible with one prior release." >&2
  exit 1
fi

state_tmp=$(mktemp /opt/fido/.current-release.XXXXXX)
printf 'BACKEND_IMAGE=%s\nFIDO_RELEASE_DIR=%s\n' "${BACKEND_IMAGE}" "${FIDO_RELEASE_DIR}" >"${state_tmp}"
chmod 0600 "${state_tmp}"
mv -f "${state_tmp}" "${STATE_FILE}"

find "${RELEASES_DIR}" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
  | sort -nr | tail -n +6 | cut -d' ' -f2- \
  | while IFS= read -r old_release; do
      [[ ${old_release} == "${FIDO_RELEASE_DIR}" || ${old_release} == "${previous_dir}" ]] || rm -rf -- "${old_release}"
    done

echo "Release ${RELEASE_ID} is healthy." >&2
