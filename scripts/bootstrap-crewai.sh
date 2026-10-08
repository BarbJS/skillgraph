#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
VENV_DIR="${ROOT}/.venv"

command -v "${PYTHON_BIN}" >/dev/null 2>&1 || {
  printf 'Python 3.11 não encontrado. Instale Python 3.11 e tente novamente.\n' >&2
  exit 1
}

if [[ -e "${VENV_DIR}" && ! -x "${VENV_DIR}/bin/python" ]]; then
  printf '%s existe, mas não é um ambiente virtual Python válido. Não será sobrescrito.\n' "${VENV_DIR}" >&2
  exit 1
fi

if [[ -x "${VENV_DIR}/bin/python" ]]; then
  version="$(${VENV_DIR}/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  if [[ "${version}" != "3.11" ]]; then
    printf '%s usa Python %s; recrie-o com Python 3.11 antes de continuar.\n' "${VENV_DIR}" "${version}" >&2
    exit 1
  fi
else
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r "${ROOT}/requirements.txt"
"${VENV_DIR}/bin/python" -m pip check
printf '[INFO] Ambiente oficial pronto: %s (%s)\n' "${VENV_DIR}" "$(${VENV_DIR}/bin/python --version)"
