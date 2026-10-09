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
- A Etapa 1 não inclui a rota de Machine Learning. A observabilidade do ML está documentada e executada separadamente na Etapa 2.

## Machine Learning e etapas

A Etapa 1 observa apenas RAG, SQL, guardrails e streaming. O pipeline ML de competências, suas métricas e seus artefatos pertencem à Etapa 2 e estão documentados em [documentacao-completa-etapa2.md](documentacao-completa-etapa2.md).

## Painel de Observabilidade da Etapa 2

O perfil `desenvolvedor` possui a área `Observabilidade`, separada do Chat e da aba ML. Ela mostra métricas agregadas e traces sanitizados por serviço/agente/tarefa. O dashboard apresenta os 10 traces mais recentes, cada um com Trace ID identificável, timestamp, rota, status, duração, quantidade de spans, tokens de entrada/saída e custo. É possível selecionar um Trace ID e abrir os detalhes dos spans para rastreabilidade sem expor perguntas, respostas, currículo ou prompts privados. O botão de atualização permite recarregar os traces da sessão. O checkbox antigo da sidebar foi removido.

Cada trace registra, quando disponível: `trace_id`, timestamp, rota, status, duração total, spans, tarefas/agentes, tokens de entrada/saída, custo estimado, erros e timeouts. O sistema não registra PII, currículo bruto, prompts privados ou chain-of-thought.

O SDK Langfuse é opcional e no-op quando `LANGFUSE_ENABLED=false`; não é necessário clonar o repositório nem adicionar um serviço ao Docker nesta fase. O painel local funciona sem credenciais. Alertas Slack também são opcionais; `SLACK_ALERTS_ENABLED=false` é o padrão. A implementação usa um Bot User OAuth Token com `chat:write` e o ID do canal; ambos ficam somente no `.env` local.

## System prompt

O comportamento documental esperado do LLM está descrito em [system-prompt.md](system-prompt.md), com regras de domínio, fundamentação no contexto recuperado, fontes e privacidade.
