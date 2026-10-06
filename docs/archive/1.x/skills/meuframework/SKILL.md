---
name: meuframework
description: Mental models e convenções do <framework-alvo> (placeholder; no corpus de dev: acme-api-client). Use para perguntas conceituais — como o framework pensa, padrões, anti-patterns, decisões de design. Para detalhe literal/atual (assinaturas, defaults, changelog) prefira o RAG via knowledge-rag (ver meuframework-router).
---

# meuframework — mental models

> Gerada a partir da documentação-alvo via fluxo book-to-skill (Steps 0–10).
> ⚠️ Placeholder: corpus = `documents/examples/acme-api-client.md` (dev).
> A data da geração e a versão da doc-fonte ficam em `docs/FRAMEWORK-TARGET.md`.

## Índice de capítulos

| Capítulo | Arquivo | O que contém | Custo aprox. |
|---|---|---|---|
| 1. API base | `chapters/01-api-base.md` | request(), parâmetros, erros | ~700 tokens |
| 2. Paginação | `chapters/02-paginacao.md` | page/page_size, iter_paginated | ~400 tokens |
| 3. Rate limits | `chapters/03-rate-limits.md` | tiers, 429, Retry-After | ~350 tokens |
| 4. Changelog | `chapters/04-changelog.md` | v3.2.0, v3.3.0, deprecations | ~400 tokens |
| 5. v3.4.0 | `chapters/05-v340.md` | compress, health autenticado, log_requests | ~300 tokens |

## Core — frameworks e convenções

1. **API explícita, erro tipado, retry controlado.**
   Colocar `body` (`dict`), `timeout` (30.0s, máx. 120.0s) e `retries`
   (padrão 2) como parâmetros nominados. Nunca assumir defaults silenciosos:
   o cliente SÓ tenta de novo em 5xx/429, e só se `retries` disponível.

2. **Contrato de versão estrito (`v3/`).**
   Path precisa do prefixo `v3/`; a ausência é *erro* (`ApiVersionError`),
   não warning. Convenção: toda nova versão da API muda o prefixo de path,
   nunca a semântica de endpoints.

3. **Erro único por condição, mensagem orientada a correção.**
   `RateLimitedError` (429, respeita `Retry-After`), `RequestTimeoutError`
   (timeout), `ApiVersionError` (path sem `v3/`). Se o usuário conseguir
   deduzir o conserto do erro, o tipo está certo.

4. **Página é detalhe de implementação.**
   Variar de page NÃO deve mudar o comportamento do caller — `iter_paginated`
   esconde `page`/`has_next`; mas é fraco e barato o suficiente para aceitar
   no máximo as primeiras 20 páginas (proteção contra laços infinitos).

5. **Backward compatibility: remoção precedida de deprecation com alerta.**
   `client.join()` foi deprecado na v3.2.0 e removido na v4. Qualquer coisa
   removida no futuro deve ter o mesmo aviso prévio por pelo menos 1 release.
   ⚠️ (v3.4.0) `GET /v3/health` quebrou expectativas antigas: recursos que
   eram publicamente abertos podem passar a exigir chave entre releases —
   checar no changelog antes de confiar em endpoints "históricos".

6. **Reroute de identidade de framework:**
   quando a doc-fonte real entrar no corpus, esta skill é re-
   gerada a partir dela (fold-in) — este arquivo é o modelo de formato.

## Mapa de decisão (cheatsheet)

| Situação | Escolha |
|---|---|
| Perceber identificador de endpoint | o path começa com `v3/` — senão levanta `ApiVersionError` |
| Implementar retry | 2 tentativas extras; só 5xx/429; respeitar `Retry-After` |
| Listar N itens | `page_size` ≤ 500; para muitos itens, `iter_paginated` |
| Erro de timeout | elevar timeout p/ ≤ 120.0s (`RequestTimeoutError` acima) |
| Workload async (v3.3.0+) | `Client.async_request()` com mesma assinatura |
| `GET /v3/health` sem chave | 401 desde a v3.4.0 — envie `x-acme-key` |

## Glossário

| Termo | Significado |
|---|---|
| ACME API v3 | API de destino com prefixo `v3/` nos paths |
| `RequestResult` | .status_code + .data + .headers |
| `RateLimitedError` | 429; usa `Retry-After` quando presente |
| `ApiVersionError` | path sem `v3/` |
| `iter_paginated` | itera até 20 páginas usando `has_next` |
