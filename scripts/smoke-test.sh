#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib.sh"

load_config
require_command curl

check_url() {
  local url="$1"
  local label="$2"
  local code
  code="$(curl --silent --output /dev/null --write-out '%{http_code}' --connect-timeout 3 --max-time 10 "${url}" || true)"
  if [[ "${code}" =~ ^[23][0-9][0-9]$ ]]; then
    printf 'PASS  %-24s %s (%s)\n' "${label}" "${url}" "${code}"
  else
    printf 'FAIL  %-24s %s (%s)\n' "${label}" "${url}" "${code:-sem resposta}"
    return 1
  fi
}

failures=0
check_url "http://localhost/" "Dify web" || failures=$((failures + 1))
check_url "http://localhost/console/api/setup" "Dify setup API" || failures=$((failures + 1))
check_url "http://${LM_STUDIO_HOST}:${LM_STUDIO_PORT}/v1/models" "LM Studio API" || failures=$((failures + 1))

if (( failures > 0 )); then
  die "Smoke test falhou em ${failures} verificação(ões). Consulte docs/model-setup.md."
fi

info "Smoke test concluído. O próximo teste funcional é executar um chat no Dify UI."
