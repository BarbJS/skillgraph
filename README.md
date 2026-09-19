# 🧠 SkillGraph

> Projeto em desenvolvimento na disciplina **AI Factory: Building Intelligent Systems**, do curso de graduação em Inteligência Artificial da **PUCPR (2026)**.
>
> Orientação: **Professor Wellington Rodrigo Monteiro**
> Desenvolvimento: **Bárbara Jaeger Specian**, com assistência de Inteligência Artificial.

## 🎯 Objetivo central

O objetivo do SkillGraph é transformar a gestão de competências e a aprendizagem corporativa em um processo orientado por dados, evidências e inteligência artificial. A aplicação foi criada para ajudar organizações a identificar lacunas de habilidades, consultar requisitos de cargos, priorizar treinamentos e orientar o desenvolvimento profissional de forma mais personalizada, transparente e auditável.

## 🧩 Declaração CBL em resumo

> As respostas completas do CBL e a documentação técnica estão em [Documentação completa da Etapa 1](docs/documentacao-completa-etapa1.md).

- **Grande ideia:** usar dados, evidências e IA para apoiar a gestão de competências e a aprendizagem corporativa.
- **Pergunta essencial:** como uma organização pode identificar lacunas de competências e recomendar trilhas de aprendizagem personalizadas na era da IA generativa?
- **Desafio:** construir uma aplicação funcional que combine RAG, dados estruturados, interface conversacional, segurança e observabilidade.
- **Justificativa:** explorar Recursos Humanos e aprendizagem corporativa como um novo domínio de aplicação de RAG, LLM local, análise de dados e governança de IA.


> **Assistente de competências e aprendizagem corporativa** para a NexaTech — uma empresa fictícia de tecnologia e serviços.

<div align="center">

**RAG** · **LLM local** · **DuckDB** · **Streamlit** · **Segurança**

</div>

O **SkillGraph** transforma documentos, dados estruturados e modelos de linguagem locais em uma experiência conversacional para consultar políticas de treinamento, entender requisitos de cargos, identificar lacunas de competências e explorar possibilidades de desenvolvimento profissional.

## 🔄 Como o SkillGraph funciona

1. **A pessoa usuária faz uma pergunta** pela interface Streamlit.
2. **Os guardrails verificam a solicitação**, bloqueando dados sensíveis, prompt injection e operações inseguras.
3. **O roteador identifica a intenção** e escolhe o fluxo adequado.
4. **Perguntas documentais seguem para o RAG:** o Dify recupera trechos no Weaviate e chama o LM Studio para gerar uma resposta baseada nas fontes.
5. **Perguntas estruturadas seguem para o DuckDB:** funções determinísticas consultam os CSVs e retornam tabelas ou indicadores.
6. **O Streamlit apresenta o resultado**, com streaming, fontes, tabelas, gráficos, feedback e métricas.

### Exemplo de pergunta documental

```text
Pergunta: Quantas horas de treinamento um funcionário sênior deve realizar por ano?
```

O sistema valida a pergunta, identifica uma intenção documental, envia a solicitação ao Chatflow do Dify, recupera os trechos relevantes da política de treinamentos no Weaviate, encaminha o contexto ao LM Studio e retorna a resposta em streaming com a fonte utilizada.

### Exemplo de pergunta estruturada

```text
Pergunta: Quais competências têm mais lacunas?
```

Nesse caso, o roteador não envia a pergunta para o RAG. Uma função de leitura consulta o DuckDB, compara o nível atual com o nível obrigatório e retorna um indicador agregado por competência.

> ✨ **Em uma frase:** uma pergunta em linguagem natural percorre a fonte mais adequada — documentos, dados relacionais ou uma ferramenta especializada — e retorna uma resposta explicável, com fontes, tabelas ou indicadores quando aplicável.

O projeto foi pensado para um contexto acadêmico, mas segue uma arquitetura funcional e reproduzível. A aplicação combina infraestrutura local, recuperação aumentada por geração, consultas analíticas determinísticas, guardrails e uma interface orientada à experiência do usuário.

> ⚠️ **Aviso importante:** os dados da NexaTech são sintéticos. O protótipo não substitui decisões de RH, avaliação humana, autenticação corporativa ou políticas reais de privacidade.

## 🧭 Comece por aqui

| Se você quer... | Comece por... |
| --- | --- |
| Entender o desenvolvimento completo | 📖 [Documentação completa da Etapa 1](docs/documentacao-completa-etapa1.md) |
| Executar o projeto localmente | 🚀 [Como executar em uma máquina nova](#-como-executar-em-uma-máquina-nova) |
| Configurar Dify e LM Studio | 🧩 [Configuração do LM Studio no Dify](docs/model-setup.md) |
| Entender o RAG | 📚 [Pipeline Dify + Weaviate](#-arquitetura-em-uma-visão) |

### 🗺️ Navegação rápida

- [✨ O que o projeto demonstra](#-o-que-este-projeto-demonstra)
- [🎯 Problema de negócio](#-problema-de-negócio)
- [🏗️ Arquitetura](#arquitetura-em-uma-visão)
- [🚀 Execução local](#como-executar-em-uma-máquina-nova)
- [💡 Exemplos](#exemplos-para-experimentar)
- [🧪 Testes](#testes-e-avaliação)
- [🛡️ Segurança](#segurança-privacidade-e-limites)
- [📚 Documentação](#documentação-e-leitura-adicional)

## ✨ O que este projeto demonstra

- 💬 Chat em linguagem natural com respostas em português e streaming.
- 📚 RAG sobre políticas, descrições de cargos, trilhas e FAQ de desenvolvimento.
- 🔎 RAG com Dify e o armazenamento vetorial gerenciado pelo próprio Dify.
- 🧮 Consultas analíticas em DuckDB sobre CSVs relacionais.
- 🛡️ Bloqueio de PII, salário individual, SQL destrutivo e tentativas de prompt injection.
- 📊 Indicadores agregados, tabelas, gráficos, fontes recuperadas e métricas locais.
- 🧑‍💼 Experiências simuladas para desenvolvedor, gestor e RH.
- 🧪 Testes automatizados e dataset dourado para avaliar o roteamento.

## 📌 Estado atual da entrega

| Área | Situação |
| --- | --- |
| Interface conversacional | ✅ Streamlit com histórico, streaming, fontes e feedback |
| RAG | ✅ Dify Chatflow + Weaviate gerenciado pelo Dify |
| System prompt | ✅ Contextualizado para RH e aprendizagem corporativa |
| Dados estruturados | ✅ DuckDB sobre cinco CSVs sintéticos |
| Segurança | ✅ Guardrails para PII, prompt injection e SQL destrutivo |
| Observabilidade | ✅ Métricas locais e logs minimizados |
| Machine Learning | 🧭 Reservado para a Etapa 2 |
| Autenticação real | 🧭 Fora do escopo do MVP |

## 🎯 Problema de negócio

A NexaTech oferece treinamentos, trilhas e oportunidades de desenvolvimento, mas suas informações estão distribuídas entre documentos e tabelas. Isso dificulta responder perguntas como:

- Quais competências são exigidas para determinado cargo?
- Qual é a carga horária anual esperada para cada nível?
- Quais competências apresentam mais lacunas?
- Quais treinamentos estão disponíveis para desenvolver uma habilidade?
- Como consultar uma situação específica sem expor dados pessoais?

O SkillGraph não automatiza promoção, demissão ou qualquer decisão de carreira. Seu objetivo é organizar evidências para apoiar conversas de desenvolvimento: funcionários consultam políticas e trilhas, gestores acompanham indicadores agregados e RH consulta regras e prioridades de aprendizagem.

## 🏗️ Arquitetura em uma visão

```text
┌──────────────────────────────────────────────────────────────┐
│ Usuário                                                      │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ Streamlit: chat, histórico, feedback, tabelas e observabilidade │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ Guardrails + roteador determinístico de intenção             │
└──────────────┬──────────────────┬──────────────────┬────────┘
               │                  │                  │
               ▼                  ▼                  ▼
       Pergunta documental  Indicador/diagnóstico  Conteúdo sensível
               │                  │                  │
               ▼                  ▼                  ▼
       Dify Chatflow       DuckDB determinístico   Bloqueio imediato
               │                  │
               ▼                  ▼
          Weaviate       CSVs relacionais
               │                  │
               ▼                  ▼
       Contexto recuperado   Resultado estruturado
               │                  │
               ▼                  │
       LM Studio local            │
       (resposta gerada)          │
               │                  │
               └──────┬───────────┘
                      ▼
        Resposta final no Streamlit
                      │
                      ▼
                    Usuário

Pipeline RAG principal:
Streamlit → Dify Chatflow → Weaviate → contexto recuperado
                              ↓
                       LM Studio local
                              ↓
               resposta aumentada → Streamlit → Usuário

Infraestrutura Dify:
Docker Desktop → Dify self-hosted → API/Chatflow/serviços auxiliares
```

### Responsabilidade de cada componente

| Componente | Responsabilidade no SkillGraph |
| --- | --- |
| 🐳 Docker Desktop | Executar o Dify e seus serviços de forma isolada e reproduzível. |
| 🧩 Dify | Orquestrar o Chatflow, disponibilizar a API e gerenciar a recuperação do RAG. |
| 🗂️ Weaviate | Armazenar e recuperar vetores dentro do caminho de RAG gerenciado pelo Dify. |
| 🧠 LM Studio | Servir localmente o modelo de chat e o modelo de embeddings por uma API compatível com OpenAI. |
| 🖥️ Streamlit | Entregar a interface, o histórico, os perfis simulados e a integração das camadas. |
| 🦆 DuckDB | Consultar os CSVs relacionais com rapidez, sem transformar dados tabulares em texto. |

O Dify orquestra o Chatflow: recebe a pergunta do Streamlit, consulta o Weaviate, combina o contexto recuperado com a pergunta e chama o modelo de chat do LM Studio. O modelo gera a resposta aumentada, que retorna pelo Dify à API do SkillGraph e é apresentada pelo Streamlit ao usuário. Para perguntas estruturadas, o roteador consulta diretamente o DuckDB e devolve o resultado ao Streamlit sem passar pelo RAG.

O Weaviate armazena e recupera os vetores usados internamente pelo Dify. Essa decisão evita duplicidade entre bases vetoriais e simplifica a operação e a evolução do sistema.

## 🚀 Como executar em uma máquina nova

### Pré-requisitos

Instale ou tenha disponível:

- Docker Desktop com Docker Compose v2;
- Python 3.11 ou superior;
- Git, `curl` e, opcionalmente, `jq`;
- LM Studio com um modelo de chat carregado;
- um modelo de embeddings compatível com o endpoint `/v1/embeddings`;
- memória e espaço suficientes para o modelo local e os containers do Dify.

Confira as ferramentas principais:

```bash
docker --version
docker compose version
git --version
python3 --version
```

### 1. Preparar a configuração local

Na raiz do projeto, crie o arquivo de ambiente a partir do exemplo:

```bash
cp env.example .env
```

Revise os IDs dos modelos depois de iniciar o servidor local do LM Studio. O arquivo `.env` é ignorado pelo Git e não deve conter informações que você pretenda publicar.

### 2. Iniciar o servidor local do LM Studio

No LM Studio, carregue um modelo de chat e inicie o servidor local na porta `1234`, que é a porta esperada pelo projeto por padrão. Em seguida, confira os IDs realmente expostos:

```bash
make check
```

O nome cadastrado no Dify deve ser o `id` retornado pela API, e não necessariamente o nome amigável exibido na interface do LM Studio. O projeto usa dois tipos de modelo com responsabilidades diferentes:

- modelo de chat: gera a resposta final;
- modelo de embeddings: transforma documentos e perguntas em vetores numéricos para a busca semântica.

Teste os dois endpoints diretamente:

```bash
make test
```

### 3. Preparar e iniciar o Dify

O bootstrap baixa a versão pinada do Dify em `.dify/`, sem versionar essa instalação no projeto:

```bash
make bootstrap
make up
make smoke
```

Acesse `http://localhost/install` para concluir a criação do administrador local. Depois, configure no Dify o provider de LM Studio, cadastre o modelo de chat e o modelo de embeddings e crie/publice o Chatflow utilizado pela aplicação. O passo a passo está em [docs/model-setup.md](docs/model-setup.md).

No host, o LM Studio normalmente responde em `http://127.0.0.1:1234/v1`. Dentro dos containers Docker Desktop, o mesmo host é acessado por `http://host.docker.internal:1234/v1`. O script de bootstrap cria o ajuste de gateway necessário para o `plugin_daemon` do Dify.

### 4. Instalar as dependências Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

No Windows, ative o ambiente virtual com o comando equivalente do PowerShell ou do terminal utilizado.

### 5. Executar o Streamlit

Com o Chatflow publicado e a chave local configurada em `.env`, execute:

```bash
streamlit run app.py
```

A aplicação normalmente ficará disponível em `http://localhost:8501`. A chave da API do Dify é utilizada pelo processo Python e não é enviada ao navegador.

## 📚 Pipeline RAG com Dify e Weaviate

O SkillGraph utiliza o Chatflow do Dify como seu único caminho de RAG. O Dify gerencia a recuperação na base de conhecimento, utiliza o Weaviate como armazenamento vetorial nesta instalação local e chama o LM Studio para gerar a resposta. A aplicação Streamlit consome o streaming retornado pela API e apresenta as fontes recuperadas.

A configuração dos documentos, embeddings, chunks e Top K é feita no próprio Dify. Para iniciar o fluxo local:

```bash
make bootstrap
make up
make smoke
streamlit run app.py
```

Depois de criar a base de conhecimento e publicar o Chatflow, não é necessário indexar uma segunda base vetorial local. Essa decisão mantém uma única fonte de recuperação, evita resultados divergentes e simplifica a reprodução e a operação do projeto.

O perfil **desenvolvedor** pode consultar as métricas do fluxo principal. Gestor e RH utilizam a aplicação pela perspectiva de negócio, sem precisar conhecer detalhes de embeddings ou armazenamento vetorial.

### Fluxo documental

```text
Pergunta → Streamlit → Dify Chatflow → Weaviate → LM Studio → resposta + fontes
```

### Fluxo estruturado

```text
Pergunta → Streamlit → roteador → função read-only → DuckDB → tabela
```

Os dois fluxos são complementares: o RAG consulta conhecimento documental; o DuckDB calcula resultados exatos sobre os CSVs relacionais.

## 💡 Exemplos para experimentar

Perguntas documentais, encaminhadas ao RAG:

```text
Quantas horas de treinamento um funcionário sênior deve realizar por ano?
Quais competências são obrigatórias para um Analista de Dados Júnior?
Como funciona a trilha de Analista de Dados Júnior para Pleno?
Quantos treinamentos simultâneos são recomendados?
```

Perguntas estruturadas, encaminhadas ao DuckDB por ferramentas seguras:

```text
Quais competências têm mais lacunas?
Quais treinamentos estão disponíveis?
```

Consulta de caso, com IDs explícitos:

```text
Qual é a situação da competência COMP003 para o funcionário F0001?
```

Comparação baseada em evidências documentais:

```text
Qual é a diferença de carga horária entre os níveis Júnior e Sênior?
```

Exemplo de solicitação bloqueada:

```text
Qual é o CPF do funcionário F0001?
```

## 🧭 Como uma pergunta percorre o sistema

Antes de chamar um modelo, o SkillGraph aplica guardrails para identificar PII, salário individual, prompt injection e operações SQL inseguras. Em seguida, o roteador determinístico classifica a intenção como pergunta documental, indicador SQL, consulta de competência, comparação, smalltalk ou bloqueio.

Perguntas documentais seguem para o backend RAG selecionado e retornam resposta com fontes quando disponíveis. Indicadores agregados utilizam ferramentas SQL allowlisted no DuckDB. Consultas de competência exigem os identificadores do funcionário e da competência. Mensagens simples, como saudações, não consomem o RAG. Solicitações sensíveis são interrompidas antes de qualquer consulta ao modelo ou ao banco.

## 📁 Organização do repositório

```text
.
├── app.py                         # interface Streamlit
├── config/                        # referências de configuração do Chatflow
├── data_bd/                       # CSVs relacionais sintéticos
├── documents_rag/                 # corpus Markdown do RAG
├── docs/                          # documentação técnica e operacional
├── evals/                         # dataset dourado e instruções de avaliação
├── scripts/                       # bootstrap, smoke tests e utilitários
├── src/                           # roteamento, RAG, SQL e segurança
├── tests/                         # testes automatizados
├── env.example                    # configuração sem segredos
├── Makefile                       # comandos operacionais
└── requirements.txt               # dependências Python da Etapa 1
```

## 🤝 Como usar e colaborar

Depois de configurar o ambiente seguindo o quickstart, outras pessoas podem explorar o SkillGraph com os dados sintéticos da NexaTech, testar perguntas documentais e estruturadas, revisar as fontes retornadas e executar a suíte de testes. Para colaborar, é possível propor melhorias na documentação, adicionar perguntas ao dataset de avaliação, revisar o corpus em `documents_rag/`, aprimorar as consultas read-only do DuckDB ou sugerir melhorias de usabilidade e acessibilidade. Toda contribuição deve preservar a privacidade, manter os dados sintéticos, evitar credenciais no repositório e explicar claramente o comportamento alterado.

Antes de propor mudanças no Chatflow, recomenda-se testar as perguntas do dataset dourado, conferir a fidelidade das fontes, verificar a ausência de evidência e registrar impactos de latência. Alterações de código devem ser acompanhadas por testes e manter a separação entre RAG documental e dados estruturados.

## 🧪 Testes e avaliação

Com o ambiente virtual ativado e as dependências instaladas:

```bash
pytest -q tests
python -m src.evaluation
```

Os testes verificam roteamento, guardrails, consultas determinísticas no DuckDB, cliente Dify, comparação de trilhas, sessões, feedback, observabilidade e o dataset dourado. A avaliação usa cenários com respostas esperadas e confirma que perguntas sensíveis não avançam para ferramentas indevidas.

Para validar a infraestrutura local:

```bash
make check          # modelos expostos pelo LM Studio
make test           # chat e embeddings do LM Studio
make smoke          # Dify e LM Studio
make status         # containers do Dify
```

## 🛡️ Segurança, privacidade e limites

- `.env`, `.dify/`, bancos locais, logs, modelos e artefatos gerados não fazem parte do pacote público.
- Não publique chaves de API, credenciais do Dify ou senhas dos containers.
- Não exponha publicamente as portas do LM Studio ou do Dify durante o desenvolvimento.
- O DuckDB aceita apenas consultas de leitura e as ferramentas da aplicação são allowlisted.
- Os logs registram metadados de execução, não o texto completo das perguntas e respostas.
- Os perfis de desenvolvedor, gestor e RH são simulações; ainda não existe login ou RBAC real.
- A base não possui uma tabela-mestre completa de funcionários com nome, cargo, gestor e departamento.
- As faixas salariais representam cargos e não autorizam inferências sobre salário individual.
- O classificador preditivo de Machine Learning pertence à Etapa 2 e não é usado para decisões nesta entrega.

Nunca use o comando abaixo em testes normais, pois ele remove volumes e dados locais do Dify:

```bash
docker compose down -v
```

## 🧩 Limitações conhecidas e próximos passos

O SkillGraph é um MVP acadêmico funcional. Antes de um uso real, seria necessário implementar autenticação corporativa, autorização por perfil, política de retenção, armazenamento protegido, observabilidade centralizada, revisão humana formal e testes de carga. Também estão planejados o classificador de risco da Etapa 2, uma possível tabela organizacional mais completa, integração com ferramentas corporativas e evolução da busca híbrida.

## 📚 Documentação e leitura adicional

### 📖 Documentação detalhada

Para entender o CBL, a evolução técnica completa, as conclusões e os próximos passos possíveis — desde a integração entre Docker, LM Studio e Dify até a incorporação de Streamlit, DuckDB, UX writing, segurança e observabilidade — leia:

➡️ **[Documentação completa da Etapa 1](docs/documentacao-completa-etapa1.md)**

Esse documento reúne a explicação aprofundada que acompanha esta entrega e serve como base para o PDF/documentação final do projeto.

### 🧰 Guias operacionais

- [Configuração do LM Studio no Dify](docs/model-setup.md)
- [Arquitetura e decisões de RAG](docs/rag-architecture-decisions.md)
- [System prompt contextualizado](docs/system-prompt.md)
- [Text-to-SQL seguro](docs/text-to-sql.md)
- [Observabilidade](docs/observability.md)

## 🎓 Contexto acadêmico e autoria

Este é um projeto em desenvolvimento na disciplina **AI Factory: Building Intelligent Systems**, do curso de graduação em Inteligência Artificial da **PUCPR (2026)**. O trabalho é orientado pelo **Professor Wellington Rodrigo Monteiro** e foi desenvolvido pela aluna **Bárbara Jaeger Specian**, com assistência de Inteligência Artificial.

O projeto responde à pergunta: **como uma organização pode identificar lacunas de competências e recomendar trilhas de aprendizagem personalizadas na era da IA generativa?** A solução combina recuperação fundamentada em documentos, análise determinística de dados estruturados, um system prompt contextualizado e uma experiência conversacional orientada por transparência.

A camada preditiva, o deploy público e as integrações corporativas permanecem como evolução posterior. O foco desta entrega é demonstrar uma base local, funcional, explicável e reproduzível para apoiar o desenvolvimento profissional com responsabilidade.
