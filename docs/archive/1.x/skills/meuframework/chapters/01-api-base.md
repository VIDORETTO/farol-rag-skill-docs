# Capítulo 1 — API base

## Client.request()

```python
client.request(method: str, path: str, *, body: dict | None = None,
               timeout: float = 30.0, retries: int = 2) -> RequestResult
```

- `method`: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`.
- `path`: ex.: `"/v3/projects"` — SEMPRE com prefixo `v3/`.
- `body`: `dict` opcional (serialização camelCase); string JSON foi retirada.
- `timeout`: 30.0s padrão; limite 120.0s (acima: `RequestTimeoutError`).
- `retries`: padrão 2; só re-tenta **5xx/429**.
- retorna `RequestResult` (status_code, data, headers).

## Erros

Veredito: um erro por condição. `RequestTimeoutError` | `RateLimitedError`
(usa `Retry-After` se presente) | `ApiVersionError` (path sem `v3/`).

## Exemplo

```python
from acme_api import Client

client = Client("acme-key-123")
result = client.request("GET", "/v3/projects")
assert result.status_code == 200
```

## Concisão (rules of thumb)

- Nunca confiar no corpo retornado sem checar `status_code` (o client não
  levanta exceção em 4xx exceto 429 — Documento base, pag. 0).
