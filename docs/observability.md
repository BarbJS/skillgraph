# Observabilidade do SkillGraph

## Métricas disponíveis

A barra lateral do Streamlit possui a opção **Mostrar observabilidade**, que exibe:

- total de perguntas processadas;
- latência média;
- rotas utilizadas (`rag`, `sql_indicator`, `competency_lookup`, `comparison`, `blocked`);
- quantidade de bloqueios;
- taxa de bloqueios;
- quantidade de fontes recuperadas;
- quantidade de funções SQL acionadas;
- erros.

## Eventos locais

Eventos de execução são registrados em `logs/skillgraph.jsonl`, arquivo ignorado pelo Git. Cada linha contém apenas metadados:

- timestamp;
- `request_id`;
- rota;
- status;
- latência;
- funções acionadas;
- quantidade de fontes;
- bloqueio/erro.

O log não registra API keys, prompts completos, respostas completas ou texto de perguntas potencialmente sensíveis.

## Rotas observadas

```text
RAG → API do Dify → Chatflow → Weaviate → LM Studio
SQL → função read-only allowlisted → DuckDB
blocked → guardrail, sem ferramenta/LLM
```

## Limitações do MVP

- As métricas ficam em memória e reiniciam quando o Streamlit reinicia.
- O JSONL é local; não há coleta centralizada.
- Os perfis são simulados, não autenticação real.
- Para produção, usar armazenamento protegido, retenção definida, controle de acesso e tracing distribuído (por exemplo, Langfuse ou OpenTelemetry).
- Machine Learning e componentes autônomos não fazem parte desta etapa.

## System prompt

O comportamento documental esperado do LLM está descrito em [system-prompt.md](system-prompt.md), com regras de domínio, fundamentação no contexto recuperado, fontes e privacidade.
