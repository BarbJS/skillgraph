# Etapa 2 — Avaliação do ML de competências

O modelo é uma classificação multiclasse de trilhas tech para colaboradores descritos por analistas e gestores de RH. O painel técnico do perfil Desenvolvedor também exibe as métricas reais de validação e teste, incluindo alerta quando há queda significativa de generalização.

## Métricas

- Macro F1: métrica principal, equilibrando as trilhas.
- Balanced accuracy: reduz o efeito de classes desiguais.
- Macro precision e macro recall: mostram falsos positivos e cobertura por trilha.
- Top-2 accuracy: útil quando trilhas próximas são alternativas plausíveis.
- Matriz de confusão: mostra confusões entre trilhas.
- ROC-AUC OvR: somente quando há suporte suficiente para todas as classes.

## Viés e fairness

O pipeline calcula métricas por trilha, suporte, precision, recall, F1 e gap máximo de recall. Fairness entre grupos protegidos só é avaliada quando atributos autorizados e consentidos existirem; não são inferidos nem usados proxies do O*NET ocupacional. Sem grupos, o relatório declara `not_evaluable_without_authorized_group_attributes` em vez de afirmar ausência de viés. Suporte insuficiente e gap acima do threshold geram alerta para revisão humana.

## Limitações

O O*NET descreve ocupações públicas e não pessoas colaboradoras. As trilhas são agrupamentos definidos no projeto e não rótulos oficiais. O perfil informado na interface não é usado para retreinar o modelo e não deve conter PII. As métricas apoiam avaliação acadêmica; não autorizam decisões laborais automatizadas.
