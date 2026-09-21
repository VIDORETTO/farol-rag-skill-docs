# Política canônica de contratos

Este documento é normativo para os envelopes JSON em `schemas/`. A árvore
`docops/schemas/` é uma cópia distribuída, reproduzida mecanicamente por
`python scripts/sync_schemas.py --write`; nenhuma alteração manual deve ser
feita nela.

## Nome público e compatibilidade

O produto se chama **Farol**. O identificador técnico da distribuição publicada
em `v1.1.0` continua sendo `consulta-documentacao`, e o namespace Python/CLI
`docops` continua disponível como compatibilidade. A migração normativa para o
contrato Farol 2.0 já foi executada nos tickets de `specs/farol-2/`; a
compatibilidade 1.x permanece onde foi explicitamente preservada, enquanto
schemas e superfícies contraídos exigem a evidência registrada no ticket.

## Versionamento

Todo schema exige o campo `schema_version` e declara a versão aceita em
`properties.schema_version.const`. Uma alteração que muda a interpretação de
um campo, remove um campo, reduz valores aceitos ou altera uma garantia de
segurança exige nova versão do envelope e uma janela de migração explícita.

## Compatibilidade expand-contract

1. Expandir primeiro: adicionar campos e comportamentos compatíveis, mantendo
   aliases e leitores capazes de consumir a versão anterior quando isso não
   enfraquecer uma proteção.
2. Validar ambas as versões durante a janela de migração e registrar a política
   de leitura/escrita no ticket correspondente.
3. Remover somente após a janela de migração, com evidência de uso zero e uma
   decisão editorial registrada.

Segurança, privacidade, autorização e revogação não podem ser tornadas
opcionais para preservar compatibilidade. Nesses casos, a mudança deve falhar
fechado (fail closed) ou introduzir uma versão nova; nunca aceitar um envelope
antigo que contorne o gate.

## Fonte e gates

`schemas/` é a única fonte normativa. `scripts/sync_schemas.py --check`
compara bytes canônicos e distribuídos; `scripts/check_contracts.py --json`
valida envelopes positivos/negativos, versão, política e a cópia instalada.
`scripts/check_documentation.py --json` verifica comandos, links, tickets
concluídos e evidência de gates atuais. Documentos em
`docs/continuous-knowledge/` são arquivo histórico e não definem o contrato
da consolidação.
