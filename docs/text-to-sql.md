# Consultas em linguagem natural sobre dados estruturados

Na Etapa 1, o SkillGraph não executa SQL livre gerado por LLM. O fluxo seguro é:

```text
pergunta em linguagem natural
→ roteador determinístico de intenção
→ função SQL read-only allowlisted
→ DuckDB
→ tabela e explicação
```

Exemplos para a demonstração:

- `Quais competências têm mais lacunas?`
- `Quais treinamentos estão disponíveis?`

O usuário não precisa conhecer SQL. As consultas permitidas são implementadas em `src/sql_tools.py`, aceitam somente leitura e bloqueiam INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/COPY/ATTACH.

### Limitação importante

Os dados atuais não possuem uma tabela mestre confiável que relacione cada funcionário a um departamento. Por isso, o sistema não inventa um indicador “por departamento” usando o dataset reservado para a Etapa 2. Essa relação poderá ser adicionada em uma etapa posterior com uma fonte estruturada documentada.

### Evolução futura

Um Text-to-SQL completo poderá ser avaliado depois com geração por LLM, parser de AST, allowlist de tabelas/colunas, somente SELECT, limites e validação antes da execução. Essa complexidade não é necessária para a demonstração segura da Etapa 1.
