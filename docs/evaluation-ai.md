# Avaliação robusta de IA

RAGAS foi removido do projeto. A avaliação de qualidade usa Golden Dataset, testes automatizados e DeepEval.

- RAGAS: não utilizado.
- DeepEval: LLM-as-a-judge com Google Gemini, somente em avaliação live explicitamente autorizada.

O judge usa `EVAL_JUDGE_MODEL=gemini-3.1-flash-lite` no endpoint Google Gemini e as métricas que dependem de embeddings usam `EVAL_EMBEDDING_MODEL=gemini-embedding-001`. Nenhum desses adapters é importado ou executado no caminho normal do chat.
- Golden Dataset: casos sintéticos versionados.
- Relatórios: `output/evaluation/`.

O modo live exige `--yes-live` e pode consumir quota do Google Gemini. Ele nunca é chamado pelo chat normal.

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

## Decisão sobre LLM Guard e segurança

O LLM Guard foi avaliado como camada complementar para prompt injection, jailbreak, PII, secrets e toxicidade. A tentativa de integração no ambiente principal revelou conflitos de dependências com CrewAI, DeepEval e o stack de ML, incluindo pins incompatíveis de `json-repair`, `click`, `numpy`, `regex` e componentes de spaCy. Para preservar a reprodutibilidade e não quebrar o runtime, o LLM Guard foi removido do ambiente, do código e dos requisitos do projeto.

Como alternativa, os guardrails determinísticos foram fortalecidos com uma camada central de validação de saída, detecção ampliada de PII/secrets, bloqueios de prompt injection/jailbreak/SQL e testes sintéticos de toxicidade e segurança no Golden Dataset. O DeepEval continua separado, sendo usado para qualidade semântica e não como filtro de segurança online.

## Execuções live manuais

Os comandos `scripts/evaluate-ai-live.py`, `scripts/test-jev.py`, `scripts/validate-langfuse-connection.py` e `scripts/validate-observability.py` são diagnósticos/avaliações live. Eles podem consumir chamadas externas, enviar traces ou acionar alertas; por isso, não são executados pela CI nem pela suíte padrão. Execute-os somente com as credenciais e confirmações apropriadas.

## 2. Golden Dataset

A execução do Golden Dataset roda os casos contra o backend atual; as perguntas e expectativas permanecem fixas para permitir comparação entre versões do repositório.

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
