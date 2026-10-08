# Avaliação robusta de IA

RAGAS foi removido do projeto. A avaliação de qualidade usa Golden Dataset, testes automatizados e DeepEval.

- RAGAS: não utilizado.
- DeepEval: LLM-as-a-judge com LM Studio local.
- Golden Dataset: casos sintéticos versionados.
- Relatórios: `output/evaluation/`.

O modo live exige `--yes-live` e pode consumir tokens do LM Studio.

## Métricas DeepEval

- Faithfulness;
- Answer Relevancy;
- Contextual Precision;
- Contextual Recall.


A avaliação possui três níveis:

## 1. Testes automatizados

`pytest -q tests` cobre componentes e contratos:

- roteamento e guardrails;
- Dify/SSE mockado;
- DuckDB read-only;
- PKL/XAI;
- JEV mockado;
- CrewAI desligado e factory/prompt;
- PDF;
- estado multi-turno;
- observabilidade/Slack;
- feedback.

Testes de integração usam mocks e não consomem créditos de JEV, Langfuse ou Slack.

## 2. Golden Dataset

`evals/golden_dataset.jsonl` contém 25 casos sintéticos de:

- RAG;
- DuckDB;
- ML/trilhas;
- currículo/perfil;
- multi-turno;
- smalltalk;
- ambiguidade;
- PII/injection;
- fora de escopo.

Execute offline:

```bash
make evaluate-ai
```

For an explicit live judge run, which may consume LM/API credits:

```bash
make evaluate-ai-live
```

The live runner requires a configured judge LLM/embeddings adapter before it is expected to produce DeepEval/DeepEval scores; it is intentionally never called by pytest or the normal Streamlit path.

O modo padrão é offline e valida schema, rota, bloqueio e ferramentas esperadas.

## 3. LLM-as-a-judge

DeepEval estão instalados para avaliação live explícita. O modo live não roda no `pytest` e pode consumir tokens/créditos.

As métricas DeepEval são:

- `faithfulness`;
- `answer_relevancy`;
- `context_precision`;
- `context_recall`.

O adapter está em `src/evaluation_ai.py`. Para usar live, forneça um judge LLM/embeddings configurado e execute um runner explícito; o relatório deve registrar modelo, versão do prompt, dataset, métricas, custo e timestamp.

Threshold inicial sugerido: `0.70` por métrica; abaixo disso é warning, abaixo de `0.50` é crítico. O judge é uma evidência de avaliação, não uma verdade absoluta.
