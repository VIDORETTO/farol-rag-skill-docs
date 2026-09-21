# GitHub settings checklist

This checklist is intentionally manual. It records the authenticated review
performed for the `1.1.0` release; no credential or token is stored here.

## Authenticated review — 2026-09-04

- **Administrator:** `VIDORETTO` (authenticated GitHub CLI identity; repository
  permission `admin`).
- [x] Branch protection is enabled on `main`: [protection endpoint](https://api.github.com/repos/VIDORETTO/farol-rag-skill-docs/branches/main/protection).
  It requires the 13 CI job checks, blocks force-push/deletion, requires linear
  history and conversation resolution. `enforce_admins=false` is intentional:
  this personal repository has one maintainer, so the owner retains a documented
  emergency/admin bypass instead of making normal maintenance impossible.
- [x] Required status checks and reviewers match the support matrix: all
  Python 3.11–3.13 OS jobs, clean-clone jobs and the wheel job are required;
  one code-owner approval is required and stale reviews are dismissed.
- [x] `CODEOWNERS` is active and valid: [CODEOWNERS](https://github.com/VIDORETTO/farol-rag-skill-docs/blob/main/.github/CODEOWNERS)
  has no API errors and names `@VIDORETTO`.
- [x] Dependabot security updates are enabled; the repository has the checked-in
  Dependabot configuration.
- [x] Secret scanning and push protection are enabled; no active secret alerts
  were returned during the review.
- [x] Release permissions use least privilege: workflows have `contents: read`,
  Actions are SHA-pinned, third-party actions are not allowed, and only the
  authenticated owner performs the manual GitHub Release.
- [x] The candidate manifest, checksums, SBOM and source SHA agree; the exact
  evidence is retained under `artifacts/candidate-1.1.0/` locally.
- [x] The Chroma residual-risk decision is recorded in
  `docs/CHROMA-RESIDUAL-DECISION.md`.

The review was performed through authenticated API endpoints on the date above.
The public repository remains the source of truth; anonymous checks must not be
used as a substitute for this record.
