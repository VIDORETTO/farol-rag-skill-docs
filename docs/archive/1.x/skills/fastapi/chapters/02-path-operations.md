# Capítulo 2 — Path operations

Fonte: fastapi-docs/tutorial/path-operations, path-params*.md, query-params*.md, response-model.md, response-status-code.md, path-operation-configuration.md, advanced/*.md

## Estrutura

```python
@app.get("/items/{item_id}", status_code=200,
         response_model=ItemOut, response_model_exclude_unset=True)
async def read_item(item_id: int, q: str | None = Query(None, max_length=10)):
    ...
```

| Aspecto | Devido a | Convenção |
|---|---|---|
| Order | roteamento método/path; order matters | definir específicas antes de `/{param}` wildcard |
| status_code | resposta; default 200 (POST 201) | definir no decorator; `status.HTTP_...` |
| response_model | filtro+serialização de saída | para dict/ORM, SEMPRE via decorator |
| metadata | openapi (`summary`, `description`, `tags`) | usar p/ section na doc |
| advanced | `response_change-status-code`, `additional-responses`, `callbacks` | caso a caso |

## Query/path/header/cookie params

| Tipo de param | Declaração |
|---|---|
| path | `item_id: int` (path prefixo) — precisa `int` p/ converter |
| query | `q: str | None = None`; validações via `Query(...)`/`Query(None, ...)` |
| header | `x_token: str | None = Header(None)`; `Header(convert_underscores=True)` |
| cookie | `lang: str = Cookie(...)` |
| models | `query-param-models`, `header-param-models`, `cookie-param-models` (reuse Pydantic) |

## Regra OWASP-ish de saída

Filhos de path que retornam dados sensíveis: SEMPRE `response_model` declarado
para nunca vazar campos extras (não confiar no endpoint retornar "exatamente o
objeto DB").
