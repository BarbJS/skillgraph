# Corpus do RAG — registro de preparação

## Versão do corpus

`skillgraph-rag-v0.1`

## Documentos incluídos

- `politica_treinamentos.md` — versão 2.1
- `descricoes_cargos.md` — versão 3.0
- `manual_trilhas.md` — versão 1.5
- `faq_desenvolvimento.md` — versão 1.2

O corpus utilizado pelo RAG está em `documents_rag/`; os materiais orientativos originais não fazem parte do repositório final.

## Alterações aplicadas

- Correção de artefatos de codificação gerados na extração/conversão do texto.
- Normalização de caracteres acentuados e palavras quebradas por hífens indevidos.
- Preservação da hierarquia de títulos, listas, tabelas, IDs de cargos, números, datas e regras de negócio.
- Padronização dos nomes dos arquivos para manter as referências cruzadas entre documentos.
- Inclusão de notas de autoridade: política e descrições de cargos são fontes formais; manual e FAQ orientam, mas não substituem as fontes normativas.
- Inclusão de limites explícitos: dados individuais e indicadores dependem das tabelas estruturadas e das permissões do usuário, não do texto documental.

## Validações realizadas

- Os quatro arquivos estão codificados em UTF-8.
- Não foram encontrados os marcadores de corrupção `¬`, `£`, `¢`, `¡`, `©`, `¥` ou soft hyphen nas cópias finais.
- As relações citadas nos documentos foram preservadas.
- A política continua sendo a fonte normativa para regras de elegibilidade, carga horária, reembolso e prazos.
- O FAQ continua funcionando como guia resumido e aponta para os documentos normativos quando aplicável.

## Decisões para a indexação

- Indexar os quatro documentos como documentos separados para preservar as fontes nas respostas.
- Usar o modelo de embedding local `text-embedding-nomic-embed-text-v1.5`, com 768 dimensões.
- Começar com indexação de alta qualidade e recuperação vetorial.
- Registrar no experimento o tamanho de chunk, overlap, Top K e threshold utilizados.
- Não indexar CSVs, scripts, prompts internos ou PDFs de planejamento como conhecimento corporativo do usuário.

## Revisão semântica v0.1.1

- As quatro cópias foram revisadas novamente para remover artefatos residuais de encoding e palavras divididas.
- A política foi marcada como referência normativa para elegibilidade, carga horária, custos, reembolso e prazos.
- As descrições de cargos foram marcadas como referência para requisitos, níveis, faixas salariais por cargo e carreira.
- O manual passou a explicitar que trilhas são recomendações sujeitas a validação humana.
- O FAQ passou a indicar que é um resumo operacional e que dados individuais/indicadores dependem das fontes estruturadas autorizadas.
- Nenhuma nova regra, curso, cargo, pessoa ou número foi inventado; foram apenas acrescentadas frases-resumo que repetem valores já presentes nas tabelas para facilitar a recuperação.

## Pendências conhecidas

- Confirmar na interface do Dify a qualidade da recuperação após a indexação.
- Decidir o tamanho final de chunks com base no conjunto de perguntas de avaliação.
- Revisar a qualidade das fontes, do Top K e do streaming no Chatflow único do Dify.
- Revisar eventuais contradições de negócio encontradas durante os testes, sem alterar regras automaticamente.
