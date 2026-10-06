# Capítulo 3 — Dependências (DI)

Fonte: fastapi-docs/tutorial/dependencies/*.md, advanced/*.md

## Onde usar

- Auth (current user), DB (session), settings, "bateria" de contexto por request.
- Reuso em cadeia: subdependências dentro de dependências compõem a DI sem
  reabrir o "parafuso do contrato" em cada endpoint.

```python
async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/items")
def list_items(db: Session = Depends(get_db)): ...
```

## Padrões

| Padrão | Quando |
|---|---|
| `def dep() -> X` | caso simples, reuso |
| `yield` em dependência | contexto try/finally (DB, recursos) |
| `dependencies=[Depends(x)]` | side-effect sem usar retorno |
| `@app.dependency_overrides[get_db]` | testes (ver capítulo 7) |
| dependência "por classe" (`CachedSession`) | estado por request |

## Segurança da DI

Dependência deve ser a única fonte de recurso no handler. NUNCA abrir conexões
dentro do path operation e passar manualmente (quebra teste/override).
