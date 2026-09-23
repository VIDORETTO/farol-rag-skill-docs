# Changelog

## Unreleased

Mudanças futuras serão registradas aqui antes da próxima release.

## 2.0.0rc1 — 2026-09-22

Release candidate Farol 2.0 (`v2.0.0-rc.1`).

- Replaced the legacy local RAG/vendor surface with the external, opt-in
  RAGFlow `0.27.2` backend and fail-closed integration profiles.
- Added canonical IR, stable locators, governed extractors, real Docling/RapidOCR
  OCR, hierarchical taxonomy, multi-skill synthesis, lineage and global routing.
- Added real RAGFlow lifecycle, mapping, retrieval, rebuild, rollback and cleanup
  evidence, plus dual-run cutover receipts and legacy contraction checks.
- Added release provenance for private originals, candidate/wheel/supply-chain
  verification, acceptance matrix coverage and the final full gate evidence.
- Updated the current README, architecture, security, dependency, operational,
  release and handoff documentation to describe Farol 2.0 accurately.
- Added the first Farol 2.0 release-candidate wheel, candidate bundle,
  supply-chain evidence and cross-platform clean-clone verification.
- This is a pre-release: the public stable compatibility release remains
  `v1.1.0`, and feedback may still change the 2.0 public contract before GA.

## 1.1.0 — 2026-09-04

- Closed post-1.0 reliability tickets 23–29 locally: candidate identity and
  source remeasurement, public-seam coverage, crash-recoverable promotion,
  executed support/bootstrap checks, community assets, named metrics and
  repeatable concurrent RAG stress evidence.
- Added effective transitive-resolution and vendor provenance evidence while
  preserving raw `pip-audit` findings separately from the narrow local Chroma
  residual policy; release still requires the human decision artifact.
- Bound the dependency exception to `chromadb==1.5.9`, retained raw audit
  stdout/stderr/exit evidence, and limited resolver evidence to the lock-rooted
  transitive closure instead of unrelated interpreter packages.
- Removed model-cache bytes from candidate bundles while retaining a verified
  external snapshot manifest/digest, and redacted queries and local paths from
  public evaluation, smoke, doctor and stress reports.
- Made clean-clone verification use a clone-owned isolated environment and made
  concurrent reindex stress distinguish recoverable residue from retained
  successful attempt history.
- Replaced Windows `os.kill(pid, 0)` lease probing with
  `OpenProcess`/`GetExitCodeProcess`; a separate reader can no longer interrupt
  its live writer while checking lease ownership.
- Made supply-chain resolution profile-aware: a core candidate may omit only
  the optional `knowledge-rag` root, while version drift, other missing roots
  and an incomplete explicit RAG profile fail independent verification.
- The package workflow now retains the complete candidate and identity evidence
  as an artifact named with the workflow commit SHA for later review.
- Kept the FastEmbed model cache outside generated packages and preserved
  structured wheel-gate errors when large CLI reports fail.
- Preserved the interpreter selected for candidate wheel and dependency
  evidence when a POSIX virtual environment exposes it through a symlink, and
  made the fail-closed release identity check an explicit manual CI input;
  incomplete `--no-install` bootstrap environments now fall back to the
  invoking interpreter instead of producing a misleading wheel failure.
- Unversioned clean-clone candidates now record CI identity as not observed
  rather than as a false SHA mismatch; release mode still requires a remote
  commit and matching CI evidence.
- Phase receipts keep a positive millisecond floor on coarse monotonic clocks,
  preserving the measured-duration contract across supported operating systems.
- The concurrent RAG stress harness now starts the reviewed vendored backend,
  matching the runtime used by indexing and MCP evaluation instead of the
  independently installed package.
- Candidate wheel builders now pin `SOURCE_DATE_EPOCH=315532800`, making
  repeated builds of the same source tree byte-identical for release-asset
  comparison while remaining valid for ZIP timestamps on Windows.
- Hardened vendored RAG search against transient Chroma rows without metadata
  during concurrent reindex; uncitable hits are discarded instead of failing
  the MCP request.
- Added an explicit authenticated GitHub settings checklist and kept commit,
  push, tag and release operations outside all local automation.
- Added the `plan`/`apply`/`inspect` operation seam with real create/update/dry-run
  lifecycle semantics, staged transactional promotion, resumable phase receipts,
  and a recoverable single-writer lease.
- Added executable contracts for manifests, handoffs, Golden sets, validation,
  plans, outcomes, results, evaluations and review-required Golden candidates.
- Distinguished scaffold, enriched-skill, corpus, indexed, evaluated and release
  readiness using observed evidence rather than editable manifest claims.
- Added resolver providers, explicit runtime provenance, redacted MCP diagnostics,
  named retrieval adapters, and MCP-backed evaluation controls.
- Added a normative support matrix, contract/release gates, immutable GitHub
  Actions revisions, and installed-wheel create/validate/evaluate coverage.

### Conteúdo de verificação e distribuição

- Hardened candidate auditing for nested runtime artifacts, binary paths,
  structured token canaries and exact Git candidate sets.
- Added deterministic MCP runtime contracts, public root Python operations,
  one-way operation primitives, snapshot revalidation and observable residue
  cleanup.
- Added installed-wheel provenance, reproducible supply-chain evidence, SPDX
  SBOM, lock/digest verification, vendor/model provenance and the explicit
  four-CVE Chroma residual-risk policy.
- Added profile-based support claims, workflow drift checks, community policy
  files and the unpublished candidate bundle/verification tools.

## 1.0.0 — 2026-08-29

- Primeira versão estável do protocolo DOCOPS para fontes locais, web e
  repositórios.
- Pacotes gerados agora são autossuficientes, com configuração MCP relativa,
  validação de divergência, harness manifest e smoke test do wheel instalado.
- Adicionados bootstrap multiplataforma, auditoria de configuração/release,
  fixtures sintéticas e documentação de integração com harnesses externos.
- Atualizado o conjunto direto de ferramentas para `pytest==9.1.1`,
  `ruff==0.12.7`, `pip-audit==2.10.1`, `setuptools==84.0.0` e bootstrap com
  `pip==26.2.1`/`setuptools==84.0.0`.
- Adicionada auditoria de dependências com allowlist estreita e documentada
  para os quatro CVEs sem correção conhecida do ChromaDB; outros achados
  permanecem bloqueadores.
- Corrigido o fallback YAML para comentários inline, tornando o doctor
  funcional em clones limpos sem PyYAML.
- Corrigidos os nomes das métricas do avaliador para refletirem qualquer
  `--top-k` válido.
- Tornado o smoke MCP resistente a timeout, EOF prematuro, stderr cheio e
  encerramento de processo sem mascarar o erro original.
- Alinhado o `serverInfo` vendorizado com `knowledge-rag==4.8.5` e feito o
  transporte HTTP/SSE recusar inicialização sem bearer token.
- Reforçadas as aquisições externas contra DNS rebinding (inclusive com IPs
  fixados no Git), redirects, submódulos, protocolo `file`, prompts interativos
  e clones acima do limite.
- Adicionados testes de regressão para SSRF/TOCTOU, repositório remoto,
  autenticação bearer, auditoria de dependências e fluxo de erro do smoke MCP.
- Mantido o perfil padrão local `stdio`; corpus adquirido, índices, caches,
  tokens e ambientes virtuais continuam fora da publicação.
