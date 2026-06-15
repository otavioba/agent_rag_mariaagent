# Guia dos Parametros do `.env`

Este arquivo explica, em detalhe, os parametros usados pela Maria no projeto.

A ideia aqui e te ajudar a estudar:

- o que cada parametro faz
- onde ele atua no fluxo do agent
- como ele impacta o comportamento
- quando vale a pena aumentar ou reduzir o valor

## Como pensar no `.env`

No seu projeto, o `.env` controla 5 partes principais:

1. infraestrutura
2. indexacao e vetorizacao
3. recuperacao de contexto
4. guardrails
5. modelo e embeddings

Fluxo resumido:

1. o SQLite guarda os dados da loja
2. o pipeline le as tabelas configuradas
3. os registros viram `Document`
4. os documentos sao quebrados em chunks
5. os chunks viram embeddings
6. os embeddings sao salvos no Chroma
7. na pergunta, a Maria usa SQL, busca vetorial, ou os dois

## 1. Infraestrutura

### `APP_ENV`

Valor atual:

```env
APP_ENV=development
```

O que faz:

- identifica o ambiente da aplicacao
- hoje ele funciona mais como marcador do ambiente do que como uma chave de comportamento

Quando mudar:

- `development`: estudo e desenvolvimento local
- `staging`: ambiente de homologacao
- `production`: ambiente real

Exemplo pratico:

- se no futuro voce quiser logs mais detalhados em desenvolvimento e mais restritos em producao, esse parametro sera a base dessa decisao

### `SQLITE_PATH`

Valor atual:

```env
SQLITE_PATH=./data/maria_agent.db
```

O que faz:

- define onde fica o banco SQLite
- esse e o banco fonte de verdade da operacao

Esse parametro impacta:

- criacao do schema
- carga dos dados
- consultas SQL do agent
- leitura para indexacao vetorial

Exemplo pratico:

```env
SQLITE_PATH=./data/maria_agent_teste.db
```

Resultado:

- a Maria passa a usar outro banco local
- isso e util se voce quiser um banco so para teste e outro para experimento

### `VECTOR_DB_DIR`

Valor atual:

```env
VECTOR_DB_DIR=./storage/chroma
```

O que faz:

- define a pasta onde o Chroma salva o banco vetorial

Exemplo pratico:

```env
VECTOR_DB_DIR=./storage/chroma_experimento_1
```

Resultado:

- voce cria um indice vetorial separado
- isso e util para comparar configuracoes de chunk ou embeddings sem sobrescrever o indice anterior

### `VECTOR_COLLECTION_NAME`

Valor atual:

```env
VECTOR_COLLECTION_NAME=maria_rag_collection
```

O que faz:

- define o nome da colecao dentro do Chroma

Exemplo pratico:

```env
VECTOR_COLLECTION_NAME=maria_autopecas_v2
```

Resultado:

- permite separar versoes logicas do indice mesmo usando o mesmo backend vetorial

## 2. Tabelas e indexacao

### `SOURCE_TABLES`

Valor atual:

```env
SOURCE_TABLES=product_catalog,sales,employees,absenteeism_events
```

O que faz:

- define quais tabelas entram no processo de indexacao vetorial

Importante:

- se uma tabela nao estiver aqui, ela nao entra na busca semantica
- ela ainda pode ser consultada por SQL se existir no banco

Exemplo pratico:

```env
SOURCE_TABLES=product_catalog,employees,absenteeism_events
```

Resultado:

- `sales` deixa de entrar no banco vetorial
- a Maria ainda pode consultar vendas com SQL
- a busca semantica passa a focar mais em cadastro e equipe

Quando usar:

- se voce quiser um RAG mais voltado a politicas, pessoas e operacao

### `INDEX_BATCH_SIZE`

Valor atual:

```env
INDEX_BATCH_SIZE=100
```

O que faz:

- define quantos chunks sao enviados por lote para o Chroma durante a reindexacao

O que muda:

- valor maior: tende a indexar mais rapido
- valor menor: tende a usar menos memoria e ser mais estavel

Exemplo pratico:

```env
INDEX_BATCH_SIZE=20
```

Resultado:

- a indexacao fica mais conservadora
- bom quando o volume crescer ou a maquina tiver menos recursos

### `AUTO_REINDEX_ON_EMPTY_INDEX`

Valor atual:

```env
AUTO_REINDEX_ON_EMPTY_INDEX=true
```

O que faz:

- quando voce roda `ask`, se o banco vetorial estiver vazio, o projeto reindexa automaticamente

Quando e bom:

- estudo
- demos
- ambientes onde voce quer evitar erros por esquecimento

Quando pode ser ruim:

- producao
- quando a indexacao e pesada e voce quer controlar esse processo separadamente

Exemplo pratico:

```env
AUTO_REINDEX_ON_EMPTY_INDEX=false
```

Resultado:

- o agent nao reindexa sozinho
- voce precisa rodar `reindex` manualmente

## 3. Chunking

Esses parametros sao centrais para RAG.

### `CHUNK_SIZE`

Valor atual:

```env
CHUNK_SIZE=900
```

O que faz:

- define o tamanho maximo de cada chunk de texto
- e usado no `RecursiveCharacterTextSplitter`

Como pensar:

- chunk grande: mais contexto em cada pedaço
- chunk pequeno: mais precisao, mas mais fragmentacao

Exemplo pratico 1:

```env
CHUNK_SIZE=400
```

Resultado:

- a Maria recebe pedaços menores
- isso pode melhorar a busca para informacoes muito especificas
- mas pode perder contexto quando a ideia depende de varias frases juntas

Exemplo pratico 2:

```env
CHUNK_SIZE=1400
```

Resultado:

- a Maria recebe pedaços maiores
- isso pode ajudar em textos longos e mais narrativos
- mas pode trazer contexto demais e reduzir precisao

Recomendacao para estudo:

- `700` a `1200` e uma faixa muito boa

### `CHUNK_OVERLAP`

Valor atual:

```env
CHUNK_OVERLAP=120
```

O que faz:

- define quanto texto sera repetido entre um chunk e outro

Por que isso existe:

- evita que uma informacao importante fique cortada bem na fronteira entre dois chunks

Exemplo pratico:

```env
CHUNK_SIZE=900
CHUNK_OVERLAP=120
```

Leitura:

- cada novo chunk reaproveita parte do final do chunk anterior

Se reduzir muito:

```env
CHUNK_OVERLAP=0
```

Resultado:

- os chunks ficam independentes
- mais risco de perda de continuidade

Se aumentar demais:

```env
CHUNK_OVERLAP=300
```

Resultado:

- mais redundancia entre chunks
- mais custo de indexacao
- pode gerar recuperacoes repetitivas

Regra pratica:

- usar algo entre 10% e 20% do `CHUNK_SIZE`

## 4. Retrieval

Esses parametros controlam como a Maria busca contexto no banco vetorial.

### `SEARCH_K`

Valor atual:

```env
SEARCH_K=4
```

O que faz:

- define quantos documentos finais a busca vetorial retorna

Se aumentar:

```env
SEARCH_K=8
```

Resultado:

- a Maria recebe mais contexto
- isso pode ajudar em perguntas amplas
- tambem pode aumentar ruído e custo

Se reduzir:

```env
SEARCH_K=2
```

Resultado:

- a Maria recebe menos contexto
- fica mais objetiva
- pode perder nuances

### `SEARCH_FETCH_K`

Valor atual:

```env
SEARCH_FETCH_K=12
```

O que faz:

- define quantos candidatos iniciais o MMR busca antes de escolher os `k` finais

Como pensar:

- `fetch_k` maior = mais diversidade
- `k` = quantos realmente voltam

Exemplo pratico:

```env
SEARCH_K=4
SEARCH_FETCH_K=20
```

Resultado:

- o algoritmo avalia mais candidatos
- tende a retornar um conjunto mais variado de documentos

Regra pratica:

- `SEARCH_FETCH_K` costuma ser de 2x a 4x o `SEARCH_K`

### `MIN_RETRIEVED_DOCUMENTS`

Valor atual:

```env
MIN_RETRIEVED_DOCUMENTS=1
```

O que faz:

- define o minimo de documentos recuperados para considerar que ha contexto suficiente

Exemplo pratico:

```env
MIN_RETRIEVED_DOCUMENTS=2
```

Resultado:

- a Maria fica mais exigente
- se vier apenas um documento, pode considerar pouco contexto

Quando aumentar:

- quando voce quiser ser mais conservadora nas respostas

### `MAX_CONTEXT_CHARS`

Valor atual:

```env
MAX_CONTEXT_CHARS=6000
```

O que faz:

- limita o tamanho total do contexto recuperado que sera entregue ao agent

Se aumentar:

```env
MAX_CONTEXT_CHARS=10000
```

Resultado:

- a Maria recebe mais texto
- pode melhorar perguntas mais amplas
- aumenta custo e pode reduzir foco

Se reduzir:

```env
MAX_CONTEXT_CHARS=3000
```

Resultado:

- respostas mais enxutas
- menos custo
- maior risco de faltar contexto

### `REQUIRE_SOURCE_ATTRIBUTION`

Valor atual:

```env
REQUIRE_SOURCE_ATTRIBUTION=true
```

O que faz:

- instrui o agent, via prompt, a citar fontes

Importante:

- isso nao e uma validacao dura
- e uma regra comportamental no prompt

Exemplo pratico:

```env
REQUIRE_SOURCE_ATTRIBUTION=false
```

Resultado:

- a Maria pode responder de forma mais natural e menos formal
- mas reduz rastreabilidade

### `FALLBACK_IF_NO_CONTEXT`

Valor atual:

```env
FALLBACK_IF_NO_CONTEXT=true
```

O que faz:

- se a busca vetorial nao trouxer contexto suficiente, a tool responde com uma mensagem amigavel em vez de estourar erro

Se mudar:

```env
FALLBACK_IF_NO_CONTEXT=false
```

Resultado:

- o sistema passa a falhar explicitamente
- isso e bom quando voce quer debugar comportamento do RAG

## 5. Tools do agent

### `ENABLE_VECTOR_TOOL`

Valor atual:

```env
ENABLE_VECTOR_TOOL=true
```

O que faz:

- liga a tool `semantic_search`

Se desativar:

```env
ENABLE_VECTOR_TOOL=false
```

Resultado:

- a Maria nao usa busca semantica
- fica dependente de SQL

Quando faz sentido:

- testes comparativos
- debugging

### `ENABLE_SQL_TOOL`

Valor atual:

```env
ENABLE_SQL_TOOL=true
```

O que faz:

- liga a tool `sql_read_only_query`

Se desativar:

```env
ENABLE_SQL_TOOL=false
```

Resultado:

- a Maria perde acesso a consultas exatas do banco
- fica mais “RAG puro”

No seu projeto:

- eu nao recomendaria desligar em cenarios operacionais
- porque gerente de loja precisa de numero exato, status e filtros

### `MAX_TOOL_CALLS`

Valor atual:

```env
MAX_TOOL_CALLS=6
```

O que faz:

- limita quantas chamadas de ferramentas a Maria pode fazer por resposta
- esse limite e aplicado via middleware do LangChain

Se reduzir:

```env
MAX_TOOL_CALLS=3
```

Resultado:

- respostas mais rapidas e baratas
- maior risco de faltar investigacao em perguntas complexas

Se aumentar:

```env
MAX_TOOL_CALLS=10
```

Resultado:

- mais liberdade para raciocinar
- mais custo
- maior risco de looping ou excesso de passos

Faixa recomendada:

- `4` a `8` para esse tipo de agent

## 6. Memoria conversacional

Esses parametros controlam como a Maria reaproveita contexto entre mensagens sem reenviar o historico inteiro.

### `ENABLE_CONVERSATION_MEMORY`

Valor atual:

```env
ENABLE_CONVERSATION_MEMORY=true
```

O que faz:

- liga a memoria por `conversation_id`
- a Maria passa a ler resumo da conversa e ultimas mensagens antes de responder

Se desativar:

```env
ENABLE_CONVERSATION_MEMORY=false
```

Resultado:

- cada pergunta volta a ser praticamente independente
- perde continuidade
- aumenta necessidade de repetir contexto manualmente

### `ENABLE_USER_MEMORY`

Valor atual:

```env
ENABLE_USER_MEMORY=true
```

O que faz:

- liga memorias duraveis por `user_id` e opcionalmente `store_id`

Exemplo de memoria duravel:

- `o gerente prefere respostas curtas`
- `a loja centro prioriza disponibilidade de itens de freio e lubrificantes`

### `MEMORY_RECENT_MESSAGES`

Valor atual:

```env
MEMORY_RECENT_MESSAGES=6
```

O que faz:

- define quantas mensagens recentes entram como historico bruto na chamada atual

Se aumentar:

```env
MEMORY_RECENT_MESSAGES=10
```

Resultado:

- mais continuidade literal
- mais consumo de tokens

Se reduzir:

```env
MEMORY_RECENT_MESSAGES=4
```

Resultado:

- menos tokens
- mais dependencia do resumo

### `MEMORY_SUMMARIZE_AFTER_MESSAGES`

Valor atual:

```env
MEMORY_SUMMARIZE_AFTER_MESSAGES=8
```

O que faz:

- define a partir de quantas mensagens a Maria comeca a resumir a conversa

Exemplo pratico:

- com `8`, uma conversa curta ainda usa historico cru
- quando passa disso, o sistema comeca a compactar as mensagens antigas

Se reduzir:

```env
MEMORY_SUMMARIZE_AFTER_MESSAGES=4
```

Resultado:

- a conversa passa a ser resumida mais cedo
- economiza tokens mais rapido
- pode perder nuances mais cedo

### `MEMORY_SUMMARY_MAX_CHARS`

Valor atual:

```env
MEMORY_SUMMARY_MAX_CHARS=1800
```

O que faz:

- orienta o tamanho maximo do resumo da conversa

Se aumentar:

```env
MEMORY_SUMMARY_MAX_CHARS=3000
```

Resultado:

- resumo mais rico
- menos compressao

Se reduzir:

```env
MEMORY_SUMMARY_MAX_CHARS=900
```

Resultado:

- resumo mais compacto
- mais economia
- maior risco de omitir detalhe importante

### `USER_MEMORY_TOP_K`

Valor atual:

```env
USER_MEMORY_TOP_K=3
```

O que faz:

- define quantas memorias duraveis do usuario entram no contexto

Se aumentar:

```env
USER_MEMORY_TOP_K=6
```

Resultado:

- a Maria considera mais preferencias e notas
- aumenta consumo de tokens

Se reduzir:

```env
USER_MEMORY_TOP_K=1
```

Resultado:

- a memoria fica mais seletiva
- pode deixar de considerar alguma preferencia relevante

## 7. Guardrails de entrada

### `MIN_QUESTION_CHARS`

Valor atual:

```env
MIN_QUESTION_CHARS=5
```

O que faz:

- bloqueia perguntas curtas demais

Exemplo:

- `oi` seria barrado
- `vendas hoje` passaria

### `MAX_QUESTION_CHARS`

Valor atual:

```env
MAX_QUESTION_CHARS=500
```

O que faz:

- limita o tamanho maximo da pergunta

Por que isso e util:

- evita entradas exageradas
- reduz risco de prompt injection grande
- protege custo

Se aumentar:

```env
MAX_QUESTION_CHARS=1200
```

Resultado:

- aceita perguntas mais longas e ricas
- aumenta superficie de risco

### `BLOCKED_INPUT_PATTERNS`

Valor atual:

```env
BLOCKED_INPUT_PATTERNS=(?i)ignore previous instructions||(?i)drop table||(?i)delete from||(?i)shutdown
```

O que faz:

- define regex bloqueadas na entrada
- os padroes sao separados por `||`

Entendendo:

- `(?i)` significa case insensitive
- `drop table` e `delete from` sao barreiras contra comandos destrutivos escritos na pergunta

Exemplo pratico:

```env
BLOCKED_INPUT_PATTERNS=(?i)ignore previous instructions||(?i)system prompt
```

Resultado:

- o agent passa a bloquear tambem tentativas de extrair o prompt

Cuidado:

- regex forte demais pode bloquear perguntas legitimas

## 8. Guardrails de SQL

### `ALLOW_ONLY_SELECT_SQL`

Valor atual:

```env
ALLOW_ONLY_SELECT_SQL=true
```

O que faz:

- obriga o agent a usar apenas `SELECT`

Esse e um dos parametros mais importantes do projeto.

Se estivesse `false`:

- o agent poderia tentar montar SQL de escrita
- isso abriria uma superficie desnecessaria de risco

Minha recomendacao:

- manter sempre `true`

### `SQL_MAX_ROWS`

Valor atual:

```env
SQL_MAX_ROWS=20
```

O que faz:

- limita a quantidade de linhas que uma query pode retornar

Se aumentar:

```env
SQL_MAX_ROWS=100
```

Resultado:

- a Maria consegue trazer mais linhas
- mas as respostas ficam mais pesadas e menos legiveis

Se reduzir:

```env
SQL_MAX_ROWS=10
```

Resultado:

- respostas mais objetivas
- menor risco de excesso de informacao

## 9. Guardrails de saida

### `MASK_EMAILS`

Valor atual:

```env
MASK_EMAILS=true
```

O que faz:

- mascara emails na entrada e na saida

### `MASK_PHONES`

Valor atual:

```env
MASK_PHONES=true
```

O que faz:

- mascara telefones quando detectados

### `MASK_CPFS`

Valor atual:

```env
MASK_CPFS=true
```

O que faz:

- redige CPFs quando encontrados

No seu contexto:

- mesmo que hoje voce nao queira dados sensiveis, esses parametros deixam a Maria mais segura se no futuro algum dado desse tipo entrar no banco

## 10. LLM principal

### `LLM_PROVIDER`

Valor atual:

```env
LLM_PROVIDER=openai
```

O que faz:

- define qual provedor sera usado para o modelo principal de chat

Opcoes hoje no projeto:

- `openai`
- `ollama`

Exemplo pratico:

```env
LLM_PROVIDER=ollama
```

Resultado:

- a Maria passa a usar um modelo local, se configurado corretamente

### `LLM_MODEL`

Valor atual:

```env
LLM_MODEL=gpt-4.1-mini
```

O que faz:

- define o modelo de chat que interpreta a pergunta, escolhe tools e responde

Se trocar:

```env
LLM_MODEL=gpt-4.1
```

Resultado:

- mais capacidade
- normalmente mais custo

### `LLM_TEMPERATURE`

Valor atual:

```env
LLM_TEMPERATURE=0
```

O que faz:

- controla aleatoriedade da resposta

Como interpretar:

- `0`: mais deterministico
- `0.3`: um pouco mais flexivel
- `0.7`: mais criativo e menos consistente

No seu caso:

- `0` faz muito sentido
- gerente de loja precisa mais de precisao do que criatividade

### `OPENAI_API_KEY`

Valor atual:

```env
OPENAI_API_KEY=sua-chave
```

O que faz:

- autentica chamadas para a OpenAI

Observacao:

- ela so e usada quando `LLM_PROVIDER=openai`

## 11. Embeddings

### `EMBEDDING_PROVIDER`

Valor atual:

```env
EMBEDDING_PROVIDER=huggingface
```

O que faz:

- define quem gera os embeddings

Opcoes suportadas hoje:

- `huggingface`
- `openai`
- `ollama`

### `EMBEDDING_MODEL`

Valor atual:

```env
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

O que faz:

- define qual modelo transforma texto em vetor

No seu projeto:

- ele nao responde ao usuario
- ele serve para comparar textos por similaridade

Se trocar por outro modelo:

- muda a qualidade da recuperacao
- muda custo, velocidade e uso de memoria

### `EMBEDDING_DEVICE`

Valor atual:

```env
EMBEDDING_DEVICE=cpu
```

O que faz:

- define onde o modelo de embedding roda

Exemplo pratico:

```env
EMBEDDING_DEVICE=cuda
```

Resultado:

- se sua maquina suportar GPU corretamente, a vetorizacao pode ficar bem mais rapida

### `EMBEDDING_NORMALIZE`

Valor atual:

```env
EMBEDDING_NORMALIZE=true
```

O que faz:

- normaliza os vetores gerados

Na pratica:

- geralmente melhora a comparacao por similaridade
- e uma configuracao boa para manter

## 12. Ollama

### `OLLAMA_BASE_URL`

Valor atual:

```env
OLLAMA_BASE_URL=http://localhost:11434
```

O que faz:

- define onde o servidor Ollama esta rodando

Quando importa:

- quando `LLM_PROVIDER=ollama`
- quando `EMBEDDING_PROVIDER=ollama`

## Parametros mais importantes para estudar primeiro

Se voce quiser entender rapidamente o que mais muda o comportamento do agent, foque nesta ordem:

1. `CHUNK_SIZE`
2. `CHUNK_OVERLAP`
3. `SEARCH_K`
4. `SEARCH_FETCH_K`
5. `MAX_CONTEXT_CHARS`
6. `ALLOW_ONLY_SELECT_SQL`
7. `MAX_TOOL_CALLS`
8. `LLM_TEMPERATURE`
9. `EMBEDDING_MODEL`

## Sugestoes praticas de experimento

### Experimento 1: chunks menores

Troque para:

```env
CHUNK_SIZE=500
CHUNK_OVERLAP=80
```

O que observar:

- a busca fica mais precisa ou mais fragmentada?
- a Maria melhora em perguntas muito especificas?

### Experimento 2: mais contexto recuperado

Troque para:

```env
SEARCH_K=6
SEARCH_FETCH_K=18
MAX_CONTEXT_CHARS=9000
```

O que observar:

- a Maria responde melhor perguntas amplas?
- ou comeca a trazer ruído?

### Experimento 3: agent mais enxuto

Troque para:

```env
MAX_TOOL_CALLS=3
SQL_MAX_ROWS=10
```

O que observar:

- respostas ficam mais curtas?
- o agent perde qualidade em perguntas complexas?

### Experimento 4: agent mais conservador

Troque para:

```env
MIN_RETRIEVED_DOCUMENTS=2
FALLBACK_IF_NO_CONTEXT=false
```

O que observar:

- a Maria passa a recusar mais respostas?
- isso melhora confiabilidade?

## Configuracao atual: leitura rapida

Seu `.env` atual esta bem equilibrado para estudo:

- `CHUNK_SIZE=900`: bom equilibrio entre contexto e precisao
- `CHUNK_OVERLAP=120`: boa continuidade
- `SEARCH_K=4`: contexto suficiente sem excesso
- `SEARCH_FETCH_K=12`: boa diversidade
- `MAX_CONTEXT_CHARS=6000`: limite saudavel
- `ALLOW_ONLY_SELECT_SQL=true`: muito importante para seguranca
- `MAX_TOOL_CALLS=6`: equilibrado
- `LLM_TEMPERATURE=0`: ideal para analise operacional
- `EMBEDDING_PROVIDER=huggingface`: bom para estudar sem custo por embedding

## Resumo final

Se eu resumisse o papel de cada bloco:

- infraestrutura: onde ficam os bancos
- indexacao: o que entra no RAG
- chunking: como o texto e quebrado
- retrieval: quanto contexto volta
- tools: quais capacidades a Maria pode usar
- guardrails: o que ela pode ou nao fazer
- llm: quem responde
- embeddings: quem encontra o contexto

Se quiser, no proximo passo eu posso criar um segundo arquivo `.md` com um formato ainda mais didatico:

- parametro
- valor atual
- valor recomendado
- risco de aumentar
- risco de diminuir
- melhor uso no seu caso de gerente de loja de autopecas
