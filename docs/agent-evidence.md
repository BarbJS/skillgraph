# Evidências do sistema multiagente — Etapa 2

Este documento registra os cenários multiagente definidos para avaliação da Etapa 2. A execução local pode usar fixtures/mocks para testes determinísticos; chamadas live a JEV, Dify e LM Studio são opcionais e não fazem parte da CI.

## Rotas e ferramentas

| Cenário | Rota | Agentes principais | Ferramenta/camada |
|---|---|---|---|
| Predição de trilha | `ml_prediction` | Core → Prediction → Reviewer → Synthesizer | PKL/XAI |
| Recomendação de treinamento | `training_recommendation` | Core → Learning Path → Reviewer → Synthesizer | DuckDB read-only |
| Política | `policy_rag` | Core → Policy → Reviewer → Synthesizer | Dify Chatflow |
| Currículo | `resume_analysis` | Core → Resume Interpreter → Profile → Reviewer → Synthesizer | OCR/PyMuPDF + JEV backend |

O Core Router continua sendo obrigatório. Com `CREWAI_ENABLED=true`, o chat principal encaminha perguntas de treinamentos e políticas para o runtime multiagente; o especialista é escolhido por rota e agentes de outras especialidades não são instanciados. Quando o CrewAI está desativado ou indisponível, as rotas normais preservam o fallback legado de RAG/SQL. Cada ferramenta recebe somente os argumentos e permissões necessários.

## Currículo

A rota de currículo usa uma chamada backend-mediated ao JEV. Essa decisão evita depender de tool calling incompatível com alguns modelos locais do LM Studio. O resultado do JEV é entregue ao Resume Interpreter como JSON sanitizado; o currículo é redigido e não é persistido.

## Limitações

- O roteamento determinístico seleciona uma rota candidata antes da crew; o Core confirma e coordena essa rota.
- O processo é sequencial dentro da rota.
- O resultado exige revisão humana e não é uma decisão de emprego.
- Execuções live devem ser registradas sem PII e com o modelo/configuração utilizados.
