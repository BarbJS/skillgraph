# Relatório técnico — Etapa 2 do SkillGraph

## 1. Visão geral das mudanças

A Etapa 2 amplia a base conversacional construída na Etapa 1 com uma camada de Machine Learning, um sistema multiagente, análise de currículos em PDF, OCR, integração com JEV, explicabilidade, observabilidade e avaliação automatizada. O objetivo deixou de ser apenas responder perguntas sobre políticas e treinamentos: agora o SkillGraph também apoia a identificação de competências e a recomendação de trilhas de desenvolvimento para colaboradores descritos por analistas ou gestores de RH.

A etapa foi integrada à aplicação Streamlit existente, preservando as rotas de RAG via Dify/Weaviate e consultas read-only via DuckDB. O usuário continua interagindo por linguagem natural, mas cada solicitação é encaminhada para a camada apropriada. Também foram adicionadas melhorias para o perfil Desenvolvedor, para a Visão do gestor, para privacidade, para o acompanhamento de traces e para a avaliação de qualidade.

## 2. Machine Learning, dataset e relação com o domínio

O modelo foi treinado com FLAML usando o **O*NET 31.0 Database**, fonte pública do U.S. Department of Labor, licenciada sob Creative Commons Attribution 4.0 International. A fonte não contém funcionários da NexaTech. Ela descreve ocupações, habilidades e atividades profissionais. Por isso, a conexão com o domínio do SkillGraph é uma analogia controlada: referências ocupacionais públicas são transformadas em trilhas de desenvolvimento técnico para apoiar conversas de aprendizagem, sem classificar pessoas como aptas ou inaptas.

A execução local registrada produziu 24 ocupações tecnológicas e 35 features, organizadas em seis trilhas: Desenvolvimento de Software, Dados e Ciência de Dados, Engenharia de Dados e Cloud, Cibersegurança, IA e Machine Learning e Tecnologia e Sistemas. A variável alvo é `track`, criada pelo projeto a partir de regras explícitas de títulos ocupacionais. Os arquivos usados incluem `occupation_data.csv`, `essential_skills.csv` e `transferable_skills.csv`. Essa transformação não é um rótulo oficial do O*NET; é uma camada de adaptação ao problema acadêmico da NexaTech.

O pipeline usa seed 42 e separa os dados em 70% para treino, 20% para validação e 10% para teste. A imputação e a padronização são ajustadas no treino e aplicadas aos demais conjuntos. Foram comparados um `DummyClassifier`, Random Forest e LightGBM por FLAML. O LightGBM foi selecionado na validação.

A métrica principal é o **Macro F1**, porque as seis trilhas precisam ser consideradas de forma equilibrada mesmo quando há classes com menos ocupações. A balanced accuracy complementa a análise em cenários desbalanceados. Precision e recall macro ajudam a observar falsos positivos e cobertura. Top-2 Accuracy é útil porque duas trilhas próximas podem ser alternativas plausíveis para uma conversa de desenvolvimento. ROC-AUC só é exibida quando há suporte matemático suficiente.

Na execução registrada, o LightGBM obteve Macro F1 de aproximadamente 0,78 na validação, mas 0,10 no teste; balanced accuracy caiu de aproximadamente 0,83 para 0,25. Esse resultado é uma limitação importante: o conjunto é pequeno e não sustenta uma afirmação de prontidão produtiva. A recomendação é usada como apoio exploratório, sempre com revisão humana.

A integração ocorre na aba Machine Learning. O usuário descreve um colaborador em linguagem natural; o LM Studio estrutura competências e níveis em JSON; o backend valida PII e níveis de 0 a 5, carrega o PKL, calcula até três trilhas e devolve prioridades, competências reconhecidas, competências desconhecidas e incerteza. O LLM recebe apenas o resultado calculado para produzir a explicação final.

## 3. Sistema multiagente e integração com as camadas existentes

O CrewAI é o orquestrador local, enquanto o LM Studio fornece o modelo. O Core Router permanece como agente obrigatório e confirma a rota candidata. Especialistas são ativados de forma condicional:

- **Resume Interpreter:** interpreta currículo sanitizado e resultado estruturado do JEV;
- **Profile Normalizer:** preserva evidências, normaliza nomes e remove PII;
- **Prediction Specialist:** utiliza PKL/XAI para recomendar trilhas;
- **Gap Analyst:** interpreta prioridades e lacunas;
- **Learning Path Agent:** consulta o catálogo DuckDB read-only;
- **Policy Specialist:** consulta o Chatflow Dify e preserva fontes;
- **Structured Data Specialist:** consulta dados agregados autorizados;
- **Safety Reviewer:** verifica schema, PII, escopo e evidência;
- **Response Synthesizer:** transforma os handoffs revisados em resposta contextualizada.

O fluxo de currículo combina PyMuPDF, OCR local, JEV e agentes. O JEV é chamado diretamente pelo backend, porque o modelo local não apresentou tool calling confiável em todos os cenários. O resultado JEV é entregue como sinal estruturado ao Resume Interpreter; o texto sanitizado é usado para extrair todas as competências e seus níveis. Essa decisão mantém a ferramenta real integrada sem tornar a análise dependente de um protocolo instável do modelo.

Cada rota recebe somente as ferramentas necessárias. A rota de predição usa PKL/XAI; a rota de treinamentos usa DuckDB; a rota de política usa Dify. O resultado passa por Reviewer e Synthesizer, que produzem linguagem natural para o usuário.

## 4. PDF, OCR e JEV

O upload ocorre no chat principal. O arquivo é validado como PDF e possui limite de tamanho. PyMuPDF extrai texto quando possível; PDFs escaneados usam Tesseract por meio de OCR local. O arquivo temporário é descartado depois da extração.

Antes de enviar dados ao JEV, o backend redige CPF, RG, e-mail, telefone e padrões identificáveis. O JEV recebe um estado transitório com texto sanitizado e perguntas específicas sobre experiência, profundidade, mentoria, LLM, open source, perfil e progressão. Esses sinais complementam a extração, mas não substituem a leitura completa do currículo nem aparecem como seção técnica na resposta final ao usuário.

## 5. XAI e explicabilidade

A recomendação retorna trilhas, compatibilidade estimada, prioridades, competências reconhecidas, desconhecidas e uma margem de incerteza entre as primeiras alternativas. Para o perfil Desenvolvedor, a interface apresenta métricas de validação/teste, qualidade da entrada, cobertura, explicações locais e importância global quando o estimador oferece suporte. Quando SHAP ou feature importance não está disponível, o sistema declara essa limitação em vez de inventar explicações.

SHAP e importâncias de árvore representam associação preditiva, não causalidade. Fairness entre grupos protegidos não é afirmada sem atributos autorizados e consentidos. Essa separação impede que uma recomendação de trilha seja confundida com avaliação de desempenho ou decisão de carreira.

## 6. Langfuse, traces e observabilidade

A Etapa 2 ampliou o tracing da Etapa 1 com `TraceContext` e `SpanContext`. As execuções registram rota, status, latência total, spans, serviços, tarefas/agentes, tokens de entrada/saída, custo e erros. A integração Langfuse é opcional e pode ser ativada apenas em uma demonstração controlada, sem commitar credenciais.

O painel do perfil Desenvolvedor mostra os dez traces mais recentes, cada um com Trace ID, timestamp, rota, status, duração, quantidade de spans, tokens e custo. O usuário técnico pode selecionar um Trace ID e consultar os spans sanitizados para rastrear OCR, JEV, CrewAI, Dify, DuckDB ou outras etapas. Currículo, prompts, respostas completas, PII e tokens secretos não são enviados ao Langfuse.

Quando a execução é local e não há preço de API, o custo é registrado como zero local/não tarifado. Quando o provedor não informa tokens, essa indisponibilidade deve permanecer explícita, sem fabricar consumo. O dashboard também apresenta métricas por serviço, tarefas, erros e timeouts.

## 7. Golden Dataset e DeepEval

O Golden Dataset principal possui 25 casos sintéticos, cobrindo RAG, SQL, competência, segurança, PII, prompt injection, smalltalk, ambiguidade, ausência de evidência, ML, lacunas, treinamentos, política, multi-turno e fora de escopo. O arquivo `evals/rag_goldens.jsonl` complementa a avaliação semântica com perguntas, respostas, contextos e ground truth. Cenários compostos de agentes são registrados separadamente em `evals/agent_goldens.jsonl`.

A avaliação offline verifica schema, rota, bloqueio e contratos. A avaliação live usa DeepEval como LLM-as-a-judge e mede Faithfulness, Answer Relevancy, Contextual Precision e Contextual Recall. Faithfulness verifica apoio no contexto; Answer Relevancy verifica aderência à pergunta; Precision avalia a ordenação dos contextos; Recall verifica suficiência da evidência.

Os resultados locais disponíveis mostraram scores altos nos cinco casos RAG avaliados, mas esse resultado deve ser interpretado com cautela: o subconjunto é pequeno e o judge usa o próprio modelo local. O relatório estruturado registra médias, mediana, mínimo, máximo, pass rate, weaknesses e recomendações. Uma weakness de relevancy ou recall pode indicar necessidade de ajustar chunking, Top K, prompt, fontes ou roteamento.

## 8. Melhorias complementares

A Visão do gestor ganhou cards executivos, indicadores de lacunas críticas/comuns, métricas de treinamentos, filtros por categoria/competência/modalidade, gráficos de aprovação e reprovação e evolução temporal mensal. Todos os indicadores são agregados e sintéticos; não há inferência por departamento ou gestor porque não existe tabela-mestre organizacional autorizada.

A experiência do usuário recebeu busca de conversas, títulos específicos por rota, sugestões clicáveis na sidebar, aviso de privacidade no upload, aviso de duração de até cinco minutos, painel de progresso e painel de erro técnico seguro com Trace ID. O perfil Desenvolvedor recebeu áreas específicas para Machine Learning, Observabilidade e Qualidade/Evals.

Também foram adicionados Python 3.11 como runtime oficial único, pre-commit, Black, Ruff, CI/CD, Dependabot, `VERSION`, `CHANGELOG.md`, testes adicionais e separação modular para OCR, privacidade, progresso, erros, reasoning, XAI e componentes de UI.

## 9. Limitações e conclusão

A Etapa 2 é uma extensão funcional da Etapa 1, mas continua sendo um protótipo acadêmico. O dataset O*NET filtrado é pequeno, o teste ML é inferior à validação, as trilhas são uma transformação do projeto, fairness não é avaliável sem atributos autorizados, Langfuse depende de configuração externa e DeepEval live avalia um subconjunto controlado. Essas limitações são apresentadas como parte da análise crítica.

A integração final combina ML, agentes, OCR, JEV, RAG, DuckDB, explicabilidade, observabilidade e avaliação em uma única interface Streamlit. Com `CREWAI_ENABLED=true`, as perguntas normais de treinamentos e políticas do chat principal passam pelo runtime multiagente; quando a flag está desativada, o fallback legado de RAG/SQL permanece disponível. A solução demonstra como uma arquitetura modular pode apoiar desenvolvimento profissional sem automatizar decisões de emprego. A Etapa 3 permanece fora do escopo desta entrega.
