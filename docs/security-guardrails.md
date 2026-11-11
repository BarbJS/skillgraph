# Segurança e guardrails

## Decisão sobre LLM Guard

O SkillGraph avaliou o LLM Guard como uma camada adicional para prompt injection, jailbreak, PII, secrets e toxicidade. A integração foi testada, mas não foi mantida no ambiente oficial porque as dependências transitivas do LLM Guard entraram em conflito com os pins do CrewAI, DeepEval e do stack de Machine Learning. Os conflitos incluíram `json-repair`, `click`, `numpy`, `regex` e componentes do spaCy.

Para não comprometer o runtime principal, o LLM Guard foi removido do código, dos requisitos e do ambiente de execução. A aplicação não depende dele para iniciar ou processar requisições.

## Camada atualmente utilizada

A proteção atual usa defesa em profundidade:

- `src/security.py`: bloqueia PII, prompt injection, jailbreak, secrets, toxicidade, SQL destrutivo e decisões trabalhistas;
- `src/agents/guardrails.py`: valida entradas/saídas de agentes, limite de tamanho, PII, decisões fora do escopo e vazamento de instruções;
- `src/privacy.py`: redige PII e secrets antes de chamadas externas e observabilidade;
- `src/output_security.py`: gate central fail-closed para respostas antes de exibição/persistência;
- `src/toxicity.py`: filtro determinístico e avaliação live opcional via DeepEval;
- allowlist de ferramentas e DuckDB read-only;
- Pydantic para contratos estruturados;
- Golden Dataset com cinco casos sintéticos adicionais de injection, jailbreak, PII/exfiltração, secrets e toxicidade;
- DeepEval separado para qualidade semântica, não para bloqueio online.

## Limitações declaradas

Esses mecanismos reduzem riscos conhecidos, mas não garantem segurança absoluta contra ataques novos, codificação adversarial, conteúdo em documentos ou falhas de provedores. A operação deve manter revisão humana, logs sanitizados, testes de regressão e atualização periódica dos casos de segurança.

Uma futura adoção do LLM Guard deverá ocorrer em ambiente isolado ou após validação de uma combinação de versões compatível com o ambiente oficial.
