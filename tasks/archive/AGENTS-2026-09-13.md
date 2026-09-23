# AGENTS.md — Farol (doc-to-skill + RAG híbrido)

Este repositório é um **sistema de conhecimento** pronto para ser importado em
qualquer projeto: agente diz qual documentação processar → o operador
(`doc-to-rag-operator`) monta skill + índice RAG + roteador, e depois responde
consultas conceituais (skill) e factuais (RAG com citação).

## Arquitetura em uma linha

`book-to-skill` (skill estruturada ≤4k tokens + capítulos; mental models) +
`knowledge-rag` MCP (busca híbrida local: semântica ONNX + BM25; rerank
opcional) + skill roteadora `<slug>-router` (quando usar qual, citação
`path#secao`). O piloto ativo é FastAPI (`skills/fastapi/` e
`skills/fastapi-router/`).

## Para operar (como agente)

1. Leia `skills/doc-to-rag-operator/SKILL.md` (na raiz do host, também em
   `skills/doc-to-rag-operator/`) — ele tem o fluxo completo Fase 0→5.
2. Ferramentas: `book-to-skill` (usar como skill de agente), MCP
   `knowledge-rag` (tools `search_knowledge`, `get_document`,
   `update_document`, `reindex_documents`, `evaluate_retrieval`…).
3. Comandos shell principais (PowerShell):

```powershell
python scripts\update_rag.py plan    # diff documentos → índice
python scripts\update_rag.py apply   # aplica add/update/remove + reindex
python scripts\update_rag.py status  # docs/chunks do servidor
python scripts\mcp_smoke.py "background tasks FastAPI"  # smoke MCP
python scripts\evaluate_golden.py --cases golden-set\test-cases-fastapi.json
pwsh -File scripts\update_skill.ps1 -Sources <fontes> -Slug <slug>  # fold-in
pwsh -File scripts\install_rag_skills.ps1                            # skills rag-*
```

`update_rag.py apply` deve ser executado em primeiro plano: ele desativa o
watcher durante as mutações explícitas e salva checkpoint após cada arquivo.
Em Windows, prefira esse modo retomável ao `--direct`.

## Regras duras (não quebrar)

- Não versionar `.venv-rag/`, `data/`, `models_cache/`, `.rag_state.json`
  (`.gitignore` já cobre) e `documents/` (material com direitos autorais).
  Antes de versionar documentos, confirmar licença (`docs/FRAMEWORK-TARGET.md` §2).
- Toda resposta factual cita fonte (`path#secao` ou `path:linha`) — ver
  `skills/rag-cite-sources` (instalada).
- Nunca expor o índice em rede/SSE sem `bearer_token` (`config.yaml` +
  `docs/USE.md` §9).
- Mudança de `models.embedding.profile` (compact/multilingual/quality) SEMPRE
  acompanhada de `reindex_documents(full_rebuild=True)`.
- Nunca usar `Get-Process python | Stop-Process`; para limpar uma instância,
  liste `Win32_Process`, confirme o `CommandLine` e encerre apenas o PID exato
  pertencente a este projeto.

## Consulta do dia a dia

- Conceitual ("como X lida com…", "qual o padrão para…") → skill `<slug>`.
- Factual/literal ("assinatura", "default", "changelog", "existe em…") →
  `search_knowledge` + citação.
- Ambígua/alto risco → skill para racional + RAG p/ confirmação, declarando
  divergência (ver `<slug>-router`).

## Estado do projeto

- Framework-alvo em uso: **piloto FastAPI** (MIT) até a doc do projeto real
  substituí-lo (`docs/FRAMEWORK-TARGET.md`).
- Corpus reconciliado: `.rag_state.json` mapeia 163 arquivos (157 FastAPI, 3
  auxiliares e 3 fixtures sintéticas); o último `plan` não encontrou
  add/update/remove. O servidor reporta 5.122 chunks e 245 entradas históricas;
  o estado lógico é mantido pelo manifesto/checkpoints e pelo state local.
- Golden FastAPI: MRR@5 **0,8595** e Recall@5 **1,0** com BM25 expandido e
  reranker desligado no piloto.
- Skill FastAPI validada com `validate_skill.py --lens claude` sem warnings.
- Skills comportamentais `rag-*` (10) do knowledge-rag instaladas no host.
- Operador `doc-to-rag-operator` instalado no host.

## Contrato do produto (DOCOPS)

O fluxo genérico está disponível no pacote `docops` e aceita nome, URL, URL de
repositório ou pasta local. O pacote não executa modelo, não escolhe provedor e
não substitui OpenCode, Claude Code, Codex ou outro harness externo:

```powershell
python -m docops doctor --json
python -m docops resolve <fonte> --json
python -m docops run <fonte> --output <pacote> --license <id> --json
python -m docops validate <pacote> --json
python -m docops golden-candidates <pacote> --json
python -m docops evaluate --package <pacote> --cases <golden-revisado.json> --json
python -m docops config-audit config.yaml --json
```

`run` produz skill, índice/corpus RAG, roteador, `harness.json`, manifesto e
checkpoints. `--index-rag` é opt-in e usa o MCP local; a avaliação exige Golden
Set revisado. Para transporte HTTP/SSE, auditar uma cópia privada de
`config/network.example.yaml` antes de iniciar o servidor. O caminho completo,
os esquemas e as políticas de publicação estão em `docs/USE.md`,
`docs/SCHEMAS.md`, `docs/HARNESSES.md` e `docs/PUBLISHING-POLICY.md`.
