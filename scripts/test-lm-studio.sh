#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib.sh"

load_config
require_command curl
require_command jq

CHAT_MODEL="${LM_STUDIO_CHAT_MODEL:-meta-llama-3-8b-instruct}"
EMBEDDING_MODEL="${LM_STUDIO_EMBEDDING_MODEL:-text-embedding-nomic-embed-text-v1.5}"
BASE_URL="http://${LM_STUDIO_HOST}:${LM_STUDIO_PORT}/v1"
API_KEY="${LM_STUDIO_API_KEY:-lm-studio-local}"

info "Testando chat com ${CHAT_MODEL}"
chat_response="$(curl --fail --silent --show-error --connect-timeout 3 --max-time 120 \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${API_KEY}" \
  -d "{\"model\":\"${CHAT_MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"Responda apenas: integração funcionando\"}],\"temperature\":0,\"max_tokens\":20}" \
  "${BASE_URL}/chat/completions")"
printf '%s\n' "${chat_response}" | jq -e '.choices[0].message.content' >/dev/null || die "Resposta de chat inválida."
printf 'PASS  chat       %s\n' "$(printf '%s' "${chat_response}" | jq -r '.choices[0].message.content')"

info "Testando embeddings com ${EMBEDDING_MODEL}"
embedding_response="$(curl --fail --silent --show-error --connect-timeout 3 --max-time 120 \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${API_KEY}" \
  -d "{\"model\":\"${EMBEDDING_MODEL}\",\"input\":\"teste de integração\"}" \
  "${BASE_URL}/embeddings")"
printf '%s\n' "${embedding_response}" | jq -e '.data[0].embedding | length > 0' >/dev/null || die "Resposta de embedding inválida."
printf 'PASS  embeddings dimensões=%s\n' "$(printf '%s' "${embedding_response}" | jq -r '.data[0].embedding | length')"

info "LM Studio chat e embeddings estão funcionais."
