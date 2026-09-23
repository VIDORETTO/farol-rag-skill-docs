# ADR 0002 — Usar IR canônica como autoridade compartilhada

## Contexto

No Farol 1.x, o normalizador reduz fontes a texto/Markdown antes da indexação,
enquanto a síntese rica pode reler a origem pelo harness. Se RAGFlow recebesse
somente esse texto, suas capacidades de layout, tabela, OCR e coordenadas seriam
perdidas. Se cada consumidor interpretasse o original separadamente, skill e
RAG poderiam divergir sem explicação.

## Decisão

Toda fonte aceita produzirá uma representação intermediária canônica,
versionada e independente de backend. Taxonomia, síntese conceitual, lineage,
chunking e indexação derivarão da mesma revisão da IR.

Originais, direitos e revisões permanecem sob autoridade do Farol. IDs internos
do RAGFlow são mapeamentos reconstruíveis e nunca identidade canônica.

## Motivo

A IR concentra conversão, qualidade e proveniência em uma Interface profunda.
Corrigir um extractor corrige todos os consumidores; revogar uma fonte invalida
skills e índice pelo mesmo lineage.

## Consequências

- A IR precisa representar blocos, hierarquia, tabelas, código, página, slide,
  célula, bounding box, timestamp, idioma, confiança e degradação.
- Adapters podem produzir capacidades diferentes, mas nunca omitir silenciosamente
  a fidelidade alcançada.
- Migrações de schema da IR usam expand–contract e invalidam derivados afetados.

## Alternativas rejeitadas

- Usar Markdown como IR universal: simples, mas perde estruturas essenciais.
- Deixar RAGFlow como autoridade documental: cria lock-in e enfraquece rollback.
- Parsing independente para skill e RAG: duplica custo e permite contradição.
