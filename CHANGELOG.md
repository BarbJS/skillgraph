# Changelog

Todas as mudanças relevantes do SkillGraph são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) e o projeto usa [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Unreleased]

### A fazer

- Consolidar o próximo ciclo de melhorias após a validação do milestone `v0.3.0`.

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

[Unreleased]: https://github.com/barbara.specian/skillgraph-proj/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/barbara.specian/skillgraph-proj/releases/tag/v0.3.0
