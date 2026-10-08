# XAI da Etapa 2

A explicabilidade combina:

- SHAP TreeExplainer para modelos de árvore quando compatível;
- comparação do perfil do colaborador com o perfil mediano da trilha;
- lista explícita de competências reconhecidas e não reconhecidas;
- prioridades e lacunas;
- margem entre a primeira e a segunda trilha como sinal simples de incerteza.

RH e gestores recebem linguagem simples. O perfil desenvolvedor recebe o painel técnico com métricas reais de validação/teste, cobertura das competências de entrada, incerteza, importância global e contribuições locais quando o estimador fornecer suporte. Quando SHAP/importância não estiver disponível, o painel declara o motivo e não inventa contribuições. SHAP explica associação do modelo, não causalidade. Fairness entre grupos protegidos não é afirmada sem atributos autorizados. O Microsoft Responsible AI Toolbox é uma possibilidade futura para análise de erros; Alibi não será usado.
