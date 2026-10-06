# Capítulo 7 — Testes

Fonte: fastapi-docs/tutorial/testing.md, advanced/async-tests.md, advanced/testing-dependencies.md, how-to/testing-database.md

## Padrão

- `TestClient(app)` (httpx sync) p/ endpoints sync; `AsyncClient`(patched)
  nos tests async.
- **Override de dependência é a única via para isolar infra**:
  `app.dependency_overrides[get_db] = fake_db`.
- `tmp_path` p/ SQLite; subir app como contexto pt no test (`with TestClient(app)`).

## Checklist mental ao escrever teste

1. Faça override de TODA dependência de IO (DB/HTTP/redis).
2. Teste tipos intencionalmente: inputs inválidos → 422 do Pydantic.
3. Teste o CONTRATO via OpenAPI (`/openapi.json`) p/ catch drift.
