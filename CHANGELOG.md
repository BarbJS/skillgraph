# Changelog

Todas as mudanças relevantes do SkillGraph são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) e o projeto usa [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Adicionado

- Execução live do Golden Dataset pela interface, percorrendo os 25 casos pelo runtime atual antes dos 12 casos RAG.
- Progresso separado para os casos Golden live e RAG live, com registro de erros de configuração ou provider sem aprová-los automaticamente.
- Diagnóstico detalhado por caso RAG, incluindo pergunta, resposta avaliada, `ground_truth`, contextos de referência, fontes recuperadas e estado de cada métrica.
- Validação dos contratos dos datasets determinístico, multiagente e RAG, com testes para IDs, campos obrigatórios, respostas, contextos e fontes da verdade.

### Corrigido

- Conversão de schemas estruturados do DeepEval para o formato aceito pelo endpoint nativo do Gemini.
- Tratamento de scores zero, scores ausentes e erros das métricas RAG no relatório e na interface.
- Remoção do adapter de embeddings que não era utilizado pelo fluxo de Evals.
- Separação explícita entre a avaliação offline rápida e a execução live com serviços externos.

### Limitações registradas

- A integração JEV/TypeSafe para classificação de competências, níveis e senioridade funciona no desenvolvimento local, mas permanece indisponível ou bloqueada em produção até a conclusão da investigação de compatibilidade entre ambientes.
- Ainda são necessários testes independentes de AppSec, infraestrutura, Red Team e segurança específica de IA antes de qualquer uso produtivo plenamente validado.

### A fazer

- Consolidar o próximo ciclo de melhorias após a validação do milestone `v0.3.0`.
- Diagnosticar e corrigir a indisponibilidade produtiva do JEV com currículo sintético, observabilidade sem PII e teste ponta a ponta.
- Executar avaliações adversariais independentes de segurança convencional e de segurança de IA, incorporando correções e retestes ao Golden Dataset.

## [0.3.0] - 2026-10-07

### Adicionado

- Runtime oficial unificado em Python 3.11 dentro de `.venv`.
- Orquestração condicional por rota com Core Router e especialistas de menor privilégio.
- Fluxo de currículo com PyMuPDF/OCR, JEV, perfil estruturado e síntese revisada.
- Reasoning estruturado público e seguro na interface.
- Resultado estruturado de currículo com competências, níveis, confiança e evidências.
- Busca de conversas na sidebar.
- Sugestões clicáveis de perguntas.
- Aviso de privacidade e aviso de duração no upload de PDF.
- Painel de erro técnico sanitizado com Trace ID.
- Visão do gestor com KPIs, filtros, lacunas críticas/comuns, indicadores de treinamentos e evolução temporal.
- Painel XAI técnico para o perfil desenvolvedor com métricas de validação/teste, incerteza e status de explicabilidade.
- Base de CI/CD, pre-commit, changelog e release automatizado.

### Corrigido

- Incompatibilidade operacional entre o ambiente principal e o CrewAI.
- Dependência de tool calling do modelo local para a chamada JEV.
- Perda de contexto estruturado entre Resume Interpreter, Profile, Reviewer e Synthesizer.
- Exibição de níveis ausentes como zero artificial.
- Exposição de detalhes técnicos do JEV na resposta final do usuário.

### Segurança

- Currículos continuam temporários e sanitizados antes de integrações externas.
- Logs, traces e alertas não devem conter currículo bruto, PII, prompts privados ou segredos.
- Indicadores gerenciais permanecem agregados e sintéticos.

[Unreleased]: https://github.com/BarbJS/skillgraph/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/BarbJS/skillgraph/releases/tag/v0.3.0
