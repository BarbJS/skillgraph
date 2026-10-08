.PHONY: check test package-etapa1 audit-delivery bootstrap up down status smoke bootstrap-flaml train-ml bootstrap-crewai run run-crewai evaluate-ai evaluate-ai-live pytest install-dev lint ci release-check

DEV_PYTHON := .venv/bin/python
DEV_PRE_COMMIT := .venv/bin/pre-commit

install-dev: bootstrap-crewai
	$(DEV_PYTHON) -m pip install -r requirements-dev.txt

lint: install-dev
	$(DEV_PRE_COMMIT) run --all-files

ci: install-dev
	$(DEV_PYTHON) -m pip check
	$(DEV_PYTHON) -m compileall -q app.py src tests scripts
	$(DEV_PYTHON) -m pytest -q tests

release-check: ci
	@test -n "$$(tr -d '[:space:]' < VERSION)"
	@test -f CHANGELOG.md
	@printf 'Release metadata: v%s\n' "$$(tr -d '[:space:]' < VERSION)"

PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest

run: bootstrap-crewai
	./scripts/start-crewai-streamlit.sh

package-etapa1:
	bash scripts/package-etapa1.sh

audit-delivery:
	bash scripts/audit-delivery.sh

# Machine Learning uses the isolated O*NET competency workflow and is not mixed with DuckDB/RAG data.

.DEFAULT_GOAL := check

check:
	./scripts/check-lm-studio.sh

test:
	./scripts/test-lm-studio.sh
bootstrap:
	./scripts/bootstrap-dify.sh

up:
	./scripts/start-dify.sh

down:
	./scripts/stop-dify.sh

status:
	./scripts/status-dify.sh

smoke:
	./scripts/smoke-test.sh

bootstrap-flaml:
	./scripts/bootstrap-flaml.sh

train-ml: bootstrap-crewai
	$(PYTHON) scripts/train-ml.py

pytest: bootstrap-crewai
	$(PYTEST) -q tests

bootstrap-crewai:
	./scripts/bootstrap-crewai.sh

run-crewai:
	./scripts/start-crewai-streamlit.sh

evaluate-ai:
	./scripts/evaluate-ai.py

evaluate-ai-live:
	./scripts/evaluate-ai-live.py

# Live RAGAS/DeepEval evaluations are explicit and may consume LLM credits.

# The ML workflow is isolated from data_bd/, DuckDB and the RAG corpus.
