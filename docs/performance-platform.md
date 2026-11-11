# Performance e configuração de plataforma

## O que é medido

Use o benchmark local para medir processos limpos:

```bash
.venv/bin/python scripts/benchmark-performance.py --runs 3
.venv/bin/python scripts/benchmark-performance.py --runs 3 --streamlit
```

O resultado contém somente:

- tempo total do processo em milissegundos;
- pico de RSS em megabytes;
- código de saída;
- final do stderr para diagnóstico técnico.

O benchmark não imprime variáveis de ambiente, prompts, respostas, currículo, conteúdo de banco ou tokens.

`resource.getrusage` mede o processo filho. Em macOS, o valor de `ru_maxrss` é convertido de bytes para MB; em Linux, de KB para MB.

## Antes/depois

Na medição local atual de três processos limpos, o import do app ficou em aproximadamente **961 ms de mediana** e **154,3 MB de pico RSS**. Esse valor é uma referência pós-otimizações anteriores, não uma comparação histórica completa da Fase 3. Execute o mesmo comando antes e depois de novas alterações e compare medianas.

A medição varia com cache do sistema operacional, CPU, versão de Python, imagem base e processo de suspensão da plataforma. Uma execução local não representa sozinha o cold start de produção.

## Perfis de dependências

- `requirements.txt`: runtime base da aplicação.
- `requirements-ml.txt`: inferência/XAI e treinamento O*NET/FLAML.
- `requirements-crewai.txt`: runtime multiagente opcional.
- `requirements-evals.txt`: DeepEval e avaliação explícita.
- `requirements-dev.txt`: todos os grupos acima mais ferramentas de teste/lint.

Produção deve instalar apenas os grupos necessários para o serviço implantado. O chat base não precisa instalar DeepEval ou FLAML. Se o perfil implantado habilitar CrewAI ou Machine Learning, instale os grupos correspondentes.

## Recomendações de plataforma

1. Fixar Python 3.11 e usar cache de dependências/build.
2. Configurar health check para `/_stcore/health` ou o mecanismo equivalente do provedor.
3. Definir timeout de startup maior que o pior caso de instalação/importação da imagem.
4. Separar o serviço web do treinamento O*NET/FLAML e das avaliações DeepEval.
5. Se cold start for requisito de produto, manter uma instância mínima ativa. Isso reduz suspensões, mas aumenta custo contínuo.
6. Se custo for prioritário, aceitar cold starts e manter a imagem mínima, usando cache de build e imports lazy.
7. Não usar arquivos SQLite/logs locais como armazenamento durável em múltiplas réplicas; usar volume persistente ou serviço externo conforme o ambiente.
8. Não provisionar serviços externos automaticamente: a escolha de instância mínima, autoscaling, volume e observabilidade depende do provedor e do orçamento.
