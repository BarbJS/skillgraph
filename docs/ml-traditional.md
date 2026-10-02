# Etapa 2 — Machine Learning de competências com FLAML

## Objetivo

A área de ML responde a esta pergunta:

> Dado o conjunto de competências de um colaborador informado por um analista ou gestor de RH, quais trilhas técnicas são mais compatíveis e quais competências devem ser priorizadas para desenvolvimento na era da IA generativa?

O problema é **classificação multiclasse de trilhas tech**. O modelo não classifica uma pessoa como boa ou ruim e não decide contratação, promoção, remuneração, punição ou desligamento. Ele apoia uma conversa de desenvolvimento sobre um colaborador descrito sem identificadores pessoais.

## Fonte

Usamos exclusivamente o **O*NET 31.0 Database**, mantido pelo U.S. Department of Labor:

- Fonte: <https://www.onetcenter.org/database.html>
- Download: <https://www.onetcenter.org/dl_files/database/db_31_0_csv.zip>
- Licença: Creative Commons Attribution 4.0 International (CC BY 4.0)
- Atribuição: O*NET 31.0 Database, U.S. Department of Labor

A implementação agrupa ocupações tech por regras de título explícitas em trilhas de desenvolvimento e agrega níveis dos arquivos de Skills, Essential Skills e Transferable Skills. Essa é uma transformação do projeto, registrada no artefato e no relatório; não é um novo rótulo oficial do O*NET.

O O*NET não contém histórico individual de colaboradores. O perfil de um colaborador é fornecido na interação pelo analista/gestor e comparado às referências públicas de ocupações. IA generativa é indicada como competência complementar quando informada, mas não é apresentada como competência oficial O*NET quando não aparece na fonte.

## Workflow

1. Baixar e validar o arquivo oficial O*NET em `.ml_artifacts/onet/`.
2. Selecionar ocupações tech e criar a matriz ocupação × competência.
3. Fazer análise de cobertura, classes e valores ausentes antes de transformar.
4. Dividir em 70% treino, 20% validação e 10% teste com `seed=42`.
5. Ajustar somente no treino a imputação e a padronização.
6. Comparar baseline `DummyClassifier`, Random Forest FLAML e LightGBM FLAML.
7. Usar Macro F1 como métrica principal, com balanced accuracy, precisão/recall macro, Top-2 accuracy, matriz de confusão e ROC-AUC OvR quando aplicável.
8. Fazer fine-tuning do vencedor sem consultar o teste.
9. Reajustar em treino+validação e avaliar uma única vez no teste.
10. Salvar `.ml_artifacts/skillgraph_competency_tracks.pkl` com modelo, pré-processador, classes, catálogo, perfis de trilha, licença, versão e métricas.

## Execução

```bash
source .venv/bin/activate
make bootstrap-flaml
make train-ml
streamlit run app.py
```

A aba é acessível aos três perfis simulados. Analistas e gestores de RH devem escrever sobre um colaborador, por exemplo: “colaborador da equipe de dados com Python avançado e SQL intermediário”. Não informe nome, CPF, e-mail ou outro identificador.

## Perguntas de exemplo

Analistas e gestores podem perguntar:

- “O colaborador da equipe de dados tem Python avançado e SQL intermediário. Qual trilha priorizar?”
- “Quais competências o colaborador precisa desenvolver para migrar de software para Machine Learning?”
- “O colaborador tem APIs, Docker e bancos de dados, mas pouca experiência em cloud. Qual próximo passo?”
- “Quais competências de IA generativa devemos priorizar para um colaborador de produtos digitais?”
- “O colaborador tem análise de dados e SQL intermediários. Qual trilha é mais compatível?”

## Limitações

A recomendação é uma referência de compatibilidade baseada em ocupações públicas dos Estados Unidos. Ela não substitui avaliação humana, conversa com o colaborador, contexto da empresa, experiência real ou um catálogo brasileiro de competências. A saída deve ser usada para explorar trilhas e prioridades de aprendizagem, nunca para decisões laborais automatizadas.
