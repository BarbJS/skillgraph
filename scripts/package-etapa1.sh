#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="${ROOT}/dist"
STAGE="${DIST}/skillgraph-etapa1"
ZIP="${DIST}/skillgraph-etapa1.zip"

rm -rf "${STAGE}" "${ZIP}"
mkdir -p "${STAGE}"

copy_if_exists() {
  local path="$1"
  [[ -e "${ROOT}/${path}" ]] || return 0
  mkdir -p "${STAGE}/$(dirname "${path}")"
  cp -R "${ROOT}/${path}" "${STAGE}/${path}"
}

for path in README.md Makefile pytest.ini requirements.txt env.example .gitignore app.py src documents_rag data_bd docs evals tests scripts; do
  copy_if_exists "${path}"
done

rm -rf "${STAGE}/.env" "${STAGE}/.dify" "${STAGE}/models" "${STAGE}/etapa2_ml" "${STAGE}/data_bd/dataset_ml.csv" "${STAGE}/scripts/train-ml.sh" "${STAGE}/src/ml_model.py" "${STAGE}/src/train_model.py" "${STAGE}/tests/test_ml_model.py"
find "${STAGE}" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "${STAGE}" -type f -name '.DS_Store' -delete

mkdir -p "${DIST}"
(cd "${DIST}" && zip -qr "$(basename "${ZIP}")" "$(basename "${STAGE}")")
printf 'Pacote criado: %s\n' "${ZIP}"
