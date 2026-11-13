# Etapa 2 — CrewAI e sistema multiagente

## O que precisa ser criado na plataforma CrewAI?

Nada para o modo local. CrewAI é um framework Python de orquestração; os agentes, prompts, tarefas e ferramentas ficam no repositório. Não é necessário criar cada agente em um painel hospedado nem criar uma conta CrewAI para executar a arquitetura local.

O CrewAI não fornece o LLM. Os agentes usam o provider configurado em `CREWAI_LLM_*` por meio de endpoint compatível. O JEV é um serviço externo separado, chamado como ferramenta pelo agente de currículo. No chat principal, as rotas de domínio passam obrigatoriamente pelo runtime multiagente; smalltalk, guardrails e pedidos de esclarecimento são as únicas respostas determinísticas fora da crew. Não existe fallback legado silencioso de RAG/SQL.

## Agentes

A primeira crew possui nove papéis:

1. Core/Router — smalltalk, explicação do SkillGraph e roteamento;
2. Resume Interpreter — texto de currículo → JEV → evidências estruturadas;
3. Profile — normalização, aliases, PII e perfil;
4. Prediction — ferramenta PKL/XAI;
5. Gap — lacunas e prioridades;
6. Training — catálogo/pré-requisitos por funções read-only;
7. Policy — Chatflow Dify existente;
8. Reviewer — segurança, schema, evidências e governança;
9. Synthesizer — resposta final em português.

Os prompts versionados estão em `src/agents/prompts/`. Todos têm persona, contexto, objetivo, fluxo obrigatório, escopo, ferramentas, guardrails, anti-alucinação, checklist e exemplos.

## Core Router e rotas abertas

O Core Router é acionado em cada turno. Ele lê a mensagem atual e o estado estruturado da conversa, escolhe uma rota especialista e recebe de volta um patch de estado. Não existe uma sequência fixa obrigatória entre todos os agentes.

Uma conversa pode seguir, por exemplo:

```text
PDF → Resume Interpreter → Core
  → pergunta de lacunas → Gap Agent → Core
  → pergunta de treinamentos → Learning Path Agent → Core
  → pergunta de política → Policy Agent → Core
```

Rotas não previstas explicitamente também devem cair em `clarify`, sem forçar um agente inadequado. O estado da conversa é a fonte de continuidade entre turnos.

## ReAct e least privilege

Os agentes especialistas usam raciocínio controlado antes da ação, com limite de iterações (`reasoning`, `max_iter=4`, quando suportado pelo CrewAI). O pensamento privado não é exibido nem persistido; somente ação, ferramenta, validação e resultado estruturado são registrados.

Cada agente recebe somente a ferramenta mínima necessária:

- Resume: JEV;
- Prediction: PKL/XAI;
- Learning Path: DuckDB read-only;
- Policy: Dify;
- Profile, Gap, Reviewer e Synthesizer: nenhuma ferramenta.

## Dados entre agentes

Os handoffs usam objetos Pydantic/JSON em `src/agents/schemas.py`. O estado comum fica em `AgentFlowState`; o processo padrão é sequencial dentro de uma rota, mas o Core pode escolher outra rota no próximo turno.

## Guardrails

Guardrails determinísticos existem antes da rota, na fronteira de cada ferramenta e na revisão final. Eles verificam PII, prompt injection, escopo, schemas, competências desconhecidas, decisões laborais, SQL livre e limites de custo. Não há um agente genérico com acesso a tudo; o Reviewer valida o resultado, mas não substitui os gates de segurança.

## Dados entre agentes

Os handoffs usam objetos Pydantic/JSON em `src/agents/schemas.py`. O estado comum fica em `AgentFlowState`; o processo padrão é sequencial. O JEV retorna JSON estruturado, o backend valida, e o LM Studio só sintetiza o resultado revisado.

## JEV

O adapter `src/jev_client.py` está pronto, mas `JEV_ENABLED=false` por padrão. Quando a chave estiver disponível, preencha no `.env`:

```env
JEV_ENABLED=true
TYPESAFE_API_KEY=sua-chave
JEV_API_BASE_URL=https://api.typesafe.ai/v1
JEV_MODEL=jev-latest
```

Nenhuma configuração manual de agente no site TypeSafe é necessária para a API. Os contratos de perguntas ficam em `config/jev_resume_questions.json`.

## Upload e OCR

O upload de currículo ocorre no chat principal: o PDF é salvo temporariamente, extraído localmente com PyMuPDF e, se necessário, processado pelo OCR local. O arquivo temporário é apagado ao final da extração. O estado do Streamlit mantém apenas texto em memória e metadados seguros (`used_ocr`, páginas e método), nunca os bytes do PDF. A interface mostra o método e exige confirmação em **Enviar análise** antes de chamar JEV/CrewAI. A aba ML continua dedicada à recomendação manual de trilhas.

Para OCR, configure `OCR_LANG` (padrão `eng`), `OCR_MAX_PAGES`, `OCR_ENABLED` e, quando necessário, `TESSERACT_CMD`. O idioma escolhido precisa aparecer em `tesseract --list-langs`; `RESUME_MAX_SIZE_MB` controla o limite do upload.

O JEV é chamado uma vez pelo backend, depois da redação de PII. A UI diferencia JEV desabilitado/sem chave, falha TLS/HTTP, resposta inválida e falha do modelo local. O sucesso só é registrado quando todas as etapas terminam; um erro nunca é mascarado como análise concluída.

O CrewAI é obrigatório para as rotas de domínio. Se estiver desativado, ausente ou indisponível, a aplicação mostra um diagnóstico e interrompe a solicitação; ela não executa outro caminho em paralelo. Recomenda-se testar primeiro um PDF textual sintético, depois um PDF escaneado e só então executar uma chamada JEV live com credencial autorizada.

### Síntese final obrigatória com Gemini

A aplicação usa o Gemini obrigatoriamente somente na redação final. Os agentes, o JEV, OCR e a revisão continuam locais. A chamada recebe somente o rascunho local e dados estruturados sanitizados. PDF, currículo bruto, PII e resposta bruta do JEV não são enviados. Se a chave faltar ou o Gemini falhar, o rascunho local não é apresentado como resposta final: a execução exibe um diagnóstico e pede correção da configuração. A observação é registrada como `gemini.final_synthesis`, usando `usageMetadata` para tokens; o custo depende das tarifas configuradas. O LLM-as-a-judge continua separado e não muda.

A aba ML continua dedicada à recomendação manual de trilhas. O CrewAI/JEV desativado não faz chamadas externas.

## Execução local

O SkillGraph usa um único ambiente oficial `.venv` com Python 3.11, que contém Streamlit, CrewAI e as demais dependências da aplicação. Para preparar e iniciar:

```bash
make bootstrap-crewai
CREWAI_ENABLED=true make run
```

O usuário não precisa alternar entre ambientes Python. O comando `make run-crewai` permanece como alias de compatibilidade e usa o mesmo `.venv` oficial.

Variáveis:

```env
CREWAI_ENABLED=true
CREWAI_LLM_MODEL=openai/meta-llama-3-8b-instruct
CREWAI_LLM_BASE_URL=http://127.0.0.1:1234/v1
CREWAI_LLM_API_KEY=lm-studio-local
CREWAI_PROCESS=sequential
```

Docker/Dify não precisam ser alterados: Dify permanece como RAG e LM Studio como LLM local. Uma futura execução em container pode usar `host.docker.internal` para acessar o LM Studio.

## Ativação humana necessária

Você não precisa criar agentes em um site CrewAI. O CrewAI local cria os agentes a partir de `src/agents/crew.py` e dos prompts versionados. O site TypeSafe/Playground também não precisa receber agentes; o JEV é chamado pela API.

Quando receber a chave TypeSafe:

1. abra o `.env` local;
2. defina `JEV_ENABLED=true`;
3. preencha `TYPESAFE_API_KEY`;
4. execute primeiro com currículo sintético;
5. valide a resposta estruturada antes de usar documentos reais.

## Fases futuras

- OCR para PDFs escaneados;
- EvalAgent/Golden Dataset para avaliar a crew;
- integração Google Drive;
- Responsible AI Toolbox para fairness/análise de erros.

Alibi não faz parte do plano.
