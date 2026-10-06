# Capítulo 4 — Changelog

## v3.3.0 (mais nova)

- `Client.async_request()` — mesma assinatura, `aiohttp`; `timeout` em float;
  `retries > 1` → backoff exponencial padrão.

## v3.2.0

- `request()` agora aceita `body` como `dict` (string JSON foi retirada).
- Novo erro `ApiVersionError` (path sem `v3/`).
- Introduzido `Client.iter_paginated`.
- **Deprecado:** `client.join(endpoint, key)` — removido na v4 (usar `path`).

## Regras do changelog

1. Remoção: deprecador no release N, removido no N+1 (ex.: join → v4).
2. Cada pergunta "o que mudou na vX" responde: adições → mudanças → deprecações.
