# Alertas Slack

A aplicação usa a API `chat.postMessage` do Slack com um **Bot User OAuth Token**. O token não é um webhook e não deve ser colocado em `SLACK_WEBHOOK_URL`.

## Configuração

No Slack:

1. Abra/crie o App do SkillGraph.
2. Em OAuth & Permissions, adicione o scope `chat:write`.
3. Instale/reinstale o app no workspace.
4. Copie o Bot User OAuth Token, normalmente iniciado por `xoxb-`.
5. Convide o bot para o canal de destino.
6. Copie o ID do canal, normalmente iniciado por `C` (canal público/privado), `G` (grupo) ou `D` (mensagem direta).

No `.env` local:

```env
SLACK_ALERTS_ENABLED=true
SLACK_BOT_TOKEN=xoxb-seu-token
SLACK_CHANNEL_ID=C0123456789
SLACK_ALERT_COOLDOWN_SECONDS=900
```

Nunca publique o token no GitHub. O código envia somente severidade, assunto, trace ID, rota, timestamp, métrica, valor e limite. Currículos, PII, prompts e respostas completas não são enviados.

## Erros comuns

- `missing_scope`: adicione `chat:write` e reinstale o app;
- `channel_not_found`: confira o ID e convide o bot ao canal;
- `no_permission`: o bot não pode publicar no canal;
- `rate_limited`: aguarde o Retry-After e não reduza o cooldown.
