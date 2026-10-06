# Golden set — FastAPI

Este conjunto mede a camada RAG e orienta a validação da skill roteadora. O
corpus ativo é o snapshot local da documentação oficial FastAPI em
`documents/fastapi-docs/`.

- Perguntas conceituais: respondidas pela skill `docs/archive/1.x/skills/fastapi/`.
- Perguntas factuais/literais: respondidas pelo RAG e acompanhadas de citação
  `source#secao`.
- Casos executáveis: `golden-set/test-cases-fastapi.json` (14 casos).

## Como rodar a avaliação

```powershell
python scripts\evaluate_golden.py --cases golden-set\test-cases-fastapi.json
```

O script normaliza os caminhos relativos dos casos para o `source` absoluto
devolvido pelo servidor e imprime MRR@5, Recall@5 e o rank de cada caso.
Neste piloto, a avaliação usa busca híbrida RRF com os aliases BM25 de
`config.yaml`; o reranker está desligado porque a medição comparativa foi
melhor sem ele.

## 1. Casos factuais e resultado final

| ID | Consulta | Fonte esperada | Rank | RR |
|---|---|---|---:|---:|
| F01 | first steps minimal app FastAPI | `tutorial/first-steps.md` | 1 | 1,0000 |
| F02 | response_model filter output data | `tutorial/response-model.md` | 1 | 1,0000 |
| F03 | OAuth2 password JWT token user | `tutorial/security/oauth2-jwt.md` | 1 | 1,0000 |
| F04 | pydantic settings BaseSettings env var | `advanced/settings.md` | 1 | 1,0000 |
| F05 | deploy docker container uvicorn | `deployment/docker.md` | 2 | 0,5000 |
| F06 | TestClient httpx override dependency | `tutorial/testing.md` | 1 | 1,0000 |
| F07 | handling errors exception handler | `tutorial/handling-errors.md` | 1 | 1,0000 |
| F08 | middleware CORS add_middleware | `tutorial/middleware.md` | 5 | 0,2000 |
| F09 | background tasks BackgroundTasks response | `tutorial/background-tasks.md` | 3 | 0,3333 |
| F10 | extend openapi schema metadata custom docs | `how-to/extending-openapi.md` | 1 | 1,0000 |
| F11 | body multiple params embed model | `tutorial/body-multiple-params.md` | 1 | 1,0000 |
| F12 | features based on open standards JSON Schema | `features.md` | 1 | 1,0000 |
| F13 | sql database SQLAlchemy sessions dependency | `tutorial/sql-databases.md` | 1 | 1,0000 |
| F14 | numeric validations path query | `tutorial/path-params-numeric-validations.md` | 1 | 1,0000 |

Resultado da execução de 2026-08-28:

| Métrica | Meta | Resultado | Situação |
|---|---:|---:|---|
| MRR@5 | ≥ 0,70 | **0,8595** | ✅ |
| Recall@5 | ≥ 0,85 | **1,0000** (14/14) | ✅ |
| Precision@5 | — | não exposta pelo retorno desta versão do servidor | n/a |
| Core `docs/archive/1.x/skills/fastapi/SKILL.md` | ≤ 4.000 tokens | **1.280** (`cl100k_base`) | ✅ |

## 2. Validação conceitual/manual da skill e do router

| ID | Pergunta | Capítulo esperado | Verificação |
|---|---|---|---|
| P01 | Por que tipos Pydantic são a fonte de verdade? | `chapters/01-type-driven.md` | ✅ regra também resumida no core |
| P02 | Quando usar `response_model`? | `chapters/02-path-operations.md` | ✅ filtro/contrato de saída |
| P03 | Como compor dependências e sobrescrevê-las em testes? | `chapters/03-dependencies.md` | ✅ `Depends` + `dependency_overrides` |
| P04 | Como pensar em OAuth2, JWT e scopes? | `chapters/04-security.md` | ✅ racional no core; detalhe no RAG |
| P05 | Quando usar `async`, `def` e `BackgroundTasks`? | `chapters/05-async.md` | ✅ regra de IO/CPU/pós-resposta |
| P06 | Como tratar settings, env vars e Docker? | `chapters/06-config-deploy.md` | ✅ configuração fora do código |
| P07 | Como testar uma aplicação FastAPI? | `chapters/07-testing.md` | ✅ TestClient, HTTPX e overrides |

O router exige `search_knowledge` para fatos literais, citação inline do
`source`, uso das duas camadas em dúvidas ambíguas/alto risco e declaração
explícita de divergência. A skill passou o validator Claude sem warnings.

## 3. Histórico de medições

| Data | Corpus/configuração | MRR@5 | Recall@5 | Observação |
|---|---|---:|---:|---|
| 2026-08-28 | acme-api-client (dev) | 1,0000 | 1,0000 | baseline histórico |
| 2026-08-28 | dev + v3.4.0 | 0,9500 | 1,0000 | baseline histórico pós-update |
| 2026-08-28 | FastAPI + aliases BM25 + reranker ligado | 0,6690 | 0,9286 | medição intermediária; abaixo da meta de MRR |
| 2026-08-28 | FastAPI + aliases BM25 + reranker desligado | **0,8595** | **1,0000** | configuração final do piloto |
| 2026-09-03 | FastAPI official docs snapshot + hybrid search, reranker desligado | **0,9048** | **1,0000** | 14/14 casos; gate CLI passou com limiares MRR 0,70 e Recall 0,85 |

Após mudanças no corpus, repetir o comando, registrar os números aqui e
reavaliar se a meta de MRR ou Recall deixou de ser atendida.
