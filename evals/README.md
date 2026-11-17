# Golden Dataset do SkillGraph

O repositório contém três conjuntos versionados e reproduzíveis:

- `golden_dataset.jsonl`: 25 casos determinísticos de roteamento, guardrails, RAG, dados estruturados, ML, treinamento, esclarecimento e segurança;
- `agent_goldens.jsonl`: 4 contratos de cenários multiagente, com agentes e ferramentas esperados;
- `rag_goldens.jsonl`: 12 casos semânticos com pergunta, resposta de referência, contextos de referência, `ground_truth` e categoria.

As expectativas de rota devem acompanhar `src/agents/router.py`. Os testes executam o roteador e os guardrails reais e falham quando um dataset fica desatualizado.

## Execução para avaliação local

Use Python 3.11, a partir da raiz do repositório:

```bash
python -m pip install -r requirements-dev.txt
python -m pip check
pytest -q tests
python scripts/evaluate-ai.py --output /tmp/skillgraph-ai-quality-report.json
```

A execução offline do Golden Dataset não precisa de chaves, Dify, Gemini ou JEV. Ela executa os 25 casos determinísticos contra o roteador/guardrails locais e grava um relatório no caminho informado.

Para validar especificamente os datasets e as rotas:

```bash
pytest -q tests/test_golden_dataset.py tests/test_agent_goldens.py tests/test_rag_cases.py
```

Os testes de integração do JEV usam mock e não enviam dados para a API. A rota real de currículo exige credenciais, serviço externo e currículo autorizado/sanitizado.

## Avaliação RAG com DeepEval

Os 12 casos de `rag_goldens.jsonl` podem ser avaliados semanticamente contra uma resposta e contextos atuais do Dify. Essa etapa não é offline: requer um Chatflow Dify acessível e um modelo judge Gemini configurado por Secrets ou variáveis de ambiente.

Configure, por exemplo:

```bash
export DIFY_API_BASE_URL="https://..."
export DIFY_API_KEY="..."
export DIFY_USER_ID="professor-local"
export EVAL_JUDGE_API_KEY="..."
export EVAL_JUDGE_MODEL="gemini-3.1-flash-lite"
export EVAL_JUDGE_BASE_URL="https://generativelanguage.googleapis.com/v1beta"
```

Execute somente após confirmar o consumo de quota:

```bash
python scripts/evaluate-ai-live.py \
  --deepeval \
  --yes-live \
  --dataset evals/rag_goldens.jsonl \
  --output /tmp/skillgraph-live-ai-report.json
```

O relatório live preserva por caso a pergunta, resposta avaliada, `ground_truth`, resposta/contextos de referência, fontes retornadas pelo Dify, quatro métricas, scores, thresholds, razões, modelo judge, estados de erro e cobertura. Score `0.0` é resultado válido; ausência de score indica erro ou execução incompleta.

## Schema e critérios

Cada caso determinístico contém `id`, `category`, `question`, `expected_route`, `expected_answer_facts`, `expected_documents`, `expected_ids`, `must_block` e `notes`.

Cada caso RAG contém `id`, `question`, `answer`, `contexts`, `ground_truth` e `category`.

Cada caso multiagente contém `id`, `category`, `question`, `expected_route`, `expected_agents`, `expected_tools`, `must_block`, `expected_answer_facts` e `notes`.

Critérios principais:

- rotas devem coincidir com `expected_route`;
- casos `must_block` devem ser bloqueados antes de qualquer ferramenta ou LLM;
- consultas SQL devem retornar dados agregados ou explicitamente solicitados;
- RAG deve citar documentos somente quando houver evidência;
- as respostas e contextos dos goldens RAG devem sustentar a `ground_truth`;
- DeepEval avalia apenas a execução live e não substitui revisão humana.

Os relatórios gerados em `output/evaluation/` são artefatos locais e não precisam ser commitados.

## Categorias

- `rag`: políticas, cargos, trilhas e FAQ.
- `sql`: indicadores e catálogo estruturado.
- `competency_lookup`: consulta relacional com IDs explícitos ou pedido de esclarecimento.
- `security`: PII, prompt injection e SQL destrutivo.
- `out_of_scope`: ausência de evidência.
- `ambiguous`: perguntas que exigem esclarecimento ou resposta cautelosa.

## Schema

Cada linha é um objeto JSON com:

- `id`, `category`, `question`;
- `expected_route`;
- `expected_answer_facts`;
- `expected_documents`;
- `expected_ids`;
- `must_block`;
- `notes`.

## Execução

Validação determinística de schema e rotas:

```bash
pytest -q tests/test_golden_dataset.py
```

Execução das camadas locais SQL, RAG e segurança:

```bash
make evaluate-ai
```

O RAG do Dify continua sendo validado com o serviço local publicado e não é chamado automaticamente pela suíte unitária. Para cada pergunta RAG, registre manualmente a resposta, fontes e latência no relatório da demonstração. A avaliação live com DeepEval é opcional e pode consumir chamadas do modelo judge; execute-a manualmente com `scripts/evaluate-ai-live.py --deepeval --yes-live --dataset evals/rag_goldens.jsonl`.

## Critérios

- Rotas devem coincidir com `expected_route`.
- Casos `must_block` devem ser bloqueados antes de qualquer ferramenta ou LLM.
- Consultas SQL devem retornar dados agregados ou consultas explicitamente solicitadas, sem expor linhas pessoais indevidas.
- Consultas de competência devem descrever apenas os campos relacionais disponíveis, sem previsão ou classificação.
- RAG deve citar documentos somente quando houver evidência.
- O caso precisa permanecer alinhado à rota atual; detalhes do pipeline de Machine Learning estão em `docs/documentacao-completa-etapa2.md` e `docs/evaluation-ml.md`.
