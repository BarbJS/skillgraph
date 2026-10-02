# Etapa 2 — Avaliação do ML de competências

O modelo é uma classificação multiclasse de trilhas tech para colaboradores descritos por analistas e gestores de RH.

## Métricas

- Macro F1: métrica principal, equilibrando as trilhas.
- Balanced accuracy: reduz o efeito de classes desiguais.
- Macro precision e macro recall: mostram falsos positivos e cobertura por trilha.
- Top-2 accuracy: útil quando trilhas próximas são alternativas plausíveis.
- Matriz de confusão: mostra confusões entre trilhas.
- ROC-AUC OvR: somente quando há suporte suficiente para todas as classes.

## Limitações

O O*NET descreve ocupações públicas e não pessoas colaboradoras. As trilhas são agrupamentos definidos no projeto e não rótulos oficiais. O perfil informado na interface não é usado para retreinar o modelo e não deve conter PII. As métricas apoiam avaliação acadêmica; não autorizam decisões laborais automatizadas.
