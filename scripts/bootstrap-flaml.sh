#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
FLAML_DIR="${ROOT}/.flaml"
FLAML_VERSION="${FLAML_VERSION:-v2.7.0}"

command -v git >/dev/null 2>&1 || { printf 'Comando obrigatório não encontrado: git\n' >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { printf 'Comando obrigatório não encontrado: python3\n' >&2; exit 1; }

if [[ "$(uname -s)" == "Darwin" ]] && command -v brew >/dev/null 2>&1 && ! brew list --formula libomp >/dev/null 2>&1; then
  printf '[INFO] Instalando libomp para os estimadores FLAML no macOS\n'
  brew install libomp
fi

if [[ -e "${FLAML_DIR}" && ! -d "${FLAML_DIR}/.git" ]]; then
  printf '%s existe, mas não parece ser um checkout Git do FLAML; não será sobrescrito.\n' "${FLAML_DIR}" >&2
  exit 1
fi

if [[ ! -d "${FLAML_DIR}/.git" ]]; then
  printf '[INFO] Clonando FLAML %s\n' "${FLAML_VERSION}"
  git clone --depth 1 --branch "${FLAML_VERSION}" https://github.com/microsoft/FLAML.git "${FLAML_DIR}"
else
  current_ref="$(git -C "${FLAML_DIR}" describe --tags --exact-match 2>/dev/null || true)"
  if [[ "${current_ref}" != "${FLAML_VERSION}" ]]; then
    printf 'Checkout FLAML em %s, esperado %s; não alterei a instalação.\n' "${current_ref:-um ref não versionado}" "${FLAML_VERSION}" >&2
    exit 1
  fi
  printf '[INFO] Checkout FLAML %s já existe\n' "${FLAML_VERSION}"
fi

printf '[INFO] Instalando FLAML e dependências do projeto no ambiente Python ativo\n'
python3 -m pip install -r "${ROOT}/requirements.txt"
python3 -m pip install -e "${FLAML_DIR}[automl]"
printf '[INFO] Bootstrap do FLAML concluído\n'
