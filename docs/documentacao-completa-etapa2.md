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

A Etapa 2 também prepara uma camada multiagente para operar sobre a fundação da Etapa 1 e o modelo de competências. O CrewAI é o orquestrador local; ele não fornece um modelo de linguagem próprio. Os agentes usam o LM Studio por uma API compatível com OpenAI.

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Streamlit — chat principal                                          │
│ mensagem + PDF opcional                                             │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Core Router — decide a rota a cada turno                            │
│ lê mensagem atual + estado estruturado da conversa                  │
└───────┬───────────────┬───────────────┬───────────────┬─────────────┘
        │               │               │               │
        ▼               ▼               ▼               ▼
   Currículo       Predição ML      Lacunas       Treinamentos
        │               │               │               │
        ▼               ▼               ▼               ▼
       JEV             PKL/XAI       estado       DuckDB read-only
        │               │               │               │
        └───────────────┴───────────────┴───────────────┘
                               ▼
                    Core Router + estado atualizado
                               ▼
                    Reviewer → Synthesizer → usuário

Rota de políticas:
Core Router → Policy Agent → Dify Chatflow → Weaviate → LM Studio
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
| `learning_recommendation` | Learning Path & Training Recommendation | funções read-only do DuckDB |
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

Os agentes especialistas podem planejar uma ação antes de executar uma ferramenta, mas com limites explícitos:

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
OCR futuro para PDF escaneado
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

## 13. Próximos passos

- aumentar e diversificar o catálogo de ocupações e competências;
- adicionar fontes licenciadas específicas de IA generativa;
- avaliar o modelo com especialistas de RH e tecnologia;
- melhorar o mapeamento de aliases e sinônimos;
- realizar divisão por grupos ocupacionais relacionados;
- criar explicações de lacunas mais fiéis às competências observadas;
- adicionar versionamento formal dos datasets e modelos;
- manter revisão humana e governança antes de qualquer uso organizacional.
