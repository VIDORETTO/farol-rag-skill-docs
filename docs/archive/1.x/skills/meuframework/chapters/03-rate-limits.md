# Capítulo 3 — Rate limits

- Free: 100 req/min — Enterprise: 1.000 req/min.
- HTTP 429 → `RateLimitedError`; se vier `Retry-After`, o respeto é obrigatório
  para não agravar (backoff deve considerar o header).
- Re-tentativa em 429 contém o número de tentativas (`retries`), e apenas se
  houver retries restantes — padrão 2.

## Regra rápida

"Recebeu 429, espere o Retry-After (ou 1s × tentativa se ausente) e tente de
novo, até `retries` esgotarem."
