#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib.sh"

export DIFY_VERSION="${DIFY_VERSION:-1.17.0}"
export DIFY_DIR="${DIFY_DIR:-.dify}"
export LM_STUDIO_HOST="${LM_STUDIO_HOST:-127.0.0.1}"
export LM_STUDIO_PORT="${LM_STUDIO_PORT:-1234}"
export LM_STUDIO_BASE_URL="${LM_STUDIO_BASE_URL:-http://host.docker.internal:1234/v1}"
load_config
validate_version
require_command git
require_command docker

if ! docker compose version >/dev/null 2>&1; then
  die "Docker Compose v2 não está disponível. Inicie/instale o Docker Desktop e tente novamente."
fi

if [[ -e "${DIFY_PATH}" && ! -d "${DIFY_PATH}/.git" ]]; then
  die "${DIFY_PATH} existe, mas não parece ser um checkout Git do Dify; não será sobrescrito."
fi

if [[ ! -d "${DIFY_PATH}/.git" ]]; then
  info "Baixando Dify ${DIFY_VERSION} para ${DIFY_PATH}"
  git clone --depth 1 --branch "${DIFY_VERSION}" https://github.com/langgenius/dify.git "${DIFY_PATH}"
else
  info "Checkout Dify existente encontrado em ${DIFY_PATH}"
  current_ref="$(git -C "${DIFY_PATH}" describe --tags --exact-match 2>/dev/null || true)"
  if [[ "${current_ref}" != "${DIFY_VERSION}" ]]; then
    die "O checkout existente está em '${current_ref:-um ref não versionado}', mas .env pede '${DIFY_VERSION}'. Não alterei a instalação."
  fi
fi

DIFY_DOCKER_PATH="${DIFY_PATH}/docker"
[[ -d "${DIFY_DOCKER_PATH}" ]] || die "Diretório docker do Dify não encontrado em ${DIFY_DOCKER_PATH}."
[[ -f "${DIFY_DOCKER_PATH}/docker-compose.yaml" || -f "${DIFY_DOCKER_PATH}/docker-compose.yml" ]] || die "Compose oficial não encontrado em ${DIFY_DOCKER_PATH}."

if [[ ! -f "${DIFY_DOCKER_PATH}/.env" ]]; then
  [[ -f "${DIFY_DOCKER_PATH}/.env.example" ]] || die "Template .env.example não encontrado no Dify."
  cp "${DIFY_DOCKER_PATH}/.env.example" "${DIFY_DOCKER_PATH}/.env"
  warn "Foi criado ${DIFY_DOCKER_PATH}/.env. Revise SECRET_KEY, senhas e URLs antes de produção."
else
  info "${DIFY_DOCKER_PATH}/.env já existe; não será sobrescrito."
fi

# Keep the local Docker Desktop gateway fix across Dify upgrades. Compose loads
# this file automatically and it only affects the plugin daemon container.
OVERRIDE_FILE="${DIFY_DOCKER_PATH}/docker-compose.override.yaml"
if [[ ! -f "${OVERRIDE_FILE}" ]]; then
  cat > "${OVERRIDE_FILE}" <<'EOF'
# Local Docker Desktop override for the LM Studio provider.
services:
  plugin_daemon:
    extra_hosts:
      - "host.docker.internal:host-gateway"
EOF
  info "Adicionado mapeamento do gateway do host ao plugin daemon."
fi

info "Bootstrap concluído. Próximo passo: make up"
