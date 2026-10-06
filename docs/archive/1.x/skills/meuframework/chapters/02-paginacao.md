# Capítulo 2 — Paginação

- `page` 1-indexado (padrão 1) e `page_size` (padrão 50, máx. 500).
- Respostas paginadas: `total_items` + `has_next`.
- `iter_paginated(path)`: acompanha `has_next` sozinho, no máximo **20 páginas**.

## Guardrails

- `page_size` > 500: o cliente não valida? A doc diz aceito até 500 — não
  pedir mais do que isso (501+ é uso indevido).
- Laços infinitos de paginação são evitados pelo teto de 20 páginas.
