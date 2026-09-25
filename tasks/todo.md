# Checkpoint Farol 2.0 — 2026-09-25

## Estado atual

- Branch `release/farol-2.0.0-rc.1`; as alterações de prontidão foram consolidadas em commit local limpo, sem push. O bundle final ainda será construído após fechar este recibo.
- `TK-020` está `in_progress`; `TK-021` foi revalidado e está `verified`. Builder/verificador da wheel, workflows e claims públicos corrigidos localmente; regressões focadas: `9 passed`.
- Gate core passou em commit limpo `98d2a1df0364ab79d82852bca14308d6dc44a22a`: 22/22 etapas, 1050 pass, 12 skips, zero falhas/bloqueios/not_run e zero entradas no worktree. Isso não é o full gate. O bundle final ainda precisa ser gerado e verificado contra o source consolidado; full gate segue bloqueado pelos inputs RAGFlow e CI remota não foi executada porque o push exige autorização explícita.
- Revisão manual Standards/Spec registrou uma claim Python ampla demais, alinhou-a à matriz suportada 3.11–3.13 e não deixou findings locais abertos.
- Full gate RAGFlow `blocked`: o usuário confirmou que não há serviço nem credenciais agora; faltam quatro inputs listados em `state.json`.
- GitHub continua sem tag/release RC ou release estável. Private vulnerability reporting foi habilitado e confirmado por API nesta retomada.
- `main` tem proteção (13 checks, uma aprovação de code owner); a branch RC não está protegida. Para a publicação, usar PR para `main` ou decidir explicitamente proteção da branch RC.
- Backup `farol-v3-backup-2026-09-21` verificado e preservado.

## Próximas ações

1. Provisionar serviço/inputs RAGFlow e rodar o full gate no SHA limpo local.
2. Usar PR para `main` protegida (ou obter decisão de proteger a branch RC) e pedir autorização explícita antes do push para CI remoto; release/tag/GA continuam decisões separadas.

## Evidência canônica

- `specs/farol-2/state.json`
- `specs/farol-2/evidence/rc1-assets-and-v3-backup-20260924.md`
- `specs/farol-2/evidence/release-readiness-hardening-20260924.md`
- `specs/farol-2/tickets/TK-020.md`
- `specs/farol-2/tickets/TK-021.md`
