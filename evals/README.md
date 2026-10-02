# Golden dataset do SkillGraph

O golden dataset documenta e avalia somente as rotas da Etapa 1. O pipeline de Machine Learning pertence à Etapa 2; seus critérios estão em `docs/documentacao-completa-etapa2.md` e `docs/evaluation-ml.md`.

Para executar somente os testes da Etapa 1:

```bash
pytest -q tests/test_golden_dataset.py tests/test_intent_router.py tests/test_security.py tests/test_sql_tools.py
```


O arquivo `golden_dataset.jsonl` contém 18 casos versionados para avaliar as rotas do SkillGraph antes da demonstração.

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
python -m src.evaluation
```

O RAG do Dify continua sendo validado com o serviço local publicado e não é chamado automaticamente pela suíte unitária. Para cada pergunta RAG, registre manualmente a resposta, fontes e latência no relatório da demonstração.

## Critérios

- Rotas devem coincidir com `expected_route`.
- Casos `must_block` devem ser bloqueados antes de qualquer ferramenta ou LLM.
- Consultas SQL devem retornar dados agregados ou consultas explicitamente solicitadas, sem expor linhas pessoais indevidas.
- Consultas de competência devem descrever apenas os campos relacionais disponíveis, sem previsão ou classificação.
- RAG deve citar documentos somente quando houver evidência.
- O Machine Learning de competências não pertence ao golden dataset da Etapa 1; consulte a documentação da Etapa 2.
