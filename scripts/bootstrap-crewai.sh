#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
command -v "${PYTHON_BIN}" >/dev/null 2>&1 || { printf 'Python 3.11 não encontrado.\n' >&2; exit 1; }
if [[ ! -x "${ROOT}/.crew-venv/bin/python" ]]; then
  "${PYTHON_BIN}" -m venv "${ROOT}/.crew-venv"
fi
"${ROOT}/.crew-venv/bin/python" -m pip install --upgrade pip
"${ROOT}/.crew-venv/bin/python" -m pip install 'crewai==0.203.2'
printf '[INFO] CrewAI instalado em .crew-venv; Python do agente: %s\n' "$(${ROOT}/.crew-venv/bin/python --version)"
