# Golden dataset do SkillGraph

O Golden Dataset documenta e avalia as rotas atuais do SkillGraph, incluindo segurança, RAG, dados estruturados, treinamento, Machine Learning, esclarecimento e casos multi-turno. Os cenários compostos de agentes ficam em `agent_goldens.jsonl`; a avaliação semântica do RAG fica em `rag_goldens.jsonl`.

As expectativas de rota devem acompanhar `src/agents/router.py`. O teste `tests/test_golden_dataset.py` executa o roteador real e falha quando uma entrada fica desatualizada.

Para validar os datasets e as rotas atuais:

```bash
pytest -q tests/test_golden_dataset.py tests/test_agent_goldens.py tests/test_intent_router.py tests/test_security.py tests/test_sql_tools.py
```


O arquivo `golden_dataset.jsonl` contém 25 casos versionados para avaliar as rotas do SkillGraph antes da demonstração. `agent_goldens.jsonl` acrescenta quatro cenários compostos de agentes; `rag_goldens.jsonl` contém doze casos com resposta, contexto e ground truth para a avaliação semântica opcional com DeepEval.

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
