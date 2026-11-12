# Cloud readiness — Problema 1

Esta etapa torna o aplicativo executável em um ambiente cloud genérico. Ela não hospeda Dify, LM Studio, JEV ou Langfuse e não resolve persistência distribuída.

## Execução local equivalente ao cloud

Use o launcher cloud:

```bash
PORT=8501 ./scripts/start-streamlit.sh
```

O launcher:

- usa `python3` por padrão, ou `PYTHON_BIN` quando informado;
- usa `PORT`, com fallback para `STREAMLIT_PORT` e depois `8501`;
- escuta em `0.0.0.0`, necessário para uma plataforma encaminhar tráfego externo;
- executa o `app.py` a partir da raiz do repositório;
- não depende do `.venv` local.

Para o ambiente oficial de desenvolvimento, `make run` continua usando o launcher com validação do `.venv` Python 3.11. `make run-cloud` usa o launcher portátil.

## Dependências do runtime web

`requirements.txt` instala o perfil cloud-ready com:

- runtime Streamlit/base;
- CrewAI para as rotas multiagente;
- dependências de inferência/XAI ML.

As dependências de DeepEval e treinamento FLAML continuam separadas do fluxo web e ficam em `requirements-evals.txt`/workflow explícito de treinamento.

## Arquivos necessários no repositório

O deploy precisa incluir:

- `app.py`;
- `src/` e `src/agents/prompts/`;
- `config/`;
- `data_bd/`;
- `documents_rag/`;
- `requirements*.txt`;
- `.streamlit/config.toml`.

Não inclua `.env`, `state/`, `logs/`, `.dify/`, `.flaml/`, `.venv/` ou artefatos locais ignorados.

## Estado e persistência

Por padrão, o app usa `state/` e `logs/` relativos ao projeto. Em cloud, configure diretórios graváveis com:

```env
SKILLGRAPH_STATE_DIR=/tmp/skillgraph-state
OBSERVABILITY_LOG_PATH=/tmp/skillgraph-observability.jsonl
```

Esses caminhos são adequados para iniciar o processo, mas não são persistência durável entre reinícios. PostgreSQL, volume persistente ou storage externo serão tratados em uma etapa posterior.

## Artefato ML

O app inicia sem `.ml_artifacts/skillgraph_competency_tracks.pkl`, mas a área Machine Learning informará que o modelo não foi preparado. Para habilitar ML no deploy, forneça o artefato por um mecanismo de build/storage apropriado e configure `SKILLGRAPH_ML_ARTIFACT` quando ele estiver fora do caminho padrão.

## Health check

O Streamlit expõe:

```text
/_stcore/health
```

Teste um endereço publicado com:

```bash
python scripts/cloud-smoke-test.py https://seu-endereco.example
```

## Limitações ainda fora desta etapa

Os endpoints padrão locais não funcionam em cloud:

- `DIFY_API_BASE_URL=http://localhost`;
- `LM_STUDIO_*` apontando para `127.0.0.1`;
- JEV local, se configurado;
- Langfuse/Slack sem URLs e secrets externos.

Esses providers serão tratados no Problema 2. A interface pode iniciar sem eles, mas rotas que dependem de um provider externo continuarão exibindo diagnóstico até receberem uma configuração acessível.
