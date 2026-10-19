# SkillGraph — Documentação completa da Etapa 2

## 1. Contexto e objetivo

A Etapa 2 dá continuidade à fundação criada na Etapa 1 com uma camada de Machine Learning tradicional para apoiar o desenvolvimento de colaboradores em competências técnicas.

A pergunta de negócio é:

> **Dado o conjunto de competências de um colaborador informado por um analista ou gestor de RH, quais trilhas técnicas são mais compatíveis e quais competências devem ser priorizadas para desenvolvimento na era da IA generativa?**

A pessoa usuária da área ML não descreve o próprio perfil necessariamente. O uso principal é feito por analistas e gestores de RH que descrevem um colaborador de forma não identificadora. O sistema não toma decisões de contratação, promoção, remuneração, punição ou desligamento.

## 2. Escopo e arquitetura da Etapa 2

A Etapa 2 adiciona uma área própria ao Streamlit, disponível aos três perfis simulados: desenvolvedor, gestor e RH.

```text
Analista/gestor descreve um colaborador sem PII
  ↓
LM Studio interpreta competências e níveis em JSON
  ↓
Backend valida schema, níveis e privacidade
  ↓
Backend carrega skillgraph_competency_tracks.pkl
  ↓
Modelo calcula trilhas Top-3 e prioridades de desenvolvimento
  ↓
LM Studio explica somente o resultado calculado
  ↓
Resposta na aba Machine Learning
```

A rota ML é deliberadamente separada:

- não consulta DuckDB;
- não usa `data_bd/`;
- não consulta o Chatflow Dify;
- não usa o corpus RAG;
- não treina durante uma pergunta;
- não recebe identificadores pessoais;
- não registra perfil completo ou resposta completa nos logs.

A Etapa 1 permanece responsável por RAG, DuckDB, Dify, Weaviate, Streamlit, segurança e observabilidade conversacional. A Etapa 2 usa o LM Studio local diretamente para interpretação e explicação, mantendo o Dify inalterado.

### 2.1 Mapa das quatro frentes desenvolvidas

A Etapa 2 foi organizada em quatro frentes integradas. Cada frente resolve um problema diferente e amplia a capacidade da aplicação sem substituir os fluxos confiáveis da Etapa 1:

| Frente | Para que serve | Como foi desenvolvida | Integração com o projeto | Impacto para o usuário final |
|---|---|---|---|---|
| **Machine Learning** | Recomendar trilhas e priorizar competências a partir de um perfil não identificador | O*NET 31.0, transformação controlada de ocupações, FLAML, comparação de modelos, artefato PKL, validação e XAI | A aba Machine Learning usa o LM Studio para interpretar a pergunta e o backend para validar o perfil e executar o PKL; não mistura ML com RAG ou DuckDB | Recebe uma recomendação exploratória de desenvolvimento com ranking, prioridades, competências reconhecidas e incerteza |
| **Sistema multiagente** | Encaminhar cada solicitação ao especialista e à ferramenta adequados | CrewAI, Core Router, crews por rota, contratos Pydantic, ferramentas allowlisted, Reviewer e Synthesizer | O chat principal chama o runtime CrewAI quando habilitado; as rotas de treinamentos e políticas usam DuckDB ou Dify, e o fallback legado permanece disponível | Recebe respostas mais especializadas, rastreáveis e com menor privilégio por agente |
| **Observabilidade e Langfuse** | Tornar execuções, latência, erros, consumo e etapas técnicas auditáveis | `TraceContext`, `SpanContext`, logs sanitizados, métricas agregadas, painel do Desenvolvedor e envio opcional ao Langfuse | Os traces são criados nas rotas de RAG, DuckDB, CrewAI, OCR e JEV; a aba ML possui métricas e explicabilidade próprias e não cria trace automático no caminho atual; a integração externa é opt-in | Permite investigar falhas e desempenho sem expor PII, currículo bruto, prompts privados ou chain-of-thought |
| **Golden Dataset e DeepEval** | Verificar contratos, roteamento, bloqueios e qualidade semântica das respostas | Golden Dataset versionado, testes offline, runner live e quatro métricas DeepEval como LLM-as-a-judge | Os casos e relatórios aparecem na área Qualidade e Evals; a execução live é explícita e separada do caminho normal da aplicação | Dá evidência de qualidade e regressão, ajudando a evitar respostas sem fonte ou mudanças que quebrem o comportamento esperado |

Nas seções seguintes, cada frente é descrita em termos de objetivo, desenvolvimento, integração, impacto e limitações. Essa separação também permite explicar a contribuição da Etapa 2 para o projeto e para cada perfil de usuário sem confundir recomendação, execução técnica, observabilidade e avaliação.

## 3. Fonte de dados e licença

A base de treinamento é exclusivamente o **O*NET 31.0 Database**, mantido pelo U.S. Department of Labor:

- página oficial: <https://www.onetcenter.org/database.html>;
- arquivo utilizado: <https://www.onetcenter.org/dl_files/database/db_31_0_csv.zip>;
- licença: Creative Commons Attribution 4.0 International (CC BY 4.0);
- atribuição: `O*NET 31.0 Database, U.S. Department of Labor`.

O O*NET descreve ocupações, habilidades, conhecimentos e competências profissionais. Ele não contém históricos individuais dos colaboradores da NexaTech. O treinamento usa somente referências ocupacionais públicas.

Os arquivos baixados ficam em `.ml_artifacts/onet/`, ignorado pelo Git. O artefato e o relatório ficam em `.ml_artifacts/` e também não são publicados.

### Transformação da fonte

O projeto seleciona ocupações de tecnologia por regras explícitas de título e cria trilhas agregadas:

- Desenvolvimento de Software;
- Dados e Ciência de Dados;
- Engenharia de Dados e Cloud;
- Cibersegurança;
- IA e Machine Learning;
- Tecnologia e Sistemas.

Essa agregação é uma transformação do projeto, não uma classificação oficial do O*NET. A versão da fonte, as regras, a licença e as modificações ficam registradas no relatório e no PKL.

A competência de IA generativa é tratada como complemento de linguagem e planejamento quando informada pelo usuário. Ela não é apresentada como uma competência oficial do O*NET quando não estiver presente na fonte.

## 4. Tipo de problema e target

O problema é **classificação supervisionada multiclasse**. Cada linha de treinamento representa uma ocupação tech com um vetor de níveis de competências O*NET e uma classe `track` criada pelo agrupamento documentado.

O modelo não classifica uma pessoa como apta ou inapta. Durante a inferência, o vetor descrito pelo RH é comparado às referências ocupacionais e o backend retorna:

- até três trilhas compatíveis;
- compatibilidade estimada;
- competências reconhecidas;
- competências prioritárias para desenvolvimento.

O resultado é uma recomendação de apoio a uma conversa de desenvolvimento, com revisão humana obrigatória.

## 5. Planejamento do treinamento

### 5.1 Ingestão e análise

O script `scripts/train-ml.py`:

1. baixa/extrai o arquivo oficial O*NET;
2. valida arquivos obrigatórios e schema;
3. filtra ocupações tech;
4. lê níveis de `essential_skills.csv` e `transferable_skills.csv`;
5. cria uma matriz ocupação × competência;
6. registra quantidade de ocupações, competências, trilhas, nulos e distribuição das classes.

### 5.2 Divisão e leakage

A divisão padrão é determinística com `seed=42`:

- 70% treino;
- 20% validação;
- 10% teste.

A imputação e a padronização são ajustadas exclusivamente no treino e aplicadas sem novo ajuste à validação e ao teste. O teste só é consultado após o modelo e seus hiperparâmetros serem congelados.

A base O*NET possui poucas ocupações após o filtro de títulos. Por isso, os resultados são demonstrativos e devem ser interpretados com cautela; uma evolução futura deve aumentar o corpus e realizar divisão por grupos ocupacionais relacionados.

### 5.3 Modelos comparados

O FLAML é clonado pelo `scripts/bootstrap-flaml.sh` na tag `v2.7.0` e instalado com os extras AutoML.

São comparados:

1. `DummyClassifier(strategy="prior")` como baseline;
2. Random Forest (`rf`) via FLAML;
3. LightGBM (`lgbm`) via FLAML.

O FLAML recebe `task="classification"`, `metric="macro_f1"`, validação externa, orçamento de tempo, seed e lista restrita de estimadores. Labels textuais são codificados numericamente para o FLAML e restaurados pelo wrapper do artefato.

### 5.4 Fine-tuning

O modelo vencedor recebe uma segunda busca FLAML. Para Random Forest, a busca pode explorar `n_estimators` e `max_features`. Para LightGBM, pode explorar `learning_rate`, `num_leaves` e `n_estimators`.

O fine-tuning só é promovido quando não piora o Macro F1 de validação. O conjunto de teste não participa dessa escolha.

## 6. Métricas e resultado executado

As métricas escolhidas são:

- **Macro F1:** principal, dando peso equilibrado às trilhas;
- **Balanced Accuracy:** reduz o efeito de classes desbalanceadas;
- **Macro Precision:** indica falsos positivos agregados;
- **Macro Recall:** indica cobertura agregada das trilhas;
- **Top-2 Accuracy:** útil quando duas trilhas próximas são plausíveis;
- **ROC-AUC OvR:** exibida somente quando há suporte matemático suficiente.

Na execução local registrada, o conjunto resultou em 24 ocupações tech, 35 features e seis trilhas. A comparação de validação observada foi:

| Modelo | Macro F1 | Balanced Accuracy | Macro Precision | Macro Recall | Top-2 Accuracy |
|---|---:|---:|---:|---:|---:|
| Baseline prior | 0,2222 | 0,3333 | 0,1667 | 0,3333 | 0,7500 |
| Random Forest FLAML | 0,5556 | — | — | — | — |
| LightGBM FLAML | **0,7778** | **0,8333** | **0,8333** | **0,8333** | **1,0000** |

O modelo selecionado foi o **LightGBM via FLAML**, por apresentar o melhor Macro F1 e a melhor balanced accuracy na validação. A execução de teste registrou Macro F1 de 0,10, balanced accuracy de 0,25 e Top-2 Accuracy de 0,50. Essa diferença reforça a limitação do conjunto pequeno e impede qualquer afirmação de prontidão produtiva.

As métricas atualizadas de cada execução ficam em `.ml_artifacts/competency_report.json`; os números acima documentam a execução local utilizada nesta etapa.

## 7. Artefato e operação

O modelo final é salvo em:

```text
.ml_artifacts/skillgraph_competency_tracks.pkl
```

O PKL contém:

- pré-processador;
- modelo final;
- nomes das features;
- classes/trilhas;
- perfis medianos de competências por trilha;
- versão O*NET;
- URL e licença;
- atribuição;
- seed;
- configuração FLAML;
- métricas de validação e teste;
- timestamp de criação.

Comandos:

```bash
make bootstrap-crewai
make bootstrap-flaml
make train-ml
make run
```

A instalação do FLAML fica em `.flaml/`, também ignorada pelo Git. A Etapa 2 não exige alteração no Docker/Dify: o Docker continua executando o Dify da Etapa 1, enquanto o Streamlit e o LM Studio executam a rota ML localmente.

## 8. Integração com LLM e usuários de RH

O interpretador LLM aceita perguntas como:

> O colaborador da equipe de dados tem Python avançado, SQL intermediário e está começando em IA generativa. Qual trilha priorizar?

Ele deve retornar somente um JSON interno com `action`, `employee_context`, `skills` e `goal`. O backend normaliza aliases como Python, SQL, análise de dados, cloud e Machine Learning, valida níveis de 0 a 5 e rejeita PII.

O LLM não pode:

- abrir o PKL;
- executar código;
- escolher arquivos;
- consultar DuckDB;
- consultar Dify;
- inventar níveis ou competências;
- produzir decisões laborais.

A explicação final recebe apenas o resultado estruturado calculado pelo backend.

### 8.1 Integração e impacto do Machine Learning

A integração preserva a separação de responsabilidades da Etapa 1: o Streamlit apresenta a interface, o LM Studio interpreta e explica, e o backend controla validação, artefato, cálculo e limites. O PKL não é treinado durante uma pergunta, não consulta o corpus RAG nem as tabelas do DuckDB e não recebe identificadores pessoais.

Para o projeto, isso adiciona uma capacidade preditiva auditável sem transformar o LLM em executor de código ou decisor de RH. Para o analista ou gestor, o impacto é uma recomendação de trilha acompanhada de prioridades, competências reconhecidas, desconhecidas e incerteza. Para o usuário desenvolvedor, a aba técnica expõe métricas, cobertura e XAI quando disponível. Para todos os perfis, a recomendação permanece exploratória e exige validação humana.

## 9. Segurança, privacidade e limites

- Nunca enviar nome completo, CPF, e-mail, telefone ou endereço do colaborador.
- Usar rótulos não identificadores, como “colaborador da equipe de dados”.
- Não guardar o perfil completo em logs.
- Não usar o modelo para ranking de pessoas ou decisões de emprego.
- Validar a recomendação com o colaborador, gestor e RH.
- Considerar que O*NET é uma referência norte-americana, não um retrato completo do mercado brasileiro.
- Considerar que IA generativa evolui rapidamente e exige fontes complementares e atualização do catálogo.

## 10. Arquivos da Etapa 2

- `src/ml_pipeline.py`: ingestão O*NET, treinamento, métricas, artefato e recomendação;
- `src/ml_assistant.py`: contrato LLM, validação de perfil e explicação;
- `scripts/bootstrap-flaml.sh`: clone pinado e instalação do FLAML;
- `scripts/train-ml.py`: treinamento reprodutível;
- `tests/test_ml_pipeline.py` e `tests/test_ml_assistant.py`: testes da etapa;
- `docs/ml-traditional.md`: guia resumido do workflow;
- `docs/ml-llm-integration.md`: integração LLM → PKL;
- `docs/evaluation-ml.md`: critérios de avaliação.

## 11. XAI e explicabilidade

A Etapa 2 inclui explicabilidade em duas camadas. Para RH e gestores, o backend retorna uma explicação simples com trilhas, competências reconhecidas, competências não reconhecidas, lacunas, prioridades e um nível de incerteza baseado na diferença entre as duas maiores probabilidades. Competências desconhecidas nunca são convertidas silenciosamente para zero: aparecem explicitamente como não reconhecidas e não influenciam a recomendação.

Para o perfil desenvolvedor, o projeto usa SHAP `TreeExplainer` quando o modelo de árvore suporta a técnica. O painel técnico pode exibir contribuições locais e importância global das features. SHAP explica associação preditiva, não causalidade. Se SHAP não estiver disponível ou não for compatível com o estimador, o backend retorna uma explicação vazia/fallback seguro, sem inventar fatores.

O Microsoft Responsible AI Toolbox fica como evolução futura para análise de erros e fairness. Alibi não faz parte desta implementação.

## 12. Sistema multiagente com CrewAI e JEV

**Objetivo e impacto.** Esta frente transforma a conversa em rotas especializadas: em vez de um agente genérico com acesso a tudo, o sistema seleciona o especialista e a ferramenta mínima para cada intenção. Para o projeto, isso conecta as capacidades novas à fundação da Etapa 1; para o usuário, produz respostas mais delimitadas, rastreáveis e compatíveis com evidências.

**Desenvolvimento e implementação.** O CrewAI foi usado como orquestrador local sobre o LM Studio, com factory de crews por rota, prompts versionados, contratos Pydantic, limites de iteração, retry e timeout, `allow_delegation=False`, guardrails de entrada e revisão final. O Core Router classifica cada turno; o especialista executa somente a tarefa da rota; o Safety Reviewer verifica schema, PII, escopo e evidência; e o Response Synthesizer redige a resposta final. O pensamento privado do modelo não faz parte do contrato público: a interface expõe somente etapas estruturadas e sanitizadas.

**Integração.** O runtime é chamado pelo chat principal quando `CREWAI_ENABLED=true`. As perguntas de treinamentos usam a rota `training_recommendation` e `TrainingCatalogTool` sobre DuckDB read-only; perguntas de política usam `policy_rag` e `DifyPolicyTool` sobre o Chatflow existente. A rota `resume_analysis` combina extração PDF/OCR, perfil, JEV e agentes. Se o CrewAI estiver desativado ou indisponível, o chat preserva o fallback legado de RAG/SQL, permitindo executar a aplicação sem a dependência opcional.

**Impacto para os usuários.** O analista ou gestor recebe uma resposta de treinamento ou política produzida por um especialista delimitado, com fontes ou registros autorizados. O perfil Desenvolvedor consegue visualizar a rota, a ferramenta e os spans sem acessar conteúdo privado. A revisão humana continua obrigatória.

### 12.1 Componentes e fluxo de dados

A implementação está distribuída entre `src/agents/router.py` (seleção), `src/agents/crew.py` (factory), `src/agents/runtime.py` (execução), `src/agents/schemas.py` (contratos), `src/agents/guardrails.py` (permissões) e `src/agents/tools.py` (fronteiras). O fluxo de uma pergunta normal é:

```text
mensagem
  → guardrail de entrada
  → Core Router
  → especialista da rota
  → ferramenta allowlisted, quando necessária
  → Safety Reviewer
  → Response Synthesizer
  → resposta + state_patch + trace sanitizado
```

Esse desenho evita misturar o cálculo ML, as consultas DuckDB e o RAG documental na mesma ferramenta e mantém a compatibilidade com a Etapa 1.

### 12.2 Currículo, OCR e JEV

O fluxo de currículo também é uma aplicação prática do sistema multiagente. O PDF é validado e limitado a 10 MB; o PyMuPDF extrai texto e, quando não há texto extraível, o OCR local é acionado. O currículo temporário não é persistido. O texto é redigido antes da chamada opcional ao JEV, e o resultado estruturado é convertido em `EmployeeProfile` validado. Para o usuário, isso transforma um PDF em competências, níveis, confiança, evidências, itens não reconhecidos e informações ausentes, sem apresentar o currículo bruto como resposta final.

A integração JEV permanece opcional (`JEV_ENABLED=false` por padrão). Quando desativada ou sem credencial, o sistema informa que a extração estruturada não foi concluída, sem fingir que houve uma chamada externa.

A relação entre a interface existente e as ferramentas da Etapa 2 é:

```text
Streamlit → Core Router/CrewAI → especialista da rota
                                ├── TrainingCatalogTool → DuckDB read-only
                                ├── DifyPolicyTool → Dify/Weaviate
                                ├── CompetencyRecommendationTool → PKL/XAI
                                └── Resume/OCR → JEV opcional
```

### O Core Router e o estado da conversa

O Core Router não executa todas as tarefas e não força uma cadeia linear de nove agentes. A cada turno, ele classifica a intenção e escolhe somente a rota necessária. O resultado do especialista retorna ao Core como um `state_patch`.

O estado estruturado é persistido por conversa em `agent_state_json`, separado do texto visual do histórico. Assim, uma conversa pode seguir caminhos diferentes:

```text
Turno 1: PDF → Resume Interpreter → perfil estruturado → Core
Turno 2: pergunta sobre lacunas → Gap Agent → Core
Turno 3: pergunta sobre cursos → Learning Path Agent → Core
Turno 4: pergunta sobre política → Policy Agent/Dify → Core
```

Rotas principais:

| Rota | Agente especialista | Fonte/ferramenta permitida |
|---|---|---|
| `resume_analysis` | Resume Interpreter + Profile | extractor local e JEV |
| `ml_prediction` | Prediction Specialist | PKL/XAI de competências |
| `gap_analysis` | Gap Analyst | estado estruturado |
| `training_recommendation` | Learning Path & Training Recommendation | funções read-only do DuckDB |
| `policy_rag` | Policy Specialist | Chatflow Dify existente |
| `structured_data` | Structured Data Specialist | funções DuckDB existentes |
| `smalltalk` | Core/local | nenhuma chamada externa |

### Agentes e tarefas

Cada agente pode executar mais de uma tarefa dentro do próprio escopo. A crew não é “uma tarefa por agente”. Por exemplo:

- **Core Router:** classificar intenção, carregar estado, escolher rota, decidir esclarecimento e solicitar síntese;
- **Resume Interpreter:** validar texto, chamar JEV, extrair evidências e validar JSON;
- **Profile Agent:** normalizar aliases, remover PII, validar níveis e mesclar o perfil ao estado;
- **Prediction Agent:** validar perfil, invocar PKL, calcular trilhas, incerteza e XAI;
- **Gap Agent:** comparar perfil/trilha, separar desconhecido de lacuna e ordenar prioridades;
- **Learning Path Agent:** consultar catálogo, verificar pré-requisitos e validar cursos existentes;
- **Policy Agent:** formular pergunta delimitada, chamar Dify, preservar fontes e declarar ausência;
- **Reviewer:** validar schema, PII, escopo, evidências e decisões indevidas;
- **Synthesizer:** compor resposta final somente a partir dos JSONs revisados.

### ReAct controlado

Quando `CREWAI_AGENT_REASONING=true` e a versão do CrewAI/modelo oferece suporte, os agentes especialistas podem planejar uma ação antes de executar uma ferramenta, mas com limites explícitos. O padrão do projeto mantém esse modo desativado para favorecer compatibilidade com modelos locais:
```text
Reason/Plan interno breve
  ↓
Act: uma ferramenta permitida
  ↓
Observe: resultado estruturado
  ↓
Validate: schema, escopo e evidência
  ↓
Handoff: Core Router/state_patch
```

O pensamento privado não é exibido nem persistido. A configuração usa `reasoning=True`, limite de iterações e `allow_delegation=False` quando suportado pela versão do CrewAI. O Core é o único componente que escolhe a próxima rota.

### Least privilege

Cada agente recebe somente a ferramenta mínima necessária:

- Resume Interpreter → `JevResumeExtractionTool`;
- Prediction Specialist → `CompetencyRecommendationTool`;
- Learning Path Agent → `TrainingCatalogTool`;
- Policy Agent → `DifyPolicyTool`;
- Core, Profile, Gap, Reviewer e Synthesizer → nenhuma ferramenta externa.

O DuckDB não treina nem executa a predição ML. O Prediction Agent não consulta DuckDB. O JEV não é um agente: é um serviço externo chamado como ferramenta pelo Resume Interpreter.

### Guardrails em camadas

Não existe um agente genérico com acesso a tudo. Os guardrails são distribuídos:

1. **Input gate:** tamanho, PII, prompt injection, escopo e limites de arquivos;
2. **Tool gate:** allowlist por agente, argumentos validados, timeout e retries limitados;
3. **State gate:** schemas Pydantic, campos permitidos e ausência de PII;
4. **Reviewer:** evidências, incerteza, competências desconhecidas e decisões laborais;
5. **Output gate:** resposta final fundamentada, sem dados inventados ou comandos.

### JEV e currículo

O upload ocorre no chat principal do Streamlit. O usuário pode enviar uma mensagem e um PDF. O processamento previsto é:

```text
PDF temporário
  ↓
PyMuPDF: extração de texto
  ↓
OCR local para PDFs escaneados quando a extração de texto não retorna conteúdo
  ↓
state JSON higienizado
  ↓
JevClient → POST /v1/systemone
  ↓
answers tipados: Score, Choice e Noul
  ↓
EmployeeProfile validado
```

A chave não é necessária para preparar o código. Enquanto `JEV_ENABLED=false`, nenhum crédito é consumido e a chamada externa não ocorre. Quando a credencial estiver disponível:

```env
JEV_ENABLED=true
TYPESAFE_API_KEY=sua-chave
JEV_API_BASE_URL=https://api.typesafe.ai/v1
JEV_MODEL=jev-latest
```

Não é necessário criar os agentes no site CrewAI ou TypeSafe. Os agentes ficam no repositório em `src/agents/`; o JEV é acessado por API.

### Integração com o sistema existente

```text
Etapa 1:
Streamlit → roteador/RAG → Dify → Weaviate → LM Studio
Streamlit → funções read-only → DuckDB

Etapa 2:
Streamlit → Core Router/CrewAI → agentes especializados
                                  ├── JEV
                                  ├── PKL/XAI
                                  ├── DuckDB allowlist
                                  ├── Dify/RAG
                                  └── LM Studio
```

Docker continua executando Dify, Weaviate, Postgres, Redis e proxies. A aplicação SkillGraph roda em um único ambiente oficial `.venv` com Python 3.11, incluindo Streamlit, CrewAI e as dependências de ML/OCR. O LM Studio permanece no host, acessível localmente por `127.0.0.1:1234` ou, em um futuro container de agentes, por `host.docker.internal:1234`.

### Arquivos da arquitetura multiagente

- `src/agents/crew.py`: factory de crews por rota;
- `src/agents/runtime.py`: execução de um turno e ferramentas fechadas;
- `src/agents/router.py`: seleção de rota;
- `src/agents/flow.py`: estado estruturado;
- `src/agents/schemas.py`: contratos Pydantic;
- `src/agents/guardrails.py`: gates e matriz de least privilege;
- `src/agents/tools.py`: fronteiras de ferramentas;
- `src/agents/prompts/`: System Prompts versionados;
- `src/jev_client.py`: adapter TypeSafe/JEV;
- `src/resume_extractor.py`: extração local de PDF;
- `config/jev_resume_questions.json`: perguntas Score/Choice/Noul.

## 13. Observabilidade, Langfuse e telemetria

**Objetivo e impacto.** Observabilidade transforma uma execução que antes seria apenas uma resposta em um registro técnico auditável. Para o projeto, ela permite medir a camada conversacional, multiagente, OCR, JEV, Dify e DuckDB usando um mesmo modelo de trace. O painel de explicabilidade da aba ML apresenta métricas do modelo separadamente; a página ML não cria um `TraceContext` próprio no caminho atual. Para o usuário técnico, isso permite investigar latência, falhas, consumo e rota sem expor conteúdo sensível.

**Desenvolvimento e implementação.** `TraceContext` representa uma execução e `SpanContext` representa uma etapa. O sistema registra rota, status, duração, serviço, tarefa/agente, tokens, custo quando disponível e erro. Os dados são sanitizados antes de serem gravados em `logs/observability.jsonl` ou enviados ao Langfuse. O painel do Desenvolvedor foi implementado como uma área própria do Streamlit para consulta de métricas e detalhes de spans.

**Integração.** O tracing acompanha o caminho legado da Etapa 1 e as rotas novas da Etapa 2: RAG/Dify, DuckDB, CrewAI, extração PDF/OCR e JEV. O Langfuse é opt-in por `LANGFUSE_ENABLED=true`; quando a flag está desligada ou o SDK/credencial não está disponível, o painel local continua funcionando. O ML possui métricas e explicabilidade próprias na aba técnica; sua integração com o tracing deve ser entendida como parte do contexto operacional, não como geração automática de trace em toda consulta ML. O envio externo contém somente agregados e identificadores sanitizados, não o prompt ou a resposta completa.

**Impacto para o usuário final.** A observabilidade não altera a resposta funcional diretamente, mas aumenta a confiabilidade percebida e a capacidade de suporte: uma falha pode ser associada a uma rota e a um Trace ID, enquanto o perfil Desenvolvedor consegue verificar onde a execução demorou ou falhou. Isso também permite comparar mudanças de modelo, prompt ou corpus com evidências operacionais.

### 13.1 Tracing local

A Etapa 2 ampliou a observabilidade criada na Etapa 1 para acompanhar não apenas as rotas RAG e DuckDB, mas também o ciclo de execução multiagente, o processamento de currículos, as chamadas ao JEV, a inferência ML e as etapas de explicabilidade.

O módulo `src/observability.py` implementa `TraceContext` e `SpanContext`. Cada execução pode registrar, de forma sanitizada:

- `trace_id` anônimo;
- timestamp;
- rota executada;
- perfil simulado;
- status (`running`, `success`, `error` ou `timeout`);
- duração total;
- duração acumulada dos spans;
- serviço executado;
- nome da tarefa/agente;
- tokens de entrada e saída, quando fornecidos pelo provedor;
- custo estimado, quando houver preço configurado;
- erros e timeouts;
- ferramenta ou integração acionada.

As rotas da Etapa 2 podem produzir spans para:

```text
Streamlit
  → extração PDF/OCR
  → Core Router
  → JEV
  → agente especialista
  → PKL/XAI ou DuckDB ou Dify
  → Reviewer
  → Synthesizer
  → resposta final
```

Os eventos locais são gravados em `logs/observability.jsonl`, que é ignorado pelo Git. O log não deve conter currículo bruto, PII, chaves, prompts privados ou chain-of-thought.

### 13.2 Langfuse

O Langfuse é uma integração opcional para tracing distribuído. Quando `LANGFUSE_ENABLED=true` e as credenciais estão disponíveis no `.env` local, o `ObservabilityStore` envia observações sanitizadas para o Langfuse. Quando a flag está desativada, a aplicação continua funcionando com o painel local e não tenta realizar chamadas externas.

A separação é importante para o contexto acadêmico:

- o tracing local funciona sem infraestrutura adicional;
- o Langfuse pode ser ativado durante uma demonstração controlada;
- as credenciais não entram no repositório;
- o currículo e as perguntas completas não são enviados ao tracing;
- o custo de modelos locais deve ser tratado como execução local sem preço de API, não como custo financeiro fictício.

O painel técnico do perfil Desenvolvedor está em `src/observability_ui.py`. Ele apresenta traces recentes, latência P50/P95/P99, taxa de erro, timeouts, tokens, custo, métricas por serviço, tarefas/agentes e erros recentes. Para a apresentação da Etapa 2, recomenda-se gerar e preservar uma evidência sanitizada com pelo menos cinco traces de rotas diferentes.

### 13.3 Alertas

`src/alerting.py` integra alertas opcionais com Slack por `chat.postMessage`. O alerta envia apenas severidade, assunto, trace ID, rota e métricas operacionais. O cooldown evita repetição excessiva. O token do bot e o canal permanecem somente no `.env`.

## 14. Golden Dataset, DeepEval e avaliação da qualidade

**Objetivo e impacto.** Esta frente verifica se as rotas, os bloqueios e as respostas continuam coerentes depois das mudanças da Etapa 2. O Golden Dataset funciona como contrato reproduzível; o DeepEval acrescenta uma avaliação semântica orientada por evidência. Para o projeto, isso reduz regressões; para o usuário final, aumenta a probabilidade de receber respostas relevantes, fundamentadas e dentro do escopo.

**Desenvolvimento e implementação.** `evals/golden_dataset.jsonl` reúne casos sintéticos de RAG, SQL, segurança, ML, lacunas, treinamentos, políticas, multi-turno e fora de escopo. `scripts/evaluate-ai.py` valida schema, rota e bloqueio sem consumir tokens. Os casos RAG em `evals/rag_goldens.jsonl` possuem resposta, contexto e ground truth. O runner live usa `FaithfulnessMetric`, `AnswerRelevancyMetric`, `ContextualPrecisionMetric` e `ContextualRecallMetric`; `src/deepeval_report.py` converte o retorno do DeepEval em resultados estruturados com médias, medianas, mínimos, máximos, pass rate, weaknesses e recomendações.

**Integração.** A área `Qualidade e Evals` do perfil Desenvolvedor carrega o Golden Dataset e exibe relatórios offline e live. A avaliação live é explicitamente separada do caminho normal do Streamlit porque pode consumir tokens do LM Studio. O adapter `src/deepeval_judge.py` utiliza o endpoint OpenAI-compatible do modelo local configurado; o mesmo relatório pode ser associado ao modelo, dataset e configuração utilizados.

**Impacto para o usuário final.** O usuário não precisa conhecer o runner ou as métricas para utilizar o chat, mas se beneficia de uma aplicação que testa bloqueios de PII/injection, roteamento e aderência ao contexto. O perfil técnico consegue identificar uma weakness de relevancy, faithfulness, precision ou recall e orientar ajustes de prompt, chunking, Top K, fontes ou roteamento.

O Golden Dataset da Etapa 2 inclui casos de ML e agentes como contrato documental, enquanto a validação live do DeepEval está concentrada nos casos que possuem resposta, contexto e ground truth, atualmente os casos RAG de `evals/rag_goldens.jsonl`. Isso evita afirmar que todas as rotas multiagente ou a inferência ML já são avaliadas semanticamente pelo runner live.

### 14.1 Golden Dataset

A Etapa 2 separa três níveis de avaliação: testes determinísticos, Golden Dataset e julgamento semântico com DeepEval.

O arquivo `evals/golden_dataset.jsonl` contém 25 casos sintéticos do domínio, cobrindo:

- perguntas documentais sobre políticas, cargos e trilhas;
- indicadores estruturados e catálogo de treinamentos;
- consultas de competência com IDs explícitos;
- smalltalk;
- comparação documental;
- recomendações de trilhas ML;
- análise de lacunas;
- recomendações de treinamento;
- política e reembolso;
- multi-turno;
- perguntas ambíguas;
- ausência de evidência;
- prompt injection;
- PII e salário individual;
- SQL destrutivo;
- solicitações fora do escopo.

Cada caso registra, quando aplicável:

- identificador;
- categoria;
- pergunta;
- rota esperada;
- ferramentas esperadas;
- fatos esperados;
- documentos esperados;
- IDs esperados;
- indicação de bloqueio;
- observações de avaliação.

A validação offline executada por `scripts/evaluate-ai.py` verifica schema, rota e bloqueio sem consumir tokens. O dataset também funciona como contrato de regressão: uma alteração no roteador ou nos guardrails deve ser comparada contra os mesmos casos antes de ser considerada estável.

Além do golden geral, `evals/rag_goldens.jsonl` contém casos com resposta, contexto e ground truth para avaliação semântica da qualidade RAG.

### 14.2 DeepEval

O módulo `src/evaluation_ai.py` integra o DeepEval como LLM-as-a-judge. O runner live é explícito e não é acionado pelo `pytest` nem pelo caminho normal do Streamlit, porque pode consumir tokens do LM Studio.

A implementação usa o modelo configurado no adapter `src/deepeval_judge.py` por meio do endpoint OpenAI-compatible do LM Studio. O mesmo provedor local pode atuar como modelo de interpretação/explicação e como juiz, mas os papéis permanecem separados: o DeepEval avalia uma resposta e não executa a lógica de negócio do SkillGraph. O relatório registra o caso avaliado, as métricas disponíveis, a média e a taxa de aprovação; quando o retorno do judge não pode ser interpretado, registra erro de parsing em vez de inventar scores.

Para o usuário final, o impacto é indireto: respostas apoiadas em contexto e rotas estáveis reduzem respostas fora do escopo. Para o desenvolvedor, cada weakness orienta uma melhoria em corpus, chunking, Top K, prompt, ferramenta ou roteamento.

Exemplo de execução live:

```bash
python scripts/evaluate-ai-live.py --deepeval --yes-live \\
  --dataset evals/rag_goldens.jsonl --deepeval-case rag-gold-003
```

O relatório é consumido pela área `Qualidade e Evals` e salvo em `output/evaluation/live_ai_report.json`, que permanece fora do controle de versão.

O nome correto da ferramenta é **DeepEval**; “Deep Evil” não é o nome do componente.

As métricas avaliadas são:

- **Faithfulness:** verifica se a resposta está apoiada no contexto recuperado;
- **Answer Relevancy:** verifica se a resposta responde à pergunta sem desvios;
- **Contextual Precision:** verifica se os contextos relevantes estão bem priorizados;
- **Contextual Recall:** verifica se o contexto contém evidência suficiente para o ground truth.

O comando live exige confirmação explícita:

```bash
make evaluate-ai-live
```

O runner utiliza `--yes-live` e seleciona apenas os casos que possuem resposta, contexto e ground truth. O relatório gerado fica em `output/evaluation/live_ai_report.json`, diretório ignorado pelo Git.

A avaliação executada localmente dos casos RAG demonstrou respostas com alta faithfulness e relevancy para as perguntas testadas. Ainda assim, o judge é uma evidência complementar, não uma verdade absoluta: resultados dependem do modelo avaliador, do prompt e do contexto fornecido.

O relatório pode ser consultado na área `Qualidade e Evals` do perfil Desenvolvedor.

### 14.3 Interpretação e melhorias

Os resultados devem ser interpretados junto com os testes determinísticos. Uma resposta pode estar na rota correta e ainda ser pouco fiel ao contexto. Por isso, as melhorias devem considerar:

- ajustar separadores e tamanho de chunks no Dify;
- revisar Top K e ausência de evidência;
- adicionar casos ambíguos e fora do escopo;
- comparar fontes recuperadas antes e depois de mudanças;
- revisar respostas com baixa faithfulness ou relevancy;
- separar novamente perguntas que deveriam ir para DuckDB ou ML;
- manter a política como fonte normativa em caso de conflito;
- registrar latência e custo de cada experimento.

## 15. Melhorias complementares de produto e interface

A Etapa 2 não se limitou ao treinamento do modelo. Foram implementadas melhorias transversais para tornar o sistema demonstrável, auditável e mais útil aos três perfis do Streamlit.

### 15.1 Experiência de currículo

O upload de PDF ocorre no chat principal. O usuário recebe aviso de privacidade antes do upload, confirmação de recebimento e aviso de que a análise pode levar até cinco minutos. Durante a execução, o painel de progresso apresenta etapas como:

```text
Currículo recebido
→ texto/OCR extraído
→ análise estruturada
→ agentes especializados
→ resposta final
```

A resposta apresenta competências em tabela/cards com:

- nome;
- nível de senioridade;
- confiança;
- evidência;
- competências não reconhecidas;
- informações ausentes ou que exigem confirmação.

O painel de erro técnico seguro mostra categoria, rota, Trace ID, tempo decorrido e próxima ação sem expor chaves, currículo, PII ou stack trace.

### 15.2 Visão do gestor

A área `Visão do gestor` permanece agregada e usa somente dados sintéticos. A Etapa 2 adicionou:

- cards de competências avaliadas, funcionários com lacuna, lacunas críticas, taxa de aprovação e nota média;
- distinção entre lacunas críticas e comuns;
- indicadores de treinamentos, aprovação, nota, horas associadas, reprovações e custo de catálogo;
- filtros por categoria, competência e modalidade;
- gráficos de aprovados versus reprovados;
- gráficos de lacunas críticas versus comuns;
- evolução temporal mensal de registros de treinamento e lacunas;
- explicação de cada indicador em linguagem simples.

A implementação não inventa indicadores por departamento ou gestor porque o dataset não possui uma tabela-mestre organizacional confiável. Essa limitação é explicitada na interface e na documentação.

### 15.3 Perfil Desenvolvedor

O perfil Desenvolvedor possui áreas separadas para:

- Machine Learning;
- Observabilidade;
- Qualidade e Evals.

Na aba ML, o Desenvolvedor pode consultar:

- métricas de validação e teste;
- alerta de queda de generalização;
- cobertura das competências de entrada;
- competências reconhecidas e não reconhecidas;
- incerteza da recomendação;
- explicações locais e globais quando suportadas;
- status explícito quando SHAP/importância não estiver disponível;
- limitações de fairness e ausência de atributos protegidos autorizados.

Na aba Observabilidade, pode analisar traces sanitizados, serviços, agentes, tarefas, consumo e erros. Na aba Qualidade e Evals, pode consultar o Golden Dataset e os relatórios offline/live.

### 15.4 Privacidade, segurança e governança

Foram reforçados:

- redação de CPF, RG, e-mail, telefone e outros identificadores;
- proibição de decisões de contratação, promoção, remuneração, punição ou desligamento;
- separação entre texto de currículo e perfil estruturado;
- não persistência de currículo bruto;
- least privilege por agente;
- consultas DuckDB read-only;
- output gate de toxicidade;
- painel de reasoning estruturado público, sem chain-of-thought privado.

## 16. Qualidade de código, ambiente e rastreabilidade

A Etapa 2 também consolidou práticas de manutenção:

- Python 3.11 como runtime oficial único em `.venv`;
- CrewAI integrado ao ambiente principal;
- `.python-version` para tornar a versão explícita;
- módulos separados para OCR, privacidade, progresso, erros, reasoning, XAI e UI;
- testes unitários e de integração com mocks;
- `requirements-dev.txt`;
- hooks pre-commit com Black, Ruff, AST, JSON, YAML e detecção de chaves;
- CI no GitHub Actions com instalação, `pip check`, compilação e pytest;
- Dependabot para atualizações controladas;
- `VERSION` e `CHANGELOG.md` para rastreabilidade;
- release automatizado por tags SemVer;
- exclusão de ambientes, bases, logs, modelos e segredos pelo `.gitignore`.

Os serviços externos continuam separados: Dify, Weaviate, PostgreSQL, Redis e proxies executam em Docker; Streamlit, CrewAI, OCR, ML e clientes JEV/Dify executam no `.venv` oficial; LM Studio permanece no host.

## 17. Limitações e avaliação honesta da Etapa 2

A Etapa 2 é funcional e reproduzível em ambiente local, mas ainda possui limitações importantes:

- o dataset O*NET filtrado é pequeno;
- o desempenho no teste é inferior ao observado na validação;
- as trilhas são agrupamentos do projeto, não rótulos oficiais do O*NET;
- o mercado brasileiro não é representado integralmente;
- a fairness entre grupos protegidos não é avaliável sem atributos autorizados;
- o Langfuse é opcional e depende de credenciais para uma demonstração externa;
- tokens e custo local podem não estar disponíveis em todos os providers;
- o DeepEval live avalia um subconjunto controlado do Golden Dataset;
- o CrewAI depende da capacidade do modelo local de seguir contratos estruturados;
- não há autenticação ou RBAC real;
- os indicadores gerenciais são sintéticos e agregados.

Essas limitações não são ocultadas. Elas orientam os próximos experimentos: ampliar o dataset, realizar divisão por grupos ocupacionais, avaliar com especialistas, formalizar evidências de tracing, expandir o conjunto DeepEval e manter revisão humana.

## 18. Próximos passos

- aumentar e diversificar o catálogo de ocupações e competências;
- adicionar fontes licenciadas específicas de IA generativa;
- avaliar o modelo com especialistas de RH e tecnologia;
- melhorar o mapeamento de aliases e sinônimos;
- realizar divisão por grupos ocupacionais relacionados;
- criar explicações de lacunas mais fiéis às competências observadas;
- adicionar versionamento formal dos datasets e modelos;
- manter revisão humana e governança antes de qualquer uso organizacional.

Este documento descreve a Etapa 2 como continuação da fundação conversacional da Etapa 1. A Etapa 3 permanece fora do escopo desta entrega.
