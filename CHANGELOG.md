# Changelog

## 3.1.0 — 2026-10-06

Additions only; nothing public was removed or renamed.

- **Security**: `get_document` no longer returns prompt-injection blocks;
  `farol connect` only removes files inside the harness's skills folder.

- **Read around a fact**: hits carry `block_id`; new MCP tool `get_context`
  (neighbours or the whole section, within `max_tokens`); `get_document` pages
  with `offset`/`limit`. On the Pro Git book, context costs 1.3k tokens instead
  of 219k for the whole document.
- **Library ranking**: several packages are merged on one scale without
  reordering any package: MRR@5 0.38 → 0.48 and wrong-package hits 40% → 6%
  on the acceptance corpus.
- **Optional local reranker** (`FAROL_RERANKER=<model>`, opt-in) and embedding
  profiles with query/passage prefixes; a model that cannot load is a typed
  error, and `farol doctor --fix` repairs indexes built with another model.
- **Faster distillation**: `farol task claim --n N` hands chapters to parallel
  subagents with leases; the synthesis plan is locked (parallel submits used to
  lose accepted chapters); `farol task plan --task-tokens T` and chapters that
  follow the author's own (Pro Git: 11 real chapters at T=24000).
- **`farol-distill` skill** installed by `farol connect`, and **one router per
  project** (≈260 tokens, backend-neutral) instead of one per source.
- **Courses**: `farol add <folder|playlist> --as course` — one package and one
  skill, lessons in natural order, modules from sub-folders, per-video licenses;
  `--slides` reads the text shown on lecture slides (ffmpeg + OCR, opt-in).
- **Composite skills**: `farol skill compose <name> --from <id> <id>`;
  `--no-skill` sources are indexed for evidence only.
- **Synthesis layer**: `search_knowledge(layer="synthesis"|"both")` searches the
  distilled statements with the blocks that support them.
- **`farol eval`**: self-assessment of any package from its skill lineage, plus
  optional agent-written questions (`farol task plan --questions N`).
- **Digital PDFs with layout** (extra `layout`, `FAROL_PDF_LAYOUT=1`): headings
  and tables kept.
- Acceptance reports context cost, splits (en/pt/validation/broad) and library
  mode; `scripts/reachability_report.py` maps code the journey never runs.

## 3.0.0 — 2026-09-28

Farol 3.0: any source becomes skills and cited evidence for any AI agent,
locally.

- **Everyday journey**: `farol add`, `farol build`, `farol sync`,
  `farol status`, `farol connect` and `farol library`; `farol advanced` keeps
  every 2.0 lifecycle command, and `docops` stays as an alias.
- **Skills written by your own AI**: `farol task next|submit` turns each source
  into an outline, chapter and core tasks; answers are validated for sections,
  block citations, budget, verbatim copying and injected instructions, then
  installed atomically with lineage. Stale chapters are reopened after changes.
- **Local cited evidence**: SQLite FTS5 (BM25) index by default, optional
  multilingual hybrid search (`semantic` extra) with abstention; citations as
  `file:line`, page or video timestamp.
- **MCP server** (`farol mcp`): `search_knowledge`, `get_document`,
  `list_skills`, `get_skill`; read-only, untrusted-content marking, one server
  for a project or a whole library.
- **Connect any agent**: Claude Code, Codex, Cursor, OpenCode or any MCP client,
  reversibly.
- **More sources**: PDF outlines and pages, arXiv papers with declared license,
  WebVTT/SRT, YouTube (captions, chapters, license) and local audio/video via
  speech recognition (`media` extra).
- **Safety**: block-level prompt-injection classification; documents that quote
  attacks keep their evidence, directives never reach the agent.
- **Quality you can check**: real licensed acceptance corpus, value benchmark,
  error catalog with next steps, `farol doctor --fix`, recorded public surface
  and semver policy.
- Distribution renamed to `farol-kit` (the old name is still recognised).
- **Better answers from technical docs**: a sentence that introduces a code
  block ("install the optional extra:") is indexed with that code, so the
  command itself is returned (HTTPX golden 77% → 92%, held-out split 77% → 85%).
- Fixed: headings of documents without H1, PDF text parsed as Markdown, code
  comments taken as scaffold titles, reuse of a damaged index file, repeated
  PDF section titles merged across chapters (two-level outline), refresh of
  skills after headings are restructured, and superseded index files piling
  up on disk (only the active and previous index are kept), and CLI and MCP
  output on Windows code pages (stdio is always UTF-8).

## 2.0.0 release-candidate follow-ups (not published separately)

Preparação adicional da release candidate 2.0, incorporada ao 3.0:

- Isolated candidate wheel builds from ignored `build/lib/` output and added an
  independent check for removed Farol 1.x wheel modules.
- Corrected CI dependency extras, validated extras against `pyproject.toml`,
  removed the obsolete corpus reindex workflow and made the remaining RAGFlow
  gate manual while external credentials are unavailable.
- Updated candidate installation and security guidance to match the current
  GitHub release and private vulnerability reporting settings.
- Updated the pinned artifact action to `actions/upload-artifact` v7.0.1.

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
- This is a pre-release, not a stable GitHub Release; feedback may still change
  the 2.0 public contract before GA.

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
