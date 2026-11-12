# Plano — Streamlit Cloud + Dify Cloud + Gemini

## Objetivo
Publicar uma versão pública e funcional do SkillGraph no Streamlit Community Cloud, usando Dify Cloud para RAG e Gemini como modelo conversacional único para Dify, CrewAI quando habilitado e síntese final.

## Premissas

- O Streamlit será o único app publicado diretamente.
- Dify Cloud terá uma nova Knowledge Base e Chatflow.
- Os documentos de `documents_rag/` serão reprocessados no Dify Cloud.
- O modelo de chat será Gemini (`gemini-3.8-flash`), tanto no nó LLM do Chatflow Dify Cloud quanto na síntese final do aplicativo, quando habilitada.
- O modelo de embeddings será um provider Google/Gemini disponível no Dify Cloud; se o modelo desejado não aparecer, escolher um provider compatível e documentar a decisão.
- LM Studio fica fora da primeira publicação cloud.
- CrewAI começa desativado até validarmos a compatibilidade do Gemini com CrewAI e seus prompts/tools.
- Persistência local e artefato ML serão tratados como limitações/etapas posteriores se o Streamlit Cloud não os preservar.

## Sequência

1. **Validar Dify Cloud**
   - Criar/configurar provider Gemini com o modelo `gemini-3.8-flash`.
   - Criar Knowledge Base.
   - Reenviar os quatro documentos do corpus.
   - Configurar parent/child chunking conforme `config/dify-chatflow-reference.json`.
   - Selecionar embedding provider/modelo.
   - Criar/publicar Chatflow.
   - Testar recuperação e fontes com perguntas do Golden Dataset.

2. **Validar Gemini como LLM único**
   - Testar geração no Dify.
   - Configurar `GEMINI_API_KEY` e `GEMINI_MODEL=gemini-3.8-flash` para síntese final do SkillGraph.
   - Fazer um teste separado de CrewAI com Gemini, sem ativá-lo publicamente ainda.
   - Se CrewAI exigir parâmetros/modelo incompatíveis, manter CrewAI desativado e registrar como próximo passo.

3. **Preparar configuração cloud**
   - Configurar `DIFY_API_BASE_URL`, `DIFY_API_KEY` e `DIFY_USER_ID` para o Dify Cloud.
   - Configurar `GEMINI_API_KEY`, modelo, timeout e limites.
   - Configurar JEV e Langfuse somente se credenciais e endpoints forem fornecidos.
   - Manter secrets exclusivamente no painel do Streamlit Cloud.
   - Não publicar `.env`, chaves, estado, logs ou artefatos locais.

4. **Disponibilizar o artefato ML**
   - Verificar se a área ML será exigida na primeira demo.
   - Se sim, usar mecanismo compatível com o Streamlit Cloud para disponibilizar o `.pkl` ou ajustar a tela para diagnóstico claro quando ausente.
   - Não incluir artefato grande ou sensível no Git sem decisão explícita.

5. **Publicar no Streamlit Cloud**
   - Conectar `BarbJS/skillgraph`, branch `main`, arquivo `app.py`.
   - Confirmar Python 3.11 e requirements cloud-ready.
   - Adicionar Secrets.
   - Deploy inicial com `CREWAI_ENABLED=false`.
   - Validar health, inicialização e logs.

6. **Testes de aceitação públicos**
   - Abrir aplicação sem login.
   - Testar perfil e UI.
   - Testar pergunta RAG com fonte.
   - Testar consulta SQL/DuckDB.
   - Testar observabilidade local/Langfuse se habilitado.
   - Testar Gemini final synthesis.
   - Testar upload/OCR somente se o runtime suportar Tesseract.
   - Testar JEV somente com autorização e credencial.
   - Testar ML e CrewAI conforme disponibilidade dos artefatos/providers.

7. **Documentar limitações e próximos passos**
   - LM Studio local não será usado no Streamlit Cloud.
   - SQLite/logs/caches não são persistência durável.
   - CrewAI pode permanecer desativado inicialmente.
   - Artefato ML pode exigir storage/build separado.
   - Registrar essas limitações no relatório, sem apresentar a demo como arquitetura empresarial completa.

## Critério de sucesso

A URL pública deve responder e permitir uma demonstração real de UI, consultas locais, RAG via Dify Cloud e síntese via Gemini, com secrets fora do repositório e diagnóstico claro para funcionalidades ainda não habilitadas.
