# Maria RAG Agent

Base profissional de estudo para uma assistente de loja chamada Maria, focada em gerentes de uma franquia de autopecas, com:

- `SQLite` como fonte de verdade
- `Chroma` como banco vetorial local
- `LangChain` para agent, tools e pipeline RAG
- `.env` para controlar chunking, retrieval, SQL guardrails e parametros do agent

## Arquitetura

O projeto foi pensado para o fluxo mais solido para RAG em dados de banco:

1. O `SQLite` guarda os dados originais.
2. O pipeline de indexacao le tabelas configuradas.
3. Cada linha vira um `Document`.
4. Os documentos sao quebrados em chunks e vetorizados.
5. O agent usa duas ferramentas:
   - `semantic_search`: busca semantica no Chroma
   - `sql_read_only_query`: consulta SQL somente leitura para dados exatos

Isso te da um agent hibrido:

- perguntas conceituais -> RAG vetorial
- perguntas exatas, numericas, datas e status -> SQL

## Memoria conversacional

O projeto agora suporta memoria persistente para multiplos usuarios com:

- `conversation_id` para continuar uma conversa
- `user_id` para isolar memorias por usuario
- resumo automatico da conversa para reduzir tokens
- memorias duraveis opcionais por usuario e loja

Na pratica, a Maria usa:

- resumo do historico antigo
- ultimas mensagens da conversa
- memorias relevantes do usuario
- dados atuais do banco e do RAG

Assim, voce evita reenviar o historico inteiro em toda chamada.

## Estrutura

```text
src/maria_rag_agent/
  agent.py
  cli.py
  config.py
  database.py
  documents.py
  guardrails.py
  prompts.py
  tools.py
  vectorstore.py
data/
storage/
```

## Como rodar

### 1. Criar ambiente e instalar dependencias

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

Se preferir instalar apenas as dependencias principais, sem modo editavel:

```powershell
pip install -r requirements.txt
```

Se quiser usar `Ollama`, instale tambem:

```powershell
pip install -e .[ollama]
```

Quando usar cada opcao:

- `pip install -e .`: melhor durante desenvolvimento, porque o projeto fica instalado em modo editavel e qualquer alteracao no codigo ja e refletida sem reinstalar.
- `pip install -r requirements.txt`: melhor quando voce quer apenas rodar o ambiente com as dependencias principais, sem instalar o pacote em modo editavel.

### 2. Criar o `.env`

```powershell
Copy-Item .env.example .env
```

Preencha pelo menos a parte do modelo. Exemplo com OpenAI:

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=sua-chave
```

Exemplo local com Ollama:

```env
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1
OLLAMA_BASE_URL=http://localhost:11434
```

## Comandos

Inicializar o banco local:

```powershell
python -m maria_rag_agent.cli init-db
```

Popular com dados de exemplo:

```powershell
python -m maria_rag_agent.cli seed-db
```

Reindexar no banco vetorial:

```powershell
python -m maria_rag_agent.cli reindex
```

Fazer uma pergunta ao agent:

```powershell
python -m maria_rag_agent.cli ask "Quais produtos mais geraram caixa nesta semana?"
```

Continuar uma conversa existente:

```powershell
python -m maria_rag_agent.cli ask "E quais setores podem cobrir uma ausencia no vendas_balcao?" --conversation-id conv_demo_01 --user-id gerente_loja_01 --store-id loja_centro
```

Listar conversas salvas:

```powershell
python -m maria_rag_agent.cli list-conversations --user-id gerente_loja_01
```

Ver mensagens recentes de uma conversa:

```powershell
python -m maria_rag_agent.cli show-conversation conv_demo_01
```

Salvar uma memoria duravel do usuario:

```powershell
python -m maria_rag_agent.cli add-user-memory gerente_loja_01 "Prefere respostas curtas com foco em acao e indicadores." --memory-type preference --store-id loja_centro --priority 3
```

Listar memorias duraveis do usuario:

```powershell
python -m maria_rag_agent.cli list-user-memories gerente_loja_01 --store-id loja_centro
```

Ver a configuracao carregada:

```powershell
python -m maria_rag_agent.cli show-config
```

## Parametros importantes no `.env`

Chunking:

- `CHUNK_SIZE`
- `CHUNK_OVERLAP`

Busca:

- `SEARCH_K`
- `SEARCH_FETCH_K`
- `MAX_CONTEXT_CHARS`
- `MIN_RETRIEVED_DOCUMENTS`

Guardrails:

- `BLOCKED_INPUT_PATTERNS`
- `ALLOW_ONLY_SELECT_SQL`
- `SQL_MAX_ROWS`
- `MASK_EMAILS`
- `MASK_PHONES`
- `MASK_CPFS`
- `MAX_TOOL_CALLS`

Memoria:

- `ENABLE_CONVERSATION_MEMORY`
- `ENABLE_USER_MEMORY`
- `MEMORY_RECENT_MESSAGES`
- `MEMORY_SUMMARIZE_AFTER_MESSAGES`
- `MEMORY_SUMMARY_MAX_CHARS`
- `USER_MEMORY_TOP_K`

## Tabelas criadas

O projeto cria quatro tabelas principais para o contexto de autopecas:

- `product_catalog`: cadastro de produtos com `sku`, descricao, categoria, estoque e precificacao
- `sales`: vendas por item com `sku`, descricao, preco bruto, receita e geracao de caixa
- `employees`: cadastro de funcionarios sem dado sensivel, com `id_colaborador`, setor e status
- `absenteeism_events`: historico de ausencias para apoiar remanejamento de equipes

## Exemplos de perguntas

- `Quais categorias mais geraram caixa entre 2026-06-09 e 2026-06-15?`
- `Quais produtos estao abaixo do ponto de reposicao?`
- `Quem do time ativo pode cobrir o setor de vendas_balcao no turno da manha?`
- `Quais faltas recentes exigiram substituicao imediata?`
- `Liste os funcionarios ativos da televendas e seus setores de apoio.`

## Proximos passos naturais

- trocar os seeds por dados reais da sua operacao
- ajustar os renderizadores em `documents.py` para a sua nomenclatura interna
- adicionar avaliacao automatica de respostas
- incluir filtros por metadata no retriever
- conectar LangSmith para tracing
