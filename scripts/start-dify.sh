#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib.sh"

"${SCRIPT_DIR}/bootstrap-dify.sh"
load_config
DIFY_DOCKER_PATH="${DIFY_PATH}/docker"

info "Iniciando serviços do Dify"
(cd "${DIFY_DOCKER_PATH}" && docker compose up -d)

info "Estado dos serviços"
(cd "${DIFY_DOCKER_PATH}" && docker compose ps)
printf '\nDify: http://localhost\nAdministração inicial: http://localhost/install\n'
