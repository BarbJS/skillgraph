# SkillGraph — Documentação completa da Etapa 3

## 1. Contexto e objetivo

A Etapa 3 inicia um ciclo de correção, endurecimento operacional e validação do SkillGraph construído nas etapas anteriores. O foco não é substituir a arquitetura da Etapa 2, mas torná-la mais confiável, observável, testável e preparada para mudanças no repositório.

O trabalho inicial da Etapa 3 concentrou-se em cinco objetivos:

1. corrigir o fluxo de currículo em PDF, OCR e JEV;
2. tornar a integração Gemini + Langfuse observável e mensurável;
3. transformar Golden Dataset e casos RAG em regressões executáveis contra o backend atual;
4. criar uma fronteira obrigatória de síntese e validação antes de exibir respostas;
5. fortalecer segurança, privacidade e guardrails sem quebrar CrewAI, DeepEval, ML ou o ambiente oficial.

A Etapa 3 mantém os dados de negócio sintéticos e continua sendo um protótipo acadêmico. Nenhuma mudança transforma o sistema em ferramenta de decisão de contratação, promoção, remuneração, punição ou desligamento.

## 2. Escopo inicial da Etapa 3

A etapa começou como uma revisão corretiva da integração existente. Em vez de adicionar funcionalidades isoladas sem validação, o projeto passou a tratar cada saída como uma cadeia verificável:

```text
entrada
  → guardrails de entrada
  → roteamento atual
  → ferramenta/LLM autorizado
  → resposta estruturada
  → síntese Gemini obrigatória
  → output gate de segurança
  → persistência sanitizada
  → Streamlit/Langfuse
```

Essa sequência é aplicada sobre as rotas de RAG, DuckDB, CrewAI, currículo e Machine Learning, respeitando as exceções necessárias para mensagens bloqueadas e interações simples.

## 3. Correção do fluxo de PDF, OCR e JEV

### 3.1 Problema identificado

O fluxo anterior extraía o PDF em um ponto diferente do trace, guardava apenas o texto no estado do Streamlit, possuía caminhos duplicados de análise e apresentava mensagens genéricas quando OCR, JEV ou CrewAI falhavam. O span de extração podia existir sem representar a extração real.

### 3.2 Upload efêmero

O módulo `src/resume_upload.py` passou a centralizar o upload:

- valida extensão PDF;
- rejeita arquivo vazio;
- copia o upload para arquivo temporário;
- extrai o conteúdo;
- remove o arquivo temporário antes de retornar;
- mantém apenas texto em memória e metadados seguros;
- nunca grava bytes do PDF no estado da sessão.

O estado mantém apenas informações como:

- nome do arquivo;
- método de extração;
- número de páginas;
- indicação de OCR;
- texto temporário necessário para a análise.

### 3.3 Extração textual e OCR

`src/resume_extractor.py` agora diferencia:

- extração nativa via PyMuPDF;
- OCR local via Tesseract.

O fluxo respeita:

```env
RESUME_MAX_SIZE_MB=10
OCR_ENABLED=true
OCR_LANG=por+eng
OCR_MAX_PAGES=10
TESSERACT_CMD=
```

O Tesseract foi instalado com os pacotes de idiomas adicionais, incluindo português. O código valida:

- existência do Tesseract;
- idioma solicitado;
- limite de páginas;
- limite de tamanho;
- PDF vazio ou inválido;
- fechamento de documentos e imagens.

### 3.4 JEV

O cliente JEV foi reforçado para:

- verificar PII antes do envio;
- enviar somente estado sanitizado;
- validar `answers` e `usage`;
- diferenciar timeout, TLS, HTTP e resposta inválida;
- registrar tokens e confiança quando o provedor fornece esses campos;
- fechar spans de observabilidade mesmo em erros;
- nunca expor a chave ou o documento bruto.

O JEV continua sendo uma etapa backend, não um agente autônomo. Seu resultado é complementar e é convertido em `EmployeeProfile` validado.

## 4. Gemini como sintetizador final

### 4.1 Motivo da mudança

O LM Studio local continua sendo o provider do ambiente de desenvolvimento, mas não é uma dependência do primeiro deploy público. Ele fornece localmente o modelo conversacional e o modelo de embeddings usados pelo Dify self-hosted. Para a produção no Streamlit Community Cloud, o RAG será recriado no Dify Cloud e o modelo conversacional será o Gemini; a Knowledge Base será reindexada com o modelo de embeddings Gemini disponível no Dify Cloud.

A Etapa 3 introduziu uma chamada Gemini obrigatória como última síntese das respostas elaboradas. O mesmo provider Gemini também será validado para o CrewAI, usando o prefixo LiteLLM `gemini/`, sem exigir uma `base_url` local.

#### Ambiente local de desenvolvimento

```text
Streamlit local
  ↓
Dify self-hosted/Docker local
  ├── Chatflow local
  ├── Knowledge Base local
  ├── LM Studio — modelo de chat
  └── LM Studio — modelo de embeddings
        ↓
DuckDB/SQLite/OCR/CrewAI/JEV
        ↓
Gemini final conforme a configuração local
```

O desenvolvimento local preserva os endpoints e ferramentas originalmente construídos, incluindo `localhost`, `127.0.0.1`, Docker, LM Studio e volumes locais.

#### Ambiente de produção atual

```text
Streamlit Community Cloud
  ├── app.py e código versionado
  ├── data_bd e documentos públicos do repositório
  ├── DuckDB read-only
  ├── CrewAI configurado para Gemini
  ├── JEV por API HTTPS
  ├── Langfuse Cloud
  └── síntese final Gemini
        ↓
Dify Cloud
  ├── Chatflow recriado/publicado
  ├── Knowledge Base reindexada
  ├── Gemini 3.1 Flash Lite — conversa
  └── gemini-embedding-001 — embeddings
```

A produção não acessa o LM Studio local. A aplicação usa Secrets do Streamlit Cloud para `DIFY_API_*`, `GEMINI_*`, `CREWAI_*`, `JEV_*` e `LANGFUSE_*`. Nenhuma chave é commitada ou enviada ao navegador.

A decisão de trocar somente os providers de produção, e não reescrever as rotas do produto, preserva a fidelidade do comportamento local enquanto torna os endpoints acessíveis pela internet.

#### Decisão sobre a migração do RAG

O Dify local e o Dify Cloud são instâncias diferentes. O Chatflow e os vetores não são tratados como arquivos independentes que possam ser copiados sem validação. A Knowledge Base é recriada no Dify Cloud, os quatro documentos de `documents_rag/` são reenviados e reindexados, e o Chatflow é publicado novamente.

A configuração de referência permanece em `config/dify-chatflow-reference.json`: parent-child, indexação de alta qualidade, busca vetorial/híbrida, Top K 4 e sem reranker/score threshold inicialmente. A separação entre modelo conversacional e modelo de embeddings é explícita: Gemini 3.1 Flash Lite gera respostas; `gemini-embedding-001` vetoriza documentos e perguntas.

#### Ajuste de chunking e recuperação validado no Dify Cloud

Durante a validação pública, a pergunta “Treinamentos online contam para a carga horária anual?” inicialmente recuperava trechos relacionados à tabela de carga horária por nível, mas não separava adequadamente a resposta do FAQ sobre cursos online. O modelo acabava misturando a regra geral de modalidades válidas com a regra específica de treinamentos com nota inferior a 7,0.

A Knowledge Base foi recriada e reindexada com:

- **Parent max characters:** 800, reduzido de 1024;
- **Child max characters:** 375, reduzido de 512;
- separação por seções/parágrafos para manter perguntas e respostas do FAQ no mesmo contexto, sem misturar a seção de aprovação com a seção de modalidades;
- recuperação híbrida, combinando semântica e palavras-chave;
- Top K 4;
- limite de pontuação desativado inicialmente;
- reranking mantido desativado até validar quota e relevância.

A redução da granularidade foi necessária porque chunks maiores agrupavam duas evidências semanticamente próximas, mas logicamente diferentes: “cursos online valem horas” e “treinamentos com nota inferior a 7,0 não contam para a carga horária mínima”. Com chunks menores, o Dify recupera a seção correta do `faq_desenvolvimento.md` e reduz a transferência indevida de condições entre seções.

Após a recriação da Knowledge Base, o teste passou a recuperar a evidência correta e responder de acordo com a pergunta. A resposta deve continuar distinguindo “vale horas” de “conta automaticamente para a carga horária mínima”; quando essa relação não estiver explícita na fonte, o sistema deve declarar a ausência e recomendar confirmação com o RH.

#### Decisão sobre a API do Dify

O cliente do projeto usa `DIFY_API_BASE_URL` e `DIFY_API_KEY`. Ele aceita a base local e a base cloud com ou sem `/v1`, normalizando o endpoint para `/v1/chat-messages` sem duplicar o caminho. O parser trata eventos Chatflow `message`, `agent_message`, `message_end`, `workflow_finished` e falhas do workflow, porque o Chatflow Cloud pode encerrar o stream sem emitir apenas chunks `message`.

Essa correção evita confundir URL incorreta, Chatflow não publicado e workflow publicado que falhou internamente. Falhas transitórias do provider podem receber tentativas adicionais somente quando `DIFY_MAX_RETRIES` for explicitamente configurado; o padrão de produção é `0`, para nunca repetir quota/rate limit acidentalmente. Erros permanentes não são repetidos e uma resposta parcial nunca é duplicada. Os timeouts padrão são 10s para conexão, 60s para leitura e 120s para a requisição completa, evitando que uma chamada bloqueie a interface por vários minutos.

#### Decisão sobre o LLM único de produção

A produção usa Gemini como provider conversacional comum para:

- modelo do Chatflow no Dify Cloud;
- síntese final obrigatória do SkillGraph;
- CrewAI, quando a execução com function calling for validada.

O ambiente local mantém LM Studio para preservar o desenvolvimento. Essa separação evita expor o computador local e reduz a quantidade de providers conversacionais no deploy.

#### Preparação cloud realizada

A Etapa 3 adicionou:

- `scripts/start-streamlit.sh`, que usa `PORT` e escuta em `0.0.0.0`;
- `make run-cloud`;
- `scripts/cloud-smoke-test.py` para `/_stcore/health`;
- requirements de produção com CrewAI e inferência ML;
- configuração de `SKILLGRAPH_STATE_DIR` e `OBSERVABILITY_LOG_PATH`;
- documentação em `docs/cloud-readiness.md`;
- plano operacional em `docs/plan-streamlit-cloud-gemini.md`.

Essas alterações tornam o processo cloud-ready sem substituir o launcher local nem os serviços do ambiente de desenvolvimento.

#### Secrets e limites do primeiro deploy

Os Secrets ficam somente no Streamlit Cloud. A primeira produção exige `CREWAI_ENABLED=true`, `JEV_ENABLED=true` e `LANGFUSE_ENABLED=true`, além das chaves de Dify e Gemini. `SLACK_ALERTS_ENABLED` pode permanecer falso até que o alerta seja necessário.

O primeiro deploy não promete persistência empresarial: SQLite, logs e caches podem ser perdidos em reinícios do Streamlit Cloud; o artefato ML precisa ser disponibilizado por storage/build; OCR depende da disponibilidade do Tesseract; não há autenticação/RBAC real. Essas limitações são intencionais e ficam registradas nos próximos passos.

#### Critério de aceitação da produção

A produção só é considerada funcional quando validar, pela URL pública:

1. Chatflow Dify Cloud com fontes;
2. Gemini final;
3. CrewAI com Gemini;
4. JEV com currículo sintético sanitizado;
5. traces no Langfuse;
6. DuckDB e dados sintéticos;
7. ML/XAI quando o artefato estiver disponível;
8. OCR quando o runtime fornecer Tesseract;
9. Qualidade/Evals conforme as dependências e o judge configurados.

A paridade é avaliada funcionalmente por rota; não significa que o processo local, o provider de embeddings ou o storage temporário sejam idênticos aos da nuvem.

### 4.2 Cliente Gemini

`src/gemini_synthesizer.py` implementa uma integração REST pequena, usando `requests` e `truststore`, sem adicionar um SDK pesado ao fluxo principal.

O cliente:

- usa `GEMINI_API_KEY` somente do `.env`;
- coleta `usageMetadata`;
- registra tokens de entrada, saída e total;
- calcula custo somente quando tarifas configuradas estão disponíveis;
- diferencia falha TLS, timeout, HTTP e resposta vazia;
- utiliza fallback de modelo disponível quando o modelo configurado não está disponível;
- não envia PDF, currículo bruto, PII, resposta bruta do JEV ou prompts privados.

A síntese é obrigatória para respostas elaboradas. Se Gemini não estiver configurado ou falhar, o sistema não apresenta o rascunho local como se fosse resposta final.

### 4.3 Rotas cobertas

A síntese final é aplicada a:

- RAG/Dify;
- consultas estruturadas;
- comparações;
- treinamento e política via agentes;
- análise de currículo;
- recomendação ML;
- respostas produzidas pelo CrewAI.

Saudações simples e mensagens de bloqueio determinístico não precisam de uma chamada elaborada ao Gemini.

## 5. Ajustes Gemini + Langfuse

### 5.1 Problema anterior

Os traces mostravam tokens zerados ou custo não identificado porque chamadas locais eram representadas como spans genéricos e não como gerações de LLM. Além disso, o uso retornado pelo provedor não estava sempre conectado ao tipo correto de observação do Langfuse.

### 5.2 Geração real

A chamada final é registrada como:

```text
gemini.final_synthesis
```

Quando suportado pela versão do SDK, o `ObservabilityStore` usa `start_generation` e envia:

- modelo;
- `usage_details` de entrada, saída e total;
- `cost_details` quando o preço foi configurado;
- rota e status sanitizados;
- duração;
- origem do uso e do custo.

LM Studio local continua marcado como local ou sem preço quando não há tarifa de API. O sistema não inventa custo financeiro para modelo local.

### 5.3 Configuração

```env
GEMINI_API_KEY=sua-chave
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_MAX_ATTEMPTS=1
GEMINI_ALLOW_FALLBACK=false
GEMINI_FALLBACK_MODEL=gemini-flash-lite-latest
GEMINI_TIMEOUT_SECONDS=120
GEMINI_MAX_OUTPUT_TOKENS=5400
GEMINI_INPUT_USD_PER_1M=
GEMINI_OUTPUT_USD_PER_1M=
```

O Langfuse permanece opcional e recebe somente metadados agregados, sem conteúdo privado. O Gemini faz uma única chamada por síntese por padrão (`GEMINI_MAX_ATTEMPTS=1`); fallback é desligado (`GEMINI_ALLOW_FALLBACK=false`) e quota/rate limit não dispara modelo alternativo.

## 6. Golden Dataset e RAG como regressão executável

### 6.1 Problema anterior

A validação inicial podia apenas ler o arquivo JSON e validar schema, rota esperada e bloqueio sem executar novamente o backend. Isso não era suficiente para detectar regressões causadas por mudanças no código.

### 6.2 Golden Dataset

O Golden Dataset mantém perguntas e expectativas fixas de propósito. Esses valores são o ground truth de regressão. O que muda a cada rodada é a execução do código atual.

O runner em `src/evaluation_runner.py` executa cada caso contra:

- roteador atual;
- guardrails atuais;
- ferramentas atuais;
- DuckDB atual;
- Dify/Gemini quando a rota exige esses serviços.

O relatório registra:

- pergunta;
- rota esperada;
- rota observada;
- bloqueio esperado;
- bloqueio observado;
- resposta executada;
- fatos esperados;
- fatos encontrados;
- erro da execução;
- aprovação do caso.

Assim, uma alteração no roteador, guardrail ou resposta pode melhorar ou piorar o resultado comparado ao mesmo ground truth.

### 6.3 Casos RAG

`evals/rag_goldens.jsonl` permanece fixo e contém:

- pergunta;
- resposta/ground truth esperada;
- contextos de referência;
- categoria.

Em uma rodada nova, o runner:

```text
pergunta fixa
  → Dify/RAG atual
  → contextos recuperados agora
  → resposta atual
  → síntese Gemini atual
  → DeepEval
  → comparação com ground truth fixo
```

As métricas são calculadas sobre a saída atual, não sobre um score armazenado no arquivo.

### 6.4 Botão na aba Desenvolvedor

A aba `Qualidade e Evals` oferece uma execução sequencial:

1. roda os casos determinísticos do Golden Dataset;
2. salva o relatório backend;
3. executa os casos RAG atuais;
4. chama DeepEval;
5. salva o relatório live;
6. exibe progresso por caso;
7. atualiza a página.

A execução RAG exige confirmação porque consome chamadas do judge e dos serviços externos.

## 7. Qualidade e DeepEval

DeepEval permanece separado da segurança online. Ele mede qualidade semântica, não bloqueia respostas em produção.

As métricas são:

- **Faithfulness:** apoio da resposta no contexto recuperado;
- **Answer Relevancy:** aderência à pergunta;
- **Contextual Precision:** priorização de contexto relevante;
- **Contextual Recall:** cobertura das evidências necessárias para o ground truth.

Os resultados por caso e os agregados gerais aparecem na aba do Desenvolvedor. O relatório registra médias, mediana, mínimo, máximo, taxa de aprovação, razões do judge e weaknesses.

A interpretação deve considerar que datasets pequenos e contextos muito limpos podem gerar scores altos. A métrica não é prova absoluta de qualidade nem substitui revisão humana.

## 8. Segurança e guardrails

### 8.1 Decisão sobre LLM Guard

O projeto tentou integrar o LLM Guard como camada complementar para prompt injection, jailbreak, PII, secrets e toxicidade. A tentativa foi interrompida porque as dependências transitivas entraram em conflito com o ambiente oficial do CrewAI, DeepEval e Machine Learning, especialmente `json-repair`, `click`, `numpy`, `regex` e pacotes do spaCy.

Para preservar a reprodutibilidade e não quebrar a aplicação, o LLM Guard foi removido do código, requisitos e ambiente. A aplicação não depende dele para iniciar nem para processar requisições.

### 8.2 Guardrails determinísticos reforçados

Em substituição, a Etapa 3 fortaleceu:

- PII em entradas e saídas;
- CPF, RG, telefone e e-mail;
- Bearer tokens, JWT, chaves `sk-`, chaves Google, tokens Slack;
- credenciais em campos textuais;
- chaves privadas PEM;
- connection strings;
- prompt injection e jailbreak conhecidos;
- SQL destrutivo;
- toxicidade explícita;
- decisões trabalhistas indevidas;
- vazamento de system prompt, developer message e chain-of-thought.

### 8.3 Output gate central

`src/output_security.py` fornece uma fronteira única fail-closed antes de a resposta ser exibida, persistida ou narrada.

```text
resposta local/Gemini/CrewAI
  → validação PII/secrets
  → validação de vazamento de instruções
  → validação de decisão trabalhista
  → toxicidade
  → Streamlit/histórico
```

Se a saída for insegura:

- não é exibida;
- não é persistida no histórico;
- não é enviada ao Langfuse;
- um diagnóstico seguro e Trace ID são apresentados.

### 8.4 Casos de segurança no Golden Dataset

O Golden Dataset mantém cinco casos adicionais para regressão:

- prompt injection;
- jailbreak;
- PII/exfiltração;
- secrets;
- toxicidade.

Esses casos são bloqueados antes de chegar a modelos externos. Eles testam as regras determinísticas atuais e não dependem de LLM Guard.

## 9. Observabilidade e governança

A observabilidade foi mantida sem conteúdo privado. Traces e spans registram:

- rota;
- status;
- serviço;
- agente/tarefa;
- duração;
- tokens;
- custo;
- categoria agregada de segurança.

Não são registrados:

- currículo bruto;
- PII;
- secrets;
- prompts privados;
- chain-of-thought;
- respostas bloqueadas completas.

A camada de segurança pode registrar somente `allowed/blocked`, categoria, rota e duração.

## 10. Testes realizados no início da Etapa 3

A suíte passou a cobrir:

- PDF textual e PDF escaneado;
- OCR e idiomas;
- upload efêmero;
- JEV mockado, PII, TLS, timeout e formato inválido;
- Gemini, TLS, fallback de modelo, tokens e custo;
- Langfuse generation;
- Golden Dataset executável;
- RAG live com resposta atual;
- prompt injection;
- jailbreak;
- PII;
- secrets;
- toxicidade;
- output gate central;
- DeepEval e relatórios.

A execução validada ao documentar este início da Etapa 3 contém **142 testes aprovados**, com `pip check` sem conflitos no ambiente oficial e Streamlit saudável.

## 11. Limitações atuais

A Etapa 3 melhora a segurança e a regressão, mas não afirma invulnerabilidade. Permanecem limitações:

- padrões determinísticos não cobrem todos os bypasses possíveis;
- DeepEval não substitui avaliação humana;
- casos RAG ainda são controlados e sintéticos;
- PII ofuscada ou em imagens exige evolução de modelos especializados;
- o ambiente não possui autenticação/RBAC real;
- integração futura de um scanner semântico deve ocorrer em processo isolado para não quebrar dependências;
- custo e disponibilidade de APIs externas dependem dos provedores.

## 12. Próximos passos

- expandir ataques sintéticos multilíngues e Unicode;
- adicionar análise de documentos recuperados antes do LLM;
- avaliar Presidio em ambiente separado para PII avançada;
- versionar métricas de segurança por commit;
- comparar relatórios entre versões do repositório;
- ampliar casos RAG difíceis e contextos distratores;
- criar testes de carga da camada de output;
- revisar guardrails com especialistas de segurança e RH;
- manter revisão humana antes de qualquer uso organizacional.

A Etapa 3, neste início, é portanto uma etapa de confiabilidade: corrige integrações, torna avaliações executáveis contra o código atual, mede o uso real de APIs, centraliza a validação de respostas e registra explicitamente as limitações da segurança implementada.
