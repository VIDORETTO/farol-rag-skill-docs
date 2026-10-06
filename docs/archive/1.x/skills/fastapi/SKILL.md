---
name: fastapi
description: Mental models, convenções e padrões do framework FastAPI (tutorial + reference + release notes indexadas em documents/fastapi-docs/). Use para perguntas conceituais — como FastAPI pensa (type-driven design, dependency injection, OpenAPI-first, async). Para detalhe literal (assinaturas exatas, defaults, changelog) prefira o RAG via knowledge-rag com citação — ver fastapi-router.
---

# FastAPI — mental models do framework

> Gerada pelo fluxo book-to-skill (Steps 0–10) sobre as docs oficiais
> (snapshot local de 2026-08-28; corpus: `documents/fastapi-docs/`,
> 157 arquivos suportados, 154 em Markdown). Frameworks,
> convenções, anti-patterns e regras de decisão — não substitui a API reference
> (RAG cita `fastapi-docs/reference/*.md`).

## Índice de capítulos

| Capítulo | Arquivo | Conteúdo |
|---|---|---|
| 1. Design de tipos | `chapters/01-type-driven.md` | type hints, Pydantic, validação, DTOs |
| 2. Path operations | `chapters/02-path-operations.md` | decorators, params, status codes, response_model |
| 3. Dependências | `chapters/03-dependencies.md` | DI, Depends, override de testes |
| 4. Segurança | `chapters/04-security.md` | OAuth2, JWT, scopes, utils de segurança |
| 5. Async & performance | `chapters/05-async.md` | sync/async misto, background tasks, streaming, SSE |
| 6. Config e deploy | `chapters/06-config-deploy.md` | pydantic-settings, env, workers, docker, HTTPS |
| 7. Testes | `chapters/07-testing.md` | TestClient, dependencies override, httpx |

## Core — frameworks e convenções

1. **Type-driven design (Pydantic como fonte de verdade).**
   Contrato de entrada e saída é o TIPO da assinatura. FastAPI extrai de
   type hints: validação, docs, serialização, filtro de saída. Nunca escreva
   validação manual no handler — use modelos.

2. **OpenAPI-first (os docs são derivados do código).**
   Swagger UI (`/docs`) e ReDoc (`/redoc`) nascem do contrato declarado.
   Se você precisa "marcar docs manual", está duplicando: ajuste tipos/`metadata`.

3. **`response_model` é sobre LIMITAR e FILTRAR saída (higiene, segurança).**
   Usado quando o retorno real (dict/ORM) difere do contrato público; sem ele,
   excesso de campos vaza. Retorno anotado diretamente quando o tipo é exato.

4. **Dependency injection via `Depends` resolve autenticação/authz, DB,
   settings e reuso — com `override` para testes.**
   Não injete lógica de request dentro de endpoint; subdependências compõem.

5. **Async-first pragmático.**
   `def` executado em threadpool, `async def` no event loop. File/IO externo →
   async; CPU-bound → def ou workers. Background tasks só p/ pós-resposta
   rápida; fila real p/ trabalho pesado.

6. **Segurança pronta (utils) — mas controle os segredos.**
   `OAuth2PasswordBearer`/`HTTPBearer` + PyJWT/passlib padrão da doc (JWT não é
   criptografia: assinar não esconde payload). Settings via `pydantic-settings`
   tira env var `str` crua do código.

## Mapa de decisão (cheatsheet)

| Situação | Escolha |
|---|---|
| "Valide e serialize JSON pela assinatura" | tipos nas anotações (models Pydantic) |
| "Retorno real difere do contrato" | decorator `response_model=` (não return type) |
| "Recurso precisa auth" | `Depends(get_current_user)` via OAuth2PasswordBearer |
| "Lógica reutilizada ou estado p/ request" | dependência + `yield` p/ contexto ; `app.dependency_overrides` em testes |
| "Trabalho pós-resposta" | `BackgroundTasks`; pesado → Celery/RQ |
| "Config de segredos" | `BaseSettings` + env vars, nunca hardcode |
| "Teste endpooint" | `TestClient` (httpx) + overrides |

## Anti-patterns (não fazer)

- Validação manual dentro de endpoint (duplica Pydantic e desvia do contrato).
- Retornar dict solto quando havia `response_model` projetado (vaza campos).
- `async def` com trabalho CPU-bound ("porque é moderno") fora de threadpool.
- Confiar em "passwords no token" (JWT é legível; não colocar secrets).
- Docs customizadas espelhando OpenAPI (duplicação e drift).

## Glossário

| Termo | Significado |
|---|---|
| path operation | endpoint (decorator) — `@app.get(...)` etc. |
| `APIRouter` | agrupa path ops p/ refactor modular |
| `Depends` | mecanismo de DI; gera subdependência em cadeia |
| `response_model` | contrato de saída (filtro/validação/JSON Schema) |
| `BackgroundTasks` | pós-resposta rápida; não bloqueia response |
| `OAuth2PasswordBearer` | extrai token do header Authorization |
| `pydantic-settings` | `BaseSettings` p/ env vars tipadas |
