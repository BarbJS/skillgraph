# Integração LLM → recomendador de competências

A aba Machine Learning atende analistas e gestores de RH que descrevem um **colaborador**, não a si próprios.

```text
Descrição não identificadora do colaborador
  ↓
LM Studio extrai competências e níveis em JSON
  ↓
backend valida/normaliza o perfil
  ↓
backend carrega skillgraph_competency_tracks.pkl
  ↓
backend calcula trilhas Top-3 e prioridades
  ↓
LM Studio explica o resultado real
```

O LLM não treina, não abre o PKL, não consulta DuckDB/Dify e não inventa competências. O resultado é uma recomendação de desenvolvimento baseada em referências O*NET e exige revisão humana.

Perguntas adequadas:

1. “O colaborador da equipe de dados tem Python avançado, SQL intermediário e está começando em IA generativa. Qual trilha priorizar?”
2. “Quais competências o colaborador precisa desenvolver para migrar de software para Machine Learning?”
3. “O colaborador tem APIs, Docker e bancos de dados, mas pouca experiência em cloud. Qual próximo passo?”
4. “Quais competências de IA generativa devemos priorizar para um colaborador que atua com produtos digitais?”
5. “O colaborador tem análise de dados e SQL intermediários. Qual trilha de aprendizagem é mais compatível?”

A resposta deve conter trilhas compatíveis, competências reconhecidas, competências não reconhecidas, prioridades de desenvolvimento e uma indicação simples de incerteza quando as trilhas estiverem próximas. SHAP e gráficos técnicos ficam restritos ao perfil desenvolvedor; o LLM recebe apenas o JSON calculado pelo backend.

Não é necessário alterar o system prompt do Chatflow Dify. A rota ML usa o LM Studio local diretamente e permanece separada do RAG e do DuckDB.
