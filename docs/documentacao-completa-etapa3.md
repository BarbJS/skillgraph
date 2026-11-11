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

O LM Studio local continua adequado para agentes e interpretação local, mas não fornece necessariamente custo de API nem uso confiável de tokens para demonstração. A Etapa 3 introduziu uma chamada Gemini obrigatória como última síntese das respostas elaboradas.

A arquitetura passou a ser:

```text
LM Studio/CrewAI/Dify/DuckDB/JEV
  ↓
rascunho ou resultado estruturado
  ↓
Gemini final
  ↓
output gate
  ↓
resposta ao usuário
```

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
GEMINI_MODEL=gemini-2.5-flash
GEMINI_FALLBACK_MODEL=gemini-flash-lite-latest
GEMINI_TIMEOUT_SECONDS=120
GEMINI_MAX_OUTPUT_TOKENS=5400
GEMINI_INPUT_USD_PER_1M=
GEMINI_OUTPUT_USD_PER_1M=
```

O Langfuse permanece opcional e recebe somente metadados agregados, sem conteúdo privado.

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
