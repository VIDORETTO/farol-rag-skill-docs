# Capítulo 1 — Design de tipos (type-driven)

Fonte: fastapi-docs/features.md, fastapi-docs/python-types.md, fastapi-docs/tutorial/body*.md, fastapi-docs/tutorial/extra-models.md

## Princípio

A assinatura da função ESCODE o contrato: FastAPI (via Pydantic) faz parse,
validação, serialização, JSON Schema e filtering a partir dos type hints.

- Parâmetros de modelo → body (Pydantic `BaseModel`).
- Tipos primitivos e `Query()`/`Path()` → query/path params.
- Sempre usar modelos tipados; hoje Pydantic v2 (migração de v1: `pydantic-settings`, `.model_dump()`, `ConfigDict`).
- `Optional`/`None` = campo opcional; valores default nos params.

## Padrões

| Intenção | Padrão |
|---|---|
| Body de entrada | class Item(BaseModel): ... ; def f(item: Item) |
| Mais de um body | parâmetro body `{ base: Model, ... }` (dict) ou `Body(embed=True)` |
| Validar string | `min_length`, `max_length`, `pattern` no campo |
| Entrada/listas aninhadas | modelos aninhados; `List[Model]` |
| Outras entidades listáveis | `extra-models`, `encoder.md` (jsonable_encoder) |

## Regra olho do contrato

"Se eu mudar o tipo, o contrato (docs/testes) muda junto" — não mantenha
validações paralelas em strings/if dentro do endpoint.
