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

## Authenticated review — 2026-09-24

- [x] `main` branch protection still requires all 13 CI checks and one
  code-owner approval; stale reviews are dismissed. The owner emergency bypass
  remains explicitly documented above.
- [x] Dependabot security updates, secret scanning and push protection are
  enabled. The authenticated API returned no open Dependabot or secret alerts.
- [x] At this review timestamp, private vulnerability reporting was disabled;
  see the authenticated follow-up below for the later enablement and check.
- [x] No `v2.0.0-rc.1` tag or GitHub Release exists as of this review. The
  candidate remains unpublished; no release action was performed.

This check is evidence for the settings observed on 2026-09-24. It does not
change repository settings or authorize publishing, tagging or GA promotion.

## Authenticated follow-up — 2026-09-25

- [x] Enabled private vulnerability reporting for
  `VIDORETTO/farol-rag-skill-docs` through the repository-scoped REST endpoint.
  The authenticated GET returned `false` before the change; after the PUT, a
  second GET returned `true`. The signed-in owner was `VIDORETTO`; no token or
  credential was written to the repository.
- [x] `SECURITY.md` now directs reporters to GitHub's private report form.
- [x] Rechecked the release state: the RC remains unpublished; no tag, release
  or GA promotion was performed.
- [x] Rechecked branch protection through the authenticated API. `main` still
  requires 13 status checks, one code-owner approval, and dismissal of stale
  reviews; admin enforcement is disabled as documented in the historical
  checklist. The RC branch returned `Branch not protected` (HTTP 404), and the
  repository/parent ruleset query returned no rulesets. No setting was changed.
  Before publishing from the RC branch, use a protected PR into `main` or have
  the owner decide whether to add equivalent protection to the RC branch.

GitHub documents this feature for public repository owners and administrators;
the [repository configuration guide](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository)
and [enable endpoint](https://docs.github.com/en/rest/repos/repos#enable-private-vulnerability-reporting-for-a-repository)
describe the setting and API operation.

## Read-only release snapshot — 2026-09-26

- [x] Private vulnerability reporting remains enabled (`GET` returned `true`).
- [x] `main` remains protected by 13 required checks, one code-owner approval,
  and stale-review dismissal. The RC branch still has no branch protection
  (HTTP 404) and no matching repository or parent ruleset.
- [x] No `v2.0.0-rc.1` tag or GitHub Release exists. PR
  [#16](https://github.com/VIDORETTO/farol-rag-skill-docs/pull/16) remains open
  to `main`, but its remote head is still `be40e16f09153cfc12e3ea389302793f920c40b2`;
  its decision is `REVIEW_REQUIRED`. The green checks completed on 2026-09-23
  apply to that old head, not local candidate `23a39c31bd09f8098af6d71bd57671d7495d10a9`.
- No setting was changed and no push, tag, release or GA promotion was
  performed. Updating the PR head and running CI on the current source requires
  explicit push authorization.
