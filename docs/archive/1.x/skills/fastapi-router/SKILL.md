---
name: fastapi-router
description: Roteador entre a skill estática (mental models de FastAPI) e o RAG híbrido knowledge-rag (busca factual/search_knowledge). Decidir por pergunta: conceitual → skill; factual/literal → RAG com citação; ambígua/alto risco → ambos e declarar divergência. Dispare em toda pergunta sobre FastAPI. Renomear estes nomes ao trocar de framework.
---

# fastapi-router — quando usar skill, quando usar RAG

## Estado do sistema (piloto FastAPI)

- Skill estática: `skills/fastapi/SKILL.md` (gerada por `book-to-skill`), com 7 capítulos e snapshot registrado em `docs/FRAMEWORK-TARGET.md`.
- RAG MCP: servidor `knowledge-rag` (tools: `search_knowledge`, `get_document`, `search_similar`, `reindex_documents`, ...). Corpus local: `documents/` — 157 fontes FastAPI, 3 auxiliares e 3 fixtures sintéticas; `add_from_url` é opcional.
- Avaliação atual: MRR@5 0,8595 e Recall@5 1,0 no Golden FastAPI; reranker permanece desligado no piloto.

## Como decidir (regra principal)

Classifique a pergunta do usuário em UM dos três tipos antes de responder:

### 1. CONCEITUAL / COMPORTAMENTAL
"como X lida com Y", "qual o padrão recomendado para Z", "por que o framework foi desenhado assim", "o que acontece quando...", "quais os anti-patterns de W".

→ **Responder primeiro pela skill estática** (`SKILL.md`, depois `chapters/…`, `patterns.md`, `cheatsheet.md` como necessário). Não precisa de `search_knowledge` a menos que a skill esteja insegura ou sem cobertura.

### 2. FACTUAL / LITERAL
"qual a assinatura exata de `Client.request()`", "qual o default de X", "o que mudou na v3.2", "esse endpoint existe?", código específico, nomes de configuração, valores, datas de changelog, versões.

→ **Chamar `search_knowledge` via MCP ANTES de responder** (siga `rag-check-first`). Cite a fonte em toda afirmação factual (siga `rag-cite-sources`).

### 3. AMBÍGUA ou ALTO RISCO
decisão de arquitetura, migração, breaking change, dúvida sobre deprecations, qualquer coisa em que errar custa caro.

→ **Usar as duas camadas**: skill para o racional/mental model + `search_knowledge` (e se necessário `get_document`/`search_similar` via `rag-deep-dive`) para confirmar o detalhe literal atual. Se divergirem, **declarar explicitamente** qual é a mais confiável e por quê.

## Regras de citação (obrigatórias)

- Toda resposta que se apoie no RAG inclui a fonte no formato `caminho/arquivo.md` (ou `caminho/arquivo.md#secao`, `arquivo:linha` quando disponível). A ferramenta devolve `source` (path) — citar esse path.
- **Inline** junto da afirmação, não ao final. Uma afirmação = uma citação.
- Quando algo vem da skill estática, indicar o arquivo da skill (ex.: `fastapi/SKILL.md`, `fastapi/chapters/03-dependencies.md`).
- Quando o conteúdo é conhecimento geral (fora do corpus e fora da skill), declarar: `[não há fonte local — conhecimento geral, verificar]`.

## Divergência skill x RAG

Se a skill (gerada em data D) e a doc atual (indexada) discordarem:

1. Preferir o RAG (doc atual) para FATOS literais; a skill para a INTENÇÃO histórica.
2. Explicitar a divergência: "A skill de <data> diz X; a doc atual diz Y — provável release posterior. Nesta resposta uso Y (fonte doc), mas o racional X ainda vale se...".
3. Registrar a divergência como pendência de fold-in (ver `scripts/update_skill.ps1`).

## Sequência prática padrão

1. Classificar a pergunta (conceitual / factual / ambígua).
2. Executar a camada escolhida.
3. Responder com citações inline (RAG) e/ou referência à skill (quando usada).
4. Se a base RAG retornar 0 resultados relevantes: avisar que o corpus não cobre, responder de conhecimento geral com aviso explícito (sem citação falsa) e sugerir `add_from_url`/documentar o gap (via `rag-index-decisions`).

## Gatilhos do use case

- Pergunta sobre FastAPI: sempre passar por este roteador antes de responder direto.
- Se o usuário pedir "fonte", ou se a pergunta tiver nome de função/endpoint/config/propriedade: tratar como FACTUAL (regra 2).
