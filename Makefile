.PHONY: check test package-etapa1 audit-delivery bootstrap up down status smoke bootstrap-flaml train-ml bootstrap-crewai

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

train-ml:
	./scripts/train-ml.py

bootstrap-crewai:
	./scripts/bootstrap-crewai.sh

# The ML workflow is isolated from data_bd/, DuckDB and the RAG corpus.
