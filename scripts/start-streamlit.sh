#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${PORT:-${STREAMLIT_PORT:-8501}}"

command -v "${PYTHON_BIN}" >/dev/null 2>&1 || {
  printf 'Python não encontrado: %s\n' "${PYTHON_BIN}" >&2
  exit 1
}

[[ "${PORT}" =~ ^[0-9]+$ ]] || {
  printf 'PORT deve ser numérica: %s\n' "${PORT}" >&2
  exit 1
}

cd "${ROOT}"
exec "${PYTHON_BIN}" -m streamlit run "${ROOT}/app.py" \
  --server.address 0.0.0.0 \
  --server.port "${PORT}"
