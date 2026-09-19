.PHONY: check test package-etapa1 audit-delivery bootstrap up down status smoke

package-etapa1:
	bash scripts/package-etapa1.sh

audit-delivery:
	bash scripts/audit-delivery.sh

# Machine Learning is reserved for Etapa 2 and is not part of this package.
# The archived material lives in etapa2_ml/.

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
