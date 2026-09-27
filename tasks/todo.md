# Checkpoint Farol 2.0 — 2026-09-27

## Estado atual

- Source de documentos públicos `eb533951fc8feaa2a469a3d491fa381501e22f08`,
  branch `release/farol-2.0.0-rc.1`; o recibo local atual registra apenas
  evidência/checkpoint. Sem push, tag ou release.
- Gate core: 22/22 etapas, 1050 passed, 12 skips e zero falhas/bloqueios/not_run;
  relatório SHA `b1558cbc5d5ee648c41a5bc7cad53a34ff7e17e85401f17cdff0a1b7de34cd77`.
  Bundle independente: digest
  `23d9c54cc582d46171f437669ebe90ce2f5e9fd89756a51c01e4db188874351d`; wheel
  SHA `a5b42459513fdccd880ab373469e040253fbe40a3a1e40272e311bab6fb02316`.
- `TK-020` permanece `in_progress`/`blocked`; `TK-021` está `verified`.
  Book-to-skill (23/23) e OCR (1/1) passaram no predecessor documental
  `c0859b6`, sem serem atribuídos ao SHA final.
- Full gate RAGFlow: `blocked/not_run`; o usuário confirmou que não há serviço
  ou credenciais. Faltam quatro inputs, o preflight do source `eb53395` não
  iniciou integração e o daemon Docker está indisponível.
- GitHub: PR #16 segue no head remoto antigo `be40e16`, com `REVIEW_REQUIRED`;
  os 26 checks verdes são de runs antigos. Não há CI para `eb53395`.
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
