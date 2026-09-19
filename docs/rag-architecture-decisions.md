# Decisões de arquitetura RAG

## Dify e Weaviate

O SkillGraph utiliza um único caminho de RAG: **Dify Chatflow + armazenamento vetorial gerenciado pelo Dify (Weaviate nesta instalação local) + LM Studio**.

- **Dify:** orquestração visual, Chatflow publicado, recuperação e API.
- **Weaviate:** armazenamento vetorial usado internamente pelo Dify para recuperar os trechos relevantes.
- **LM Studio:** servidor local do modelo de chat e do modelo de embeddings.
- **Streamlit:** interface que consome o streaming e apresenta a resposta e suas fontes.

A decisão de usar o armazenamento vetorial nativo do Dify evita duplicar a recuperação em duas bases e mantém a pipeline mais simples. Em uma evolução de produção, essa abordagem também concentra configuração, indexação, observabilidade operacional e governança em um único fluxo de RAG.

## Área técnica do desenvolvedor

O perfil Desenvolvedor pode consultar a configuração e o comportamento do Chatflow principal por meio da área de observabilidade. Gestor e RH não precisam conhecer detalhes internos de chunking, embeddings ou armazenamento vetorial para utilizar o SkillGraph.

A evolução do corpus deve ser avaliada no próprio Dify com perguntas fixas, conferência de fontes, latência e taxa de ausência de evidência antes de promover mudanças ao fluxo publicado.

## Recomendações futuras

- Entrada por voz: avaliar Web Speech API ou faster-whisper depois da entrega.
- Busca híbrida: combinar similaridade semântica com BM25 para IDs, termos e nomes exatos dentro da estratégia suportada pelo Dify.
- Reranker: avaliar depois de medir falhas de precisão.
- Autenticação real e autorização por perfil antes de qualquer deploy público.
