# SkillGraph — Documentação completa da Etapa 1

## 1. Declaração CBL: perguntas e respostas

### Qual é a grande ideia do projeto?

Transformar a gestão de competências e a aprendizagem corporativa em um processo orientado por dados, evidências e inteligência artificial, permitindo que organizações identifiquem lacunas de habilidades, priorizem treinamentos e orientem o desenvolvimento profissional de forma personalizada e auditável.

### Qual é a pergunta essencial?

**Como uma organização pode identificar lacunas de competências dos funcionários e recomendar trilhas de aprendizagem personalizadas na era da IA generativa?**

### Qual é o desafio proposto?

Construir uma aplicação web chamada SkillGraph para a NexaTech, uma empresa fictícia de tecnologia e serviços, capaz de consultar políticas de treinamento, descrições de cargos, competências e trilhas de desenvolvimento por meio de RAG; analisar dados estruturados de competências e treinamentos; responder indicadores agregados; orientar caminhos de desenvolvimento fundamentados; bloquear dados sensíveis e registrar métricas de uso.

A primeira entrega integra Streamlit, Dify, LM Studio, Docker, Weaviate e DuckDB, mantendo respostas baseadas em fontes, consultas determinísticas e revisão humana. Nesta etapa, não foram incluídos agentes Python, Machine Learning, autenticação real ou uma segunda pipeline de RAG.

### Por que esse tema foi escolhido? - Justificativas

- **Pessoal:** Neste semestre, decidi explorar um domínio diferente dos que trabalhei anteriormente na disciplina AI Factory. No primeiro semestre, desenvolvi um projeto relacionado ao controle e à garantia da qualidade em linhas de inspeção industrial (onde tenho experiência); no segundo, explorei e-commerce, análise de dados e análise de sentimentos (relacionando com o início do meu estágio). E agora escolhi o domínio de Recursos Humanos para aplicar meus conhecimentos, ampliar minha visão sobre as possibilidades de exercício da IA nesta área, e também ampliar minhas possibilidades de atuação com IA nesse novo contexto.

- **Social:** A escolha também se relaciona ao impacto atual e contínuo da transformação digital e da inteligência artificial sobre as competências exigidas pelas empresas. À medida que ferramentas e funções mudam, torna-se cada vez mais importante compreender o que cada cargo exige, quais habilidades as equipes já possuem e quais oportunidades de aprendizagem podem apoiar seu desenvolvimento.

### Qual é o contexto da NexaTech?

A NexaTech é uma empresa fictícia de tecnologia e serviços com aproximadamente 300 colaboradores, distribuídos entre áreas como Tecnologia, Produto, Dados, Operações, Comercial, RH e Financeiro. A empresa oferece treinamentos, mas enfrenta dificuldades para compreender quais competências estão abaixo do nível exigido, quais trilhas são mais adequadas e como transformar informações de desenvolvimento em orientações úteis.

Em empresas de diferentes portes, principalmente nas pequenas e médias, a relação entre cargos, competências e oportunidades de aprendizagem muitas vezes ainda é construída de maneira informal. Pode existir conhecimento prático sobre as ferramentas que determinada função exige, mas nem sempre esse conhecimento está organizado de uma forma que ajude a avaliar equipes, priorizar treinamentos ou planejar o desenvolvimento profissional.

### Qual é a finalidade do SkillGraph?

O SkillGraph é uma aplicação inteligente que integra RAG, dados estruturados, modelos de linguagem locais, consultas analíticas, segurança e experiência do usuário. Ele não é apenas um chat: combina diferentes camadas para transformar informações de desenvolvimento profissional em respostas, indicadores e orientações de aprendizagem.

A aplicação apoia diferentes públicos:

- **Funcionários:** consultam requisitos, políticas, competências e trilhas de aprendizagem.
- **Gestores:** acompanham indicadores agregados de competências e treinamentos.
- **RH:** consulta políticas, prioridades e orientações de desenvolvimento.
- **Desenvolvedores:** observam o funcionamento técnico da aplicação e suas métricas.

Os perfis são simulados para demonstrar experiências diferentes. Nesta etapa, ainda não existe autenticação ou controle de acesso real.

O objetivo é ajudar a empresa e as pessoas colaboradoras a compreenderem melhor as competências necessárias, identificarem oportunidades de desenvolvimento e encontrarem caminhos de aprendizagem mais alinhados às necessidades de cada contexto.

## 2. Escopo e arquitetura da Etapa 1

O SkillGraph é uma aplicação inteligente que integra RAG, dados estruturados, modelos de linguagem locais, consultas analíticas, segurança e experiência do usuário. Ele não é apenas um chat: combina diferentes camadas para transformar informações de desenvolvimento profissional em respostas, indicadores e orientações de aprendizagem.

### Como uma pergunta percorre o sistema

```text
Pergunta do usuário
  ↓
Streamlit
  ↓
Guardrails e roteador determinístico
  ├── Pergunta documental → Dify → Weaviate → LM Studio → resposta + fontes
  ├── Pergunta estruturada → função read-only → DuckDB → tabela ou indicador
  └── Solicitação sensível → bloqueio imediato
```

Exemplo documental: ao perguntar “Quantas horas de treinamento um funcionário sênior deve realizar por ano?”, o sistema valida a entrada, identifica uma intenção documental, envia a pergunta ao Chatflow do Dify, recupera trechos da política no Weaviate, encaminha o contexto ao LM Studio e apresenta a resposta em streaming com a fonte utilizada.

Exemplo estruturado: ao perguntar “Quais competências têm mais lacunas?”, o roteador não envia a pergunta ao RAG. Uma função de leitura consulta o DuckDB, compara o nível atual com o nível obrigatório e retorna um indicador agregado por competência.

### Responsabilidade resumida das ferramentas

- **Docker:** containerização e ambiente reproduzível para o Dify.
- **Dify:** orquestração do Chatflow, recuperação, API e streaming.
- **Weaviate:** armazenamento vetorial gerenciado pelo Dify.
- **LM Studio:** modelos locais de chat e embeddings.
- **Streamlit:** interface, histórico, feedback e apresentação dos resultados.
- **DuckDB:** consultas exatas sobre os CSVs relacionais.
- **Roteador e guardrails:** escolha do fluxo e proteção da aplicação.

## 3. Desenvolvimento técnico

### 3.1. Docker, LM Studio e Dify

O primeiro desafio foi estabelecer uma fundação técnica confiável antes de construir a aplicação final. O Docker Desktop foi escolhido para executar o Dify self-hosted e seus serviços auxiliares de maneira isolada e reproduzível. Em vez de instalar manualmente cada serviço, o projeto utiliza o compose oficial do Dify e scripts de bootstrap que baixam uma versão definida, preparam o ambiente local e preservam configurações já existentes.

Essa escolha reduz a variabilidade entre execuções e separa o código do projeto da infraestrutura gerenciada localmente. O checkout do Dify, seus containers, volumes e bancos de apoio pertencem ao ambiente de execução e não ao pacote de código da aplicação.

O LM Studio foi adotado como servidor local de modelos porque oferece uma API compatível com o padrão OpenAI e permite executar os modelos sem enviar perguntas e documentos para um provedor externo durante o desenvolvimento. Ele exerce duas funções diferentes:

- o modelo de chat interpreta o contexto recuperado e redige a resposta;
- o modelo de embeddings converte documentos e perguntas em vetores numéricos.

Um modelo capaz de conversar não é automaticamente adequado para gerar embeddings. Por isso, os dois endpoints são validados separadamente antes da construção do RAG.

A integração entre Docker e LM Studio também exigiu compreender que `localhost` muda de significado conforme o processo que faz a chamada. O Streamlit executado no computador utiliza `127.0.0.1:1234`, enquanto um container Docker Desktop acessa o host por `host.docker.internal`. O bootstrap cria o ajuste necessário para que o `plugin_daemon` do Dify consiga alcançar o servidor do LM Studio no host.

O Dify foi introduzido como camada de orquestração visual. Ele permite cadastrar o provider de modelo, criar a base de conhecimento, configurar o Chatflow, publicar a API e observar o processo de recuperação. Nesse caminho, o Dify recebe a pergunta, recupera trechos da base, monta o contexto para o modelo, chama o LM Studio e devolve a resposta em streaming.

### 3.2. Corpus, embeddings e RAG

Depois de validar o primeiro chat, o conhecimento da NexaTech foi organizado em um corpus formado por quatro documentos Markdown:

- `politica_treinamentos.md`;
- `descricoes_cargos.md`;
- `manual_trilhas.md`;
- `faq_desenvolvimento.md`.

A política contém regras e condições; as descrições de cargos relacionam níveis a competências; o manual orienta sequências de desenvolvimento; e o FAQ resume dúvidas operacionais.

O processo de indexação divide os documentos em chunks e gera um embedding para cada trecho. Quando a pessoa faz uma pergunta, essa pergunta também é convertida em vetor e o mecanismo de busca procura trechos semanticamente próximos. O modelo de chat recebe a pergunta acompanhada pelos trechos relevantes e gera uma resposta condicionada por esse contexto.

No Dify, o Weaviate atua como armazenamento vetorial interno, enquanto o Dify permanece responsável pela orquestração, pela API, pelo fluxo visual e pela composição da resposta. A configuração de chunks, overlap, Top K e indexação fica concentrada na Knowledge Base do Dify.

Chunks muito grandes podem trazer contexto irrelevante. Chunks muito pequenos podem perder a relação entre regras e exceções. O Top K também influencia a qualidade: valores baixos podem omitir evidências, enquanto valores altos podem introduzir ruído. Por isso, o projeto considera perguntas respondíveis, ambíguas e fora do domínio, incluindo situações nas quais o comportamento correto é declarar ausência de evidência.

### 3.3. Interface Streamlit e experiência do usuário

O Streamlit foi escolhido porque permite transformar rapidamente os componentes Python em uma aplicação web navegável, sem exigir a construção inicial de um frontend separado. Ele oferece chat, estado de sessão, tabelas, gráficos, componentes HTML e atualização progressiva da resposta.

A interface evoluiu de uma tela inicial de validação para uma experiência mais clara e responsiva. Durante uma consulta documental, a pessoa vê uma mensagem de processamento e acompanha a resposta sendo construída por streaming. Durante uma consulta estruturada, recebe uma indicação de que os dados estão sendo consultados. Durante uma comparação, a interface informa que está comparando as informações.

A evolução também envolveu UX writing. O placeholder do chat orienta o tipo de pergunta, a barra lateral apresenta exemplos, as mensagens de carregamento explicam o que está acontecendo e as mensagens de erro evitam expor detalhes técnicos desnecessários.

A interface possui perfis simulados:

- o desenvolvedor visualiza métricas de observabilidade e informações técnicas;
- o gestor consulta indicadores agregados sobre competências e treinamentos;
- o RH utiliza o chat para consultar políticas, cargos e orientações de desenvolvimento.

As fontes ficam disponíveis em um painel expansível, as consultas analíticas aparecem em tabelas e gráficos, o histórico permite retomar conversas e o feedback cria um ciclo de melhoria.

### 3.4. DuckDB e dados estruturados

O DuckDB foi escolhido para a parte analítica porque oferece consultas SQL rápidas sobre dados locais, funciona embutido no processo Python e não exige um servidor de banco de dados para o MVP.

Os CSVs da pasta `data_bd/` são carregados em tabelas de uma conexão em memória:

- `cargos.csv`;
- `competencias.csv`;
- `funcionario_competencia.csv`;
- `funcionario_treinamento.csv`;
- `treinamentos.csv`.

Os documentos do RAG ficam em `documents_rag/`. Eles não são misturados aos dados tabulares, porque cada tipo de informação precisa de uma estratégia diferente.

O RAG recupera explicações e regras documentais. O DuckDB calcula resultados exatos sobre registros. Para identificar as competências com mais lacunas, por exemplo, o sistema compara nível atual e nível obrigatório, relaciona a competência ao seu nome e conta funcionários distintos por competência.

As consultas estruturadas são determinísticas. O usuário pergunta em linguagem natural, o roteador identifica a intenção e uma função previamente implementada executa apenas uma consulta de leitura. O LLM não gera SQL livre e não acessa diretamente o DuckDB.

### 3.5. Roteamento, segurança e observabilidade

O roteador determinístico classifica cada pergunta como RAG, indicador SQL, consulta de competência, comparação, smalltalk ou bloqueio.

- Perguntas sobre políticas, cargos e trilhas seguem para o Dify.
- Indicadores agregados seguem para funções read-only do DuckDB.
- Consultas específicas exigem identificadores como `F0001` e `COMP003`.
- Saudações são respondidas sem consultar o RAG.
- Perguntas sensíveis são bloqueadas antes de chamar o modelo ou o banco.

Como o contexto envolve Recursos Humanos, os guardrails bloqueiam CPF, RG, CNPJ, e-mail pessoal, telefone pessoal, endereço pessoal, salário individual, prompt injection e operações SQL destrutivas.

Os perfis são simulações, não autenticação real. A visão do gestor apresenta apenas indicadores agregados e não exibe decisões automáticas de carreira. A aplicação também não infere informações pessoais que não estejam presentes em fontes autorizadas.

A observabilidade registra somente metadados, como rota, status, latência, request ID, funções acionadas, quantidade de fontes, bloqueios e erros. O log não registra perguntas e respostas completas nem chaves de API.

## 4. Execução, testes e demonstração

### Pré-requisitos

- Docker Desktop com Docker Compose v2;
- LM Studio com modelos de chat e embeddings;
- Python 3.11 ou superior;
- Git;
- `curl` e, opcionalmente, `jq`.

### Configuração e execução

Na raiz do projeto:

```bash
cp env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make bootstrap
make up
make smoke
streamlit run app.py
```

O Dify local fica em `http://localhost` e o Streamlit em `http://localhost:8501`. A chave do Dify deve permanecer somente no `.env` local. O arquivo `env.example` serve como modelo para que outras pessoas saibam quais variáveis configurar.

### Testes

```bash
pytest -q tests
python -m src.evaluation
```

Os testes cobrem roteamento, guardrails, cliente Dify, consultas DuckDB, comparação, sessões, feedback, observabilidade e dataset dourado.

### Demonstração da Etapa 1

A demonstração deve apresentar:

1. uma pergunta documental respondida com fonte;
2. duas consultas estruturadas retornadas pelo DuckDB;
3. uma tentativa de acesso a CPF ou salário bloqueada;
4. o streaming no Streamlit;
5. as métricas de observabilidade.

## 5. Conclusão

O desenvolvimento do SkillGraph foi organizado como uma construção progressiva de camadas. Primeiro, Docker, LM Studio e Dify estabeleceram uma infraestrutura local para executar e orquestrar os modelos. Em seguida, os documentos foram preparados para RAG, os embeddings permitiram a busca semântica e o Dify passou a recuperar o contexto antes da geração. A utilização do armazenamento vetorial gerenciado pelo próprio Dify manteve uma única pipeline documental e simplificou a operação.

Depois, o Streamlit reuniu esses componentes em uma interface conversacional, enquanto o DuckDB acrescentou consultas exatas sobre dados estruturados. O roteador determinístico e os guardrails definiram qual caminho poderia responder a cada pergunta. Fontes, feedback, histórico, UX writing e observabilidade aproximaram o protótipo de uma experiência de produto, e não apenas de uma demonstração de modelo.

Um dos principais aprendizados foi compreender que sistemas inteligentes confiáveis não surgem de uma única tecnologia. Eles dependem da combinação entre infraestrutura, modelos, dados, regras, interface e critérios de avaliação. Aprendi que modelos de chat e de embeddings possuem responsabilidades diferentes; que documentos e tabelas exigem estratégias distintas; que respostas geradas precisam estar relacionadas a evidências; e que a ausência de informação deve ser tratada como um resultado válido.

Do ponto de vista do meu desenvolvimento como aluna e profissional, o projeto ampliou minha capacidade de investigar ferramentas, diagnosticar problemas de integração, organizar conhecimento, testar hipóteses e tomar decisões de arquitetura justificadas pelo contexto de uso. Mais do que conectar um LLM a uma aplicação, aprendi a construir uma solução de IA aplicada com responsabilidade, mantendo o usuário, a explicabilidade e o impacto da solução como referências constantes.

## 6. Próximos passos possíveis

Os próximos passos são possibilidades futuras e não fazem parte da entrega atual. Entre eles estão a camada de Machine Learning para classificação de risco, autenticação OAuth, RBAC real, uma tabela organizacional mais completa, persistência em PostgreSQL, integrações com Slack ou Teams, observabilidade centralizada, avaliação mais ampla da qualidade do RAG e atualização controlada do corpus.

Essas evoluções devem preservar os princípios definidos nesta etapa: separação de responsabilidades, dados sintéticos bem delimitados, transparência sobre fontes, proteção de informações pessoais e revisão humana. O objetivo é ampliar a solução sem transformar suas previsões ou recomendações em decisões automáticas sobre pessoas.
