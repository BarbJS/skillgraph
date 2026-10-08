# Toxicidade e tom das respostas

A camada de toxicidade é um output gate do SkillGraph, não um agente separado. Ela protege respostas do chat e da síntese multiagente.

- modo padrão: regras determinísticas locais, sem custo;
- modo live opcional: `ToxicityMetric` do DeepEval com judge local;
- score alto significa resposta segura;
- resposta abaixo do threshold é substituída por uma resposta profissional;
- o texto tóxico não é enviado para Langfuse ou Slack;
- o modelo não deve responder agressivamente mesmo quando a entrada é rude.

Configuração:

```env
TOXICITY_THRESHOLD=0.90
TOXICITY_LIVE_ENABLED=false
```
