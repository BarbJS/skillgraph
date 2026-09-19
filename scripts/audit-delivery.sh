#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

printf '%s\n' '== Secrets/candidate sensitive literals in deliverable files =='
grep -RIn --exclude-dir=.git --exclude-dir=.dify --exclude-dir=.venv --exclude-dir=__pycache__ --exclude-dir=dist \
  -E 'sk-[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_-]{20,}|-----BEGIN .* PRIVATE KEY-----|DIFY_API_KEY=[^r][^e][^p][^l]|password=[^ ]+' \
  README.md app.py src docs documents data evals env.example requirements.txt Makefile tests scripts || true

printf '%s\n' '== ML material outside Etapa 1 package =='
grep -RIn --exclude-dir=.git --exclude-dir=.dify --exclude-dir=.venv --exclude-dir=__pycache__ \
  -E 'dataset_ml|RiskClassifier|ml_model|train-ml|ML_GUIDE' app.py src docs tests README.md requirements.txt Makefile scripts || true

printf '%s\n' '== .env ignore rule =='
git check-ignore -v .env
