# AGENTS.md — Farol

## Escopo do projeto

Farol transforma documentação em skill, corpus RAG, roteador e artefatos
DOCOPS. O piloto atual usa FastAPI; a evolução Farol 2.0 é governada por
`specs/farol-2/`.

## Fontes de verdade

- Use os tickets em `specs/farol-2/tickets/` como unidade canônica de trabalho.
- Use `specs/farol-2/state.json`, `backlog.md` e `todo.md` para o estado agregado.
- Mantenha `tasks/todo.md` como checkpoint curto de retomada, não como diário.
- Preserve mudanças preexistentes do usuário e não altere arquivos fora do
  escopo necessário.

## Invariantes

- Não versione `documents/`, `.venv*`, `data/`, `models_cache/`,
  `.rag_state.json`, credenciais, tokens, corpus adquirido ou artefatos gerados.
- Confirme licença e direitos antes de incluir qualquer fonte distribuível.
- Respostas e avaliações factuais devem manter citações verificáveis
  (`path#secao`, `path:linha` ou locator canônico equivalente).
- Transporte HTTP/SSE exige autenticação por bearer token; `stdio` local é o
  padrão seguro.
- Mudança do perfil de embedding exige rebuild completo e evidência nova.
- Preserve compatibilidade de `docops`, schemas e formatos distribuídos, salvo
  quando um ticket autorizar explicitamente uma quebra.
- Ausência de serviço, credencial, runtime ou harness externo é `blocked` ou
  `not_run`, nunca sucesso.
- Não faça cutover, contração de legado, publicação, tag, release, reindexação
  de corpus real ou alteração de infraestrutura externa sem autorização e
  evidência exigidas pelo ticket.
- No Windows, encerre somente o PID exato cuja linha de comando pertença a este
  projeto; nunca finalize processos Python em massa.

## Execução

- Leia apenas os contratos, tickets e código relevantes à tarefa atual.
- Prefira a menor mudança coerente que resolva a causa raiz e mantenha os seams
  públicos.
- Use subagentes apenas quando houver frentes realmente independentes; não são
  obrigatórios.
- Registre resultados duráveis no ticket/evidência canônicos. Não acumule
  histórico operacional em `AGENTS.md` ou `tasks/todo.md`.

## Verificação proporcional

- Comece por testes direcionados ao comportamento alterado.
- Amplie para lint, contratos, documentação e regressões relacionadas conforme
  o risco.
- Execute a suíte ampla uma vez quando a mudança justificar esse custo.
- Não repita uma verificação sem mudança relevante, nova hipótese de diagnóstico
  ou exigência explícita do gate.
- Registre falhas, skips, bloqueios externos e comandos realmente observados sem
  convertê-los em aprovação.
