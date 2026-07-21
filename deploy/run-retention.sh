#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

state=/opt/fido/current-release
env_file=/etc/fido/fido.env
[[ ${EUID} -eq 0 && -f ${state} && -f ${env_file} ]] || exit 1

BACKEND_IMAGE=$(sed -n 's/^BACKEND_IMAGE=//p' "${state}" | tail -n 1)
FIDO_RELEASE_DIR=$(sed -n 's/^FIDO_RELEASE_DIR=//p' "${state}" | tail -n 1)
[[ -n ${BACKEND_IMAGE} && -d ${FIDO_RELEASE_DIR} ]] || exit 1
export BACKEND_IMAGE FIDO_RELEASE_DIR FIDO_ENV_FILE=${env_file}

docker compose --project-name fido --env-file "${env_file}" \
  -f "${FIDO_RELEASE_DIR}/docker-compose.prod.yml" \
  run --rm --no-deps backend python -m app.retention
