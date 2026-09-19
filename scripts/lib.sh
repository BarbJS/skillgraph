#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
CONFIG_FILE="${PROJECT_ROOT}/.env"

info() { printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[WARN]\033[0m %s\n' "$*" >&2; }
error() { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; }
die() { error "$*"; exit 1; }

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Comando obrigatório não encontrado: $1"
}

load_config() {
  # Environment variables take precedence, allowing CI or a shell session to
  # run without creating a local secrets file.
  if [[ -f "${CONFIG_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${CONFIG_FILE}"
    set +a
  fi
  : "${DIFY_VERSION:?DIFY_VERSION não definido. Use env.example ou exporte DIFY_VERSION.}"
  : "${DIFY_DIR:=.dify}"
  : "${LM_STUDIO_HOST:=127.0.0.1}"
  : "${LM_STUDIO_PORT:=1234}"
  : "${LM_STUDIO_BASE_URL:=http://host.docker.internal:${LM_STUDIO_PORT}/v1}"
  DIFY_PATH="${PROJECT_ROOT}/${DIFY_DIR}"
}

validate_version() {
  [[ "${DIFY_VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "DIFY_VERSION deve ser uma versão semver simples (ex.: 1.17.0)."
}

compose() {
  (cd "${DIFY_PATH}" && docker compose "$@")
}
