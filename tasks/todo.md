# Checkpoint Farol 2.0 — 2026-09-26

## Estado atual

- Branch `release/farol-2.0.0-rc.1`; source local limpo `cbee436d5e42aeb81f7c27006f65406e724fa4a9`, sem push. Core 22/22 e bundle final auditável verificados; digest `023d4ef786f8d2f43ae9d5c90672a58085a0b8f3db83fb7919417dea79ce387b`.
- `TK-020` está `in_progress`; `TK-021` foi revalidado e está `verified`. Builder/verificador da wheel, workflows e claims públicos corrigidos localmente; regressões focadas: `9 passed`.
- Gate core no source do bundle: 22/22 etapas, 1050 pass, 12 skips, zero falhas/bloqueios/not_run; relatório SHA `e01c3eca…`. Bundle: `artifacts/farol-2.0.0-rc.1-cbee436-final-audit-20260926`; verificação independente sem erros; wheel de 392925 bytes, SHA `c018bd60…`. O full gate segue bloqueado pelos inputs RAGFlow.
- Revisão manual Standards/Spec registrou uma claim Python ampla demais, alinhou-a à matriz suportada 3.11–3.13 e não deixou findings locais abertos.
- Full gate RAGFlow `blocked`: o usuário confirmou que não há serviço nem credenciais agora; faltam quatro inputs listados em `state.json`.
- GitHub continua sem tag/release RC ou release estável. Private vulnerability reporting está habilitado. PR #16 permanece aberto com head remoto antigo (`be40e16`), checks antigos verdes e `REVIEW_REQUIRED`; atualizar o head requer push autorizado.
- `main` tem proteção (13 checks, uma aprovação de code owner); a branch RC não está protegida. Para a revisão, atualizar o PR #16 para `main`; seu head está stale e atualizar exige push autorizado.
- Backup `farol-v3-backup-2026-09-21` verificado e preservado.

## Próximas ações

1. Quando serviço e quatro inputs RAGFlow estiverem disponíveis, rodar o full
   gate no source candidato registrado em `state.json`.
2. Após autorização explícita de push, atualizar o head do PR #16 e aguardar CI
   do SHA exato e aprovação de code owner na `main` protegida.
3. Depois do gate e merge aprovados, reconstruir o artefato a partir do source
   aprovado; tag, release e GA continuam decisões separadas.

## Evidência canônica

- `specs/farol-2/state.json`
- `specs/farol-2/evidence/rc1-assets-and-v3-backup-20260924.md`
- `specs/farol-2/evidence/release-readiness-hardening-20260924.md`
- `specs/farol-2/tickets/TK-020.md`
- `specs/farol-2/tickets/TK-021.md`
