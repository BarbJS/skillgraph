# Configurar LM Studio como provider no Dify

## 1. Preparar o LM Studio

1. Abra o LM Studio e baixe/carregue um modelo de chat.
2. Vá à área **Developer/Local Server** e inicie o servidor.
3. Confirme a porta configurada no `.env` (`1234` por padrão).
4. Se o LM Studio oferecer uma opção semelhante a **Serve on Local Network**, habilite-a quando o container não conseguir acessar o host. Não habilite exposição pública nem encaminhamento de porta no roteador.
5. Na raiz do projeto, execute:

   ```bash
   make check
   ```

   Anote exatamente o `id` retornado em `/v1/models`. Esse valor é o nome do modelo a cadastrar no Dify; não substitua pelo nome amigável mostrado na interface.

A API compatível usa a base `http://localhost:1234/v1` no host. Dentro de um container Docker Desktop, use `http://host.docker.internal:1234/v1`.

## 2. Qual provider instalar no Dify?

Na tela mostrada, você **não deve instalar OpenAI, Anthropic, Gemini ou DeepSeek**: esses cards são providers de serviços específicos e normalmente exigem credenciais próprias. Para LM Studio, instale o plugin chamado **LM Studio**, publicado por `stvlynn`.

1. Na tela **Integrações → Fornecedor de modelo**, clique em **Instalar**.
2. Pesquise por **LM Studio**.
3. Instale o provider/plugin **LM Studio**. O pacote oficial da comunidade declara suporte a `llm` e `text-embedding`, exatamente os dois tipos que você já expôs no LM Studio.
4. Após a instalação, abra **LM Studio → Adicionar modelo**.

Se **LM Studio** não aparecer no Marketplace, use a alternativa **OpenAI-API-compatible**, caso ela esteja disponível na sua versão. Porém, na versão atual que estamos executando, o plugin dedicado LM Studio é a opção mais direta e permite cadastrar chat e embeddings no mesmo provider. Não instale um plugin aleatório sem verificar autor, permissões e suporte.

## 3. Cadastrar o modelo de chat

1. Abra `http://localhost` e faça login no workspace.
2. Acesse **Integrações → Fornecedor de modelo → LM Studio → Adicionar modelo**.
3. Selecione o tipo **LLM/Chat** e informe:
   - **Model Name/ID**: `meta-llama-3-8b-instruct`;
   - **Base URL**: `http://host.docker.internal:1234` — neste plugin dedicado, **não acrescente `/v1`**, pois o plugin acrescenta `/v1` internamente;
   - **API Key**: `lm-studio-local`;
   - **Completion mode**: `Chat`;
   - **Model context size**: informe o limite configurado para o modelo;
   - **Upper bound for max tokens**: use um valor menor ou igual ao limite do modelo, por exemplo `4096` inicialmente.
4. Salve e teste o modelo. Depois configure-o como modelo padrão do sistema se o Dify solicitar.
5. Crie um app **Chatbot** simples e faça uma pergunta curta. Isso valida Dify → container → host → LM Studio.

> O plugin dedicado valida a URL consultando `${Base URL}/v1/models` e usa internamente `${Base URL}/v1` para chat e embeddings. Por isso a URL no campo deve terminar no host/porta, e não em `/v1`.

> O Dify pode separar providers de texto, visão e ferramentas. Cadastre somente os recursos que o modelo realmente suporta.

## 4. Embeddings para RAG

RAG requer um modelo de embedding, que é diferente de um modelo de chat. Primeiro verifique se o LM Studio expõe embeddings para um modelo compatível:

```bash
curl --fail http://127.0.0.1:1234/v1/models
curl --fail http://127.0.0.1:1234/v1/embeddings \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer lm-studio-local' \
  -d '{"model":"SEU_ID_DE_EMBEDDING","input":"teste"}'
```

Substitua `SEU_ID_DE_EMBEDDING` pelo ID real. O resultado precisa conter um vetor numérico em `data[0].embedding`. Um modelo de chat que responde a `/v1/chat/completions` não é automaticamente um modelo de embedding.

Nesta máquina, o teste foi bem-sucedido com `text-embedding-nomic-embed-text-v1.5`, que retornou um vetor de 768 dimensões. O modelo de chat disponível é `meta-llama-3-8b-instruct`. Os IDs podem mudar em outra instalação; sempre confira `make check`.

No Dify, cadastre esse ID como **Text Embedding/Embedding** no provider compatível e teste antes de criar uma Knowledge Base. Se não houver suporte confiável a embeddings no LM Studio, escolha um provider de embedding local compatível com o Dify para essa parte; mantenha o chat no LM Studio e registre a decisão no projeto.

## 5. Diagnóstico

### `make check` falha

- O servidor do LM Studio não foi iniciado.
- O modelo não foi carregado.
- A porta em `.env` não coincide com a porta do servidor.
- Outro processo ocupa a porta.

### Dify não conecta, mas `make check` funciona

- No provider dedicado **LM Studio**, confirme que a URL é `http://host.docker.internal:1234`, sem `/v1`.
- O bootstrap deste projeto cria automaticamente `.dify/docker/docker-compose.override.yaml`, adicionando `host.docker.internal:host-gateway` ao `plugin_daemon`. Depois de uma alteração, execute `make up` para recriar o container.
- Confirme a resolução e o acesso de dentro do container:

  ```bash
  docker exec docker-plugin_daemon-1 getent hosts host.docker.internal
  docker exec docker-plugin_daemon-1 curl -4 -fsS http://host.docker.internal:1234/v1/models
  ```

- Em Linux nativo, confirme que o gateway `host-gateway` é suportado pelo Docker e que o LM Studio aceita conexões da rede Docker.
- Verifique `make status` e os logs do serviço responsável pelo request: `docker compose logs --tail=100 plugin_daemon` dentro de `.dify/docker`.

### Timeout ou resposta truncada

- Reduza o contexto e o número máximo de tokens no app do Dify.
- Confirme que o modelo permanece carregado no LM Studio.
- Aumente recursos de CPU/RAM do Docker Desktop e do LM Studio somente se a máquina suportar.

### O chatbot funciona, mas o RAG não

- Verifique se o modelo de embedding foi cadastrado e testado.
- Refaça a indexação da Knowledge Base depois de trocar o embedding.
- Comece com um documento pequeno e texto simples para isolar parsing, chunking e recuperação.

## 6. Crescimento do corpus e avaliação

Adicionar documentos não exige necessariamente trocar o modelo de embeddings. Continue usando o mesmo modelo quando ele representar bem o idioma e o domínio do corpus e quando as fontes recuperadas permanecerem relevantes. Ao ampliar a Knowledge Base, reindexe o conteúdo novo e repita a avaliação com um conjunto fixo de perguntas, fontes esperadas, taxa de ausência de evidência e latência.

Trocar o modelo de embeddings é uma mudança maior: como os vetores podem ter dimensões e espaços semânticos diferentes, a Knowledge Base inteira deve ser reindexada com o novo modelo. Compare o comportamento antes e depois no próprio Dify antes de atualizar o Chatflow publicado.

Altere uma configuração por vez e mantenha o Chatflow principal como referência da Etapa 1.

## 7. Diagnóstico

### `make check` falha

- O servidor local não foi iniciado.
- O modelo não foi carregado.
- A porta configurada é diferente da porta do servidor.
- Outro processo ocupa a porta.

Depois, execute novamente `make check`.

### Dify não conecta, mas `make check` funciona

- No provider dedicado **LM Studio**, confirme que a URL é `http://host.docker.internal:1234`, sem `/v1`.
- O bootstrap deste projeto cria automaticamente `.dify/docker/docker-compose.override.yaml`, adicionando `host.docker.internal:host-gateway` ao `plugin_daemon`.
- Verifique `make status` e os logs do serviço responsável pelo request.

### Timeout ou resposta truncada

- Reduza o contexto e o número máximo de tokens no app do Dify.
- Confirme que o modelo permanece carregado no LM Studio.
- Aumente recursos de CPU/RAM somente se a máquina suportar.

### O chatbot funciona, mas o RAG não

- Verifique se o modelo de embedding foi cadastrado e testado.
- Refaça a indexação da Knowledge Base depois de trocar o embedding.
- Comece com um documento pequeno e texto simples para isolar parsing, chunking e recuperação.

## 8. Configuração de produção

O Chatflow principal é o único fluxo utilizado pela aplicação. A chave fica no `.env` local e o Streamlit chama a API publicada sem enviar a credencial ao navegador.
