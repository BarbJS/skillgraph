#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib.sh"

load_config
[[ -d "${DIFY_PATH}/docker" ]] || die "Instalação Dify não encontrada em ${DIFY_PATH}."

info "Parando os serviços sem remover volumes persistentes"
(cd "${DIFY_PATH}/docker" && docker compose down)
