# Release 1.1.0

The end-to-end plan from candidate closure through controlled publication,
post-release canary, rollback and progressive publicity is in
[`PRODUCTION-PUBLICITY-PLAN.md`](PRODUCTION-PUBLICITY-PLAN.md). This document
remains the technical gate runbook referenced by that plan.

The release notes are in
[`RELEASE-NOTES-1.1.0.md`](RELEASE-NOTES-1.1.0.md) and were reviewed against
the final public assets for the GitHub Release.

The current release evidence and post-release handoff are recorded in
[`RELEASE-READINESS-2026-09-04.md`](RELEASE-READINESS-2026-09-04.md). The
post-release canary/rollback handoff template is
[`POST-RELEASE-HANDOFF-TEMPLATE.md`](POST-RELEASE-HANDOFF-TEMPLATE.md).

The controlled `1.1.0` publication is the
[GitHub Release v1.1.0](https://github.com/VIDORETTO/agent-knowledge-kit/releases/tag/v1.1.0);
this runbook remains the technical procedure for future candidates.

The current publication verdict is recorded in
`docs/GITHUB-PUBLICATION-AUDIT-2026-09-02.md`. It supersedes the historical
2026-09-01 audit for release decisions; the release identity, dependency
decision and remote CI evidence are recorded separately in the readiness log.

This is the executable runbook for the post-1.0 candidate. Every gate must
refer to the same Git `HEAD` and candidate digest recorded by
`candidate-manifest.json`. The runbook produces local evidence only; it never
commits, tags, pushes, publishes or creates a release.

For the consolidation, the canonical local orchestration is the sequential
runner below. It creates one unique ignored workspace per stage, captures the
exact redacted commands and denominators, fails closed on required gates, and
uses the reviewed vendor plus the selected interpreter for the temporary RAG
stage:

```text
python scripts/run_release_gates.py --root . --profile full --json
```

The final integration decision is recorded without promotion by:

```text
python scripts/prepare_candidate.py --root . --output artifacts/candidate --profile core
```

This report compares `origin/main` and `origin/feat/continuous-knowledge`,
records feature provenance and residual risks, and keeps promotion blocked until
a human authorization record, a clean commit and matching CI evidence exist.

Run the gates in this order from a clean clone or the explicitly selected
working-tree candidate:

```text
python scripts/bootstrap.py --dev --rag
python -m docops doctor --json
python -m pip check
python -m pip_audit --requirement requirements.lock --format json
python scripts/audit_dependencies.py --requirements requirements.lock --local --strict --evidence-dir artifacts/dependency-audit
python scripts/check_support_matrix.py --json
python scripts/validate_workflows.py --json
python scripts/check_contracts.py --json
python scripts/check_public_seams.py --json
python -m pytest -q
python -m ruff check docops tests scripts
python -m ruff format --check docops tests scripts
python -m compileall -q docops tests scripts
git diff --check
python scripts/verify_clean_clone.py --bootstrap
python scripts/verify_wheel.py --core
python scripts/verify_wheel.py --require-rag
SOURCE_DATE_EPOCH=315532800 python -m pip wheel --no-deps --wheel-dir dist .
python scripts/generate_supply_chain.py --root . --wheel dist/<wheel>.whl --output artifacts/supply-chain --profile core
python scripts/verify_supply_chain.py --root . --evidence artifacts/supply-chain
python scripts/audit_release.py --tracked-only --json
python -m docops run documents/fixtures/acme-docs --output artifacts/acme --slug acme --license MIT --index-rag
python -m docops validate artifacts/acme --json
python -m docops evaluate --package artifacts/acme --cases golden-set/test-cases-fixture.json --adapter mcp --runtime-root . --json
python scripts/run_release_gates.py --profile ragflow --json
python scripts/run_release_gates.py --profile ragflow --json
python scripts/audit_release.py --candidate --json
python scripts/prepare_candidate.py --root . --output artifacts/candidate-1.1.0 --profile core
python scripts/verify_candidate.py --root artifacts/candidate-1.1.0
python scripts/verify_candidate.py --root artifacts/candidate-1.1.0 --source-root .
python scripts/verify_candidate.py --root artifacts/candidate-1.1.0 --source-root . --release
```

The raw `pip-audit` command is intentionally separate from the policy wrapper.
The wrapper reruns both the lock and local-environment audits and preserves their
unaltered stdout, stderr and exit codes under `artifacts/dependency-audit/`.
Its narrow Chroma exception is not an assertion that the raw audit is clean.
The final `--release` verification is expected to fail closed until the human
CVE decision, remote ref and same-SHA CI evidence are all present.

The optional RAG profile runs in its own environment. It must execute
`run --index-rag` → `validate` → `evaluate --adapter mcp`; a missing optional
runtime is recorded as `SKIPPED [rag_optional_unavailable]`, while a requested
RAG gate fails. The wheel gate sets `DOCOPS_REQUIRE_WHEEL_RAG=1` when RAG is
part of the candidate and must report the installed-package provenance.

The Farol 2.0 RAGFlow profile is separate from that legacy `full` profile. It
repeats the provider-free core gates and appends the fail-closed RAGFlow and
local OCR contract spikes:

```text
python3.13 -m pip install --editable '.[dev,formats,ragflow,ocr]'
python scripts/run_release_gates.py --root . --profile core --json
python scripts/run_release_gates.py --root . --profile ragflow --json
```

The RAGFlow profile requires `DOCOPS_RAGFLOW_ENDPOINT`,
`DOCOPS_RAGFLOW_TOKEN`, `DOCOPS_RAGFLOW_IMAGE_DIGEST` in
`repository@sha256:<64 hex>` form, `DOCOPS_RAGFLOW_SDK_VERSION=0.27.2`, and
an operator-provisioned service. Missing inputs fail the required profile with
a redacted blocker report; they are never counted as a successful skip.

The OCR stage pins `docling==2.129.0` and `onnxruntime==1.30.0`, renders a
synthetic scanned PDF, and proves extracted text, page/bbox locators and
confidence through `PdfExtractor` without sending the source remotely.

The FastAPI Golden is an internal pilot artifact and is intentionally outside
the public `1.1.0` scope because its private documentation corpus is not
licensed in this checkout. Do not run the external RAGFlow profile for this
release unless an authorized corpus is supplied; the reviewed MIT fixture is
the public Golden gate.

## Candidate identity and artifacts

`prepare_candidate.py` builds a byte-reproducible wheel with one selected interpreter,
using `SOURCE_DATE_EPOCH=315532800` (the first timestamp representable by ZIP)
for archive metadata, audits
the exact tracked plus non-ignored candidate file set, records `HEAD` and a
SHA-256 candidate digest, and emits:

- `candidate-manifest.json` with version `1.1.0`, gate identity and publication
  status;
- `wheel/*.whl`, top-level `SHA256SUMS` and the repository metadata;
- `evidence/sbom.json`, lock evidence, vendor/model provenance and independent
  supply-chain checksums;
- Code of Conduct, governance/maintainers, support policy and issue/PR
  templates under `community/`, plus the recognized root `CODE_OF_CONDUCT.md`
  and `.github/CODEOWNERS`.

The CI package job uploads the complete, already-audited candidate directory as
`candidate-1.1.0-${GITHUB_SHA}` for 30 days. Hidden files are included because
the bundle's `.github` and `.gitignore` entries are part of its measured source
set; `if-no-files-found: error` prevents a green job with missing evidence.
The uploaded artifact is evidence for review, not a GitHub Release asset.

The ordinary push and pull-request CI stops at candidate verification. The
final `--release` identity/residual-risk gate is intentionally manual: dispatch
`.github/workflows/ci.yml` on `main` with the boolean input
`release_verification=true` after the maintainer has reviewed the remote CI,
GitHub settings and Chroma decision. This keeps engineering CI green without
turning an unresolved human release decision into an automated approval.

`verify_candidate.py` is an independent local verifier. It checks the wheel
metadata, bundle checksums, required community/metadata files, candidate audit,
source identity, publication=false and the supply-chain evidence. Model
snapshots are never distributed in the candidate. Supplying `--model-cache`
records a deterministic external snapshot manifest and digest. Dependency and
model requirements are explicit and independent: use
`--profile rag --require-model` for a RAG candidate. The core profile may omit
only the optional the retired backend lock root; version drift and every other
missing root remain fatal.

`candidate-manifest.json` e `candidate-identity.json` distinguem
`working-tree-candidate`, `local-commit-candidate`, `commit-candidate` e
`unversioned-clean-clone`. Para re-medição da fonte use
`python scripts/verify_candidate.py --root <bundle> --source-root <checkout>`.
O modo `--release` exige working tree limpo, uma ref remota alcançável verificada
por `git ls-remote` e evidência GitHub Actions com o mesmo commit e digest; sem
isso o verificador falha fechado. O workflow registra essa identidade nos logs,
mas não faz commit, push, tag ou release.

## Security and operational review

The four documented Chroma advisories remain an explicit residual risk limited
to the local `PersistentClient` threat model. HTTP Chroma, remote model
repositories and `trust_remote_code` invalidate the candidate policy. Review
licenses, vendor provenance, model provenance and the residual advisories
before publication.

The local GitHub settings checklist is
`community/GITHUB-SETTINGS-CHECKLIST.md`; anonymous inspection cannot prove
branch protection, secret scanning, push protection, reviewers or release
permissions. The Chroma decision gate is documented in
`docs/CHROMA-RESIDUAL-DECISION.md` and must be completed by a human maintainer.

Branch protections, required reviewers, CODEOWNERS and least-privilege release
permissions are represented as `human-review-required` evidence. A maintainer
must verify those GitHub settings before authorizing publication; local scripts
do not attempt to change them.

The public `docops.inspect()` seam waits for an active writer lease to settle
before returning a generation. This is the supported reader guarantee. Raw
filesystem consumers may observe a platform-specific directory replacement
window, so the product does not claim distributed or universally atomic
promotion.

The published `1.0.0` release and its historical workflow evidence remain
documented in `docs/GITHUB-PUBLICATION-AUDIT-2026-09-01.md` and the older
records in `tasks/todo.md`. The current critical re-audit is
`docs/GITHUB-PUBLICATION-AUDIT-2026-09-02.md`; this candidate does not reuse
the 1.0.0 release identity.
