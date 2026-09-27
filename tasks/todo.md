# Checkpoint Farol 2.0 — 2026-09-27

## Estado atual

- Source de produto `8f06ee7d31fbd4431de63f953ca9f843035c6859`, branch local
  `release/farol-2.0.0-rc.1`; mudanças de evidência/checkpoint ficam em commit
  local posterior. Sem push, tag ou release.
- Gate core: 22/22 etapas, 1050 passed, 12 skips e zero falhas/bloqueios/not_run.
  Bundle local independente: digest
  `6bc0784cf884675f9a4aa2690a11b5217abe3efa4a9d1d32478dc9596a88c464`; wheel
  SHA `9b734abc8f360a9fb55468b029078bd1f55570c19d2f460807b9c40501c19067`.
- `TK-020` permanece `in_progress`/`blocked`; `TK-021` está `verified`.
  Book-to-skill (23/23) e OCR (1/1) passaram no predecessor documental
  `c0859b6`, sem serem atribuídos ao SHA final.
- Full gate RAGFlow: `blocked/not_run`; o usuário confirmou que não há serviço
  ou credenciais. Faltam quatro inputs, o preflight não iniciou integração e o
  daemon Docker está indisponível.
- GitHub: PR #16 segue no head remoto antigo `be40e16`, com `REVIEW_REQUIRED`;
  os 26 checks verdes são de runs antigos. Não há CI para o candidato local.
  `main` requer 13 checks e uma aprovação de code owner; atualizar o PR requer
  autorização de push.
- Backup `farol-v3-backup-2026-09-21` verificado e preservado.

## Próximas ações

1. Quando RAGFlow e os quatro inputs estiverem disponíveis, executar o full
   gate no candidato aprovado então vigente.
2. Com autorização explícita de publicação, atualizar o PR #16 e obter CI do
   SHA exato e aprovação de code owner na `main` protegida.
3. Após gate, CI, revisão e merge, reconstruir o artefato. Tag, release e GA
   exigem autorização própria.

## Evidência canônica

- `specs/farol-2/state.json`
- `specs/farol-2/evidence/rc1-assets-and-v3-backup-20260924.md`
- `specs/farol-2/evidence/release-readiness-hardening-20260924.md`
- `specs/farol-2/tickets/TK-020.md`
- `specs/farol-2/tickets/TK-021.md`
