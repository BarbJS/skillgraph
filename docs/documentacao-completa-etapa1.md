# SkillGraph — Documentação completa da Etapa 1

## 1. Declaração CBL

### Grande ideia

Transformar a gestão de competências e a aprendizagem corporativa em um processo orientado por dados, evidências e inteligência artificial, permitindo consultar políticas, compreender requisitos de cargos e organizar oportunidades de desenvolvimento de forma transparente.

### Pergunta essencial

**Como uma organização pode identificar lacunas de competências e recomendar trilhas de aprendizagem personalizadas na era da IA generativa?**

### Escopo da Etapa 1

A Etapa 1 constrói a fundação conversacional do SkillGraph para a NexaTech, empresa fictícia de tecnologia e serviços. Ela integra Streamlit, Dify, LM Studio, Docker, Weaviate e DuckDB para:

- consultar políticas, cargos, competências e trilhas por RAG;
- responder indicadores agregados em dados estruturados;
- apresentar fontes, tabelas, gráficos, streaming e feedback;
- bloquear PII, prompt injection, SQL destrutivo e solicitações inseguras;
- registrar métricas operacionais minimizadas.

A camada de Machine Learning tradicional pertence à **Etapa 2** e possui documentação própria em [documentacao-completa-etapa2.md](documentacao-completa-etapa2.md). Ela não faz parte do escopo técnico desta documentação.

## 2. Contexto e finalidade

A NexaTech é uma empresa fictícia com colaboradores distribuídos por Tecnologia, Produto, Dados, Operações, Comercial, RH e Financeiro. As informações de cargos, competências, treinamentos e políticas estão distribuídas entre documentos e tabelas.

O SkillGraph apoia:

- **Funcionários:** consulta de requisitos, políticas e trilhas;
- **Gestores:** indicadores agregados;
- **RH:** regras, prioridades e orientações de desenvolvimento;
- **Desenvolvedores:** observabilidade e diagnóstico técnico.

Os perfis são simulados. A Etapa 1 não possui autenticação real ou RBAC.

## 3. Arquitetura da Etapa 1

```text
Pergunta
  ↓
Streamlit
  ↓
Guardrails + roteador determinístico
  ├── pergunta documental → Dify → Weaviate → LM Studio → resposta + fontes
  ├── indicador/consulta permitida → função read-only → DuckDB → tabela/indicador
  ├── smalltalk → resposta local
  └── conteúdo sensível → bloqueio
```

O Dify orquestra o Chatflow documental e o Weaviate gerenciado. O DuckDB consulta apenas os cinco CSVs sintéticos autorizados em `data_bd/`. O LLM não gera SQL livre.

## 4. Componentes

- **Docker Desktop:** executa Dify e serviços auxiliares de modo reproduzível.
- **Dify:** API, Chatflow, recuperação e streaming.
- **Weaviate:** armazenamento vetorial gerenciado pelo Dify.
- **LM Studio:** modelo de chat e modelo de embeddings em API compatível com OpenAI.
- **Streamlit:** interface, histórico, perfis simulados, tabelas, gráficos e feedback.
- **DuckDB:** consultas read-only nos CSVs estruturados.
- **Guardrails/roteador:** proteção e escolha determinística do fluxo.

## 5. Dados e RAG

O corpus documental contém:

- `politica_treinamentos.md`;
- `descricoes_cargos.md`;
- `manual_trilhas.md`;
- `faq_desenvolvimento.md`.

A base estruturada contém:

- `cargos.csv`;
- `competencias.csv`;
- `funcionario_competencia.csv`;
- `funcionario_treinamento.csv`;
- `treinamentos.csv`.

Documentos e tabelas permanecem separados: RAG responde regras e explicações; DuckDB calcula indicadores exatos.

## 6. Segurança e observabilidade

Os guardrails bloqueiam CPF, RG, CNPJ, e-mail, telefone, endereço, salário individual, prompt injection e SQL destrutivo. A Etapa 1 não automatiza decisões de carreira.

Os logs locais registram apenas metadados como rota, status, latência, request ID, bloqueios, erros, fontes e ferramentas. Não registram chaves, perguntas ou respostas completas.

## 7. Execução

Pré-requisitos:

- Docker Desktop com Compose v2;
- Python 3.11.x (versão oficial suportada pelo projeto);
- Git, `curl` e opcionalmente `jq`;
- LM Studio com chat e embeddings.

```bash
cp env.example .env
make bootstrap-crewai
# O comando prepara o ambiente oficial .venv com Python 3.11.
make bootstrap
make up
make smoke
make run
```

O Dify fica em `http://localhost` e o Streamlit em `http://localhost:8501`.

## 8. Testes e demonstração

```bash
pytest -q tests
python -m src.evaluation
```

A demonstração da Etapa 1 deve apresentar:

1. pergunta documental com fonte;
2. consultas estruturadas retornadas pelo DuckDB;
3. tentativa de acessar PII bloqueada;
4. streaming do Chatflow;
5. métricas de observabilidade.

Testes e documentação da Etapa 2 são executados separadamente conforme [documentacao-completa-etapa2.md](documentacao-completa-etapa2.md).

## 9. Limitações e continuidade

A Etapa 1 é um MVP acadêmico. Antes de uso real seriam necessários autenticação corporativa, RBAC, retenção, armazenamento protegido, observabilidade centralizada, revisão humana formal e testes de carga.

A continuidade de Machine Learning, FLAML, O*NET, artefatos PKL e recomendações de trilhas está documentada na Etapa 2.
