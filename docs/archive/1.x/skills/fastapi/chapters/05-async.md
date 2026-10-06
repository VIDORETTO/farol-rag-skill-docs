# Capítulo 5 — Async & performance

Fonte: fastapi-docs/async.md, advanced/websockets.md, advanced/stream-data.md, advanced/events.md, tutorial/background-tasks.md, tutorial/server-sent-events.md

## Regras

- `async def` → event loop; `def` → threadpool. FastAPI espera coroutine/timeout.
- Chamadas I/O externo (DB async, HTTP) devem ser async quando disponíveis.
- CPU-bound vs IO-bound: IO → async def; CPU → `def` (threadpool) ou workers.
- `BackgroundTasks` é p/ pós-resposta rápido; heavy job → fila externa (Celery/RQ);
  com `dependencies` para atualizar o estado do sistema.
- WebSocket: `await websocket.receive_text()/send_json`; SSE: `StreamingResponse`;
  `stream-json-lines` p/ JSON streaming.

## Eventos lifecycle (deprecated) → use lifespan

`@app.on_event("startup"/"shutdown")` foi deprecado. Usar:

```python
from contextlib import asynccontextmanager
@asynccontextmanager
async def lifespan(app): ...
app = FastAPI(lifespan=lifespan)
```
