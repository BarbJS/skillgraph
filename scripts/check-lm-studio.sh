#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib.sh"

load_config
require_command curl

BASE_URL="http://${LM_STUDIO_HOST}:${LM_STUDIO_PORT}/v1"
MODELS_URL="${BASE_URL}/models"

info "Consultando LM Studio em ${MODELS_URL}"
if ! response="$(curl --fail --silent --show-error --connect-timeout 3 --max-time 10 "${MODELS_URL}")"; then
  cat >&2 <<EOF
Não foi possível acessar o LM Studio.

Verifique:
  1. O servidor local está iniciado em LM Studio (Developer > Start Server).
  2. Existe um modelo carregado.
  3. A porta configurada é ${LM_STUDIO_PORT}.
  4. O LM Studio está aceitando conexões locais/rede, se o Dify estiver em Docker.

Depois, tente novamente: make check
EOF
  exit 1
fi

if command -v jq >/dev/null 2>&1; then
  printf '%s\n' "${response}" | jq -r '.data[]?.id // empty' | while IFS= read -r model; do
    printf '  - %s\n' "${model}"
  done
else
  warn "jq não encontrado; exibindo a resposta JSON bruta."
  printf '%s\n' "${response}"
fi

info "API de modelos respondeu corretamente."
info "Para embeddings, confirme que um endpoint /v1/embeddings é suportado pelo modelo escolhido."
