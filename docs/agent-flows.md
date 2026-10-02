# Fluxos de conversa multiagente

O Core Router é acionado em cada turno. Os agentes não formam uma cadeia fixa; o estado da conversa permite que qualquer rota compatível seja chamada em seguida.

## Currículo → lacunas → treinamentos

```text
chat + PDF
  → Resume Interpreter/JEV
  → Core + EmployeeProfile
  → pergunta de lacunas
  → Gap Agent
  → Core
  → pergunta de treinamento
  → Learning Path Agent/DuckDB read-only
  → Core → Synthesizer
```

## Perfil manual → ML → política

```text
mensagem com competências
  → Core
  → Prediction Agent/PKL-XAI
  → Core
  → Policy Agent/Dify
  → Core → Synthesizer
```

## Dados estruturados

```text
pergunta de indicador
  → Core
  → Structured Data Specialist
  → funções DuckDB existentes
  → Core → Synthesizer
```

O DuckDB nunca é usado para treinar o PKL e o Prediction Agent nunca consulta as tabelas estruturadas.
