#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

printf '%s\n' '== Secrets/candidate sensitive literals in deliverable files =='
grep -RIn --exclude-dir=.git --exclude-dir=.dify --exclude-dir=.venv --exclude-dir=__pycache__ --exclude-dir=dist \
  -E 'sk-[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_-]{20,}|-----BEGIN .* PRIVATE KEY-----|DIFY_API_KEY=[^r][^e][^p][^l]|password=[^ ]+' \
  README.md app.py src docs documents_rag data_bd evals env.example requirements.txt Makefile tests scripts || true

printf '%s\n' '== Required ML documentation =='
for path in docs/ml-traditional.md docs/ml-llm-integration.md docs/evaluation-ml.md; do
  [[ -f "${path}" ]] || { printf 'Missing: %s\n' "${path}" >&2; exit 1; }
done

printf '%s\n' '== ML artifacts remain ignored =='
git check-ignore -v .ml_artifacts/skillgraph_competency_tracks.pkl .flaml


printf '%s\n' '== Machine Learning competency workflow =='
grep -RIn --exclude-dir=.git --exclude-dir=.dify --exclude-dir=.flaml --exclude-dir=.ml_artifacts --exclude-dir=.venv --exclude-dir=__pycache__ \
  -E 'O\\*NET|FLAML|competency_tracks|recommend_track|train-ml|ml_assistant' app.py src docs tests README.md requirements.txt Makefile scripts || true
printf '%s\n' '== Obsolete industrial-productivity references =='
grep -RIn --exclude-dir=.git --exclude-dir=.dify --exclude-dir=.flaml --exclude-dir=.ml_artifacts --exclude-dir=.venv --exclude-dir=__pycache__ \
  -E 'actual_productivity|SMV|WIP|Productivity Prediction|skillgraph_productivity' app.py src docs tests README.md requirements.txt Makefile scripts || true

printf '%s\n' '== .env ignore rule =='
git check-ignore -v .env
