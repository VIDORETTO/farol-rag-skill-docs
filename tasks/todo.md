# Checkpoint Farol 2.0 — 2026-09-27

## Estado atual

- Branch `release/farol-2.0.0-rc.1`; source local limpo `129d517a899e5ed39b1d48666ae736de246e09a6`, sem push. Core 22/22 e bundle final auditável verificados; digest `e3bd485758d4ecf751e5c6e740b678f410f5d8f74eb5cf164199d53a0ff46017`.
- `TK-020` está `in_progress`; `TK-021` foi revalidado e está `verified`. Builder/verificador da wheel, workflows e claims públicos corrigidos localmente; regressões focadas: `9 passed`.
- Gate core no source do bundle: 22/22 etapas, 1050 pass, 12 skips, zero falhas/bloqueios/not_run; relatório SHA `ccf3b1c5…`. Bundle: `artifacts/farol-2.0.0-rc.1-129d517-final-audit-20260926`; verificação independente sem erros; wheel de 393132 bytes, SHA `34cb4aa8…`. O full gate segue bloqueado pelos inputs RAGFlow.
- Book-to-skill e OCR também passaram isoladamente no worktree limpo do mesmo SHA. OCR: 1 teste, sem rede, Docling 2.129.0/ONNX Runtime 1.30.0; book-to-skill: duas skills, cinco claims de lineage, outputs temporários não retidos. Os recibos/hash estão em `state.json` e na evidência de prontidão.
- Revisão manual Standards/Spec registrou uma claim Python ampla demais, alinhou-a à matriz suportada 3.11–3.13 e não deixou findings locais abertos.
- Full gate RAGFlow `blocked`: o usuário confirmou que não há serviço nem credenciais agora; faltam quatro inputs listados em `state.json`.
- Revalidação 2026-09-27: preflight `blocked/missing_external_inputs` antes do subprocesso; variáveis ausentes em Process/User/Machine e daemon Docker indisponível. Recibo e SHA em `state.json`.
- GitHub continua sem tag/release RC ou release estável. Private vulnerability reporting está habilitado. PR #16 permanece aberto com head remoto antigo (`be40e16`), checks antigos verdes e `REVIEW_REQUIRED`; atualizar o head requer push autorizado.
- Snapshot GitHub 2026-09-27: PR #16 está `BLOCKED`/`REVIEW_REQUIRED`; 26/26 checks verdes em dois runs de 23/09 sobre o head antigo. Nenhum check para a branch local, que estava 8 commits à frente no instante da consulta.
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
