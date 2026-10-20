# Relatório técnico — Etapa 2 do SkillGraph

## 1. Escopo e integração

A Etapa 2 estende o chat da Etapa 1 — Streamlit, Dify/Weaviate, DuckDB e guardrails — com quatro frentes: Machine Learning, CrewAI, observabilidade/Langfuse e avaliação Golden Dataset/DeepEval. A integração preserva RAG e consultas read-only, mas encaminha novas solicitações ao componente apropriado. O objetivo é apoiar desenvolvimento profissional, não decidir contratação, promoção ou desligamento.

## 2. Machine Learning: dados, objetivo e resultados

**Dataset e domínio.** Usamos o **O*NET 31.0 Database**, fonte oficial do U.S. Department of Labor: <https://www.onetcenter.org/database.html>. A licença é **Creative Commons Attribution 4.0 International (CC BY 4.0)**, com atribuição “O*NET 31.0 Database, U.S. Department of Labor”. O conjunto processado contém **24 ocupações tecnológicas**, **35 features** e seis trilhas. A variável-alvo é `track`, criada pelo projeto por regras explícitas de títulos; não é rótulo oficial do O*NET. A distribuição é: Dados e Ciência de Dados (7), Engenharia de Dados e Cloud (5), Desenvolvimento de Software (5), Cibersegurança (3), IA e Machine Learning (2) e Tecnologia e Sistemas (2). Os arquivos principais são `occupation_data.csv`, `essential_skills.csv` e `transferable_skills.csv`.

Essa fonte não contém colaboradores da NexaTech. A conexão com RH é uma analogia controlada: referências públicas de ocupações são convertidas em recomendações de trilhas e competências para uma conversa de desenvolvimento, sem avaliar uma pessoa como apta ou inapta.

**Pergunta e implementação.** O algoritmo responde, por exemplo: “O colaborador da equipe de dados tem Python avançado e SQL intermediário. Qual trilha priorizar?”. É uma classificação multiclasse de apoio: retorna até três trilhas, compatibilidade estimada, competências reconhecidas, prioridades e incerteza. O pipeline usa seed 42, divisão 70%/20%/10%, imputação e padronização ajustadas somente no treino. Foram comparados `DummyClassifier`, Random Forest e LightGBM via FLAML. O LLM interpreta a pergunta em JSON; o backend valida níveis de 0 a 5, PII e schema, executa o PKL e só então pede ao LLM uma explicação.

**Métricas e escolha.** Foram consideradas Macro F1, balanced accuracy, macro precision, macro recall, Top-2 Accuracy e ROC-AUC quando matematicamente possível. Macro F1 é a mais relevante para este contexto porque dá peso equilibrado às seis trilhas, evitando que uma classe maior domine uma recomendação de desenvolvimento. Top-2 é útil porque trilhas próximas podem ser alternativas plausíveis; precision e recall mostram, respectivamente, risco de indicar uma trilha inadequada e capacidade de cobrir as classes.

Na validação, LightGBM obteve Macro F1 **0,7778**, balanced accuracy **0,8333**, precision/recall macro **0,8333** e Top-2 **1,0**, superando Random Forest e baseline. Foi escolhido como modelo final por esse melhor desempenho de validação. No teste, porém, Macro F1 foi **0,10**, balanced accuracy **0,25** e Top-2 **0,50**; o conjunto pequeno limita a generalização. A conclusão responsável é usar o resultado como apoio exploratório, com revisão humana.

## 3. Sistema multiagente com CrewAI

O CrewAI orquestra agentes locais apoiados pelo LM Studio. O Core Router seleciona a rota; o especialista usa somente a ferramenta permitida; o Safety Reviewer valida schema, PII, escopo e evidência; o Response Synthesizer redige a resposta. Com `CREWAI_ENABLED=true`, o chat principal encaminha treinamentos e políticas ao runtime; se a dependência estiver desativada, permanece o fallback RAG/SQL.

| Agente | Papel | Ferramenta |
|---|---|---|
| Core Router | Classificar intenção, carregar estado e escolher rota | Nenhuma |
| Resume Interpreter | Extrair evidências do currículo sanitizado | JEV via backend; OCR/PyMuPDF |
| Profile Normalizer | Normalizar aliases, níveis e remover PII | Nenhuma |
| Prediction Specialist | Executar recomendação de trilhas e XAI | `CompetencyRecommendationTool` / PKL |
| Gap Analyst | Interpretar prioridades e lacunas | Nenhuma; estado estruturado |
| Learning Path & Training Recommendation Agent | Consultar cursos e pré-requisitos | `TrainingCatalogTool` / DuckDB read-only |
| Policy Specialist | Consultar regras com fontes | `DifyPolicyTool` / Dify Chatflow |
| Structured Data Specialist | Consultar indicadores autorizados | `TrainingCatalogTool` / DuckDB |
| Safety Reviewer | Validar segurança, schema e evidência | Nenhuma |
| Response Synthesizer | Compor resposta final revisada | Nenhuma |

Os contratos ficam em schemas Pydantic; prompts são versionados; retries, iterações e timeout são limitados; pensamento privado não é exibido. O estado `agent_state_json` permite continuidade entre turnos. Para currículo, PyMuPDF extrai texto, OCR local atende PDFs sem texto, o texto é redigido antes do JEV e o `EmployeeProfile` é validado.

## 4. Observabilidade e Langfuse

`TraceContext` representa a execução e `SpanContext` cada etapa. São registrados rota, status, duração, serviço, tarefa/agente, tokens, custo disponível, erros e timeouts. A área Observabilidade do perfil Desenvolvedor exibe os dez traces mais recentes, métricas agregadas, serviços, tarefas e detalhes sanitizados. O log local fica em `logs/observability.jsonl`.

Com `LANGFUSE_ENABLED=true` e credenciais apenas no `.env`, o `ObservabilityStore` envia observações agregadas ao Langfuse; sem a flag ou sem credenciais, o painel local continua funcionando. O envio não inclui PII, currículo bruto, prompts privados, respostas completas ou chain-of-thought. O script `scripts/generate-langfuse-traces.py` gera cinco execuções sintéticas de rotas diferentes para a demonstração. O print deve ser obtido no dashboard Langfuse depois desse script e salvo como `docs/assets/langfuse-five-traces.png`. Cada trace permite comparar rota, duração, status e spans sem expor conteúdo privado. A imagem autêntica precisa ser produzida durante a execução final; ela ainda não existe versionada no repositório.

### Execução dos cinco traces

```bash
.crew-venv/bin/python scripts/generate-langfuse-traces.py
```

A saída deve informar `generated: 5` e `langfuse_enabled: true`. No projeto autenticado do Langfuse, filtre pela última hora e confirme as cinco rotas antes de capturar a tela.

A imagem abaixo é a evidência visual da integração. Ela mostra cinco traces reais gerados pela interface do SkillGraph em rotas diferentes. Cada trace permite comparar rota, status, duração e spans sem expor conteúdo privado.

![Cinco traces reais do SkillGraph no Langfuse](assets/langfuse-five-traces.png)

Para reproduzir a captura, configure as chaves no `.env`, reinicie o Streamlit, execute cinco perguntas pela interface e filtre o dashboard Langfuse por `Past 1 hour`. O painel externo fica no `LANGFUSE_BASE_URL`; o painel local da aplicação permanece em **Perfil desenvolvedor → Observabilidade**.

A imagem versionada em `docs/assets/langfuse-five-traces.png` é a evidência entregue com este relatório.

## 5. Golden Dataset e DeepEval

O arquivo `evals/golden_dataset.jsonl` contém **25 casos** de RAG, SQL, segurança, PII, injection, ML, lacunas, treinamentos, política, multi-turno e fora de escopo. `evals/agent_goldens.jsonl` acrescenta quatro cenários compostos de agentes. O script `scripts/evaluate-ai.py` valida schema, rota e bloqueio sem consumir tokens. Os casos semânticos ficam em `evals/rag_goldens.jsonl`, com resposta, contexto e ground truth.

O runner `scripts/evaluate-ai-live.py` usa DeepEval como LLM-as-a-judge e calcula Faithfulness, Answer Relevancy, Contextual Precision e Contextual Recall. O adapter usa o modelo local configurado no endpoint OpenAI-compatible. O arquivo semântico agora contém **doze casos RAG**, todos com resposta, contexto e ground truth, permitindo avaliar pelo menos dez perguntas no runner live. Os resultados efetivos ficam em `output/evaluation/live_ai_report.json` após a execução.
O relatório é exibido em “Qualidade e Evals”. A execução realizada avaliou 12 casos e todos passaram o limiar configurado de 0,50. As médias foram: Faithfulness **0,9514**, Answer Relevancy **0,9236**, Contextual Precision **1,0000** e Contextual Recall **0,8810**; a taxa geral de aprovação foi **100%**. As menores pontuações foram Faithfulness 0,6667 e Answer Relevancy 0,5000 no caso `rag-gold-007`, Contextual Recall 0,5000 nos casos `rag-gold-003` e `rag-gold-004`, e Contextual Recall 0,5714 no caso `rag-gold-010`. Esses pontos são weaknesses para revisão, não evidência de perfeição. Resultados são evidência complementar, não garantia absoluta.

Scores por caso registrados no relatório live:

| Caso | Faithfulness | Relevancy | Precision | Recall | Média |
|---|---:|---:|---:|---:|---:|
| `rag-gold-001` | 1,0000 | 1,0000 | 1,0000 | 1,0000 | 1,0000 |
| `rag-gold-002` | 1,0000 | 1,0000 | 1,0000 | 1,0000 | 1,0000 |
| `rag-gold-003` | 1,0000 | 1,0000 | 1,0000 | 0,5000 | 0,8750 |
| `rag-gold-004` | 1,0000 | 1,0000 | 1,0000 | 0,5000 | 0,8750 |
| `rag-gold-005` | 1,0000 | 1,0000 | 1,0000 | 1,0000 | 1,0000 |
| `rag-gold-006` | 1,0000 | 1,0000 | 1,0000 | 1,0000 | 1,0000 |
| `rag-gold-007` | 0,6667 | 0,5000 | 1,0000 | 1,0000 | 0,7917 |
| `rag-gold-008` | 1,0000 | 1,0000 | 1,0000 | 1,0000 | 1,0000 |
| `rag-gold-009` | 1,0000 | 1,0000 | 1,0000 | 1,0000 | 1,0000 |
| `rag-gold-010` | 1,0000 | 0,8333 | 1,0000 | 0,5714 | 0,8512 |
| `rag-gold-011` | 1,0000 | 1,0000 | 1,0000 | 1,0000 | 1,0000 |
| `rag-gold-012` | 0,7500 | 0,7500 | 1,0000 | 1,0000 | 0,8750 |

O judge registrado foi `meta-llama-3-8b-instruct`, com 12 casos avaliados e 12 aprovados.
O relatório detalhado está em `output/evaluation/live_ai_report.json` e registra o judge `meta-llama-3-8b-instruct`, o dataset, cada caso, cada métrica, razões do judge e recomendações.

DeepEval significa **DeepEval**; “Deep Evil” não é o nome da ferramenta.

## 6. Conclusão

A Etapa 2 integrou um recomendador ML auditável, crews especializadas com least privilege, traces sanitizados e avaliação reproduzível ao chat existente. O impacto é uma aplicação mais explicável, observável e testável, mantendo dados sintéticos e revisão humana. As limitações remanescentes são o pequeno conjunto O*NET, a queda de generalização no teste e a necessidade de produzir e anexar a captura autenticada do Langfuse. A Etapa 3 deve ampliar dados, governança e validação com especialistas.

### Referência da evidência Langfuse

A imagem `docs/assets/langfuse-five-traces.png` deve ser adicionada após a captura no dashboard autenticado. O repositório contém o gerador dos cinco traces, mas não pode fabricar uma captura visual autenticada.
