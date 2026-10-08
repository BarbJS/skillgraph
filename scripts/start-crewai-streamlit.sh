#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT}/.venv"
[[ -x "${VENV_DIR}/bin/python" ]] || { printf 'Ambiente oficial ausente. Execute make bootstrap-crewai.\n' >&2; exit 1; }
version="$(${VENV_DIR}/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
[[ "${version}" == "3.11" ]] || { printf 'O ambiente oficial precisa usar Python 3.11; encontrado %s.\n' "${version}" >&2; exit 1; }
[[ -x "${VENV_DIR}/bin/streamlit" ]] || { printf 'Streamlit ausente no ambiente oficial. Execute make bootstrap-crewai.\n' >&2; exit 1; }
exec "${VENV_DIR}/bin/streamlit" run "${ROOT}/app.py" --server.address 127.0.0.1 --server.port "${STREAMLIT_PORT:-8501}"
